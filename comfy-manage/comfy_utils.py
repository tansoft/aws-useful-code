import json
import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import urllib.request
import urllib.parse
import urllib.error
import time
import boto3
from botocore.exceptions import ClientError

class ComfyWorkflow:
    def __init__(self, server_address='127.0.0.1:8080'):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())
        self.ws = websocket.WebSocket()
        self.ws.connect("ws://{}/ws?clientId={}".format(self.server_address, self.client_id))

    # 定义一个函数向服务器队列发送提示信息
    def queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request("http://{}/prompt".format(self.server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())

    # 定义一个函数来获取图片
    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(self.server_address, url_values)) as response:
            return response.read()

    # 定义一个函数来获取历史记录
    def get_history(self, prompt_id):
        with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, prompt_id)) as response:
            return json.loads(response.read())

    def reset_connection(self):
        self.ws.close()
        self.ws = websocket.WebSocket()
        self.ws.connect("ws://{}/ws?clientId={}".format(self.server_address, self.client_id))

    # 定义一个函数来获取图片，这涉及到监听WebSocket消息
    def run_workflow(self, prompt):
        prompt_id = self.queue_prompt(prompt)['prompt_id']
        print('prompt')
        print(prompt)
        print('prompt_id:{}'.format(prompt_id))
        output_images = {}
        while True:
            out = self.ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        print('执行完成')
                        break  # 执行完成
            else:
                continue  # 预览为二进制数据

        history = self.get_history(prompt_id)[prompt_id]
        print(history)
        for o in history['outputs']:
            for node_id in history['outputs']:
                node_output = history['outputs'][node_id]
                # 图片分支
                if 'images' in node_output:
                    images_output = []
                    for image in node_output['images']:
                        image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                        images_output.append(image_data)
                    output_images[node_id] = images_output
                # 视频分支
                if 'videos' in node_output:
                    videos_output = []
                    for video in node_output['videos']:
                        video_data = self.get_image(video['filename'], video['subfolder'], video['type'])
                        videos_output.append(video_data)
                    output_images[node_id] = videos_output

        print('获取图片完成')
        # print(output_images)
        return output_images

    # 生成图像并显示
    def generate_clip(self, prompt_data):
        images = self.run_workflow(prompt_data)
        # 这些是从接口中拿到的图片数据，ComfyUI默认已经有保存的output目录上
        for node_id in images:
            for image_data in images[node_id]:
                print(f"image job {node_id} finish.")
                #from datetime import datetime
                #output_file = datetime.now().strftime("%Y%m%d%H%M%S") + '.png'
                #with open(output_file, "wb") as binary_file:
                #    binary_file.write(image_data)
                #print("{} DONE!!!".format(output_file))

