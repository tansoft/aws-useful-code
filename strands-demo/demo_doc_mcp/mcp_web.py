import json
import logging
import os
import uuid
import base64
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse,Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from strands import Agent
from strands.models import BedrockModel
from strands.session import FileSessionManager, S3SessionManager
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.tools.mcp import MCPClient
from strands_tools import http_request, current_time
from mcp.client.streamable_http import streamablehttp_client

from role_config import role_manager, RoleConfig

# Custom StaticFiles class with cache headers
class CachedStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        self.cache_max_age = kwargs.pop('cache_max_age', 604800)  # Default 7 days
        super().__init__(*args, **kwargs)
    
    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = f"public, max-age={self.cache_max_age}"
        return response

# Initialize session directory
SESSION_DIR = os.environ.get("SESSION_DIR", os.path.join(os.path.dirname(__file__), "sessions"))
VALID_TOKEN = os.environ.get("VALID_TOKEN", "secret_token")
# "apac.anthropic.claude-sonnet-4-20250514-v1:0"
BEDROCK_MODEL_ID = os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0")
REGION_NAME = os.environ.get("REGION_NAME", "ap-northeast-1")
PORT=int(os.environ.get("PORT", "9000"))

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logging.getLogger("strands").setLevel(logging.WARNING)

# Initialize session directory
if not SESSION_DIR.startswith("s3://"):
    os.makedirs(SESSION_DIR, exist_ok=True)

# Global MCP client cache
mcp_clients: Dict[str, MCPClient] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    yield
    # 停止所有MCP客户端
    for client in mcp_clients.values():
        try:
            client.stop(None, None, None)
        except Exception as e:
            logging.error(f"Error stopping MCP client: {e}")


app = FastAPI(lifespan=lifespan)

def validate_token(request: Request) -> None:
    """Validate authentication token from request."""
    if request.query_params.get('token') != VALID_TOKEN:
        raise HTTPException(status_code=403)

class ImageData(BaseModel):
    """Image data model for multimodal requests."""
    data: str  # Base64 encoded image data
    format: str  # Image format (png or jpeg)


class PromptRequest(BaseModel):
    """Chat prompt request model."""
    message: str
    session_id: Optional[str] = None
    image: Optional[ImageData] = None
    role_id: Optional[str] = "aws_architect"  # 默认角色
    custom_prompt: Optional[str] = None  # 自定义提示词
    enabled_mcps: Optional[list[str]] = None  # 启用的MCP列表，如果为None则使用角色默认配置

# Initialize components
bedrock_model = BedrockModel(model_id=BEDROCK_MODEL_ID, region_name=REGION_NAME)

def get_mcp_client(mcp_id: str) -> Optional[MCPClient]:
    """获取或创建MCP客户端.

    Args:
        mcp_id: MCP配置ID

    Returns:
        MCP客户端实例，如果创建失败返回None
    """
    if mcp_id in mcp_clients:
        return mcp_clients[mcp_id]

    mcp_config = role_manager.get_mcp_config(mcp_id)
    if not mcp_config:
        return None

    try:
        client = MCPClient(lambda: streamablehttp_client(url=mcp_config.url))
        client.start()
        mcp_clients[mcp_id] = client
        return client
    except Exception as e:
        logging.error(f"Failed to create MCP client for {mcp_id}: {e}")
        return None

# Initialize template engine and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", CachedStaticFiles(directory="static", cache_max_age=604800), name="static")

# 初始化默认的AWS文档客户端
aws_doc_client = get_mcp_client("aws_docs")

@app.get("/")
async def read_root(request: Request):
    """Serve the main chat interface."""
    validate_token(request)
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/debug/routes")
async def debug_routes(request: Request):
    """调试路由信息."""
    validate_token(request)

    routes_info = []
    for route in app.router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes_info.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else [],
                "name": getattr(route, 'name', 'unknown')
            })

    return {"routes": routes_info}

