#!/usr/bin/env python3
import os
import json
import boto3
import time
from botocore.exceptions import ClientError
from comfy_utils import ComfyWorkflow

class AutoScalingManager:
    def __init__(self, region='us-east-1', env='base'):
        self.sqs = boto3.client('sqs', region_name=region)
        self.asg = boto3.client('autoscaling', region_name=region)
        self.env = env
        self.queue_name = f"simple-comfy-{self.env}-queue"
        self.asg_name = f"simple-comfy-{self.env}-asg"
        self.queue_url = self._get_queue_url()

    def _get_queue_url(self):
        """获取SQS队列URL"""
        try:
            response = self.sqs.get_queue_url(QueueName=self.queue_name)
            return response['QueueUrl']
        except ClientError as e:
            print(f"Error getting queue URL: {e}")
            return None

    def get_queue_attributes(self):
        """获取队列中的消息数量"""
        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            return int(response['Attributes']['ApproximateNumberOfMessages'])
        except ClientError as e:
            print(f"Error getting queue attributes: {e}")
            return 0

    def get_asg_instance_count(self):
        """获取Auto Scaling Group中的实例数量"""
        try:
            response = self.asg.describe_auto_scaling_groups(
                AutoScalingGroupNames=[self.asg_name]
            )
            if response['AutoScalingGroups']:
                return len(response['AutoScalingGroups'][0]['Instances'])
            return 0
        except ClientError as e:
            print(f"Error getting ASG instance count: {e}")
            return 0

    def adjust_capacity(self, desired_capacity):
        """调整Auto Scaling Group容量"""
        try:
            self.asg.set_desired_capacity(
                AutoScalingGroupName=self.asg_name,
                DesiredCapacity=desired_capacity
            )
            print(f"Adjusted ASG capacity to {desired_capacity}")
        except ClientError as e:
            print(f"Error adjusting capacity: {e}")

    def send_message(self, message):
        """发送消息到SQS队列"""
        try:
            response = self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message)
            )
            print(f"Message sent successfully: {response['MessageId']}")
            return True
        except ClientError as e:
            print(f"Error sending message: {e}")
            return False

    def manage_scaling(self):
        """管理自动扩缩容"""
        queue_size = self.get_queue_attributes()
        instance_count = self.get_asg_instance_count()
        
        print(f"Current queue size: {queue_size}")
        print(f"Current instance count: {instance_count}")

        # 如果有消息但没有实例，启动一个实例
        if queue_size > 0 and instance_count == 0:
            print("Starting first instance...")
            self.adjust_capacity(1)
            return

        # 如果有实例在运行，根据消息数量调整实例数
        if instance_count > 0:
            messages_per_instance = queue_size / instance_count if instance_count > 0 else 0
            
            if messages_per_instance > 3:
                # 需要扩容，但不超过最大值5
                new_count = min(instance_count + 1, 5)
                if new_count > instance_count:
                    print(f"Scaling out to {new_count} instances...")
                    self.adjust_capacity(new_count)
            
            elif messages_per_instance < 3:
                # 需要缩容，但保持至少
                new_count = max(instance_count - 1, 0)
                if new_count < instance_count:
                    print(f"Scaling in to {new_count} instances...")
                    self.adjust_capacity(new_count)

# 直接调用comfyui的接口，获取生成文件并保存到本地
def call_comfyui(prompt_data):
    workflow.generate_clip(prompt_data)

def call_sqs(prompt_data, env='base'):
    manager = AutoScalingManager(env=env)
    if manager.send_message(prompt_data):
        print("Job submitted successfully")
    else:
        print("Failed to submit job")
    # 执行一次扩缩容检查
    manager.manage_scaling()

if __name__ == "__main__":
    with open('simple_workflow.json', 'r', encoding="utf-8") as f:
        prompt_data = json.load(f)
        # 设置输入参数等
        prompt_data["6"]["inputs"]["text"] = "beautiful scenery nature glass bottle landscape, , purple galaxy bottle,"
        if True:
            # 发送 sqs 方式
            call_sqs(prompt_data, env='pro')
        else:
            # 直接请求 ComfyUI 方式
            workflow = ComfyWorkflow(server_address='1.2.3.4:8080')
            call_comfyui(prompt_data)
