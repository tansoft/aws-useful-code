import logging
import boto3
import json
import time
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from strands import Agent, tool
from strands.models import BedrockModel

# Set up logging
logging.getLogger("strands").setLevel(logging.INFO)  # Change to INFO to see more details
logging.basicConfig(
    level=logging.INFO,  # Set to INFO level
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

app = FastAPI()

class PromptRequest(BaseModel):
    message: str

# Initialize Bedrock model
bedrock_model = BedrockModel(
    #model_id="us.amazon.nova-pro-v1:0",
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    # "max_tokens": 300000
    params={"temperature": 0.1}
)

# Define tools using @tool decorator
@tool
def get_services():
    """
    Get a list of available AWS services.
    """
    try:
        cache = True
        all_services = []
        print('get_services', cache)
        if cache:
            all_services = ['A4B', 'ACM', 'AWSAmplify', 'AWSAppFabric', 'AWSAppRunner', 'AWSAppStudio', 'AWSAppSync', 'AWSApplicationMigrationSvc', 'AWSB2Bi', 'AWSBCMPricingCalculator', 'AWSBackup', 'AWSBillingConductor', 'AWSBudgets', 'AWSCertificateManager', 'AWSCleanRooms', 'AWSCloudFormation', 'AWSCloudMap', 'AWSCloudTrail', 'AWSCloudWAN', 'AWSCodeArtifact', 'AWSCodeCommit', 'AWSCodeDeploy', 'AWSCodePipeline', 'AWSComputeOptimizer', 'AWSConfig', 'AWSCostExplorer', 'AWSDataExchange', 'AWSDataSync', 'AWSDataTransfer', 'AWSDatabaseMigrationSvc', 'AWSDeepRacer', 'AWSDeveloperSupport', 'AWSDeviceFarm', 'AWSDirectConnect', 'AWSDirectoryService', 'AWSELB', 'AWSElasticDisasterRecovery', 'AWSElementalMediaConvert', 'AWSElementalMediaLive', 'AWSElementalMediaPackage', 'AWSElementalMediaStore', 'AWSElementalMediaTailor', 'AWSEndUserMessaging3pFees', 'AWSEnterpriseOnRamp', 'AWSEntityResolution', 'AWSEvents', 'AWSFIS', 'AWSFMS', 'AWSGlobalAccelerator', 'AWSGlueElasticViews', 'AWSGlue', 'AWSGreengrass', 'AWSGroundStation', 'AWSIAMAccessAnalyzer', 'AWSIoT1Click', 'AWSIoTAnalytics', 'AWSIoTEvents', 'AWSIoTFleetWise', 'AWSIoTSiteWise', 'AWSIoTThingsGraph', 'AWSIoT', 'AWSLakeFormation', 'AWSLambda', 'AWSM2', 'AWSMDC', 'AWSMediaConnect', 'AWSMigrationHubRefactorSpaces', 'AWSNetworkFirewall', 'AWSOutposts', 'AWSPCS', 'AWSPrivate5G', 'AWSQueueService', 'AWSR53AppRecoveryController', 'AWSResilienceHub', 'AWSRoboMaker', 'AWSSecretsManager', 'AWSSecurityHub', 'AWSServiceCatalog', 'AWSShield', 'AWSStorageGatewayDeepArchive', 'AWSStorageGateway', 'AWSSupplyChain', 'AWSSupportBusiness', 'AWSSupportEnterprise', 'AWSSystemsManager', 'AWSTelcoNetworkBuilder', 'AWSTransfer', 'AWSWickr', 'AWSWisdom', 'AWSXRay', 'AlexaTopSites', 'AlexaWebInfoService', 'AmazonA2I', 'AmazonApiGateway', 'AmazonAppStream', 'AmazonAthena', 'AmazonBedrockService', 'AmazonBedrock', 'AmazonBraket', 'AmazonChimeBusinessCalling', 'AmazonChimeCallMeAMCS', 'AmazonChimeCallMe', 'AmazonChimeDialInAMCS', 'AmazonChimeDialin', 'AmazonChimeFeatures', 'AmazonChimeServices', 'AmazonChimeVoiceConnector', 'AmazonChime', 'AmazonCloudDirectory', 'AmazonCloudFront', 'AmazonCloudSearch', 'AmazonCloudWatch', 'AmazonCodeWhisperer', 'AmazonCognitoSync', 'AmazonCognito', 'AmazonConnectCases', 'AmazonConnectVoiceID', 'AmazonConnect', 'AmazonDAX', 'AmazonDataZone', 'AmazonDeadline', 'AmazonDetective', 'AmazonDevOpsGuru', 'AmazonDocDB', 'AmazonDynamoDB', 'AmazonEC2', 'AmazonECRPublic', 'AmazonECR', 'AmazonECS', 'AmazonEFS', 'AmazonEI', 'AmazonEKSAnywhere', 'AmazonEKS', 'AmazonES', 'AmazonETS', 'AmazonEVS', 'AmazonElastiCache', 'AmazonFSx', 'AmazonFinSpace', 'AmazonForecast', 'AmazonFraudDetector', 'AmazonGameLiftStreams', 'AmazonGameLift', 'AmazonGlacier', 'AmazonGrafana', 'AmazonGuardDuty', 'AmazonHealthLake', 'AmazonHoneycode', 'AmazonIVSChat', 'AmazonIVS', 'AmazonInspectorV2', 'AmazonInspector', 'AmazonKendra', 'AmazonKinesisAnalytics', 'AmazonKinesisFirehose', 'AmazonKinesisVideo', 'AmazonKinesis', 'AmazonLex', 'AmazonLightsail', 'AmazonLocationService', 'AmazonLookoutEquipment', 'AmazonLookoutMetrics', 'AmazonLookoutVision', 'AmazonMCS', 'AmazonML', 'AmazonMQ', 'AmazonMSK', 'AmazonMWAA', 'AmazonMacie', 'AmazonManagedBlockchain', 'AmazonMedicalImaging', 'AmazonMemoryDB', 'AmazonMonitron', 'AmazonNeptune', 'AmazonOmics', 'AmazonPersonalize', 'AmazonPinpoint', 'AmazonPolly', 'AmazonPrometheus', 'AmazonQLDB', 'AmazonQ', 'AmazonQuickSight', 'AmazonRDS', 'AmazonRedshift', 'AmazonRekognition', 'AmazonRoute53', 'AmazonS3GlacierDeepArchive', 'AmazonS3', 'AmazonSES', 'AmazonSNS', 'AmazonSWF', 'AmazonSageMaker', 'AmazonSecurityLake', 'AmazonSimpleDB', 'AmazonStates', 'AmazonSumerian', 'AmazonTextract', 'AmazonTimestream', 'AmazonVPC', 'AmazonVerifiedPermissions']
        else:
            pricing_client = boto3.client('pricing', region_name='us-east-1')
            all_services = []        
            next_token = None
            while True:
                params = {'MaxResults': 100}
                if next_token:
                    params['NextToken'] = next_token
                response = pricing_client.describe_services(**params)
                services = [service['ServiceCode'] for service in response['Services']]
                all_services.extend(services)
                if 'NextToken' in response:
                    next_token = response['NextToken']
                else:
                    break
        print('all_services', len(all_services))
        return json.dumps({"services": all_services})
    except Exception as e:
        print('error', e)
        return json.dumps({"error": str(e)})

@tool
def get_instance_types():
    """
    Get a list of available EC2 instance types.
    """
    try:
        print('get_instance_types')
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_instance_types()
        instance_types = [instance['InstanceType'] for instance in response['InstanceTypes']]
        print('instance_types', len(instance_types))
        return json.dumps({"instance_types": instance_types})
    except Exception as e:
        print('error', e)
        return json.dumps({"error": str(e)})

@tool
def get_service_pricing(service_code: str, region: str = "us-east-1"):
    """
    Get pricing information for a specific service.
    
    Args:
        service_code: The service code (e.g., AmazonEC2, AmazonRDS)
        region: AWS region code (e.g., us-east-1)
    """
    try:
        print('get_service_pricing', service_code, region)
        pricing_client = boto3.client('pricing', region_name='us-east-1')
        filters = [
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': _get_region_name(region)},
        ]
        response = pricing_client.get_products(
            ServiceCode=service_code,
            Filters=filters,
            MaxResults=100
        )
        products = []
        for price_item in response.get('PriceList', []):
            products.append(json.loads(price_item))
        print('products:', len(products))
        return json.dumps({"pricing": products})
    except Exception as e:
        print('error', e)
        return json.dumps({"error": str(e)})

def _get_region_name(region_code):
    """Convert region code to region name for pricing API."""
    region_names = {
        'af-south-1': 'Africa (Cape Town)',
        'ap-east-1': 'Asia Pacific (Hong Kong)',
        'ap-east-2': 'Asia Pacific (Taipei)',
        'ap-northeast-1': 'Asia Pacific (Tokyo)',
        'ap-northeast-2': 'Asia Pacific (Seoul)',
        'ap-northeast-3': 'Asia Pacific (Osaka)',
        'ap-south-1': 'Asia Pacific (Mumbai)',
        'ap-south-2': 'Asia Pacific (Hyderabad)',
        'ap-southeast-1': 'Asia Pacific (Singapore)',
        'ap-southeast-2': 'Asia Pacific (Sydney)',
        'ap-southeast-3': 'Asia Pacific (Jakarta)',
        'ap-southeast-4': 'Asia Pacific (Melbourne)',
        'ap-southeast-5': 'Asia Pacific (Malaysia)',
        'ap-southeast-7': 'Asia Pacific (Thailand)',
        'ca-central-1': 'Canada (Central)',
        'ca-west-1': 'Canada West (Calgary)',
        'eu-central-1': 'EU (Frankfurt)',
        'eu-central-2': 'EU (Zurich)',
        'eu-north-1': 'EU (Stockholm)',
        'eu-south-1': 'EU (Milan)',
        'eu-south-2': 'EU (Spain)',
        'eu-west-1': 'EU (Ireland)',
        'eu-west-2': 'EU (London)',
        'eu-west-3': 'EU (Paris)',
        'il-central-1': 'Israel (Tel Aviv)',
        'me-central-1': 'Middle East (UAE)',
        'me-south-1': 'Middle East (Bahrain)',
        'mx-central-1': 'Mexico (Central)',
        'sa-east-1': 'South America (São Paulo)',
        'us-east-1': 'US East (N. Virginia)',
        'us-east-2': 'US East (Ohio)',
        'us-west-1': 'US West (N. California)',
        'us-west-2': 'US West (Oregon)'
    }
    return region_names.get(region_code, 'US East (N. Virginia)')

@tool
def get_regions():
    """
    Get a list of available AWS regions.
    """
    try:
        print('get_regions')
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_regions()
        regions = [region['RegionName'] for region in response['Regions']]
        print('regions', len(regions))
        return json.dumps({"regions": regions})
    except Exception as e:
        print('error', e)
        return json.dumps({"error": str(e)})

@tool
def get_instance_pricing(instance_type: str = 'm6g', region: str = "us-east-1", operatingSystem: str = "Linux"):
    """
    Get pricing information for a specific EC2 instance type.
    
    Args:
        instance_type: The EC2 instance type (e.g., t2.micro, m5.large)
        region: AWS region code (e.g., us-east-1)
        operatingSystem: Operating System (e.g., Linux)
    """
    try:
        print('get_instance_pricing', instance_type, region, operatingSystem)
        pricing_client = boto3.client('pricing', region_name='us-east-1')
        filters = [
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': _get_region_name(region)},
            {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
            {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': operatingSystem},
            {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}
        ]        
        response = pricing_client.get_products(
            ServiceCode='AmazonEC2',
            Filters=filters,
        )
        products = []
        for price_item in response.get('PriceList', []):
            products.append(json.loads(price_item))
        print('products', len(products))
        return json.dumps({"pricing": products})
    except Exception as e:
        print('error', e)
        return json.dumps({"error": str(e)})

@tool
def get_spot_instance_pricing(instance_type: str = 'm6g', region: str = "us-east-1", operatingSystem: str = "Linux"):
    """
    Get spot pricing information for a specific EC2 instance type.
    
    Args:
        instance_type: The EC2 instance type (e.g., t2.micro, m5.large)
        region: AWS region code (e.g., us-east-1)
        operatingSystem: Operating System (e.g., Linux)
    """
    try:
        print('get_spot_instance_pricing', instance_type, region, operatingSystem)
        ec2_client = boto3.client('ec2', region_name=region)
        if operatingSystem == "Linux":
            operatingSystem = "Linux/UNIX (Amazon VPC)"
        elif operatingSystem == "Windows":
            operatingSystem = "Windows (Amazon VPC)"
        response = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            ProductDescriptions=[operatingSystem]
        )
        products = []
        for price_item in response['SpotPriceHistory']:
            products.append({"SpotPrice": price_item['SpotPrice'], "AvailabilityZone": price_item['AvailabilityZone'], "InstanceType": price_item['InstanceType']})
        print('spot', len(products))
        return json.dumps({"pricing": products})
    except Exception as e:
        print('error', e)
        return json.dumps({"error": str(e)})

# List our custom tools
custom_tools = [
    get_instance_types,
    get_spot_instance_pricing,
    get_instance_pricing,
    get_services,
    get_service_pricing,
]

# Create the agent with our custom tools
agent = Agent(
    model=bedrock_model,
    system_prompt="""你是一个AWS价格专家，可以提供AWS服务、实例类型和价格信息。你可以使用以下工具：
1. get_instance_types - 获取可用EC2实例类型列表
2. get_spot_instance_pricing - 获取EC2竞价实例类型的价格信息
3. get_instance_pricing - 获取EC2按需和预留实例类型的价格信息
4. get_services - 获取可用AWS服务列表
5. get_service_pricing - 获取特定服务的价格信息
6. get_regions - 获取目前已经支持的region列表，请确保调用这个工具，获取最新的区域信息。

请提供准确的AWS价格信息，并解释价格结构、可用区域和服务特性。
请以中文回答，并在需要时提供相关文档链接。
价格信息请使用表格返回。""",
    tools=custom_tools,
)

# Log available methods on agent to help debug
agent_methods = [method for method in dir(agent) if not method.startswith('_')]
logging.info(f"Available agent methods: {agent_methods}")

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
            alltext = ''
            async for event in agent.stream_async(request.message):
                if "data" in event:
                    # text = event["data"].replace("<","&lt;").replace(">","&gt;")
                    alltext += event["data"]
                    alltext = alltext.replace('<thinking>','***').replace('</thinking>',"***\n\n")
                    yield f"data: {json.dumps({'type': 'response', 'content': alltext})}\n\n"
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
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
    uvicorn.run(app, host="0.0.0.0", port=8000)