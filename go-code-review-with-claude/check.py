import boto3
import json

def list_model():
    bedrock = boto3.client(
        service_name="bedrock",
        region_name="us-east-1"
    )
    print(bedrock.list_foundation_models())

def get_claude_model_response(content):
    bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

    system_case1='''
You are an experienced Golang developer.
You are skilled in developing Golang projects and adept at architectural design.
You will be participating in a project review.
You will not answer questions that are not relevant to the context.
You will answer questions use Chinese.
Your answer should be wrapped in <code> tags.
If the question is not relevant, say "I am sorry, I cannot answer that question."
Do not include any other explanatory text.
Do not include any other text formatings.
Only answer questions related to the code.
'''

    system_case2='''
Your task is to analyze the provided Golang code snippet, identify any bugs or errors present,
and provide a corrected version of the code that resolves these issues. 
Explain the problems you found in the original code and how your fixes address them. 
The corrected code should be functional, efficient, and adhere to best practices in Golang programming.
You will answer questions use Chinese.
'''

    system_case3='''
Your task is to analyze the provided Golang code snippet and suggest improvements to optimize its performance. 
Identify areas where the code can be made more efficient, faster, or less resource-intensive. 
Provide specific suggestions for optimization, along with explanations of how these changes can enhance the code's performance. 
The optimized code should maintain the same functionality as the original code while demonstrating improved efficiency.
Skip the preamble, go straight into the answer.
Maker sure there is no syntax error.
You will answer questions use Chinese.
'''

    system_case4='''
You are an experienced Golang developer.
You are skilled in developing Golang projects and adept at architectural design.
You will be participating in a project review.
Your task is to analyze the provided Golang code snippet, identify any bugs or errors present,
and provide a corrected version of the code that resolves these issues.
You can suggest improvements to optimize its performance, Identify areas where the code can be made more efficient, faster, or less resource-intensive. 
Provide specific suggestions for optimization, along with explanations of how these changes can enhance the code's performance.
The optimized code should maintain the same functionality as the original code while demonstrating improved efficiency.
Explain the problems you found in the original code and how your fixes address them. 
The corrected code should be functional, efficient, and adhere to best practices in Golang programming.
Skip the preamble, go straight into the answer.
Maker sure there is no syntax error.
Please provide a concise summary of the bug found in the code, 
describing its characteristics, location, and potential effects on the overall functionality 
and performance of the application.\n\n
Also provide your code suggestion if there is a more time efficient or memory efficient way 
to implement the same functionality.\n\nI would appreciate any feedback you can provide to 
help me improve my coding skills. Please let me know if you need any clarification or 
additional context about the code.\n\n
Important: Include block of code / diff in the summary.\n\n
I want the outout as the follwing JSON format:\n[\n{\n\"level\": \"serious / major / warning\",\n\t\t\"title\": \"summary a title, less than 30 words\",\n
\"content\": \"the code review result\",\n\"filepath\": \"filepath @ line number range\"\n},\n{\n\"level\": \"serious\",\n\t\t\"title\": \"NullPoint Issue\"\n
\"content\": \"There are some NullPoinit issue, ...\",\n\"filepath\": \"path/file.go @line 3\"\n    },\n
//...\n]\n\n
You must:\n
- No preamble needed, no additional explanation is needed. Just give JSON output.\n- You will not display any correct interfaces. \n
- Just tell the incorrect interfaces. \n
- Note that single quotes and double quotes in JSON need to be escaped\n
- Format the JSON output to one line\n
- Use Chinese in field title and content, use English in other fields\n
'''

    body = json.dumps({
        "max_tokens": 4096,
        "system": system_case4,
        "temperature": 1,
        "top_p": 0.999,
        "top_k": 1,
        "stop_sequences": ["</code>"],
        "messages": [{"role": "user", "content": content}],
        "anthropic_version": "bedrock-2023-05-31"
    }).encode('utf-8')
    # claude-3-5-sonnet-20240620
    response = bedrock.invoke_model(body=body, modelId="anthropic.claude-3-sonnet-20240229-v1:0")

    response_body = json.loads(response.get("body").read().decode('utf-8'))
    return response_body.get("content")[0]['text']

with open('samples/meaningless-multiple-judgments.go', 'r') as file:
    file_contents = file.read()

content = '以下是需要检查的代码：<code>' + file_contents
response = get_claude_model_response(content=content)
#print(response) 不够好看
json_str = json.dumps(json.loads(response), indent=4, sort_keys=True, ensure_ascii=False)
print(json_str)
