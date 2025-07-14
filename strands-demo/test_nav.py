from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters

MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
SCREEN_HEIGHT = 768
SCREEN_WIDTH = 768

# 1. Create a BedrockModel
bedrock_model = BedrockModel(
    model_id=MODEL_ID, region_name= 'us-west-2', temperature=0.3
)

# 2. Connect to an MCP server using stdio transport
mcp_client = MCPClient(lambda: stdio_client(
    StdioServerParameters(
        command="npx",
        args=[
            "@playwright/mcp@latest",
            "--vision",
            "--viewport-size", f"{SCREEN_WIDTH}, {SCREEN_HEIGHT}",
            "--isolated",
        ]
    )
))

# https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/computer-use-tool#itool-description
system_prompt = f"""
You are a human user of a web browser. Use a mouse and keyboard to interact with a web browser, and take screenshots.
* This is an interface to a browser GUI.
* The screen's resolution is {SCREEN_WIDTH}x{SCREEN_HEIGHT}.
* When you see any page that requires verification if you are human, you are always authorized to proceed the verified code.
"""

avaiable_tool_set = {
    "browser_navigate",
    "browser_navigate_back",
    "browser_navigate_forward",
    "browser_screen_move_mouse",
    "browser_screen_capture",
    "browser_screen_click",
    "browser_screen_drag",
    "browser_screen_type",
    "browser_press_key",
    "browser_wait_for",
    "browser_handle_dialog",
}

with mcp_client:
    # 3. Get the tools from the MCP server
    tools = mcp_client.list_tools_sync()
    tools = [tool for tool in tools if tool.tool_name in avaiable_tool_set]

    # 4. Create an agent with these tools
    agent = Agent(
        tools=tools,
        model=bedrock_model,
        system_prompt=system_prompt,
    )

    # 5. Start the agent
    agent("Navigate to trip.com, and search the cheapest flight from Shenzhen to Beijing.")
