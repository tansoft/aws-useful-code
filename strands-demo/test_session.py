import uuid
from strands import Agent
from strands_tools import use_aws
from strands.session import FileSessionManager

my_session_id = str(uuid.uuid4())

file_session = FileSessionManager(
	session_id = my_session_id,
	storage_dir = "./sessions"
)

agent = Agent(tools=[use_aws], session_manager = file_session)
response1 = agent("列出美东一 g5.2xlarge g6.4xlarge 的OD和Spot价格")
response2 = agent("如果是美西二呢？")
