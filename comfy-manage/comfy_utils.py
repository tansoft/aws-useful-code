import json
import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import urllib.request
import urllib.parse
import random

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
        for node_id in images:
            for image_data in images[node_id]:
                from datetime import datetime
                output_file = datetime.now().strftime("%Y%m%d%H%M%S") + '.png'
                with open(output_file, "wb") as binary_file:
                    binary_file.write(image_data)
                print("{} DONE!!!".format(output_file))

# Execute the main function
if __name__ == "__main__":
    workflow = ComfyWorkflow(server_address="127.0.0.1:8080")
    workflowfile = 'simple_workflow.json'
    prompt_data = json.load(workflowfile)
    # 设置文本提示
    prompt_data["6"]["inputs"]["text"] = "beautiful scenery nature glass bottle landscape, , purple galaxy bottle,"
    workflow.generate_clip(prompt_data)
