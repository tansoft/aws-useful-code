from strands import Agent

def test_calculator():
    from strands_tools import calculator
    agent = Agent(tools=[calculator])
    '''
    I'll calculate 80 divided by 4 for you using the calculator tool.
    Tool #1: calculator
    The answer is 20.
    '''
    response = agent("What is 80 / 4?")
    # Basic arithmetic evaluation
    response1 = agent.tool.calculator(expression="2 * sin(pi/4) + log(e**2)")
    print(response1)
    # Equation solving
    response2 = agent.tool.calculator(expression="x**2 + 2*x + 1", mode="solve")
    print(response2)

def test_file():
    from strands_tools import file_read, file_write, editor
    agent = Agent(tools=[file_read, file_write, editor])
    agent.tool.file_read(path="config.json")
    agent.tool.file_write(path="output.txt", content="Hello, world!")
    agent.tool.editor(command="view", path="script.py")

def test_http_request():
    from strands_tools import http_request
    import json
    agent = Agent(tools=[http_request])
    # 直接请求url
    #   agent.tool.http_request(url="XXXXXXXXXXXXXXXXXXXXXX")
    # 基于已知请求直接提问：
    """
    I can help you find out where the International Space Station (ISS) is currently located. I'll use an API to get its current position.
    Tool #1: http_request
    Based on the API data I just retrieved, the International Space Station is currently at:

    - Latitude: -26.9114° (South)
    - Longitude: -150.1951° (West)

    This position places the ISS over the South Pacific Ocean, likely several hundred miles off the coast of South America. 

    The ISS orbits the Earth at approximately 28,000 km/h (17,500 mph), completing about 16 orbits per day, so this location is constantly changing. The coordinates I provided are accurate as of the current timestamp in the data.
    """
    print(agent("Where is the " + "International Space Station?"))
    # 进行 POST 请求
    response = agent.tool.http_request(
        method="POST",
        url="https://api.example.com/resource",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"key": "value"}),
        auth_type="Bearer",
        auth_token="your_token_here"
    )

def test_shell():
    from strands_tools import shell
    agent = Agent(tools=[shell])
    agent.tool.shell(command="ls -l")

def test_python_repl():
    from strands_tools import python_repl
    agent = Agent(tools=[python_repl])
    # Execute Python code with state persistence
    result = agent.tool.python_repl(code="""
    import pandas as pd

    # Load and process data
    data = pd.read_csv('data.csv')
    processed = data.groupby('category').mean()

    processed.head()
    """)

def test_aws():
    from strands_tools import use_aws
    agent = Agent(tools=[use_aws])
    # Get the list of EC2 subnets
    result = agent.tool.use_aws(
        service_name="ec2",
        operation_name="describe_subnets",
        parameters={},
        region="us-east-1",
        label="List all subnets"
    )
    print(result)
    # Get the contents of a specific S3 bucket
    # 如果桶不存在会打印：AWS call threw exception: ClientError
    # result对象中有详情：{'toolUseId': 'tooluse_use_aws_402153595', 'status': 'error', 'content': [{'text': 'AWS call threw exception: An error occurred (AccessDenied) when calling the ListObjectsV2 operation: Access Denied'}]}
    result = agent.tool.use_aws(
        service_name="s3",
        operation_name="list_objects_v2",
        # Replace with your actual bucket name, If the bucket does not exist, a ClientError will be reported
        parameters={"Bucket": "xxxxxx"},
        region="us-east-1",
        label="List objects in a specific S3 bucket"
    )
    print(result)
    # 通过大模型调用
    '''
    我需要调用 AWS S3 API 来列出您的 S3 桶。我将使用 `list_buckets` 操作来获取您账户中的所有 S3 桶列表。
    Tool #1: use_aws
    以下是您的 S3 桶列表:

    | 序号 | 桶名 | 创建日期 |
    |------|------|----------|
    | 1 | xxxxx1 | 2023-01-06 |
    | 2 | xxxxx2 | 2024-12-28 |
    ...
    | 10 | xxxxx0 | 2024-04-10 |

    这只是您所有 S3 桶的前 10 个。您总共有 118 个 S3 桶。如果您想查看特定桶的内容或需要更详细的信息，请告诉我您想查看哪个桶的内容。
    '''
    agent("列出我的s3桶")
    '''
好的，我将为您查询美东一区域(us-east-1)的g5.2xlarge和g6.4xlarge实例的按需(On-Demand)和竞价(Spot)价格。
Tool #2: use_aws

Tool #3: use_aws

Tool #4: use_aws
根据查询到的信息，我为您整理美东一区域(us-east-1)的g5.2xlarge和g6.4xlarge实例的价格信息：

## 按需(On-Demand)价格

| 实例类型 | vCPU | 内存 | GPU | GPU内存 | 存储 | 按需价格(每小时) |
|---------|------|------|-----|---------|------|----------------|
| g5.2xlarge | 8 | 32 GiB | 1 | 24 GB | 1x450 GB NVMe SSD | $1.212 |
| g6.4xlarge | 16 | 64 GiB | 1 | 24 GB | 1x600 GB NVMe SSD | $1.3232 |

## 竞价(Spot)价格

竞价实例的价格会根据可用区和供需情况不断变化。以下是最近的平均竞价价格：

### g5.2xlarge 竞价价格(各可用区)
- us-east-1a: 约 $0.457 - $0.486 (最低约为按需价格的38%)
- us-east-1b: 约 $0.650 - $0.661 (最低约为按需价格的54%)
- us-east-1c: 约 $0.605 - $0.630 (最低约为按需价格的50%)
- us-east-1d: 约 $0.505 - $0.520 (最低约为按需价格的42%)
- us-east-1f: 约 $0.415 - $0.460 (最低约为按需价格的34%，价格最低的可用区)

### g6.4xlarge 竞价价格(各可用区)
- us-east-1a: 约 $0.545 - $0.595 (最低约为按需价格的41%)
- us-east-1b: 约 $0.530 - $0.630 (最低约为按需价格的40%)
- us-east-1c: 约 $0.560 - $0.615 (最低约为按需价格的42%)
- us-east-1d: 约 $0.645 - $0.725 (最低约为按需价格的49%)

## 总结与比较

1. **性能比较**:
   - g6.4xlarge 拥有更多的vCPU和内存(16核64GB vs 8核32GB)
   - 两者都有1个GPU，均为24GB显存
   - g6为较新一代实例，性能理论上更优

2. **性价比**:
   - g5.2xlarge 按需价格为 $1.212/小时
   - g6.4xlarge 按需价格为 $1.3232/小时，约贵10%但资源翻倍
   - 竞价实例可节省约50-65%的成本，特别是在us-east-1a和us-east-1f可用区

3. **最佳选择建议**:
   - 如果需要更高的计算能力和内存，g6.4xlarge更适合
   - 如果预算有限但仍需GPU资源，g5.2xlarge性价比略高
   - 使用竞价实例可大幅降低成本，尤其是选择us-east-1a或us-east-1f可用区的g5.2xlarge

如需更稳定的服务，建议使用按需实例；如果能接受实例可能被回收的风险，竞价实例可以节省大量成本。
    '''
    agent("列出美东一 g5.2xlarge g6.4xlarge 的OD和Spot价格")

