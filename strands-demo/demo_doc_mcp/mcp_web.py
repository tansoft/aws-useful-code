import logging
import json
import uvicorn
import os
import uuid
import base64
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel
from strands.session import FileSessionManager
from strands_tools import http_request, current_time
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from contextlib import asynccontextmanager
from typing import Optional

# Set up logging
logging.getLogger("strands").setLevel(logging.INFO)  # Change to INFO to see more details
logging.basicConfig(
    level=logging.INFO,  # Set to INFO level
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# Session storage directory
SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

# Setup lifespan context manager for proper startup/shutdown of resources
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - clients are already initialized in the module scope
    logging.info("Application startup")
    yield
    # Shutdown - clean up resources
    logging.info("Shutting down MCP clients")
    aws_doc_client.stop(None, None, None)
    logging.info("MCP clients shut down successfully")

app = FastAPI(lifespan=lifespan)

# Token for authentication
VALID_TOKEN = "secret_token"

# Token validation dependency
def validate_token(request: Request):
    token = request.query_params.get('token')
    if not token or token != VALID_TOKEN:
        raise HTTPException(status_code=403)
    return True

class ImageData(BaseModel):
    data: str  # Base64 encoded image data
    format: str  # Image format (png or jpeg)

class PromptRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    image: Optional[ImageData] = None

# Initialize Bedrock model
bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name="us-west-2",
    params={"temperature": 0.1}
)

# Initialize MCP client with streamable HTTP transport
aws_doc_transport = lambda: streamablehttp_client(url="https://knowledge-mcp.global.api.aws")

aws_doc_client = MCPClient(aws_doc_transport)

# Start the clients immediately when the app starts
aws_doc_client.start()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root(request: Request):
    # Validate token for root endpoint
    validate_token(request)
    # 注意：必须传递request参数
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/chat_stream")
async def stream_response(request: PromptRequest, raw_request: Request):
    # Validate token for chat stream endpoint
    validate_token(raw_request)
    async def generate():
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
            if request.message.strip():
                messages.append({"text": request.message})
            
            # Add image if provided
            if request.image:
                try:
                    # Decode base64 image data
                    image_bytes = base64.b64decode(request.image.data)
                    image_format = request.image.format.lower()
                    
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

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering if using nginx
            'Keep-Alive': 'timeout=300'  # 增加Keep-Alive超时时间为300秒
        }
    )



if __name__ == "__main__":
    # 增加超时时间设置
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8080,
        timeout_keep_alive=120,  # 保持连接超时时间（秒）
    )
