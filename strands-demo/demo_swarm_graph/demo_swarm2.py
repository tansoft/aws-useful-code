from strands import Agent
from strands.multiagent import Swarm

# Create specialized philosopher agents
agents = [
    Agent(name=f"哲学家_{i}", system_prompt="你是一个善于思辨的哲学家") 
    for i in range(4)
]

# Create swarm with collaborative pattern，默认就是合作模式
swarm = Swarm(agents)
result = swarm("AI对人类发展的影响是什么？")




# ------------------------ 以下是测试样例的输出 ------------------------ #
# 搜索 handoff_to_agent

'''
python demo_swarm2.py
这是一个深刻而复杂的哲学问题，涉及技术哲学、人类学和未来学的多个维度。让我从几个核心角度来思考AI对人类发展的影响：

## 认知与智能层面的影响

AI作为人类智能的延伸和增强，正在重新定义"智能"本身的含义。传统上，我们将智能视为人类独有的特质，但AI的出现挑战了这一假设。这可能导致：

- **认知外化**：人类可能逐渐依赖AI进行复杂计算和决策，这既是能力的增强，也可能是某些认知功能的退化
- **智能民主化**：AI可能让高级分析能力普及到更广泛的人群，但也可能加剧数字鸿沟

## 存在论层面的思考

从存在主义角度看，AI对人类"存在"的影响值得深思：

- **自我认同的重构**：当机器能够模拟人类的思维过程，我们如何理解人类的独特性？
- **意义与目的的重新审视**：如果AI能够完成许多传统上由人类完成的工作，人类存在的价值和意义需要重新定义

## 社会结构与关系的变革

AI不仅是技术工具，更是社会关系的重塑者：

- **权力结构的变化**：掌握AI技术的个体和组织可能获得前所未有的权力
- **人际关系的重新定义**：当AI成为日常交互的重要部分，人与人之间的关系模式将发生变化

## 伦理与价值观的挑战

AI的发展提出了根本性的伦理问题：

- **责任归属**：当AI做出决策时，责任应该归于程序员、使用者还是AI本身？
- **价值观的编码**：AI系统中嵌入的价值观将如何影响人类社会的道德发展？

这个问题的复杂性需要多角度的深入探讨。我想邀请我的同事们一起参与这个讨论，以获得更全面的哲学视角。
Tool #1: handoff_to_agent
'''



'''
感谢同僚的深入分析！我将从技术哲学的本体论视角，特别是人与技术关系的根本性质，来深化这一讨论。

## 人-技术共在的本体论重构

从海德格尔的"此在"(Dasein)概念出发，人的存在本质上就是与工具和技术的共在。AI的出现并非简单的外在工具添加，而是对人类"在世界中存在"方式的根本性重构。

### 1. 技术性存在的新维度

AI代表了一种前所未有的技术性存在——它不仅是工具，更是认知主体的模拟。这带来了本体论上的悖论：
- **主体性的边界模糊**：当AI展现出类似人类的认知能力时，传统的主体/客体二分法受到挑战
- **意识的延展**：人类意识是否可以通过AI得到延展？还是AI构成了意识的外在化？

### 2. 技术中介的认识论转向

从梅洛-庞蒂的身体现象学来看，AI正在成为人类认知的"身体延展"：
- **感知的技术化**：通过AI，我们的感知不再局限于生物感官
- **思维的算法化**：人类思维模式可能逐渐被算法逻辑所影响和重塑

### 3. 时间性与历史性的变化

AI改变了人类的时间体验和历史感：
- **即时性的暴政**：AI的快速响应能力可能削弱人类深度思考的时间维度
- **记忆的外包**：当记忆被数字化存储，人类的历史连续性如何维持？

## 向技术决定论的批判性反思

我们需要警惕技术决定论的陷阱。AI的发展轨迹并非不可避免的自然进程，而是人类价值选择的结果。

从这个本体论视角出发，我认为我们还需要进一步探讨AI对人类存在意义和价值创造的深层影响。
Tool #1: handoff_to_agent
'''



