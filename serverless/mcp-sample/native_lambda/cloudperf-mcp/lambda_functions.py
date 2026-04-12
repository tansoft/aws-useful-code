import os
import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_client = boto3.client('secretsmanager')
lambda_client = boto3.client('lambda')

SECRET_NAME = os.environ.get('CLOUDPERF_SECRET', '')
CLOUDPERF_API_LAMBDA = os.environ.get('CLOUDPERF_API_LAMBDA', '')

def get_secret():
    response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(response['SecretString'])

secrets = get_secret()
CLOUDPERF_USERNAME = secrets.get('username', '')
CLOUDPERF_PASSWORD = secrets.get('password', '')
CLOUDPERF_CPTOKEN = secrets.get('cptoken', '')

def call_cloudperf(fn, params):
    alb_payload = {
        "httpMethod": "GET",
        "path": "/api/" + fn,
        "queryStringParameters": params,
        "headers": {
            "cookie": "cp_token=" + CLOUDPERF_CPTOKEN,
            "user-agent": "mcp-client",
            "host": "mcp.cloudperf.vpc",
        },
        "body": None,
        "isBase64Encoded": False
    }

    response = lambda_client.invoke(
        FunctionName=CLOUDPERF_API_LAMBDA,
        InvocationType='RequestResponse',
        Payload=json.dumps(alb_payload)
    )
    #if response['StatusCode'] != 200:
    #    return response['StatusCode']
    return json.loads(response['Payload'].read())

def call_cloudperf_with_token(fn, params):
    global CLOUDPERF_CPTOKEN
    if CLOUDPERF_CPTOKEN == '':
        print('need login first...')
        ret = call_cloudperf('login',{'username': CLOUDPERF_USERNAME, 'password': CLOUDPERF_PASSWORD})
        if ret['statusCode'] != 200:
            return ret
        ret = json.loads(ret['body'])
        CLOUDPERF_CPTOKEN = f"{ret['token']}|{ret['user']}|{ret['auth']}"
    ret = call_cloudperf(fn, params)
    if ret['statusCode'] == 403:
        print('token expire...')
        CLOUDPERF_CPTOKEN = ''
        return call_cloudperf_with_token(fn, params)
    ret = json.loads(ret['body'])
    return ret

def lambda_handler(event, context):
    try:
        print(event)
        # limit = event.get("limit", 50)
        # Get the tool name from the context
        delimiter = "___"
        org_tool_name = context.client_context.custom['bedrockAgentCoreToolName']
        # find tool name and discard action (get_ or find_)
        tool_name = org_tool_name.split(delimiter, 1)[1].split('_', 1)[1]
        # hack for performance api with rawData=1 flag
        if tool_name == "rawdata":
            tool_name = "performance"
            event["rawData"] = 1
        return call_cloudperf_with_token(tool_name, event)
    except Exception as e:
        logger.error(f"Handler error: {e!s}", exc_info=True)
        return {"error": f"Failed to fetch: {e!s}"}
