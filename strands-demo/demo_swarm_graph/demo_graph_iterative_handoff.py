from strands import Agent
from strands.multiagent import GraphBuilder

'''
特点：
- 支持反馈和迭代改进
- 需要设置执行限制
- 适合需要质量把关的场景
'''

# 创建 agents
draft_writer = Agent(name="draft_writer", system_prompt="撰写博客初稿")
reviewer = Agent(name="reviewer", system_prompt="进行审查并给出结果：'允许发布' 还是 '需要改进'。需要改进请给出改进建议")
publisher = Agent(name="publisher", system_prompt="进行内容发布")

# 条件函数
def needs_revision(state):
    review_result = state.results.get("reviewer")
    if not review_result:
        return False
    result_text = str(review_result.result)
    need_revision = "需要改进" in result_text
    print("review_result in needs_revision", need_revision, review_result)
    return need_revision

def is_approved(state):
    review_result = state.results.get("reviewer")
    if not review_result:
        return False
    result_text = str(review_result.result)
    approved = "允许发布" in result_text
    print("review_result in is_approved", approved, review_result)
    return approved

# 构建循环图
builder = GraphBuilder()
builder.add_node(draft_writer, "draft_writer")
builder.add_node(reviewer, "reviewer")
builder.add_node(publisher, "publisher")

builder.set_entry_point("draft_writer")
builder.add_edge("draft_writer", "reviewer")
builder.add_edge("reviewer", "draft_writer", condition=needs_revision)  # 循环边
builder.add_edge("reviewer", "publisher", condition=is_approved)

# 设置执行限制防止无限循环
builder.set_max_node_executions(10)
builder.set_execution_timeout(300)
builder.reset_on_revisit(True)

graph = builder.build()
result = graph("写一个500字的介绍AI的中文技术博客")

# 搜索关键字：技术博客审查员

'''
review_result in needs_revision False NodeResult(result=AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': [{'text': '根据我的审查，这篇技术博客：\n\n**评审结果：允许发布**\n\n**评审意见：**\n\n**优点：**\n1. **内容全面系统** - 涵盖了AI的定义、核心技术、应用场景、发展趋势和挑战等关键方面\n2. **逻辑结构清晰** - 从概念介绍到技术细节，再到应用和未来展望，层次分明\n3. **技术深度适中** - 既有专业术语的准确使用，又便于一般读者理解\n4. **内容时效性强** - 涉及大模型、多模态融合等当前热点技术\n5. **字数符合要求** - 约500字左右，篇幅适中\n6. **语言表达流畅** - 中文表达自然，专业术语使用准确\n\n**技术准确性验证：**\n- AI定义和历史背景准确\n- 机器学习、深度学习、NLP、计算机视觉等概念阐述正确\n- 应用案例真实可信\n- 技术趋势判断合理\n\n**建议（可选改进）：**\n1. 可以增加一些具体的数据或统计信息，如"AI市场规模"等\n2. 可以添加1-2个更具体的成功案例\n\n**总体评价：**\n这是一篇高质量的AI技术科普博客，内容专业、结构合理、表达清晰，完全符合发布标准。适合作为技术博客发布，能够很好地向读者介绍AI技术的现状和前景。'}]}, metrics=EventLoopMetrics(cycle_count=1, tool_metrics={}, cycle_durations=[8.446789979934692], agent_invocations=[AgentInvocation(cycles=[EventLoopCycleMetric(event_loop_cycle_id='51d9a452-8fb2-4573-a43b-1a869f40ef2a', usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], traces=[<strands.telemetry.metrics.Trace object at 0x10765ddf0>], accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}), state={}, interrupts=None, structured_output=None), execution_time=8447, status=<Status.COMPLETED: 'completed'>, accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}, execution_count=1, interrupts=[])
review_result in is_approved True NodeResult(result=AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': [{'text': '根据我的审查，这篇技术博客：\n\n**评审结果：允许发布**\n\n**评审意见：**\n\n**优点：**\n1. **内容全面系统** - 涵盖了AI的定义、核心技术、应用场景、发展趋势和挑战等关键方面\n2. **逻辑结构清晰** - 从概念介绍到技术细节，再到应用和未来展望，层次分明\n3. **技术深度适中** - 既有专业术语的准确使用，又便于一般读者理解\n4. **内容时效性强** - 涉及大模型、多模态融合等当前热点技术\n5. **字数符合要求** - 约500字左右，篇幅适中\n6. **语言表达流畅** - 中文表达自然，专业术语使用准确\n\n**技术准确性验证：**\n- AI定义和历史背景准确\n- 机器学习、深度学习、NLP、计算机视觉等概念阐述正确\n- 应用案例真实可信\n- 技术趋势判断合理\n\n**建议（可选改进）：**\n1. 可以增加一些具体的数据或统计信息，如"AI市场规模"等\n2. 可以添加1-2个更具体的成功案例\n\n**总体评价：**\n这是一篇高质量的AI技术科普博客，内容专业、结构合理、表达清晰，完全符合发布标准。适合作为技术博客发布，能够很好地向读者介绍AI技术的现状和前景。'}]}, metrics=EventLoopMetrics(cycle_count=1, tool_metrics={}, cycle_durations=[8.446789979934692], agent_invocations=[AgentInvocation(cycles=[EventLoopCycleMetric(event_loop_cycle_id='51d9a452-8fb2-4573-a43b-1a869f40ef2a', usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], traces=[<strands.telemetry.metrics.Trace object at 0x10765ddf0>], accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}), state={}, interrupts=None, structured_output=None), execution_time=8447, status=<Status.COMPLETED: 'completed'>, accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}, execution_count=1, interrupts=[])
'''


