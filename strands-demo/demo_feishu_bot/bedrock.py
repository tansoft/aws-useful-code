import json
import logging
import os
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
    model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="ap-northeast-1",
    temperature=0.1
)

# Initialize MCP client with streamable HTTP transport
aws_doc_transport = lambda: streamablehttp_client(url="https://knowledge-mcp.global.api.aws")

aws_doc_client = MCPClient(aws_doc_transport)

# Start the clients immediately when the app starts
aws_doc_client.start()

async def async_bedrock_sendMessage(app_id: str, message_id: str, user_id: str, message) -> None:
    try:
        # Check if clients are still active, if not restart them
        if not aws_doc_client._is_session_active():
            logging.warning("AWS DOC client not active, restarting...")
            aws_doc_client.start()
            
        # Get fresh tools list after potential restart
        current_tools = aws_doc_client.list_tools_sync() + [http_request, current_time]

        # Handle session management
        session_id = user_id
        if not session_id:
            # Create a new session if none provided
            session_id = str(uuid.uuid4())
            # yield f"data: {json.dumps({'type': 'session_created', 'session_id': session_id})}\n\n"
        
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
        image = None
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
                #yield f"data: {json.dumps({'type': 'error', 'error': f'Error processing image: {str(e)}'})}\n\n"
                #return
    
        # Process the entire stream
        alltext = ''
        
        print(messages)
        # If we have messages, stream the response
        if messages:
            async for event in agent.stream_async(messages):
                print(event)
                if "data" in event:
                    alltext += event["data"]
                    alltext = alltext.replace('<thinking>','***').replace('</thinking>',"***\n\n")
                    print('step build card')
                    card_content = build_card("处理结果", get_current_time(), alltext, False, True)
                    updateTextCard(app_id, message_id, card_content)
                    #yield f"data: {json.dumps({'type': 'response', 'content': alltext, 'session_id': session_id})}\n\n"
                    print('step build card updated')
        
        print('finish build card')
        card_content = build_card("处理结果", get_current_time(), alltext, True, True)
        updateTextCard(app_id, message_id, card_content)
        print('finish build card updated')
        #yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id})}\n\n"

    except Exception as e:
        errmsg = f"Error in stream_response: {str(e)}"
        logging.error(errmsg)
        card_content = build_card("处理结果", get_current_time(), errmsg, True, True)
        updateTextCard(app_id, message_id, card_content)
        #yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