@app.post("/api/roles")
async def get_roles(request: Request):
    """获取所有可用角色配置."""
    validate_token(request)

    roles_data = []
    for role_id, role in role_manager.get_all_roles().items():
        mcp_configs = [
            role_manager.get_mcp_config(mcp_id).__dict__
            for mcp_id in role.mcp_configs
            if role_manager.get_mcp_config(mcp_id)
        ]

        roles_data.append({
            "id": role.id,
            "name": role.name,
            "icon": role.icon,
            "description": role.description,
            "is_editable": role.is_editable,
            "mcp_configs": mcp_configs
        })

    return {"roles": roles_data}

@app.post("/api/mcps")
async def get_mcps(request: Request):
    """获取所有可用的MCP配置."""
    validate_token(request)

    mcp_data = [
        {
            "id": mcp_config.id,
            "name": mcp_config.name,
            "url": mcp_config.url,
            "description": mcp_config.description
        }
        for mcp_id, mcp_config in role_manager.mcp_configs.items()
    ]

    return {"mcps": mcp_data}

@app.post("/api/roles/{role_id}")
async def get_role(role_id: str, request: Request):
    """获取指定角色的配置."""
    validate_token(request)

    role = role_manager.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    mcp_configs = [
        role_manager.get_mcp_config(mcp_id).__dict__
        for mcp_id in role.mcp_configs
        if role_manager.get_mcp_config(mcp_id)
    ]

    return {
        "id": role.id,
        "name": role.name,
        "icon": role.icon,
        "system_prompt": role.system_prompt,
        "description": role.description,
        "is_editable": role.is_editable,
        "mcp_configs": mcp_configs
    }

# 注释掉全局角色提示词更新功能，现在只支持会话级别的自定义提示词
# class UpdatePromptRequest(BaseModel):
#     system_prompt: str

# @app.put("/api/roles/{role_id}/prompt")
# async def update_role_prompt(role_id: str, request: UpdatePromptRequest, raw_request: Request):
#     """更新角色的系统提示词"""
#     validate_token(raw_request)

#     success = role_manager.update_role_prompt(role_id, request.system_prompt)
#     if not success:
#         raise HTTPException(status_code=400, detail="Unable to update role prompt")

#     return {"message": "Role prompt updated successfully"}


@app.post("/api/chat_stream")
async def stream_response(request: PromptRequest, raw_request: Request):
    """Stream chat responses using the configured AI agent."""
    validate_token(raw_request)

    async def generate():
        """Generate streaming response from AI agent."""
        try:
            # Get role configuration
            role_id = request.role_id or "aws_architect"
            role = role_manager.get_role(role_id)
            if not role:
                error_msg = {'type': 'error', 'error': f'未找到角色配置: {role_id}'}
                yield f"data: {json.dumps(error_msg)}\n\n"
                return

            # Setup MCP tools
            enabled_mcps = _get_enabled_mcps(request, role)
            current_tools = _setup_mcp_tools(enabled_mcps)

            logging.info(f"Using MCPs: {enabled_mcps} for role: {role_id}")
            logging.info(f"Configured tools count: {len(current_tools)}")

            # Setup agent and session
            system_prompt = request.custom_prompt or role.system_prompt
            session_id = request.session_id or str(uuid.uuid4())

            # 处理空工具列表的情况，避免Bedrock工具配置错误
            if len(current_tools) == 0:
                logging.info("No tools configured, using empty tools list")
                # 可以在这里添加一个dummy工具或者使用None，取决于Strands的实现
                pass

            # Notify frontend of new session
            if not request.session_id:
                session_data = {
                    'type': 'session_created',
                    'session_id': session_id,
                    'role_id': role_id
                }
                yield f"data: {json.dumps(session_data)}\n\n"

            # Create agent
            agent = _create_agent(system_prompt, current_tools, session_id, role_id)

            # Process messages
            messages = _process_messages(request)
            if not messages:
                error_msg = {'type': 'error', 'error': '没有提供消息内容或图片'}
                yield f"data: {json.dumps(error_msg)}\n\n"
                return

            # Stream agent response
            last_event_type = None
            async for event in agent.stream_async(messages):
                response_data = _process_stream_event(event, session_id, last_event_type)
                if response_data:
                    yield response_data[0]
                    last_event_type = response_data[1]

            complete_msg = {'type': 'complete', 'session_id': session_id}
            yield f"data: {json.dumps(complete_msg)}\n\n"

        except Exception as e:
            error_msg = {'type': 'error', 'error': str(e)}
            yield f"data: {json.dumps(error_msg)}\n\n"

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


