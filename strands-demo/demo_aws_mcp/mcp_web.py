import logging
import json
import uvicorn
import os
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from strands import Agent, tool
from strands.models import BedrockModel
from strands.session import FileSessionManager
from strands_tools import http_request
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from contextlib import asynccontextmanager
from typing import Dict, Optional

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
async def lifespan(app_: FastAPI):
    # Startup - clients are already initialized in the module scope
    logging.info("Application startup")
    yield
    # Shutdown - clean up resources
    logging.info("Shutting down MCP clients")
    aws_doc_client.stop(None, None, None)
    logging.info("MCP clients shut down successfully")

app = FastAPI(lifespan=lifespan)

class PromptRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

# Initialize Bedrock model
bedrock_model = BedrockModel(
    #model_id="us.amazon.nova-pro-v1:0",
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name="us-east-1",
    # "max_tokens": 300000
    params={"temperature": 0.1}
)

# Initialize MCP clients once and keep them open for the application lifetime
# This avoids the slow initialization on each request
aws_doc_transport = lambda: stdio_client(StdioServerParameters(command="uvx", args=["awslabs.aws-documentation-mcp-server@latest"]))

aws_doc_client = MCPClient(aws_doc_transport)

# Start the clients immediately when the app starts
aws_doc_client.start()

templates = Jinja2Templates(directory="templates")
# app.mount("/", StaticFiles(directory="templates"), name="static")

@app.get("/")
async def read_root(request: Request):
    # 注意：必须传递request参数
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/chat_stream")
async def stream_response(request: PromptRequest):
    async def generate():
        try:
            # Check if clients are still active, if not restart them
            if not aws_doc_client._is_session_active():
                logging.warning("AWS DOC client not active, restarting...")
                aws_doc_client.start()
                
            # Get fresh tools list after potential restart
            current_tools = aws_doc_client.list_tools_sync() + [http_request]

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
                system_prompt="""你是一个AWS助手
                你需要通过MCP的文档或者搜索互联网的方式帮助回答客户的问题，给出回答时对应的参考链接
                输出的内容使用markdown的格式。""",
                tools=current_tools,
                session_manager=session_manager,
                agent_id="default"  # 使用固定的 agent_id
            )
            
            # Process the entire stream
            alltext = ''
            async for event in agent.stream_async(request.message):
                if "data" in event:
                    alltext += event["data"]
                    alltext = alltext.replace('<thinking>','***').replace('</thinking>',"***\n\n")
                    yield f"data: {json.dumps({'type': 'response', 'content': alltext, 'session_id': session_id})}\n\n"
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
            'X-Accel-Buffering': 'no'  # Disable nginx buffering if using nginx
        }
    )



if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)