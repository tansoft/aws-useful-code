from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator, http_request
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_model = BedrockModel(
    model="qwen.qwen3-coder-480b-a35b-v1:0",
    params={"max_tokens": 1600, "temperature": 0.7}
)

agent = Agent(model=bedrock_model, tools=[calculator, http_request])

def lambda_handler(event, context):
    """AI MCP Handler - Ask AI"""
    logger.info(f"AI MCP event: {json.dumps(event, default=str)}")

    # Get the tool name from the context
    delimiter = "___"
    org_tool_name = context.client_context.custom['bedrockAgentCoreToolName']
    tool_name = org_tool_name[org_tool_name.index(delimiter) + len(delimiter):]

    try:
        if tool_name == 'ask_ai':
            question = event.get("question", "python中如何打印class方法?")
            response = agent(question)
            return {"response": str(response)}
            pass
        elif tool_name == 'calculator':
            question = event.get("expression", "2 * sin(pi/4) + log(e**2)")
            response = agent.tool.calculator(expression=expression)
            return {"response": response}
            pass
        else:
            # Handle unknown tool
            return {"response": f"unknown tools ${tool_name}"}
            pass

    except Exception as e:
        logger.error(f"Handler error: {e!s}", exc_info=True)
        return {"error": f"Failed to fetch Bedrock: {e!s}"}