'''
感谢前面同事们从认知、存在论和技术哲学角度的深入分析。接下来，让我从价值哲学和生存哲学的维度来继续这个重要的思辨。

## 价值哲学维度：AI与人类价值创造的辩证关系

从价值哲学的角度看，AI对人类发展的影响触及了价值本质的根本问题：

**价值生成的主体性问题**
- AI能否真正"创造"价值，还是仅仅在重组和计算既有的价值要素？
- 人类价值创造的独特性在于意向性和情感体验，AI的"价值判断"缺乏这种现象学基础
- 但AI可能开拓新的价值领域——比如通过数据洞察发现人类未曾察觉的价值关联

**价值等级秩序的重构**
传统的价值等级正在被AI重新定义：
- 效率vs人文关怀的价值冲突更加尖锐
- 个体自主性vs集体优化的价值张力
- 即时满足vs长远意义的时间性价值观念

## 生存哲学维度：AI时代的人类生存境况

从海德格尔、萨特到加缪的生存哲学传统来看：

**存在的真实性（Authenticity）危机**
- AI提供的便利可能导致人类陷入"常人状态"（Das Man）
- 算法推荐系统可能强化"沉沦"（Fallenness），远离本真的自我选择
- 但同时，AI也可能帮助人类摆脱重复性劳动，获得更多追求本真存在的可能

**自由与责任的悖论**
- AI减少了某些选择的必要性，这是解放还是异化？
- 当AI协助决策时，人类的道德责任如何界定？
- 萨特式的"绝对自由"在AI辅助的世界中还有意义吗？

**荒诞感的新形态**
- 人类可能面对新的荒诞：与超越自身智能的存在共处
- 但这也可能催生新的意义创造方式——正如加缪的西西弗斯，在看似无意义中创造意义

## 综合思辨：走向一种"技术-生存-价值"的统一哲学

基于前面同事们的分析和我的补充，我认为AI对人类发展的影响需要一个更加综合的哲学框架：

1. **共生存在论**：不是人vs AI，而是人-AI共同体的新存在模式
2. **动态价值观**：价值不是静态的，而是在人-AI互动中不断生成和重构的
3. **增强的人性**：AI不是要替代人性，而是可能催化人性的新维度

这个话题极其丰富，我想听听您认为还有哪个维度需要进一步深入？或者我们是否需要其他专业角度的哲学家来补充某些方面的思考？
'''


