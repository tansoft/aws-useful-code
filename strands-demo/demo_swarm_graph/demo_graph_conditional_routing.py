from strands import Agent
from strands.multiagent import GraphBuilder

'''
特点：
- 基于条件的动态路由
- 确定性的执行流程
- 适合需要分支逻辑的场景
'''

# 创建 agents
classifier = Agent(name="classifier", system_prompt="Classify the request type...")
tech_specialist = Agent(name="tech_specialist", system_prompt="Handle technical requests...")
business_specialist = Agent(name="business_specialist", system_prompt="Handle business requests...")

# 条件函数
def is_technical(state):
    classifier_result = state.results.get("classifier")
    if not classifier_result:
        return False
    result_text = str(classifier_result.result)
    return "technical" in result_text.lower()

def is_business(state):
    classifier_result = state.results.get("classifier")
    if not classifier_result:
        return False
    result_text = str(classifier_result.result)
    return "business" in result_text.lower()

# 构建图
builder = GraphBuilder()
builder.add_node(classifier, "classifier")
builder.add_node(tech_specialist, "tech_specialist")
builder.add_node(business_specialist, "business_specialist")

# 添加条件边
builder.add_edge("classifier", "tech_specialist", condition=is_technical)
builder.add_edge("classifier", "business_specialist", condition=is_business)

graph = builder.build()

print("\n👨 可以问我技术问题或者商务问题，输入 'exit' 退出.\n")
while True:
    user_input = input("\nYou > ")
    if user_input.lower() in ['quit','exit']:
        print("Happy day! ")
        break
    result = graph(user_input+"，请以中文回答。")