class AutoScalingManager:
    def __init__(self, region, queue_name, asg_name, min_instances=0, max_instances=20, backlogsize_per_instance=3):
        self.sqs = boto3.client('sqs', region_name=region)
        self.asg = boto3.client('autoscaling', region_name=region)
        self.queue_name = queue_name
        self.asg_name = asg_name
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.backlogsize_per_instance = backlogsize_per_instance
        self.queue_url = self._get_queue_url()
        self.token_expire = 0
        self.token = None
        self.lifecycle_expire = 0

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
            # need check spot status immediately
            self.lifecycle_expire = time.time() - 1
        except ClientError as e:
            print(f"Error adjusting capacity: {e}")

    def send_message(self, message):
        """发送消息到SQS队列"""
        try:
            response = self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message)
            )
            print(f"Message sent successfully: {response['MessageId']} {self.queue_url}")
            return True
        except ClientError as e:
            print(f"Error sending message: {e}")
            return False

    def get_imdsv2_token(self):
        if self.token_expire < time.time():
            try:
                req = urllib.request.Request(
                    url="http://169.254.169.254/latest/api/token",
                    method="PUT",
                    headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"}  # 令牌有效期6小时
                )
                self.token = urllib.request.urlopen(req).read().decode('utf-8')
                self.token_expire = time.time() + 7200
                print(f"IMDSv2 token refreshed: {self.token} {self.token_expire}")
            except urllib.error.URLError as e:
                print(f"Error requesting IMDSv2 token: {e}")
                return None
            except Exception as e:
                print(f"Unexpected error getting IMDSv2 token: {e}")
                return None
        return self.token

    def get_metadata(self, path):
        try:
            req = urllib.request.Request(
                url=f"http://169.254.169.254/latest/meta-data/{path}",
                headers={"X-aws-ec2-metadata-token": self.get_imdsv2_token()}
            )
            ret = urllib.request.urlopen(req).read().decode('utf-8')
            print(f"metadata: {path} -> {ret}")
            return ret
        except urllib.error.HTTPError as e:
            if e.code == 404:  # 元数据路径不存在
                return None
            return None
        except Exception as e:
            return None

    def complete_lifecycle_action(self):
        try:
            instance_id = self.get_metadata("instance-id")
            response = self.asg.complete_lifecycle_action(
                LifecycleHookName = self.asg_name,
                AutoScalingGroupName = self.asg_name,
                LifecycleActionResult = 'CONTINUE',
                InstanceId=instance_id
            )
            print(f"Lifecycle action completed: {instance_id} {response}")
            return response
        except Exception as e:
            print(f"Error completing lifecycle action: {e}")
            return None

    def is_self_terminated(self):
        if self.lifecycle_expire < time.time():
            self.lifecycle_expire = time.time() + 20
            target_state = self.get_metadata("autoscaling/target-lifecycle-state")        
            if target_state:
                print(f"Current target lifecycle state: {target_state}")
                if target_state == "Terminated" or target_state == "Terminating:Wait" or target_state == "Terminating:Proceed":                    
                    # 通知 Auto Scaling 继续终止实例
                    # self.complete_lifecycle_action()
                    return True
        return False

    def manage_scaling_policy_without_capacity(self):
        """管理初始容量"""
        queue_size = self.get_queue_attributes()
        instance_count = self.get_asg_instance_count()

        print(f"without capcity check current queue/instance: {queue_size}/{instance_count}")

        # 如果有消息但没有实例，启动一个实例
        if queue_size > 0 and instance_count == 0:
            print("Starting first instance...")
            self.adjust_capacity(1)
            return

    def manage_scaling_policy_tracking_backlog(self):
        """管理自动扩缩容"""
        queue_size = self.get_queue_attributes()
        instance_count = self.get_asg_instance_count()
        
        print(f"tracking backlog check current queue/instance: {queue_size}/{instance_count}")

        # 如果有实例在运行，根据消息数量调整实例数
        if instance_count > 0:
            messages_per_instance = queue_size / instance_count

            if messages_per_instance > self.backlogsize_per_instance:
                new_count = min(instance_count + 1, self.max_instances)
                if new_count > instance_count:
                    print(f"Scaling out to {instance_count} -> {new_count} instances...")
                    self.adjust_capacity(new_count)
            
            elif messages_per_instance < self.backlogsize_per_instance:
                min_count = self.min_instances
                if min_count == 0 and queue_size > 0:
                    min_count = 1
                new_count = max(instance_count - 1, min_count)
                if new_count < instance_count:
                    print(f"Scaling in to {instance_count} -> {new_count} instances...")
                    self.adjust_capacity(new_count)

# Execute the main function
if __name__ == "__main__":
    workflow = ComfyWorkflow(server_address="127.0.0.1:8080")
    workflowfile = 'simple_workflow.json'
    prompt_data = json.load(workflowfile)
    # 设置文本提示
    prompt_data["6"]["inputs"]["text"] = "beautiful scenery nature glass bottle landscape, , purple galaxy bottle,"
    workflow.generate_clip(prompt_data)
