# Agentic Search — 无需向量数据库的智能文档与代码搜索

基于论文 [Keyword search is all you need (arXiv:2602.23368)](https://arxiv.org/abs/2602.23368) 实现，使用 [Strands Agents SDK](https://strandsagents.com/) 构建。

## 核心思想

传统 RAG 需要维护向量数据库和 embedding 管线。本项目证明：**一个具备关键词搜索工具的 LLM Agent，通过多轮迭代检索，可以达到 RAG 90%+ 的效果**，且无需任何向量数据库。同时扩展支持代码文件搜索，可对 PHP、Python、JS 等代码库进行结构感知的检索。

```
┌─────────┐     ┌──────────────────────────────────────┐     ┌──────────┐
│  用户问题 │ ──▶ │  ReAct Agent Loop (思考→搜索→观察)     │ ──▶ │  最终答案  │
└─────────┘     │  ┌──────────┐  ┌──────────┐          │     └──────────┘
                │  │ 元数据分析 │→│ 广泛搜索  │→ ...     │
                │  └──────────┘  └──────────┘          │
                │  ┌──────────┐  ┌──────────┐          │
                │  │代码/精确搜│→│ 上下文提取│→ 综合     │
                │  └──────────┘  └──────────┘          │
                └──────────────────────────────────────┘
```

## 项目结构

```
agentic_search/
├── agent.py           # Agent 主程序 + CLI 入口
├── tools.py           # 6 个搜索工具 + token 优化
├── test_search.py     # 测试套件（14 项测试）
├── requirements.txt   # 依赖
├── files/             # 📂 放入待搜索的文档和代码
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install strands-agents strands-agents-tools PyPDF2
```

### 2. 配置 AWS 凭证

默认使用 Amazon Bedrock 上的 Claude Sonnet 模型：

```bash
# 方式一：环境变量
export AWS_ACCESS_KEY_ID=<your-key>
export AWS_SECRET_ACCESS_KEY=<your-secret>
export AWS_DEFAULT_REGION=us-west-2

# 方式二：AWS CLI
aws configure
```

确保在 Bedrock 控制台中已开启 Claude Sonnet 模型的访问权限。

### 3. 放入文件

将需要搜索的文档或代码放入 `files/` 目录（支持子目录，会递归扫描）：

```bash
# 文档
cp ~/my-documents/*.pdf ./files/

# 代码项目
cp -r ~/my-php-project/src ./files/src
```

### 4. 运行

```bash
# 交互模式
python agent.py ./files

# 示例：文档问答
Q: What are the main components of Hyperledger Fabric?

# 示例：代码搜索
Q: 找到所有 PHP 中处理用户认证的函数
```

### 5. 代码调用

```python
from agent import create_agent, ask

agent = create_agent()

# 文档问答
answer = ask(agent, "论文的主要结论是什么？", "./files")

# 代码搜索
answer = ask(agent, "AuthService 类的 authenticate 方法是怎么实现的？", "./files")
```

## 搜索工具说明

Agent 拥有 6 个工具，按工作流分为三层：

### 第一层：发现

| 工具 | 用途 |
|------|------|
| `file_metadata` | 递归扫描文件夹，列出文件名、大小、PDF 页数、代码行数。**必须首先调用** |

### 第二层：搜索

| 工具 | 用途 |
|------|------|
| `keyword_search` | 跨文件关键词/正则搜索，支持 OR 模式（`keyword1\|keyword2`）和 `file_ext` 过滤 |
| `code_search` | 代码结构感知搜索，`definitions_only=True` 时只返回函数/类定义 |
| `pdf_page_search` | 指定 PDF 页码范围的精确搜索 |

### 第三层：提取上下文

| 工具 | 用途 |
|------|------|
| `extract_page_text` | 提取 PDF 指定页的完整文本 |
| `read_file_lines` | 按行号范围读取代码/文本文件 |

### 支持的文件类型

| 类别 | 扩展名 |
|------|--------|
| 代码 | `.php` `.py` `.js` `.ts` `.jsx` `.tsx` `.java` `.go` `.rb` `.rs` `.c` `.cpp` `.h` `.hpp` `.cs` `.swift` `.kt` `.scala` `.sh` `.sql` `.html` `.css` `.scss` `.vue` `.svelte` `.lua` `.pl` `.r` |
| 文本 | `.txt` `.md` `.csv` `.json` `.xml` `.yaml` `.yml` `.toml` `.ini` `.cfg` `.conf` `.log` |
| 文档 | `.pdf`（通过 PyPDF2 解析） |

搜索命令优先级：`rga` → `grep -rE` → 纯 Python fallback，确保在任何环境下都能运行。

### 代码定义模式识别

`code_search` 的 `definitions_only` 模式内置了 10 种语言的定义模式：

| 语言 | 识别的定义 |
|------|-----------|
| PHP | `function`, `class`, `interface`, `trait`, `namespace` |
| Python | `def`, `class`, `import`, `from` |
| JS/TS | `function`, `class`, `interface`, `type`, `const =`, `export` |
| Java | `class`, `interface`, `public/private` 方法 |
| Go | `func`, `type struct`, `type interface` |
| Ruby | `def`, `class`, `module` |
| Rust | `fn`, `struct`, `impl`, `trait`, `enum` |
| C/C++ | 函数定义, `struct`, `typedef`, `class`, `namespace` |

## Token 优化机制

论文的一个关键挑战是 LLM 的 context window 限制。本项目实现了多层 token 优化：

| 策略 | 配置 | 说明 |
|------|------|------|
| 单次结果截断 | `MAX_CONTEXT_CHARS = 4000` | 每次搜索结果上限 ~1000 tokens |
| 总量预算控制 | `MAX_TOTAL_CHARS = 12000` | 所有结果总量上限 ~3000 tokens |
| 上下文窗口 | `CONTEXT_LINES = 3` | 每个匹配只返回前后 3 行 |
| 智能截断 | `_truncate()` | 在句子边界截断，保持语义完整 |
| 实时预算检查 | 搜索过程中 | 累计字符数超限即停止，附加截断标记 |

可在 `tools.py` 顶部修改这些参数：

```python
MAX_CONTEXT_CHARS = 4000   # 调大 = 更多上下文，更多 token 消耗
MAX_TOTAL_CHARS = 12000    # 调大 = 允许更多搜索结果
CONTEXT_LINES = 3          # 调大 = 每个匹配返回更多周围行
```

## Agent 多轮搜索流程

Agent 遵循 ReAct (Reasoning + Acting) 模式。以下是两个典型场景：

### 场景一：文档问答

```
Step 1: file_metadata("./files")
        → 发现 blockchain.pdf (42 pages), report.md (120 lines)

Step 2: keyword_search("./files", "Hyperledger|Fabric|component")
        → 定位到 blockchain.pdf 第 14 页有相关内容

Step 3: pdf_page_search("./files/blockchain.pdf", "component", 14, 16)
        → 获取精确的页面内容

Step 4: 综合结果，生成带引用的答案
```

### 场景二：代码搜索

```
Step 1: file_metadata("./files")
        → 发现 src/UserController.php (42 lines), src/AuthService.php (35 lines)

Step 2: code_search("./files", "authenticate", file_ext="php", definitions_only=True)
        → 找到 AuthService.php:17 的函数定义

Step 3: read_file_lines("./files/src/AuthService.php", 15, 35)
        → 读取完整的函数实现

Step 4: keyword_search("./files", "authenticate", file_ext="php")
        → 查找所有调用点

Step 5: 综合结果，解释认证流程
```

如果某一步搜索失败，Agent 会自动：
- 尝试不同的关键词/同义词
- 将复杂查询拆分为简单查询
- 切换搜索工具（如从 `keyword_search` 切到 `code_search`）

## 自定义模型

```python
from agent import create_agent

agent = create_agent(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    temperature=0.001,
    max_tokens=4096,
)
```

## 运行测试

```bash
# 单元测试（无需 AWS 凭证，14 项测试）
python test_search.py

# 包含 Agent 集成测试（需要 Bedrock 访问）
python test_search.py --agent
```

测试覆盖：
- ✅ Token 截断逻辑（句子边界、长度限制）
- ✅ 文件元数据列举（递归子目录、代码类型识别、行数统计）
- ✅ 单关键词搜索 / OR 模式搜索 / 无匹配处理
- ✅ 指定文件搜索 / `file_ext` 扩展名过滤
- ✅ PHP 代码搜索（函数、类、`definitions_only` 模式）
- ✅ 按行号范围读取代码文件
- ✅ Token 预算强制执行
- ✅ Agent 端到端问答（多轮工具调用 + 答案验证）

## 可选：安装 rga 提升搜索能力

[ripgrep-all](https://github.com/phiresky/ripgrep-all) 可以搜索 PDF、Word、ZIP 等多种格式内的文本：

```bash
# macOS
brew install ripgrep-all

# Linux
apt install ripgrep-all
```

未安装时系统会自动 fallback 到 `grep` 或纯 Python 搜索，功能不受影响。

## 参考

- 论文：[Keyword search is all you need: Achieving RAG-Level Performance without vector databases using agentic tool use](https://arxiv.org/abs/2602.23368) (Subramanian et al., 2025)
- SDK：[Strands Agents SDK](https://strandsagents.com/)
- 模型：[Amazon Bedrock - Claude](https://docs.aws.amazon.com/bedrock/latest/userguide/)
