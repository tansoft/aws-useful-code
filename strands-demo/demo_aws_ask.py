import logging
import sys, os, boto3
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp import stdio_client,StdioServerParameters
from strands.models import BedrockModel

if __name__ == "__main__":
    logging.getLogger("strands").setLevel(logging.ERROR)
    logging.basicConfig(
        format="%(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler()]
    )
    bedrock_model = BedrockModel(
        model_id= "us.amazon.nova-pro-v1:0",
        params={"max_tokens": 300000, "temperature": 0.1}
    )
    stdio_mcp_client = MCPClient(lambda: stdio_client(StdioServerParameters(command="uvx", args=["awslabs.aws-documentation-mcp-server@latest"])))
    with stdio_mcp_client:
        agent = Agent(model=bedrock_model,
                    system_prompt="你是一个AWS专家",
                    tools=stdio_mcp_client.list_tools_sync())
        print("\n👨 AWSBot: Ask me about AWS question! Type 'exit' to quit.\n")

        # Run the agent in a loop for interactive conversation
        while True:
            user_input = input("\nYou > ")
            if user_input.lower() in ['quit','exit']:
                print("Happy day! ")
                break
            response = agent(user_input+"，请以中文回答，并提供相关文档链接。")
            print(f"\nAWSBot > {response}")