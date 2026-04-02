import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cloudperf_api_lambda="CloudperfStack-apiC8550315-XlWq8GDTE8k0"

def lambda_handler(event, context):
    try:
        print(event)
        limit = event.get("limit", 50)
        # Get the tool name from the context
        delimiter = "___"
        org_tool_name = context.client_context.custom['bedrockAgentCoreToolName']
        tool_name = org_tool_name[org_tool_name.index(delimiter) + len(delimiter):]

        if tool_name == 'ask_ai':
            question = event.get("question", "python中如何打印class方法?")

        lambda_client = boto3.client('lambda')
        response = lambda_client.invoke(
            FunctionName=cloudperf_api_lambda,
            InvocationType='RequestResponse',
            Payload=json.dumps({"limit": limit})
        )
    
        result = json.loads(response['Payload'].read())
        return result
    except Exception as e:
        logger.error(f"Handler error: {e!s}", exc_info=True)
        return {"error": f"Failed to fetch: {e!s}"}
