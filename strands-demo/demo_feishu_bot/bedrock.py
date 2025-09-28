import json
import logging
import os
import time
from strands import Agent
from strands.models import BedrockModel
from strands.session import FileSessionManager
from strands.agent.conversation_manager import SummarizingConversationManager
from strands_tools import http_request, current_time
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from cardBuild import build_card
from api import get_current_time, updateTextCard

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
    #model_id="apac.anthropic.claude-sonnet-4-20250514-v1:0",
    model_id="apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
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
        conversation_manager = SummarizingConversationManager(summary_ratio=0.3, preserve_recent_messages=6)

        # 为每个请求创建一个新的 Agent 实例
        # 所有会话数据仍会持久化到磁盘，下次请求会自动加载
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
        alltext = ' '
        
        print(messages)
        # If we have messages, stream the response
        st = time.time()
        toolsidx = 1
        toolsmsg = ""
        if messages:
            async for event in agent.stream_async(messages):
                #print(event)
                if "current_tool_use" in event:
                    tool_name = event["current_tool_use"].get('name', '未知工具')
                    toolsmsg = "#" + str(toolsidx) + " " + tool_name
                    toolsidx+=1
                if "data" in event:
                    alltext += event["data"]
                    alltext = alltext.replace('<thinking>','***').replace('</thinking>',"***\n\n")
                    if time.time() - st > 2:
                        st = time.time()
                        print('step build card')
                        card_content = build_card(alltext, False, toolsmsg)
                        updateTextCard(app_id, message_id, card_content)
                        #yield f"data: {json.dumps({'type': 'response', 'content': alltext, 'session_id': session_id})}\n\n"
                        print('step build card updated')
        
        print('finish build card')
        card_content = build_card(alltext, True)
        updateTextCard(app_id, message_id, card_content)
        print('finish build card updated')
        #yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id})}\n\n"

    except Exception as e:
        errmsg = f"Error in stream_response: {str(e)}"
        logging.error(errmsg)
        card_content = build_card(errmsg, True)
        updateTextCard(app_id, message_id, card_content)
        #yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
