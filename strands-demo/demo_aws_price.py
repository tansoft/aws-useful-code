import logging
import boto3
import json
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from strands.models import BedrockModel

class AWSPricingTool:
    """Tool for querying AWS pricing information."""

    def get_services(self):
        """Get list of available AWS services."""
        try:
            pricing_client = boto3.client('pricing', region_name='us-east-1')
            response = pricing_client.describe_services()
            services = [service['ServiceCode'] for service in response['Services']]
            return json.dumps({"services": services})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def get_instance_types(self):
        """Get list of available EC2 instance types."""
        try:
            ec2_client = boto3.client('ec2', region_name='us-east-1')
            response = ec2_client.describe_instance_types()
            instance_types = [instance['InstanceType'] for instance in response['InstanceTypes']]
            return json.dumps({"instance_types": instance_types})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def get_service_pricing(self, service_code):
        """Get pricing information for a specific service."""
        try:
            pricing_client = boto3.client('pricing', region_name='us-east-1')
            response = pricing_client.get_products(
                ServiceCode=service_code,
                MaxResults=100
            )
            products = []
            for price_item in response.get('PriceList', []):
                products.append(json.loads(price_item))
            
            return json.dumps({"pricing": products})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def get_instance_pricing(self, instance_type, region='us-east-1'):
        """Get pricing information for a specific EC2 instance type."""
        try:
            pricing_client = boto3.client('pricing', region_name='us-east-1')
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_region_name(region)},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}
            ]
            
            response = pricing_client.get_products(
                ServiceCode='AmazonEC2',
                Filters=filters
            )
            
            products = []
            for price_item in response.get('PriceList', []):
                products.append(json.loads(price_item))
            
            return json.dumps({"pricing": products})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def _get_region_name(self, region_code):
        """Convert region code to region name for pricing API."""
        region_names = {
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            'ap-east-1': 'Asia Pacific (Hong Kong)',
            'ap-south-1': 'Asia Pacific (Mumbai)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)',
            'ap-northeast-2': 'Asia Pacific (Seoul)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-southeast-2': 'Asia Pacific (Sydney)',
            'ca-central-1': 'Canada (Central)',
            'eu-central-1': 'EU (Frankfurt)',
            'eu-west-1': 'EU (Ireland)',
            'eu-west-2': 'EU (London)',
            'eu-west-3': 'EU (Paris)',
            'eu-north-1': 'EU (Stockholm)',
            'sa-east-1': 'South America (São Paulo)'
        }
        return region_names.get(region_code, 'US East (N. Virginia)')

if __name__ == "__main__":
    # Set up logging
    logging.getLogger("strands").setLevel(logging.ERROR)
    logging.basicConfig(
        format="%(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler()]
    )
    
    # Initialize Bedrock model
    bedrock_model = BedrockModel(
        model_id= "us.amazon.nova-pro-v1:0",
        params={"max_tokens": 300000, "temperature": 0.1}
    )
    
    # Create AWS pricing tool
    aws_pricing_tool = AWSPricingTool()
    
    # Define tools using @tool decorator
    @tool
    def get_services():
        """
        Get a list of available AWS services.
        """
        return aws_pricing_tool.get_services()
    
    @tool
    def get_instance_types():
        """
        Get a list of available EC2 instance types.
        """
        return aws_pricing_tool.get_instance_types()
    
    @tool
    def get_service_pricing(service_code: str):
        """
        Get pricing information for a specific service.
        
        Args:
            service_code: The service code (e.g., AmazonEC2, AmazonRDS)
        """
        return aws_pricing_tool.get_service_pricing(service_code)
    
    @tool
    def get_instance_pricing(instance_type: str, region: str = "us-east-1"):
        """
        Get pricing information for a specific EC2 instance type.
        
        Args:
            instance_type: The EC2 instance type (e.g., t2.micro, m5.large)
            region: AWS region code (e.g., us-east-1)
        """
        return aws_pricing_tool.get_instance_pricing(instance_type, region)
    
    # List our custom tools
    custom_tools = [
        get_services,
        get_instance_types,
        get_service_pricing,
        get_instance_pricing
    ]
    
    # Create the agent with our custom tools and AWS documentation MCP
    # stdio_mcp_client = MCPClient(lambda: stdio_client(StdioServerParameters(command="uvx", args=["awslabs.aws-documentation-mcp-server@latest"])))
    
    #with stdio_mcp_client:
    #    tools=[*custom_tools, *stdio_mcp_client.list_tools_sync()]

    # Create the agent with both our custom tools and MCP tools
    agent = Agent(
        model=bedrock_model,
        system_prompt="""你是一个AWS价格专家，可以提供AWS服务、实例类型和价格信息。你可以使用以下工具：
1. get_services - 获取可用AWS服务列表
2. get_instance_types - 获取可用EC2实例类型列表
3. get_service_pricing - 获取特定服务的价格信息
4. get_instance_pricing - 获取特定EC2实例类型的价格信息
5. AWS文档工具 - 查询AWS文档以获取更多信息

请提供准确的AWS价格信息，并解释价格结构、可用区域和服务特性。如果用户询问非价格相关的AWS问题，你也可以使用AWS文档工具来回答。""",
        tools = custom_tools
    )
    
    print("\n👨 AWS价格助手: 询问关于AWS服务、实例类型和价格的问题! 输入'exit'退出。\n")
    
    # Run the agent in a loop for interactive conversation
    while True:
        # 美东一amd机型，2x系列，spot价格对比，saving plan价格对比，输出一个表格
        user_input = input("\n您 > ")
        if user_input.lower() in ['quit', 'exit']:
            print("感谢使用AWS价格助手！")
            break
        response = agent(user_input + "，请以中文回答，并在需要时提供相关价格和文档链接。")
        print(f"\nAWS价格助手 > {response}")