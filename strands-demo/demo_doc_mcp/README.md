# SA Helper - AI 助手平台

基于 FastAPI 的 Web 应用程序，使用 AWS Bedrock 和 Strands agents 框架提供 AI 助手平台。具有多角色聊天界面，用户可以与针对不同用途配置的 AI 代理进行交互。

## 功能特性

- **多角色 AI 助手**：预配置的 AWS 解决方案架构师、PPT 分析师和自由对话角色
- **MCP 集成**：模型上下文协议支持外部工具访问（AWS 文档、HTTP 请求、时间）
- **持久化会话**：基于文件的会话管理，自动对话摘要
- **流式响应**：使用服务器发送事件（SSE）的实时流式聊天
- **多模态支持**：支持图像输入（PNG/JPEG）用于视觉交互
- **角色自定义**：每个角色可配置系统提示词和 MCP 工具访问

## 架构说明

### 技术栈

- **后端**：FastAPI 0.117.1, Uvicorn 0.36.0
- **AI 框架**：Strands 0.1.0
- **AI 模型**：AWS Bedrock Claude Sonnet 4 (`apac.anthropic.claude-sonnet-4-20250514-v1:0`)
- **会话存储**：文件存储，自动摘要
- **前端**：静态 HTML/CSS/JS，Bootstrap 5

### 核心组件

- `mcp_web.py`：主 FastAPI 应用程序，包含流式聊天端点
- `role_config.py`：角色和 MCP 配置管理
- `templates/index.html`：带角色选择的聊天界面
- `static/`：前端资源文件（CSS、JavaScript）
- `sessions/`：持久化会话存储（自动创建）

## 环境要求

- Python 3.8+
- AWS 账户，开通 Bedrock 访问权限
- 配置有效的 AWS 凭证
- 必需的环境变量

## 安装步骤

1. **进入项目目录**
   ```bash
   cd demo_sa_helper
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   ```bash
   export VALID_TOKEN="your-secure-token-here"
   ```

4. **配置 AWS 凭证**

   确保 AWS 凭证可通过以下方式之一获取：
   - 环境变量（`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`）
   - AWS 凭证文件（`~/.aws/credentials`）
   - IAM 角色（用于 EC2/ECS/Lamda 部署）

   使用区域：`ap-northeast-1`

## 使用说明

### 启动服务器

```bash
python mcp_web.py
```

服务器运行在：`http://0.0.0.0:9000`

### 访问应用

浏览器访问：
```
http://localhost:9000?token=your-secure-token-here
```

**注意**：所有请求都需要 token 认证。

### 可用角色

1. **AWS 架构师** (`aws_architect`)
   - AWS 解决方案架构咨询
   - 通过 MCP 访问 AWS 文档
   - 中文回复

2. **PPT 阅读器** (`ppt_reader`)
   - 游戏架构 PPT 分析
   - 文档分析能力

3. **自由对话** (`free_talk`)
   - 通用对话助手
   - 灵活的讨论主题

## API 接口

### 聊天端点

**POST** `/api/chat_stream`

使用服务器发送事件（SSE）的流式聊天端点。

**请求体：**
```json
{
  "message": "你的问题",
  "session_id": "可选的会话UUID",
  "role_id": "aws_architect",
  "custom_prompt": "可选的自定义系统提示词",
  "enabled_mcps": ["aws_docs", "http_request"],
  "image": {
    "data": "base64编码的图像数据",
    "format": "png"
  }
}
```

**响应事件：**
- `session_created`：新会话已初始化
- `response`：AI 响应内容块
- `status`：工具使用状态更新
- `heartbeat`：保活信号
- `complete`：响应完成
- `error`：发生错误

### 角色管理

**POST** `/api/roles`
- 获取所有可用角色

**POST** `/api/roles/{role_id}`
- 获取特定角色配置

**POST** `/api/mcps`
- 获取所有可用的 MCP 配置

## 配置说明

### 添加新角色

编辑 [role_config.py](role_config.py)：

```python
ROLES = {
    "custom_role": RoleConfig(
        id="custom_role",
        name="自定义角色名称",
        icon="bi-star",
        system_prompt="你的自定义系统提示词...",
        mcp_configs=["aws_docs", "http_request"],
        description="角色描述",
        is_editable=True
    )
}
```

### 添加 MCP 服务器

编辑 [role_config.py](role_config.py) 中的 `_init_mcp_configs()` 方法：

```python
"custom_mcp": MCPConfig(
    id="custom_mcp",
    name="自定义 MCP",
    url="https://your-mcp-server.com",
    description="自定义 MCP 描述"
)
```

## 会话管理

- 会话自动创建并持久化到 `sessions/` 目录
- 每个会话有唯一的 UUID
- 当上下文增长过大时，对话历史会自动摘要
- 保留最近 6 条消息 + 30% 的旧内容摘要
- 可通过在请求中提供 `session_id` 恢复会话

## 安全说明

- **Token 认证**：所有请求都需要通过查询参数提供有效 token
- **基于环境变量的安全性**：Token 通过环境变量配置
- **无默认凭证**：应用程序需要显式配置

## 故障排除

### 认证错误（HTTP 504）

- 检查 `VALID_TOKEN` 环境变量是否已设置
- 确保 URL 中的 token 与环境变量匹配
- 检查查询参数格式：`?token=your-token`

### AWS Bedrock 错误

- 检查 AWS 凭证是否正确配置
- 确保 IAM 权限包含 Bedrock 访问权限
- 检查区域配置（默认：`ap-northeast-1`）

### MCP 连接问题

- 检查到 MCP 服务器的网络连接
- 验证 [role_config.py](role_config.py) 中的 MCP 服务器 URL
- 查看应用程序日志以获取详细错误信息

## 开发说明

### 项目结构

```
sa_helper/
├── mcp_web.py              # 主 FastAPI 应用程序
├── role_config.py          # 角色和 MCP 配置
├── requirements.txt        # Python 依赖
├── templates/
│   └── index.html         # 聊天界面
├── static/
│   ├── style.css          # 自定义样式
│   └── app.js             # 前端逻辑
└── sessions/              # 会话存储（自动创建）
```

### 调试端点

**GET** `/debug/routes`
- 查看所有注册的路由及其详细信息

## 许可证

[在此添加许可证信息]

## 贡献

[在此添加贡献指南]

## 支持

如有问题，请参阅项目文档或联系维护者。
