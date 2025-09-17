import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTrigger, P2CardActionTriggerResponse
from lark_oapi.event.callback.model.p2_url_preview_get import P2URLPreviewGet, P2URLPreviewGetResponse

# 监听「卡片回传交互 card.action.trigger」
def do_card_action_trigger(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    print(lark.JSON.marshal(data))
    resp = {
        "toast": {
            "type": "info",
            "content": "卡片回传成功 from python sdk"
        }
    }
    return P2CardActionTriggerResponse(resp)

# 监听「拉取链接预览数据 url.preview.get」
def do_url_preview_get(data: P2URLPreviewGet) -> P2URLPreviewGetResponse:
    print(lark.JSON.marshal(data))
    resp = {
        "inline": {
            "title": "链接预览测试",
        }
    }
    return P2URLPreviewGetResponse(resp)

# 注册接收消息事件，处理接收到的消息。
# Register event handler to handle received messages.
# https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/events/receive
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    res_content = ""
    if data.event.message.message_type == "text":
        res_content = json.loads(data.event.message.content)["text"]
    else:
        res_content = "解析消息失败，请发送文本消息\nparse message failed, please send text message"

    content = json.dumps(
        {
            "text": f'收到你发送的消息：{res_content}\nReceived message:{res_content}'
        }
    )
    content = json.dumps(
        {
            "text": ask_ai(res_content)
        }
    )

    if data.event.message.chat_type == "p2p":
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.event.message.chat_id)
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )
        # 使用发送OpenAPI发送消息
        # Use send OpenAPI to send messages
        # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/create
        response = client.im.v1.message.create(request)

        if not response.success():
            raise Exception(
                f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
    else:
        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(data.event.message.message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type("text")
                .build()
            )
            .build()
        )
        # 使用回复OpenAPI回复消息
        # Use send OpenAPI to send messages
        # https://open.larkoffice.com/document/server-docs/im-v1/message/reply
        response: ReplyMessageResponse = client.im.v1.message.reply(request)
        if not response.success():
            raise Exception(
                f"client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )

# 注册事件回调
# Register event handler.
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .register_p2_card_action_trigger(do_card_action_trigger)
    .register_p2_url_preview_get(do_url_preview_get)
    .build()
)

# Load environment variables from .env file
from dotenv import load_dotenv
import os
load_dotenv()
lark.APP_ID = os.getenv("FEISHU_APP_ID")
lark.APP_SECRET = os.getenv("FEISHU_APP_SECRET")

# 创建 LarkClient 对象，用于请求OpenAPI, 并创建 LarkWSClient 对象，用于使用长连接接收事件。
# Create LarkClient object for requesting OpenAPI, and create LarkWSClient object for receiving events using long connection.
# client = lark.Client.builder().app_id(lark.APP_ID).app_secret(lark.APP_SECRET).build()
wsClient = lark.ws.Client(
    lark.APP_ID,
    lark.APP_SECRET,
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
)

import json
import logging
from strands import Agent
from strands.models import BedrockModel
from strands.session import FileSessionManager
from strands_tools import http_request, current_time
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from contextlib import asynccontextmanager

logging.getLogger("strands").setLevel(logging.INFO)  # Change to INFO to see more details
logging.basicConfig(
    level=logging.INFO,  # Set to INFO level
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# Session storage directory
SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

# Initialize Bedrock model
bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name="us-west-2",
    temperature=0.1
)

# Initialize MCP client with streamable HTTP transport
aws_doc_transport = lambda: streamablehttp_client(url="https://knowledge-mcp.global.api.aws")

aws_doc_client = MCPClient(aws_doc_transport)

# Start the clients immediately when the app starts
aws_doc_client.start()

async def ask_ai(message, image=None):
    try:
        # Check if clients are still active, if not restart them
        if not aws_doc_client._is_session_active():
            logging.warning("AWS DOC client not active, restarting...")
            aws_doc_client.start()
            
        # Get fresh tools list after potential restart
        current_tools = aws_doc_client.list_tools_sync() + [http_request, current_time]

        # Handle session management
        session_id = request.session_id
        if not session_id:
            # Create a new session if none provided
            session_id = str(uuid.uuid4())
            yield f"data: {json.dumps({'type': 'session_created', 'session_id': session_id})}\n\n"
        
        # 为每个请求创建一个新的 SessionManager 实例
        # FileSessionManager 会自动从磁盘加载已有的会话数据
        session_manager = FileSessionManager(
            session_id=session_id,
            storage_dir=SESSION_DIR
        )
        
        # 为每个请求创建一个新的 Agent 实例
        # 所有会话数据仍会持久化到磁盘，下次请求会自动加载
        agent = Agent(
            model=bedrock_model,
            system_prompt="""你是一个AWS解决方案架构师
            处理问题的逻辑按以下步骤：
            1. 需要通过MCP的能力或者搜索互联网的方式以准确回答客户的问题，并给出相应的参考链接以证明其真实性
            2. 在遇到无法处理的问题时，也可以提出相关建议或者解决方案
            3. 在调用工具时，告知一下将调用的工具及方法
            4. 输出的内容使用markdown的格式
            输出格式如下：
            ### 总结
            {简要的总结内容}
            ### 参考链接
            {链接}-{链接内容简要说明}
            ### 更多建议(如有)
            {建议的内容}
            ### 补充内容
            {有可能需要额外了解的内容/或者会被进一步提问的问题}""",
            tools=current_tools,
            session_manager=session_manager,
            agent_id="default"  # 使用固定的 agent_id
        )
        
        # Prepare the messages list for agent
        messages = []
        
        # Add text message if provided
        if message.strip():
            messages.append({"text": message})
        
        # Add image if provided
        if image:
            try:
                # Decode base64 image data
                image_bytes = base64.b64decode(image.data)
                image_format = image.format.lower()
                
                # Validate image format
                if image_format not in ["png", "jpeg"]:
                    raise ValueError(f"Unsupported image format: {image_format}")
                
                # Add image to messages
                messages.append({
                    "image": {
                        "format": image_format,
                        "source": {
                            "bytes": image_bytes
                        }
                    }
                })
            except Exception as e:
                logging.error(f"Error processing image: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'error': f'Error processing image: {str(e)}'})}\n\n"
                return
        
        # Process the entire stream
        alltext = ''
        
        # If we have messages, stream the response
        if messages:
            async for event in agent.stream_async(messages):
                if "data" in event:
                    alltext += event["data"]
                    alltext = alltext.replace('<thinking>','***').replace('</thinking>',"***\n\n")
                    yield f"data: {json.dumps({'type': 'response', 'content': alltext, 'session_id': session_id})}\n\n"
        else:
            # If no message content, return an error
            yield f"data: {json.dumps({'type': 'error', 'error': '没有提供消息内容或图片'})}\n\n"
            return
            
        yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id})}\n\n"

    except Exception as e:
        logging.error(f"Error in stream_response: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

def main():
    #  启动长连接，并注册事件处理器。
    #  Start long connection and register event handler.
    wsClient.start()


if __name__ == "__main__":
    main()