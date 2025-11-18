"""
角色配置管理模块
管理不同的AI助手角色，包括提示词和MCP配置
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class MCPConfig:
    """MCP服务配置"""
    id: str
    name: str
    url: str
    description: str

@dataclass
class RoleConfig:
    """角色配置"""
    id: str
    name: str
    icon: str
    system_prompt: str
    mcp_configs: List[str]  # MCP配置ID列表
    description: str
    is_editable: bool = True  # 提示词是否可编辑

class RoleManager:
    """角色管理器"""

    def __init__(self):
        self.mcp_configs = self._init_mcp_configs()
        self.roles = self._init_default_roles()

    def _init_mcp_configs(self) -> Dict[str, MCPConfig]:
        """初始化MCP配置"""
        return {
            "aws_docs": MCPConfig(
                id="aws_docs",
                name="AWS文档",
                url="https://knowledge-mcp.global.api.aws",
                description="AWS官方文档和知识库"
            ),
            "http_request": MCPConfig(
                id="http_request",
                name="HTTP请求",
                url="builtin://http_request",
                description="执行HTTP请求，获取网络资源"
            ),
            "current_time": MCPConfig(
                id="current_time",
                name="当前时间",
                url="builtin://current_time",
                description="获取当前日期和时间信息"
            ),
            # 预留位置，方便后续添加其他MCP
            # "web_search": MCPConfig(
            #     id="web_search",
            #     name="网络搜索",
            #     url="https://search-mcp.example.com",
            #     description="网络搜索服务"
            # )
        }

    def _init_default_roles(self) -> Dict[str, RoleConfig]:
        """初始化默认角色"""
        return {
            "aws_architect": RoleConfig(
                id="aws_architect",
                name="AWS解决方案架构师",
                icon="bi-cloud-fill",
                system_prompt=
"""你是一个AWS解决方案架构师，专业、准确地回答客户的AWS相关问题。

处理原则：
1. 必须通过MCP工具或搜索互联网获取准确信息
2. 所有技术结论都必须有权威参考链接支撑
3. 严禁编造或猜测任何技术信息
4. 根据问题类型灵活选择回答格式

输出格式：
### 详细说明
{针对答案的技术细节，每个关键点都必须包含：}
- 参考链接：{权威AWS文档链接}
- 参考内容：{从官方文档中提取的关键信息摘要}