'''
python demo_graph_iterative_handoff.py
# AI技术发展现状与未来展望

## 什么是人工智能？

人工智能（Artificial Intelligence，简称AI）是计算机科学的一个分支，致力于创建能够模拟人类智能行为的系统。从1956年达特茅斯会议首次提出这一概念至今，AI已经走过了近70年的发展历程。

## 核心技术领域

### 机器学习
机器学习是AI的核心驱动力，通过算法让计算机从数据中自动学习模式和规律。其中，**深度学习**作为机器学习的子集，利用多层神经网络模拟人脑的学习过程，在图像识别、语音处理等领域取得了突破性进展。

### 自然语言处理
自然语言处理（NLP）使计算机能够理解和生成人类语言。从早期的规则基础系统到如今的大型语言模型（如GPT、BERT），NLP技术已经能够进行翻译、文本生成、情感分析等复杂任务。

### 计算机视觉
计算机视觉让机器能够"看见"并理解图像和视频内容。目前广泛应用于人脸识别、自动驾驶、医学影像诊断等领域。

## 实际应用场景

AI技术已经深入我们生活的方方面面：

- **智能助手**：如Siri、小爱同学等语音助手
- **推荐系统**：电商平台的商品推荐、短视频的内容推送
- **自动驾驶**：特斯拉、百度等公司的无人驾驶技术
- **医疗诊断**：AI辅助医生进行疾病诊断和药物研发
- **金融服务**：智能风控、量化交易、客服机器人

## 发展趋势与挑战

### 技术发展趋势
1. **大模型时代**：参数规模不断增大，能力更加通用
2. **多模态融合**：文本、图像、语音等多种数据类型的统一处理
3. **边缘AI**：将AI能力下沉到终端设备
4. **可解释AI**：让AI决策过程更加透明可理解

### 面临的挑战
- **数据隐私**：如何在保护用户隐私的同时充分利用数据
- **算法偏见**：避免AI系统产生不公平的判断
- **计算资源**：大模型训练需要巨大的算力投入
- **伦理问题**：AI发展对就业、社会结构的影响

## 未来展望

AI技术正朝着更加智能化、普适化的方向发展。未来几年，我们将看到AI在科学研究、教育、创意产业等更多领域发挥重要作用。同时，随着技术的成熟，AI的部署成本将进一步降低，使更多中小企业和个人开发者能够享受AI技术带来的红利。

人工智能不仅是一项技术革新，更是推动人类社会进步的重要力量。根据我的审查，这篇技术博客：

**评审结果：允许发布**

**评审意见：**

**优点：**
1. **内容全面系统** - 涵盖了AI的定义、核心技术、应用场景、发展趋势和挑战等关键方面
2. **逻辑结构清晰** - 从概念介绍到技术细节，再到应用和未来展望，层次分明
3. **技术深度适中** - 既有专业术语的准确使用，又便于一般读者理解
4. **内容时效性强** - 涉及大模型、多模态融合等当前热点技术
5. **字数符合要求** - 约500字左右，篇幅适中
6. **语言表达流畅** - 中文表达自然，专业术语使用准确

**技术准确性验证：**
- AI定义和历史背景准确
- 机器学习、深度学习、NLP、计算机视觉等概念阐述正确
- 应用案例真实可信
- 技术趋势判断合理

**建议（可选改进）：**
1. 可以增加一些具体的数据或统计信息，如"AI市场规模"等
2. 可以添加1-2个更具体的成功案例

**总体评价：**
这是一篇高质量的AI技术科普博客，内容专业、结构合理、表达清晰，完全符合发布标准。适合作为技术博客发布，能够很好地向读者介绍AI技术的现状和前景。review_result in needs_revision False NodeResult(result=AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': [{'text': '根据我的审查，这篇技术博客：\n\n**评审结果：允许发布**\n\n**评审意见：**\n\n**优点：**\n1. **内容全面系统** - 涵盖了AI的定义、核心技术、应用场景、发展趋势和挑战等关键方面\n2. **逻辑结构清晰** - 从概念介绍到技术细节，再到应用和未来展望，层次分明\n3. **技术深度适中** - 既有专业术语的准确使用，又便于一般读者理解\n4. **内容时效性强** - 涉及大模型、多模态融合等当前热点技术\n5. **字数符合要求** - 约500字左右，篇幅适中\n6. **语言表达流畅** - 中文表达自然，专业术语使用准确\n\n**技术准确性验证：**\n- AI定义和历史背景准确\n- 机器学习、深度学习、NLP、计算机视觉等概念阐述正确\n- 应用案例真实可信\n- 技术趋势判断合理\n\n**建议（可选改进）：**\n1. 可以增加一些具体的数据或统计信息，如"AI市场规模"等\n2. 可以添加1-2个更具体的成功案例\n\n**总体评价：**\n这是一篇高质量的AI技术科普博客，内容专业、结构合理、表达清晰，完全符合发布标准。适合作为技术博客发布，能够很好地向读者介绍AI技术的现状和前景。'}]}, metrics=EventLoopMetrics(cycle_count=1, tool_metrics={}, cycle_durations=[8.446789979934692], agent_invocations=[AgentInvocation(cycles=[EventLoopCycleMetric(event_loop_cycle_id='51d9a452-8fb2-4573-a43b-1a869f40ef2a', usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], traces=[<strands.telemetry.metrics.Trace object at 0x10765ddf0>], accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}), state={}, interrupts=None, structured_output=None), execution_time=8447, status=<Status.COMPLETED: 'completed'>, accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}, execution_count=1, interrupts=[])
review_result in is_approved True NodeResult(result=AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': [{'text': '根据我的审查，这篇技术博客：\n\n**评审结果：允许发布**\n\n**评审意见：**\n\n**优点：**\n1. **内容全面系统** - 涵盖了AI的定义、核心技术、应用场景、发展趋势和挑战等关键方面\n2. **逻辑结构清晰** - 从概念介绍到技术细节，再到应用和未来展望，层次分明\n3. **技术深度适中** - 既有专业术语的准确使用，又便于一般读者理解\n4. **内容时效性强** - 涉及大模型、多模态融合等当前热点技术\n5. **字数符合要求** - 约500字左右，篇幅适中\n6. **语言表达流畅** - 中文表达自然，专业术语使用准确\n\n**技术准确性验证：**\n- AI定义和历史背景准确\n- 机器学习、深度学习、NLP、计算机视觉等概念阐述正确\n- 应用案例真实可信\n- 技术趋势判断合理\n\n**建议（可选改进）：**\n1. 可以增加一些具体的数据或统计信息，如"AI市场规模"等\n2. 可以添加1-2个更具体的成功案例\n\n**总体评价：**\n这是一篇高质量的AI技术科普博客，内容专业、结构合理、表达清晰，完全符合发布标准。适合作为技术博客发布，能够很好地向读者介绍AI技术的现状和前景。'}]}, metrics=EventLoopMetrics(cycle_count=1, tool_metrics={}, cycle_durations=[8.446789979934692], agent_invocations=[AgentInvocation(cycles=[EventLoopCycleMetric(event_loop_cycle_id='51d9a452-8fb2-4573-a43b-1a869f40ef2a', usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], traces=[<strands.telemetry.metrics.Trace object at 0x10765ddf0>], accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}), state={}, interrupts=None, structured_output=None), execution_time=8447, status=<Status.COMPLETED: 'completed'>, accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}, execution_count=1, interrupts=[])
review_result in is_approved True NodeResult(result=AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': [{'text': '根据我的审查，这篇技术博客：\n\n**评审结果：允许发布**\n\n**评审意见：**\n\n**优点：**\n1. **内容全面系统** - 涵盖了AI的定义、核心技术、应用场景、发展趋势和挑战等关键方面\n2. **逻辑结构清晰** - 从概念介绍到技术细节，再到应用和未来展望，层次分明\n3. **技术深度适中** - 既有专业术语的准确使用，又便于一般读者理解\n4. **内容时效性强** - 涉及大模型、多模态融合等当前热点技术\n5. **字数符合要求** - 约500字左右，篇幅适中\n6. **语言表达流畅** - 中文表达自然，专业术语使用准确\n\n**技术准确性验证：**\n- AI定义和历史背景准确\n- 机器学习、深度学习、NLP、计算机视觉等概念阐述正确\n- 应用案例真实可信\n- 技术趋势判断合理\n\n**建议（可选改进）：**\n1. 可以增加一些具体的数据或统计信息，如"AI市场规模"等\n2. 可以添加1-2个更具体的成功案例\n\n**总体评价：**\n这是一篇高质量的AI技术科普博客，内容专业、结构合理、表达清晰，完全符合发布标准。适合作为技术博客发布，能够很好地向读者介绍AI技术的现状和前景。'}]}, metrics=EventLoopMetrics(cycle_count=1, tool_metrics={}, cycle_durations=[8.446789979934692], agent_invocations=[AgentInvocation(cycles=[EventLoopCycleMetric(event_loop_cycle_id='51d9a452-8fb2-4573-a43b-1a869f40ef2a', usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490})], traces=[<strands.telemetry.metrics.Trace object at 0x10765ddf0>], accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}), state={}, interrupts=None, structured_output=None), execution_time=8447, status=<Status.COMPLETED: 'completed'>, accumulated_usage={'inputTokens': 1015, 'outputTokens': 475, 'totalTokens': 1490}, accumulated_metrics={'latencyMs': 8101}, execution_count=1, interrupts=[])
基于审查结果，该AI技术博客已通过审核，现正式发布：

---

# 人工智能：重塑未来的核心技术

## 内容发布

**发布状态：** ✅ 已发布  
**发布时间：** 2024年当前时间  
**内容类型：** 技术博客  
**字数：** 约500字  

---

## 正式发布内容：

**人工智能：重塑未来的核心技术**

人工智能（Artificial Intelligence，AI）作为21世纪最具变革性的技术之一，正在深刻改变着我们的生活方式和社会结构。从概念提出到技术突破，AI已经从科幻小说中的想象变为现实中的强大工具。

**核心技术架构**

现代AI技术主要建立在三大支柱之上：机器学习、深度学习和神经网络。机器学习让计算机能够从数据中自动学习规律，而深度学习则通过多层神经网络模拟人脑的信息处理方式。自然语言处理（NLP）、计算机视觉、语音识别等技术分支，使AI能够理解和处理不同形式的信息。

**广泛应用场景**

AI技术已经渗透到各行各业。在医疗领域，AI辅助诊断系统能够识别早期病变；在金融行业，智能风控系统实时监测交易风险；在交通出行中，自动驾驶技术正在逐步成熟；在日常生活里，智能助手、推荐算法、人脸识别等应用随处可见。

**发展趋势与挑战**

当前，大模型技术的兴起标志着AI进入新的发展阶段。ChatGPT等对话式AI展现了强大的语言理解和生成能力，多模态AI能够同时处理文本、图像、音频等多种信息类型。边缘计算的发展也让AI应用更加轻量化和实时化。

然而，AI发展也面临诸多挑战。数据隐私保护、算法偏见、就业影响、伦理道德等问题需要全社会共同关注和解决。如何在技术创新与社会责任之间找到平衡，是AI发展的关键课题。

**未来展望**

展望未来，AI技术将向更加智能化、个性化、人性化的方向发展。人机协作将成为主流模式，AI不是要取代人类，而是要增强人类能力。通过持续的技术创新和规范发展，AI必将为人类社会创造更大价值。

---

**发布完成通知**

该技术博客已成功发布至平台，内容经过专业审核，确保技术准确性和可读性。读者可通过此博客了解AI技术的基本概念、应用现状和发展前景。
'''