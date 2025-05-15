#!/usr/bin/env python3
import os
import json
import boto3
import requests
import time
from botocore.exceptions import ClientError
from comfy_utils import ComfyWorkflow

def get_queue_url(sqs_client, queue_name):
    """获取SQS队列URL"""
    try:
        response = sqs_client.get_queue_url(QueueName=queue_name)
        return response['QueueUrl']
    except ClientError as e:
        print(f"Error getting queue URL: {e}")
        return None

def process_message(message_body):
    """处理消息内容，发送HTTP POST请求"""
    global workflow
    try:
        prompt_data = json.loads(message_body)
        workflow.generate_clip(prompt_data)
        return True
    except (json.JSONDecodeError, requests.RequestException, ValueError) as e:
        print(f"Error processing message: {e}")
        return False

def main():
    # 获取环境变量
    env = os.getenv('ENV', 'base')
    prefix = os.getenv('PREFIX', 'simple-comfy')
    queue_name = f"{prefix}-{env}-queue"
    region = os.getenv('AWS_REGION', 'us-east-1')
    # 初始化AWS客户端
    sqs = boto3.client('sqs', region_name=region)
    
    # 获取队列URL
    queue_url = get_queue_url(sqs, queue_name)
    if not queue_url:
        print(f"Failed to get queue URL {queue_name}")
        return
    
    print(f"Starting to process messages from queue: {queue_name}")
    
    workflow = ComfyWorkflow(server_address="127.0.0.1:8080")

    while True:
        try:
            # 接收消息
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20  # 启用长轮询
            )
            
            messages = response.get('Messages', [])
            
            for message in messages:
                receipt_handle = message['ReceiptHandle']
                message_body = message['Body']
                
                print(f"Processing message: {message_body}")
                
                if process_message(message_body):
                    # 处理成功，删除消息
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=receipt_handle
                    )
                    print("Message processed and deleted successfully")
                else:
                    print("Failed to process message, will retry later")
                    
        except ClientError as e:
            print(f"AWS Error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
