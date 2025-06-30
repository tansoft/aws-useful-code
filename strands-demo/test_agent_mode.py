from strands import Agent
from strands_tools import swarm, file_read

agent = Agent(tools=[swarm, file_read])
result = agent.tool.swarm(
    task = '2025年广东高考物理516分+生政科目组合志愿规划',
    system_prompt = '你是一个高考志愿填报的专家',
    swarm_size=4,
    coordination_pattern = 'collaborative'
)
print(result)
# print(agent("Use a swam of 4 agents to analyze this dataset and identify trends."))
