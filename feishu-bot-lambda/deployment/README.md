# 飞书机器人系统部署指南

本文档介绍如何部署飞书机器人系统到AWS云环境。

## 前置要求

### 1. AWS环境准备

- AWS账户和适当的IAM权限
- AWS CLI已配置
- Python 3.9+ 环境
- 安装必要的Python包：`pip install boto3 requests`

### 2. 飞书应用准备

1. 登录[飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取以下配置信息：
   - App ID（应用ID）
   - App Secret（应用密钥）
   - Verification Token（验证Token）
   - Encrypt Key（加密密钥）

### 3. 权限配置

确保AWS IAM用户/角色具有以下权限：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:*",
                "lambda:*",
                "apigateway:*",
                "sqs:*",
                "iam:*",
                "ssm:*",
                "logs:*"
            ],
            "Resource": "*"
        }
    ]
}
```

## 部署步骤

### 1. 配置验证

在部署前，建议先运行配置验证脚本：

```bash
# 使用命令行参数
python deployment/validate_config.py \
    --feishu-app-id "your_app_id" \
    --feishu-app-secret "your_app_secret" \
    --feishu-verification-token "your_verification_token" \
    --feishu-encrypt-key "your_encrypt_key" \
    --region us-east-1

# 或使用配置文件
python deployment/validate_config.py --config-file config.json
```

### 2. 准备配置文件

创建配置文件 `config.json`：

```json
{
    "FeishuAppId": "your_app_id",
    "FeishuAppSecret": "your_app_secret",
    "FeishuVerificationToken": "your_verification_token",
    "FeishuEncryptKey": "your_encrypt_key",
    "FeishuBotName": "MyFeishuBot",
    "FeishuAlertChatIds": "chat_id_1,chat_id_2",
    "LogLevel": "INFO"
}
```

或创建环境变量文件 `config.env`：

```bash
FeishuAppId=your_app_id
FeishuAppSecret=your_app_secret
FeishuVerificationToken=your_verification_token
FeishuEncryptKey=your_encrypt_key
FeishuBotName=MyFeishuBot
FeishuAlertChatIds=chat_id_1,chat_id_2
LogLevel=INFO
```

### 3. 执行部署

```bash
# 使用配置文件部署
python deployment/deploy.py \
    --stack-name feishu-bot-prod \
    --environment prod \
    --region us-east-1 \
    --config-file config.json

# 使用命令行参数部署
python deployment/deploy.py \
    --stack-name feishu-bot-dev \
    --environment dev \
    --feishu-app-id "your_app_id" \
    --feishu-app-secret "your_app_secret" \
    --feishu-verification-token "your_verification_token" \
    --feishu-encrypt-key "your_encrypt_key"
```

### 4. 配置飞书Webhook

部署完成后，获取API Gateway的Webhook URL：

```bash
# 从部署输出中获取
# 或者查看CloudFormation栈输出
aws cloudformation describe-stacks \
    --stack-name feishu-bot-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
    --output text
```

在飞书开放平台中配置Webhook URL：
1. 进入应用管理页面
2. 点击"事件订阅"
3. 配置请求网址为获取的API Gateway URL
4. 订阅"接收消息"事件

## 部署参数说明

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--stack-name` | 是 | - | CloudFormation栈名称 |
| `--environment` | 否 | dev | 部署环境（dev/staging/prod） |
| `--region` | 否 | us-east-1 | AWS区域 |
| `--profile` | 否 | - | AWS配置文件 |
| `--config-file` | 否 | - | 配置文件路径 |
| `--feishu-app-id` | 是 | - | 飞书应用ID |
| `--feishu-app-secret` | 是 | - | 飞书应用密钥 |
| `--feishu-verification-token` | 是 | - | 飞书验证Token |
| `--feishu-encrypt-key` | 是 | - | 飞书加密密钥 |
| `--feishu-bot-name` | 否 | FeishuBot | 机器人名称 |
| `--feishu-alert-chat-ids` | 否 | - | 告警群聊ID（逗号分隔） |
| `--log-level` | 否 | INFO | 日志级别 |
| `--no-code-update` | 否 | - | 不更新Lambda代码 |

## 更新部署

更新现有部署：

```bash
python deployment/deploy.py \
    --stack-name feishu-bot-prod \
    --environment prod \
    --config-file config.json
```

仅更新Lambda代码（不更新基础设施）：

```bash
python deployment/deploy.py \
    --stack-name feishu-bot-prod \
    --environment prod \
    --config-file config.json
```

## 删除部署

删除整个系统：

```bash
python deployment/deploy.py \
    --stack-name feishu-bot-prod \
    --delete
```

## 验证部署

验证现有部署状态：

```bash
python deployment/validate_config.py \
    --stack-name feishu-bot-prod \
    --region us-east-1
```

## 监控和日志

### CloudWatch日志

Lambda函数日志位置：
- 接收函数：`/aws/lambda/feishu-bot-{environment}-receive`
- 处理函数：`/aws/lambda/feishu-bot-{environment}-process`
- 监控函数：`/aws/lambda/feishu-bot-{environment}-monitor`

### CloudWatch指标

系统会自动创建以下告警：
- Lambda函数错误率
- SQS队列深度
- API Gateway错误率

### 查看系统状态

```bash
# 查看栈状态
aws cloudformation describe-stacks --stack-name feishu-bot-prod

# 查看Lambda函数
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `feishu-bot-prod`)]'

# 查看SQS队列
aws sqs list-queues --queue-name-prefix feishu-bot-prod
```

## 故障排查

### 常见问题

1. **部署失败**
   - 检查AWS权限
   - 验证飞书配置参数
   - 查看CloudFormation事件

2. **消息接收失败**
   - 检查API Gateway日志
   - 验证飞书Webhook配置
   - 检查签名验证

3. **消息处理失败**
   - 查看Lambda函数日志
   - 检查SQS队列状态
   - 验证飞书API调用

### 日志查看

```bash
# 查看Lambda函数日志
aws logs tail /aws/lambda/feishu-bot-prod-receive --follow

# 查看特定时间段的日志
aws logs filter-log-events \
    --log-group-name /aws/lambda/feishu-bot-prod-process \
    --start-time 1640995200000 \
    --end-time 1640998800000
```

### 手动测试

测试API Gateway端点：

```bash
curl -X POST https://your-api-gateway-url/prod/webhook \
    -H "Content-Type: application/json" \
    -H "X-Lark-Request-Timestamp: $(date +%s)" \
    -H "X-Lark-Request-Nonce: test-nonce" \
    -H "X-Lark-Signature: test-signature" \
    -d '{"challenge": "test-challenge"}'
```

## 安全最佳实践

1. **参数存储**
   - 敏感配置存储在Parameter Store中
   - 使用SecureString类型加密存储

2. **网络安全**
   - API Gateway仅接受HTTPS请求
   - Lambda函数运行在VPC中（可选）

3. **访问控制**
   - 使用最小权限原则配置IAM角色
   - 定期轮换飞书应用密钥

4. **监控告警**
   - 配置CloudWatch告警监控系统健康状态
   - 设置日志保留策略

## 成本优化

1. **Lambda配置**
   - 根据实际需求调整内存和超时设置
   - 使用预留并发控制成本

2. **日志管理**
   - 设置合适的日志保留期
   - 使用日志过滤减少存储成本

3. **监控成本**
   - 定期检查AWS成本和使用情况
   - 使用AWS Cost Explorer分析费用

## 支持和维护

- 定期更新Lambda运行时版本
- 监控飞书API变更和更新
- 备份重要配置和数据
- 制定灾难恢复计划