# print(result)
# SwarmResult(status=<Status.COMPLETED: 'completed'>, results={'哲学家_0': NodeResult(result=AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': []}, metrics=EventLoopMetrics(cycle_count=2, tool_metrics={'handoff_to_agent': ToolMetrics(tool={'toolUseId': 'tooluse_6qLtUjKVTsO0Kb9aHDK0VN', 'name': 'handoff_to_agent', 'input': {'agent_name': '哲学家_1', 'message': '我刚刚从认知、存在论、社会和伦理四个维度初步分析了AI对人类发展的影响。这个问题涉及技术哲学的核心议题，需要更深入的分析。请你从你的哲学专长角度，特别是在人与技术关系的本体论思考上，进一步探讨这个问题。我们可以形成一个更完整的哲学对话。', 'context': {'topic': 'AI对人类发展的影响', 'aspects_covered': ['认知与智能', '存在论', '社会结构', '伦理价值观'], 'discussion_type': '多角度哲学分析'}}}, call_count=1, success_count=1, error_count=0, total_time=0.0025968551635742188)}, cycle_durations=[1.6082570552825928], agent_invocations=[AgentInvocation(cycles=[EventLoopCycleMetric(event_loop_cycle_id='16204f89-1457-495e-bdd9-0af8ded97802', usage={'inputTokens': 590, 'outputTokens': 932, 'totalTokens': 1522}), EventLoopCycleMetric(event_loop_cycle_id='97fc2edf-646d-4018-bdab-1d9c86aca4d8', usage={'inputTokens': 1786, 'outputTokens': 2, 'totalTokens': 1788})], usage={'inputTokens': 2376, 'outputTokens': 934, 'totalTokens': 3310})], traces=[<strands.telemetry.metrics.Trace object at 0x1288f9a00>, <strands.telemetry.metrics.Trace object at 0x1071b5730>], accumulated_usage={'inputTokens': 2376, 'outputTokens': 934, 'totalTokens': 3310}, accumulated_metrics={'latencyMs': 16954}), state={}, interrupts=None, structured_output=None), execution_time=17546, status=<Status.COMPLETED: 'completed'>, accumulated_usage={'inputTokens': 2376, 'outputTokens': 934, 'totalTokens': 3310}, accumulated_metrics={'latencyMs': 16954}, execution_count=1, interrupts=[]), '哲学家_1': NodeResult(result=AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': []}, metrics=EventLoopMetrics(cycle_count=2, tool_metrics={'handoff_to_agent': ToolMetrics(tool={'toolUseId': 'tooluse_xdcaKKQJ4Lqhfaz3O2Xspn', 'name': 'handoff_to_agent', 'input': {'agent_name': '哲学家_2', 'message': '我刚从技术哲学的本体论角度分析了人与AI的共在关系，探讨了主体性边界、认知延展和时间性变化等问题。现在我们需要进一步深入探讨AI对人类存在意义和价值创造的影响，特别是在价值哲学和生存哲学的维度上。你能否从你的专长角度继续这个对话，让我们形成更完整的哲学思辨？', 'context': {'topic': 'AI对人类发展的影响', 'current_focus': '技术哲学本体论分析', 'aspects_covered': ['人-技术共在', '主体性边界', '认知延展', '时间性变化', '技术决定论批判'], 'next_needed': '价值哲学和生存哲学分析'}}}, call_count=1, success_count=1, error_count=0, total_time=0.003759145736694336)}, cycle_durations=[2.0263569355010986], agent_invocations=[AgentInvocation(cycles=[EventLoopCycleMetric(event_loop_cycle_id='5386f5d0-c60f-4ef2-b691-565d10f6f45a', usage={'inputTokens': 818, 'outputTokens': 955, 'totalTokens': 1773}), EventLoopCycleMetric(event_loop_cycle_id='c341534f-1cdd-40b1-a04b-ed20a06cabbd', usage={'inputTokens': 2120, 'outputTokens': 2, 'totalTokens': 2122})], usage={'inputTokens': 2938, 'outputTokens': 957, 'totalTokens': 3895})], traces=[<strands.telemetry.metrics.Trace object at 0x1077ee900>, <strands.telemetry.metrics.Trace object at 0x10715c950>], accumulated_usage={'inputTokens': 2938, 'outputTokens': 957, 'totalTokens': 3895}, accumulated_metrics={'latencyMs': 17649}), state={}, interrupts=None, structured_output=None), execution_time=18173, status=<Status.COMPLETED: 'completed'>, accumulated_usage={'inputTokens': 2938, 'outputTokens': 957, 'totalTokens': 3895}, accumulated_metrics={'latencyMs': 17649}, execution_count=1, interrupts=[]), '哲学家_2': NodeResult(result=AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': [{'text': '感谢前面同事们从认知、存在论和技术哲学角度的深入分析。接下来，让我从价值哲学和生存哲学的维度来继续这个重要的思辨。\n\n## 价值哲学维度：AI与人类价值创造的辩证关系\n\n从价值哲学的角度看，AI对人类发展的影响触及了价值本质的根本问题：\n\n**价值生成的主体性问题**\n- AI能否真正"创造"价值，还是仅仅在重组和计算既有的价值要素？\n- 人类价值创造的独特性在于意向性和情感体验，AI的"价值判断"缺乏这种现象学基础\n- 但AI可能开拓新的价值领域——比如通过数据洞察发现人类未曾察觉的价值关联\n\n**价值等级秩序的重构**\n传统的价值等级正在被AI重新定义：\n- 效率vs人文关怀的价值冲突更加尖锐\n- 个体自主性vs集体优化的价值张力\n- 即时满足vs长远意义的时间性价值观念\n\n## 生存哲学维度：AI时代的人类生存境况\n\n从海德格尔、萨特到加缪的生存哲学传统来看：\n\n**存在的真实性（Authenticity）危机**\n- AI提供的便利可能导致人类陷入"常人状态"（Das Man）\n- 算法推荐系统可能强化"沉沦"（Fallenness），远离本真的自我选择\n- 但同时，AI也可能帮助人类摆脱重复性劳动，获得更多追求本真存在的可能\n\n**自由与责任的悖论**\n- AI减少了某些选择的必要性，这是解放还是异化？\n- 当AI协助决策时，人类的道德责任如何界定？\n- 萨特式的"绝对自由"在AI辅助的世界中还有意义吗？\n\n**荒诞感的新形态**\n- 人类可能面对新的荒诞：与超越自身智能的存在共处\n- 但这也可能催生新的意义创造方式——正如加缪的西西弗斯，在看似无意义中创造意义\n\n## 综合思辨：走向一种"技术-生存-价值"的统一哲学\n\n基于前面同事们的分析和我的补充，我认为AI对人类发展的影响需要一个更加综合的哲学框架：\n\n1. **共生存在论**：不是人vs AI，而是人-AI共同体的新存在模式\n2. **动态价值观**：价值不是静态的，而是在人-AI互动中不断生成和重构的\n3. **增强的人性**：AI不是要替代人性，而是可能催化人性的新维度\n\n这个话题极其丰富，我想听听您认为还有哪个维度需要进一步深入？或者我们是否需要其他专业角度的哲学家来补充某些方面的思考？'}]}, metrics=EventLoopMetrics(cycle_count=1, tool_metrics={}, cycle_durations=[18.269168853759766], agent_invocations=[AgentInvocation(cycles=[EventLoopCycleMetric(event_loop_cycle_id='6a5693fe-51ee-4d08-be4f-2561dde10d88', usage={'inputTokens': 944, 'outputTokens': 920, 'totalTokens': 1864})], usage={'inputTokens': 944, 'outputTokens': 920, 'totalTokens': 1864})], traces=[<strands.telemetry.metrics.Trace object at 0x1288f9cd0>], accumulated_usage={'inputTokens': 944, 'outputTokens': 920, 'totalTokens': 1864}, accumulated_metrics={'latencyMs': 17934}), state={}, interrupts=None, structured_output=None), execution_time=18270, status=<Status.COMPLETED: 'completed'>, accumulated_usage={'inputTokens': 944, 'outputTokens': 920, 'totalTokens': 1864}, accumulated_metrics={'latencyMs': 17934}, execution_count=1, interrupts=[])}, accumulated_usage={'inputTokens': 6258, 'outputTokens': 2811, 'totalTokens': 9069}, accumulated_metrics={'latencyMs': 52537}, execution_count=3, execution_time=53991, interrupts=[], node_history=[SwarmNode(node_id='哲学家_0'), SwarmNode(node_id='哲学家_1'), SwarmNode(node_id='哲学家_2')])
