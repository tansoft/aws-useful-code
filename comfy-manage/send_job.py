#!/usr/bin/env python3
import os
import json
from dotenv import load_dotenv
from comfy_utils import ComfyWorkflow
from comfy_utils import AutoScalingManager

def call_sqs(prompt_data, region, queue_name, asg_name):
    manager = AutoScalingManager(region=region, queue_name=queue_name, asg_name=asg_name)
    if manager.send_message(prompt_data):
        print("Job submitted successfully")
    else:
        print("Failed to submit job")
    # 执行初始扩缩容检查
    manager.manage_scaling_policy_without_capacity()

if __name__ == "__main__":
    # 获取环境变量
    load_dotenv('./env')
    env = os.getenv('ENV', 'base')
    prefix = os.getenv('PREFIX', 'simple-comfy')
    queue_name = os.getenv('SQS_NAME', f"{prefix}-{env}-queue")
    asg_name = os.getenv('ASG_NAME', f"{prefix}-{env}-asg")
    region = os.getenv('REGION', 'us-east-1')

    with open('simple_workflow.json', 'r', encoding="utf-8") as f:
        prompt_data = json.load(f)
        # 设置输入参数等
        prompt_data["6"]["inputs"]["text"] = "beautiful scenery nature glass bottle landscape, , purple galaxy bottle,"
        if True:
            # 发送 sqs 方式
            call_sqs(prompt_data, region=region, queue_name=queue_name, asg_name=asg_name)
        else:
            # 直接调用comfyui的接口，获取生成文件并保存到本地
            workflow = ComfyWorkflow(server_address='1.2.3.4:8188')
            workflow.generate_clip(prompt_data)

    if False:
        # 这里演示提交shell执行脚本，让 parse_job.py 脚本在服务器环境执行命令，如想在base环境中下载模型文件：
        execute_data = {
            "exec_cmd": "wget 'https://huggingface.co/linsg/AWPainting_v1.5.safetensors/resolve/main/AWPainting_v1.5.safetensors?download=true' -O /home/ubuntu/comfy/ComfyUI/models/checkpoints/AWPainting_v1.5.safetensors",
        }
        call_sqs(execute_data, region=region, queue_name=queue_name, asg_name=asg_name)