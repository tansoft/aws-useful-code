#!/usr/bin/env python3
import os
import json
import boto3
import requests
import time
import logging
import sys
import builtins
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from comfy_utils import ComfyWorkflow
from comfy_utils import AutoScalingManager

def get_queue_url(sqs_client, queue_name):
    """获取SQS队列URL"""
    try:
        response = sqs_client.get_queue_url(QueueName=queue_name)
        return response['QueueUrl']
    except ClientError as e:
        print(f"Error getting queue URL: {e}")
        return None

def setup_logging(log_dir='./logs', app_name='parse_job', 
                  redirect_print=True, console_output=True, 
                  print_to_console=False):
    """
    设置日志配置，可选择重定向print到日志
    
    Args:
        log_dir: 日志文件目录
        app_name: 应用名称，用于日志文件名
        redirect_print: 是否将print输出重定向到日志
        console_output: 是否通过logger输出到控制台
        print_to_console: 重定向print后是否仍然输出到控制台（可能导致双重输出）
    
    Returns:
        logger: 配置好的logger对象
    """
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 获取记录器
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    
    # 如果记录器已经有处理器，先清除
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 创建文件处理器 (每日轮转)
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, f'{app_name}.log'),
        when='midnight',
        interval=1,
        backupCount=30
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 创建错误文件处理器 (大小轮转)
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, f'{app_name}_error.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # 添加控制台处理器（可选）
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 重定向print到logger（可选）
    if redirect_print:
        original_print = builtins.print
        
        def custom_print(*args, sep=' ', end='\n', file=None, flush=False):
            if file is None or file == sys.stdout:
                message = sep.join(str(arg) for arg in args)
                logger.info(message)  # 直接使用INFO级别，不添加"PRINT:"前缀
                
                # 只有当明确要求且logger没有配置控制台输出时，才使用原始print
                if print_to_console and not console_output:
                    original_print(*args, sep=sep, end=end, flush=flush)
            else:
                original_print(*args, sep=sep, end=end, file=file, flush=flush)
        
        builtins.print = custom_print
    
    return logger


def main():
    setup_logging()
    # 获取环境变量
    load_dotenv('./env')
    env = os.getenv('ENV', 'base')
    prefix = os.getenv('PREFIX', 'simple-comfy')
    queue_name =os.getenv('SQS_NAME', f"{prefix}-{env}-queue")
    asg_name = os.getenv('ASG_NAME', f"{prefix}-{env}-asg")
    region = os.getenv('REGION', 'us-east-1')
    min_instances = int(os.getenv('MIN_INSTANCES', '0'))
    max_instances = int(os.getenv('MAX_INSTANCES', '20'))
    backlogsize_per_instance = int(os.getenv('BACKLOGSIZE_PER_INSTANCE', '3'))
    scale_cooldown = int(os.getenv('SCALE_COOLDOWN', '180'))

    print(f"ENV: {env} start")

    # 初始化AWS客户端
    sqs = boto3.client('sqs', region_name=region)
    manager = AutoScalingManager(region=region, queue_name=queue_name, asg_name=asg_name,
        min_instances=min_instances, max_instances=max_instances, backlogsize_per_instance=backlogsize_per_instance)
    
    # 获取队列URL
    queue_url = get_queue_url(sqs, queue_name)
    if not queue_url:
        print(f"Failed to get queue URL {queue_name}")
        return
    
    print(f"Starting to process messages from queue: {queue_name}")

    workflow = None

    while True:
        try:
            workflow = ComfyWorkflow(server_address="127.0.0.1:8188")
            break
        except ConnectionRefusedError as e:
            print("waiting comfyui server ready...")
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(5)

    last_check = time.time()

    while True:
        try:
            # 接收消息
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20  # 启用长轮询
            )
            
            if manager.is_self_terminated():
                # 这里可以添加自定义善后工作逻辑，例如复制日志到 output 目录上
                instance_id = manager.get_metadata("instance-id")
                os.system(f"cp /home/ubuntu/comfy/ComfyUI/user/comfyui_8188.log /home/ubuntu/comfy/ComfyUI/output/{instance_id}.log")

                # 通知 auto scaling 可以结束实例
                manager.complete_lifecycle_action()
                break

            if last_check < time.time():
                last_check = time.time() + scale_cooldown
                manager.manage_scaling_policy_tracking_backlog()

            messages = response.get('Messages', [])
            
            for message in messages:
                receipt_handle = message['ReceiptHandle']
                message_body = message['Body']
                
                print(f"Processing message: {message_body}")

                try:
                    prompt_data = json.loads(message_body)
                    if "exec_cmd" in prompt_data:
                        os.system(prompt_data["exec_cmd"])
                    else:
                        workflow.generate_clip(prompt_data)
                        # 这里可以添加自定义任务的业务回调处理

                    # 处理成功，删除消息
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=receipt_handle
                    )
                    print("Message processed and deleted successfully")
                except (json.JSONDecodeError, requests.RequestException, ValueError) as e:
                    print(f"Failed to process message, will retry later: {e}")
                    
        except ClientError as e:
            print(f"AWS Error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
