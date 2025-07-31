# AWS 价格助手 Web 应用

这个应用将原有的 AWS 价格查询工具转换为网页版对话式界面，方便用户通过浏览器查询 AWS 服务价格信息。

## 功能特点

- 网页聊天界面，支持对话方式查询 AWS 价格
- 利用 AWS Bedrock 大语言模型提供自然语言交互
- 支持查询各种 AWS 服务价格信息
- 支持查询特定 EC2 实例类型的价格
- 支持比较不同实例类型的价格和性能
- 响应式设计，适配桌面和移动设备

## 安装说明

1. 确保已安装 Python 3.8 或更高版本
2. 安装所需依赖：

```bash
pip install -r requirements.txt
```

3. 确保已配置有效的 AWS 凭证（以下任一方式）：
   - 配置环境变量 `AWS_ACCESS_KEY_ID` 和 `AWS_SECRET_ACCESS_KEY`
   - 使用 AWS CLI 配置 (~/.aws/credentials)
   - 如果在 EC2 上运行，可使用 IAM 角色

4. 设置 AWS Bedrock 访问权限，确保有权限访问 Nova 模型

## 使用说明

1. 运行应用：

```bash
python aws_price_web.py
```

2. 在浏览器中访问 `http://localhost:8000` 即可打开 AWS 价格助手界面
3. 在聊天框中输入问题，例如：
   - "列出可用的 AWS 服务"
   - "列出美东一 g5.2xlarge g6.4xlarge 的 OD 和 Spot 价格"
   - "比较 us-east-1 和 us-west-2 的 t3.xlarge 实例价格"

## 示例查询

以下是一些可以尝试的示例查询：

- "列出所有可用的 AWS 服务"
- "列出 EC2 实例类型"
- "列出美东一 g5.2xlarge g6.4xlarge 的 OD 和 Spot 价格"
- "比较 t3.xlarge 和 m5.xlarge 的价格和性能"
- "查询 RDS MySQL 实例价格"

## 注意事项

- 由于 AWS 限制，某些价格查询可能需要较长时间响应
- 确保您的 AWS 凭证有足够权限访问 EC2 和 Pricing API
- 初次使用时，AWS Bedrock 模型加载可能需要一定时间