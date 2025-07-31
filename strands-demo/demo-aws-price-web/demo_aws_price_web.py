import logging
import boto3
import json
import time
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from strands import Agent, tool
from strands.models import BedrockModel

# Set up logging
logging.getLogger("strands").setLevel(logging.ERROR)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

app = Flask(__name__)

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

# Initialize AWS pricing tool
aws_pricing_tool = AWSPricingTool()

# Initialize Bedrock model
bedrock_model = BedrockModel(
    model_id="us.amazon.nova-pro-v1:0",
    params={"max_tokens": 300000, "temperature": 0.1}
)

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

# Create the agent with our custom tools
agent = Agent(
    model=bedrock_model,
    system_prompt="""你是一个AWS价格专家，可以提供AWS服务、实例类型和价格信息。你可以使用以下工具：
1. get_services - 获取可用AWS服务列表
2. get_instance_types - 获取可用EC2实例类型列表
3. get_service_pricing - 获取特定服务的价格信息
4. get_instance_pricing - 获取特定EC2实例类型的价格信息

请提供准确的AWS价格信息，并解释价格结构、可用区域和服务特性。""",
    tools=custom_tools
)

@app.route('/')
def index():
    """Render the main chat interface."""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Legacy non-streaming chat API for backwards compatibility."""
    try:
        # Get user input from request
        data = request.get_json()
        user_input = data.get('message', '')
        
        # Process with agent
        response = agent(user_input + "，请以中文回答，并在需要时提供相关价格和文档链接。")
        
        # Convert agent result to string if needed
        if not isinstance(response, str):
            response = str(response)
            
        return jsonify({
            'status': 'success',
            'response': response
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/chat_stream', methods=['POST'])
def chat_stream():
    """Handle streaming chat API requests."""
    
    @stream_with_context
    def generate_streaming_response():
        try:
            # Get user input from request
            data = request.get_json()
            user_input = data.get('message', '')
            
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'message': '已连接到 AWS 价格助手'})}\n\n"
            
            # Check if query involves specific AWS operations
            needs_services = 'services' in user_input.lower() or '服务' in user_input.lower()
            needs_instances = any(keyword in user_input.lower() for keyword in ['ec2', 'instance', 't2', 'm5', 'c5', 'r5', '实例'])
            needs_pricing = any(keyword in user_input.lower() for keyword in ['price', 'cost', 'pricing', '价格', '费用'])
            
            progress = 0
            total_steps = sum([needs_services, needs_instances, needs_pricing, True])  # +1 for AI processing
            
            # Fetch services if needed
            if needs_services:
                progress += 1
                yield f"data: {json.dumps({'type': 'step', 'message': '正在获取 AWS 服务列表...', 'progress': progress/total_steps*100})}\n\n"
                services = json.loads(aws_pricing_tool.get_services())
                service_count = len(services.get("services", []))
                yield f"data: {json.dumps({'type': 'partial', 'content': f'已获取 {service_count} 个 AWS 服务'})}\n\n"
            
            # Fetch instance types if needed
            if needs_instances:
                progress += 1
                yield f"data: {json.dumps({'type': 'step', 'message': '正在获取 EC2 实例类型...', 'progress': progress/total_steps*100})}\n\n"
                instances = json.loads(aws_pricing_tool.get_instance_types())
                instance_count = len(instances.get("instance_types", []))
                yield f"data: {json.dumps({'type': 'partial', 'content': f'已获取 {instance_count} 种 EC2 实例类型'})}\n\n"
            
            # Fetch pricing if needed
            if needs_pricing:
                progress += 1
                yield f"data: {json.dumps({'type': 'step', 'message': '正在获取价格信息...', 'progress': progress/total_steps*100})}\n\n"
                # This step will be handled by the agent through the provided tools
                yield f"data: {json.dumps({'type': 'partial', 'content': '正在分析价格数据'})}\n\n"
            
            # Final AI processing
            progress += 1
            yield f"data: {json.dumps({'type': 'step', 'message': '正在生成回复...', 'progress': progress/total_steps*100})}\n\n"
            
            # Process with agent
            response = agent(user_input + "，请以中文回答，并在需要时提供相关价格和文档链接。")
            
            # Convert agent result to string if needed
            if not isinstance(response, str):
                response = str(response)
            
            # Send final response
            yield f"data: {json.dumps({'type': 'response', 'content': response})}\n\n"
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return Response(
        generate_streaming_response(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering if using nginx
        }
    )

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)