def test_mem0():
    # https://github.com/strands-agents/samples/blob/222e5c1579fa31efc1bf9741e75d4442d050acc5/01-tutorials/01-fundamentals/07-memory-persistent-agents/personal_agent_with_memory.ipynb
    # pip install mem0ai opensearch-py faiss-cpu
    from strands_tools import mem0_memory
    import os
    # os.environ["OPENSEARCH_HOST"] = "xxx"
    # os.environ["MEM0_API_KEY"] = "xxx"
    agent = Agent(tools=[mem0_memory])
    # Store memory in Memory
    agent.tool.mem0_memory(
        action="store",
        content="Important information to remember",
        user_id="alex",  # or agent_id="agent1"
        metadata={"category": "meeting_notes"}
    )
    # Retrieve content using semantic search
    agent.tool.mem0_memory(
        action="retrieve",
        query="meeting information",
        user_id="alex"  # or agent_id="agent1"
    )
    # List all memories
    agent.tool.mem0_memory(
        action="list",
        user_id="alex"  # or agent_id="agent1"
    )

def test_memory():
    from strands_tools.memory import memory
    agent = Agent(tools=[memory])
    # Store content in Knowledge Base
    response = agent.tool.memory(
        action="store",
        content="Important information to remember",
        title="Meeting Notes",
        STRANDS_KNOWLEDGE_BASE_ID="my1234kb"
    )
    print(response)
    # Retrieve content using semantic search
    response1 = agent.tool.memory(
        action="retrieve",
        query="meeting information",
        min_score=0.7,
        STRANDS_KNOWLEDGE_BASE_ID="my1234kb"
    )
    print(response1)
    # List all documents
    response2 = agent.tool.memory(
        action="list",
        max_results=50,
        STRANDS_KNOWLEDGE_BASE_ID="my1234kb"
    )
    print(response2)

def test_speak():
    from strands_tools import speak
    agent = Agent(tools=[speak])
    agent.tool.speak(text="What is the capital of France?")

def test_wolfram_alpha():
    from strands_tools import wolfram_alpha
    agent = Agent(tools=[wolfram_alpha])
    agent.tool.wolfram_alpha(query="What is the capital of France?")

def test_custom_tools():
    agent = Agent()
    # 依赖工具 tools/weather_forecast.py 和 tools/air_pollution_forecast.py （自动加载）
    print(agent("What's the weather and air pollution forecast in Seattle tmw?"))

def debug_mode():
    # logging
    import logging
    # Enables Strands debug log level
    logging.getLogger("strands").setLevel(logging.DEBUG)

    # Sets the logging format and streams logs to stderr
    logging.basicConfig(
        format="%(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler()]
    )

if __name__ == "__main__":
    # 需要详细调试信息时，请调用这个函数开启调试模式
    #debug_mode()
    test_calculator()
    test_file()
    test_http_request()
    test_shell()
    test_python_repl()
    test_aws()
    #test_mem0()
    #test_memory()
    test_speak()
    test_custom_tools()
