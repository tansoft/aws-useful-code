from strands import Agent, tool
from strands.types.tools import ToolResult, ToolUse
from typing import Any

# 方式二：以TOOL_SPEC方式声明，函数用法和参数
TOOL_SPEC = {
    "name": "air_pollution_forecast",
    "description": "Get air pollution forecast for a city.",
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The name of the city"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days for the forecast",
                    "default": 3
                }
            },
            "required": ["city"]
        }
    }
}
def air_pollution_forecast(tool: ToolUse, **kwargs: Any) -> ToolResult:
    if "city" in tool["input"]:
        city = tool["input"]["city"]
    else:
        city = None
    if "days" in tool["input"]:
        days = tool["input"]["days"]
    else:
        days = 3
    return {
        "toolUseId": tool["toolUseId"],
        "status": "success",
        "content": [{"text": f"Air pollution forecast for {city} for the next {days} days..."}],
    }