# Helper functions for chat stream processing
def _get_enabled_mcps(request: PromptRequest, role) -> list[str]:
    """Get enabled MCP configurations for the request."""
    # 如果请求明确指定了MCP列表（包括空列表），使用它；否则使用角色默认配置
    if request.enabled_mcps is not None:
        return request.enabled_mcps
    else:
        return role.mcp_configs


def _setup_mcp_tools(enabled_mcps: list[str]) -> list:
    """Setup MCP tools based on enabled configurations."""
    current_tools = []
    for mcp_id in enabled_mcps:
        if mcp_id not in role_manager.mcp_configs:
            logging.warning(f"Unknown MCP ID: {mcp_id}")
            continue

        # Handle built-in tools
        if mcp_id == "http_request":
            current_tools.append(http_request)
        elif mcp_id == "current_time":
            current_tools.append(current_time)
        else:
            # Handle external MCP clients
            mcp_client = get_mcp_client(mcp_id)
            if mcp_client and mcp_client._is_session_active():
                current_tools.extend(mcp_client.list_tools_sync())
            elif mcp_client:
                try:
                    mcp_client.start()
                    current_tools.extend(mcp_client.list_tools_sync())
                except Exception as e:
                    logging.warning(f"Failed to start MCP client {mcp_id}: {e}")

    return current_tools


def _create_agent(system_prompt: str, tools: list, session_id: str, role_id: str) -> Agent:
    """Create and configure the AI agent."""

    # Choose session manager based on environment variable
    if SESSION_DIR.startswith("s3://"):
        s3_path = SESSION_DIR[5:].split('/', 1)
        bucket = s3_path[0]
        path = s3_path[1] if len(s3_path) > 1 else ""
        session_manager = S3SessionManager(session_id=session_id,
            bucket=bucket, prefix=path, region_name=REGION_NAME)
    else:
        session_manager = FileSessionManager(session_id=session_id, storage_dir=SESSION_DIR)

    # 使用SlidingWindowConversationManager，自动截断过大的工具结果
    conversation_manager = SlidingWindowConversationManager(
        window_size=30,  # 保留最近30条消息
        should_truncate_results=True  # 自动截断过大的工具结果，防止context overflow
    )

    # 如果没有工具，传递None而不是空列表，让Strands处理
    agent_tools = tools if tools else None

    return Agent(
        model=bedrock_model,
        callback_handler=None,
        conversation_manager=conversation_manager,
        system_prompt=system_prompt,
        tools=agent_tools,
        session_manager=session_manager,
        agent_id=role_id
    )


def _process_messages(request: PromptRequest) -> list[Dict[str, Any]]:
    """Process and validate input messages."""
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
            logging.error(f"Error processing image: {e}")
            raise ValueError(f"Error processing image: {str(e)}")

    return messages


def _process_stream_event(event: Dict[str, Any], session_id: str, last_event_type: str) -> Optional[tuple[str, str]]:
    """Process streaming event from agent."""
    if "data" in event:
        content = event['data']
        if last_event_type == 'tool':
            content = '<br/>\n' + content
        response_data = {
            'type': 'response',
            'content': content,
            'session_id': session_id
        }
        return f"data: {json.dumps(response_data)}\n\n", 'data'

    elif "current_tool_use" in event:
        tool_name = event["current_tool_use"].get('name', '未知工具')
        status_data = {
            'type': 'status',
            'content': f'🔧 {tool_name}',
            'session_id': session_id
        }
        return f"data: {json.dumps(status_data)}\n\n", 'tool'

    elif "init_event_loop" in event or "start_event_loop" in event or "message" in event:
        heartbeat_data = {'type': 'heartbeat', 'session_id': session_id}
        return f"data: {json.dumps(heartbeat_data)}\n\n", last_event_type

    return None


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, timeout_keep_alive=120)
