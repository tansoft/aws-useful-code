#!/usr/bin/env python3
import os
import json
import boto3
import requests
import time
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

def main():
    # 获取环境变量
    load_dotenv('/home/ubuntu/comfy/env')
    env = os.getenv('ENV', 'base')
    prefix = os.getenv('PREFIX', 'simple-comfy')
    queue_name =os.getenv('SQS_NAME', f"{prefix}-{env}-queue")
    asg_name = os.getenv('ASG_NAME', f"{prefix}-{env}-asg")
    region = os.getenv('REGION', 'us-east-1')
    min_instances = int(os.getenv('MIN_INSTANCES', '0'))
    max_instances = int(os.getenv('MAX_INSTANCES', '20'))
    backlogsize_per_instance = int(os.getenv('BACKLOGSIZE_PER_INSTANCE', '3'))
    scale_cooldown = int(os.getenv('SCALE_COOLDOWN', '180'))

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