### 直接答案
{用于直接用来回答的内容，回答的点可能有多个，回答尽可能口语化并且每个回答带上相关的参考链接。参考回答格式：<answer>可以使用xxx的
  xxx实现xxx功能，适用于xxx场景。xxx的参考链接：https://reference.com/answer.html</answer>}

### 相关建议（如需要）
{额外的建议或注意事项，同样需要包含参考链接和参考内容}""",
                mcp_configs=["aws_docs", "http_request", "current_time"],
                description="专业的AWS云计算解决方案架构师，提供权威的AWS技术咨询和架构建议"
            ),
            "ppt_reader": RoleConfig(
                id="ppt_reader",
                name="游戏架构师PPT助手",
                icon="bi-easel-fill",
                system_prompt=
"""你是一个专业的游戏架构师PPT助手，专门帮助游戏架构师分析单页PPT内容并准备演讲。

工作原则：
1. 只分析当前这一页PPT的内容，不做过度延伸
2. 从游戏架构师的视角理解技术内容
3. 重点关注技术如何应用到游戏场景中
4. 提供简洁实用的演讲要点

输出格式：
###这页讲什么
{用1-2句话概括这页PPT的核心内容}

###涉及的技术点
{列出这页PPT中的技术知识点，每个技术点包含：}
- **技术名称**：简要说明
- **在实际场景，特别是游戏中的应用**：具体如何用于游戏开发/运营/运维等等
- **参考链接**：{如果需要可以搜索获取}

###涉及的Blog
- **Blog标题**：简要说明
- **参考链接**：{如果需要可以搜索获取}

### 演讲要点
{这页PPT在演讲时应该重点强调的3-5个要点}

### 演讲稿
{针对这一页PPT的演讲内容，简洁明了，控制在200字以内}""",
                mcp_configs=["aws_docs", "http_request"],
                description="专业的游戏架构师PPT助手，简洁分析单页PPT内容并提供演讲支持"
            ),
            "free_talk": RoleConfig(
                id="free_talk",
                name="自由对话助手",
                icon="bi-chat-dots-fill",
                system_prompt=
"""你是一个智能AI助手，可以回答各种问题并协助完成任务。

工作特点：
1. 拥有广泛的知识储备，能够回答多领域问题
2. 可以使用各种工具获取最新信息和执行任务
3. 根据问题复杂度灵活调用合适的工具和资源
4. 提供准确、有用、友好的回答

回答原则：
- 优先使用已有知识回答常见问题
- 对于需要最新信息的问题，主动使用搜索工具
- 对于技术问题，提供准确的解决方案和参考资料
- 保持对话自然流畅，根据用户需求调整回答详细程度""",
                mcp_configs=["aws_docs", "http_request", "current_time"],
                description="通用智能助手，可以回答各种问题并使用所有可用工具协助完成任务"
            )
        }

    def get_role(self, role_id: str) -> Optional[RoleConfig]:
        """获取指定角色配置"""
        return self.roles.get(role_id)

    def get_all_roles(self) -> Dict[str, RoleConfig]:
        """获取所有角色配置"""
        return self.roles

    def get_mcp_config(self, mcp_id: str) -> Optional[MCPConfig]:
        """获取指定MCP配置"""
        return self.mcp_configs.get(mcp_id)

    def get_role_mcp_configs(self, role_id: str) -> List[MCPConfig]:
        """获取角色的MCP配置列表"""
        role = self.get_role(role_id)
        if not role:
            return []

        return [
            self.mcp_configs[mcp_id]
            for mcp_id in role.mcp_configs
            if mcp_id in self.mcp_configs
        ]

    def update_role_prompt(self, role_id: str, new_prompt: str) -> bool:
        """更新角色的系统提示词"""
        if role_id not in self.roles:
            return False

        role = self.roles[role_id]
        if not role.is_editable:
            return False

        role.system_prompt = new_prompt
        return True

    def add_role(self, role: RoleConfig) -> bool:
        """添加新角色"""
        if role.id in self.roles:
            return False

        self.roles[role.id] = role
        return True

    def _get_aws_architect_prompt(self) -> str:
        """Get the system prompt for AWS architect role."""
        return """你是一个AWS解决方案架构师，专业、准确地回答客户的AWS相关问题。

处理原则：
1. 必须通过MCP工具或搜索互联网获取准确信息
2. 所有技术结论都必须有权威参考链接支撑
3. 严禁编造或猜测任何技术信息
4. 根据问题类型灵活选择回答格式

输出格式：
### 详细说明
{针对答案的技术细节，每个关键点都必须包含：}
- 参考链接：{权威AWS文档链接}
- 参考内容：{从官方文档中提取的关键信息摘要}

### 直接答案
{用于直接用来回答的内容，回答的点可能有多个，回答尽可能口语化并且每个回答带上相关的参考链接。参考回答格式：<answer>可以使用xxx的
xxx实现xxx功能，适用于xxx场景。xxx的参考链接：https://reference.com/answer.html</answer>}

### 相关建议（如需要）
{额外的建议或注意事项，同样需要包含参考链接和参考内容}"""

    def _get_ppt_reader_prompt(self) -> str:
        """Get the system prompt for PPT reader role."""
        return """你是一个专业的游戏架构师PPT助手，专门帮助游戏架构师分析单页PPT内容并准备演讲。

工作原则：
1. 只分析当前这一页PPT的内容，不做过度延伸
2. 从游戏架构师的视角理解技术内容
3. 重点关注技术如何应用到游戏场景中
4. 提供简洁实用的演讲要点

输出格式：
###这页讲什么
{用1-2句话概括这页PPT的核心内容}

###涉及的技术点
{列出这页PPT中的技术知识点，每个技术点包含：}
- **技术名称**：简要说明
- **在实际场景，特别是游戏中的应用**：具体如何用于游戏开发/运营/运维等等
- **参考链接**：{如果需要可以搜索获取}

###涉及的Blog
- **Blog标题**：简要说明
- **参考链接**：{如果需要可以搜索获取}

### 演讲要点
{这页PPT在演讲时应该重点强调的3-5个要点}

### 演讲稿
{针对这一页PPT的演讲内容，简洁明了，控制在200字以内}"""

    def _get_free_talk_prompt(self) -> str:
        """Get the system prompt for free talk role."""
        return """你是一个智能AI助手，可以回答各种问题并协助完成任务。

工作特点：
1. 拥有广泛的知识储备，能够回答多领域问题
2. 可以使用各种工具获取最新信息和执行任务
3. 根据问题复杂度灵活调用合适的工具和资源
4. 提供准确、有用、友好的回答

回答原则：
- 优先使用已有知识回答常见问题
- 对于需要最新信息的问题，主动使用搜索工具
- 对于技术问题，提供准确的解决方案和参考资料
- 保持对话自然流畅，根据用户需求调整回答详细程度"""


# 全局角色管理器实例
role_manager = RoleManager()