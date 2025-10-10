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
from strands.agent.conversation_manager import SummarizingConversationManager
from typing import Optional
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logging.getLogger("strands").setLevel(logging.WARNING)

# Initialize session directory
SESSION_DIR = os.environ.get("SESSION_DIR", os.path.join(os.path.dirname(__file__), "sessions"))
os.makedirs(SESSION_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    aws_doc_client.stop(None, None, None)

app = FastAPI(lifespan=lifespan)

VALID_TOKEN = os.environ.get("VALID_TOKEN", "secret_token")

def validate_token(request: Request):
    if request.query_params.get('token') != VALID_TOKEN:
        raise HTTPException(status_code=403)

class ImageData(BaseModel):
    data: str  # Base64 encoded image data
    format: str  # Image format (png or jpeg)

class PromptRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    image: Optional[ImageData] = None

# Initialize components
# model_id="apac.anthropic.claude-sonnet-4-20250514-v1:0"
bedrock_model = BedrockModel(model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0", region_name="ap-northeast-1")
aws_doc_client = MCPClient(lambda: streamablehttp_client(url="https://knowledge-mcp.global.api.aws"))
aws_doc_client.start()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root(request: Request):
    validate_token(request)
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/chat_stream")
async def stream_response(request: PromptRequest, raw_request: Request):
    validate_token(raw_request)

    async def generate():
        try:
            if not aws_doc_client._is_session_active():
                aws_doc_client.start()

            current_tools = aws_doc_client.list_tools_sync() + [http_request, current_time]

            session_id = request.session_id or str(uuid.uuid4())
            if not request.session_id:
                yield f"data: {json.dumps({'type': 'session_created', 'session_id': session_id})}\n\n"

            session_manager = FileSessionManager(session_id=session_id, storage_dir=SESSION_DIR)
            conversation_manager = SummarizingConversationManager(summary_ratio=0.3, preserve_recent_messages=6)

            agent = Agent(
                model=bedrock_model,
                callback_handler=None,
                conversation_manager=conversation_manager,
                system_prompt="""你是一个AWS解决方案架构师，专业、准确地回答客户的AWS相关问题。

处理原则：
1. 必须通过MCP工具或搜索互联网获取准确信息
2. 所有技术结论都必须有权威参考链接支撑
3. 严禁编造或猜测任何技术信息
4. 根据问题类型灵活选择回答格式

输出格式：
### 详细说明
{针对答案的技术细节，每个关键点都必须包含：}
- 参考链接：{权威AWS文档链接}
- 参考内容：{从官方文档中提取的关键信息摘要}

### 直接答案
{用于直接用来回答的内容，回答的点可能有多个，回答尽可能口语化并且每个回答带上相关的参考链接。参考回答格式：<answer>可以使用xxx的
  xxx实现xxx功能，适用于xxx场景。xxx的参考链接：https://reference.com/answer.html</answer>}

### 相关建议（如需要）
{额外的建议或注意事项，同样需要包含参考链接和参考内容}""",
                tools=current_tools,
                session_manager=session_manager,
                agent_id="default"
            )
            
            messages = []

            if request.message.strip():
                messages.append({"text": request.message})

            if request.image:
                try:
                    image_bytes = base64.b64decode(request.image.data)
                    image_format = request.image.format.lower()

                    if image_format not in ["png", "jpeg"]:
                        raise ValueError(f"Unsupported image format: {image_format}")

                    messages.append({
                        "image": {
                            "format": image_format,
                            "source": {"bytes": image_bytes}
                        }
                    })
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'error': f'Error processing image: {str(e)}'})}\n\n"
                    return
            
            if not messages:
                yield f"data: {json.dumps({'type': 'error', 'error': '没有提供消息内容或图片'})}\n\n"
                return

            last_event_type = None
            async for event in agent.stream_async(messages):
                if "data" in event:
                    content = event['data']
                    if last_event_type == 'tool':
                        content = '<br/>\n' + content
                    yield f"data: {json.dumps({'type': 'response', 'content': content, 'session_id': session_id})}\n\n"
                    last_event_type = 'data'
                elif "current_tool_use" in event:
                    tool_name = event["current_tool_use"].get('name', '未知工具')
                    yield f"data: {json.dumps({'type': 'status', 'content': f'🔧 {tool_name}', 'session_id': session_id})}\n\n"
                    last_event_type = 'tool'
                elif "init_event_loop" in event or "start_event_loop" in event or "message" in event:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'session_id': session_id})}\n\n"
                
            yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Keep-Alive': 'timeout=300'
        }
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9000")), timeout_keep_alive=120)
