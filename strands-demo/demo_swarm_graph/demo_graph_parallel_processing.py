from strands import Agent
from strands.multiagent import GraphBuilder

# 创建 agents
coordinator = Agent(name="coordinator", system_prompt="Coordinate tasks...")
worker1 = Agent(name="worker1", system_prompt="Process data from perspective 1...")
worker2 = Agent(name="worker2", system_prompt="Process data from perspective 2...")
worker3 = Agent(name="worker3", system_prompt="Process data from perspective 3...")
aggregator = Agent(name="aggregator", system_prompt="Aggregate all results...")

# 构建并行图
builder = GraphBuilder()
builder.add_node(coordinator, "coordinator")
builder.add_node(worker1, "worker1")
builder.add_node(worker2, "worker2")
builder.add_node(worker3, "worker3")
builder.add_node(aggregator, "aggregator")

# 并行分发
builder.add_edge("coordinator", "worker1")
builder.add_edge("coordinator", "worker2")
builder.add_edge("coordinator", "worker3")

# 聚合结果
builder.add_edge("worker1", "aggregator")
builder.add_edge("worker2", "aggregator")
builder.add_edge("worker3", "aggregator")

graph = builder.build()
result = graph("Analyze this dataset from multiple perspectives")

'''
特点：
- 独立任务并行执行
- 提高处理效率
- 适合可分解的大任务
'''
