# 飞书机器人系统部署指南

本指南将帮助您完成飞书机器人系统的完整部署过程。

## 目录

1. [前置要求](#前置要求)
2. [飞书应用配置](#飞书应用配置)
3. [AWS环境准备](#aws环境准备)
4. [环境变量配置](#环境变量配置)
5. [部署步骤](#部署步骤)
6. [验证部署](#验证部署)
7. [故障排查](#故障排查)

## 前置要求

### 软件要求

- Python 3.9 或更高版本
- AWS CLI v2
- Git
- 具有管理员权限的AWS账户

### 权限要求

确保您的AWS用户或角色具有以下权限：

- CloudFormation 完整权限
- Lambda 完整权限
- API Gateway 完整权限
- SQS 完整权限
- IAM 角色创建和管理权限
- CloudWatch 完整权限
- Parameter Store 读写权限

## 飞书应用配置

### 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 登录您的飞书账号
3. 点击"创建应用" → "自建应用"
4. 填写应用信息：
   - 应用名称：飞书机器人
   - 应用描述：企业内部消息处理机器人
   - 应用图标：上传合适的图标

### 2. 获取应用凭证

在应用管理页面的"凭证与基础信息"中获取：

- **App ID**：应用唯一标识
- **App Secret**：应用密钥
- **Verification Token**：用于验证请求来源
- **Encrypt Key**：用于加密和解密

### 3. 配置应用权限

在"权限管理"页面添加以下权限：

**机器人权限：**
- 获取与发送单聊、群组消息
- 读取用户发给机器人的单聊消息
- 获取群组中所有消息
- 以应用的身份发送消息

**API权限：**
- 通过手机号或邮箱获取用户 ID
- 获取用户基本信息
- 获取部门基本信息

### 4. 配置事件订阅

在"事件订阅"页面：

1. 启用事件订阅
2. 添加事件类型：
   - 接收消息 (im.message.receive_v1)
   - 消息已读 (im.message.message_read_v1)
3. 请求网址配置将在部署完成后填写

## AWS环境准备

### 1. 配置AWS CLI

```bash
# 配置AWS凭证
aws configure

# 验证配置
aws sts get-caller-identity
```

### 2. 选择部署区域

建议选择以下区域之一：
- `us-east-1` (美国东部-弗吉尼亚)
- `ap-southeast-1` (亚太-新加坡)
- `eu-west-1` (欧洲-爱尔兰)

## 环境变量配置

### 1. 复制环境变量模板

```bash
cp .env.template .env
```

### 2. 配置必需变量

编辑 `.env` 文件，填入以下必需信息：

```bash
# 飞书应用配置（必需）
FEISHU_APP_ID=cli_xxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxxxxxxxxxx
FEISHU_ENCRYPT_KEY=xxxxxxxxxxxxxxxx

# AWS配置
AWS_REGION=us-east-1
PROJECT_NAME=feishu-bot
ENVIRONMENT=dev

# 告警配置
FEISHU_ALERT_CHAT_IDS=oc_xxxxxxxxxx,oc_yyyyyyyyyy
```

### 3. 可选配置

根据需要调整以下可选配置：

```bash
# 系统配置
LOG_LEVEL=INFO
MAX_RETRY_ATTEMPTS=3
RETRY_DELAY_BASE=1

# 监控配置
CUSTOM_METRICS_NAMESPACE=FeishuBot
ENABLE_DETAILED_MONITORING=false

# 安全配置
REQUEST_MAX_AGE=300
ENABLE_SIGNATURE_VERIFICATION=true
```

## 部署步骤

### 1. 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装部署工具依赖
pip install boto3 requests
```

### 2. 验证配置

```bash
# 验证AWS配置和权限
python deployment/validate_config.py \
  --config-file .env \
  --region us-east-1

# 验证飞书配置
python deployment/validate_config.py \
  --feishu-app-id $FEISHU_APP_ID \
  --feishu-app-secret $FEISHU_APP_SECRET \
  --feishu-verification-token $FEISHU_VERIFICATION_TOKEN \
  --feishu-encrypt-key $FEISHU_ENCRYPT_KEY
```

### 3. 执行部署

#### 方法一：使用Python部署脚本

```bash
python deployment/deploy.py \
  --stack-name feishu-bot-dev \
  --environment dev \
  --region us-east-1 \
  --config-file .env
```

#### 方法二：使用Shell脚本

```bash
chmod +x deployment/deploy.sh
./deployment/deploy.sh \
  --stack-name feishu-bot-dev \
  --environment dev \
  --region us-east-1 \
  --config-file .env
```

### 4. 等待部署完成

部署过程大约需要5-10分钟。部署完成后，您将看到以下输出：

```
=== 部署结果 ===
ApiGatewayUrl: https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/dev/webhook
MessageQueueUrl: https://sqs.us-east-1.amazonaws.com/123456789012/feishu-bot-dev-messages
ReceiveLambdaArn: arn:aws:lambda:us-east-1:123456789012:function:feishu-bot-dev-receive
ProcessLambdaArn: arn:aws:lambda:us-east-1:123456789012:function:feishu-bot-dev-process
MonitorLambdaArn: arn:aws:lambda:us-east-1:123456789012:function:feishu-bot-dev-monitor
```

### 5. 配置飞书Webhook URL

1. 复制部署输出中的 `ApiGatewayUrl`
2. 返回飞书开放平台的应用管理页面
3. 在"事件订阅"中填入请求网址：
   ```
   https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/dev/webhook
   ```
4. 点击"保存"并等待验证通过

### 6. 发布应用版本

1. 在飞书开放平台点击"版本管理与发布"
2. 创建新版本
3. 填写版本说明
4. 提交审核（企业内部应用通常自动通过）

## 验证部署

### 1. 健康检查

```bash
# 检查系统整体健康状态
python scripts/monitoring_tools.py health \
  --project feishu-bot \
  --environment dev \
  --region us-east-1
```

### 2. 功能测试

1. **URL验证测试**：
   - 飞书平台的Webhook URL验证应该显示"验证成功"

2. **消息处理测试**：
   - 在飞书中向机器人发送消息
   - 机器人应该能够回复消息

3. **监控告警测试**：
   - 检查CloudWatch中是否有自定义指标数据
   - 验证告警配置是否正常

### 3. 查看日志

```bash
# 查看最近的错误日志
python scripts/monitoring_tools.py logs \
  --project feishu-bot \
  --environment dev \
  --level ERROR \
  --hours 1
```

### 4. 创建监控仪表板

```bash
# 创建CloudWatch仪表板
python scripts/monitoring_tools.py dashboard \
  --project feishu-bot \
  --environment dev
```

## 故障排查

### 常见问题

#### 1. 部署失败

**问题**：CloudFormation栈创建失败

**解决方案**：
```bash
# 查看栈事件
aws cloudformation describe-stack-events \
  --stack-name feishu-bot-dev \
  --region us-east-1

# 删除失败的栈
aws cloudformation delete-stack \
  --stack-name feishu-bot-dev \
  --region us-east-1
```

#### 2. Lambda函数错误

**问题**：Lambda函数执行失败

**解决方案**：
```bash
# 查看Lambda函数日志
aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/feishu-bot-dev

# 查看具体日志流
aws logs get-log-events \
  --log-group-name /aws/lambda/feishu-bot-dev-receive \
  --log-stream-name [LOG_STREAM_NAME]
```

#### 3. 飞书Webhook验证失败

**问题**：飞书平台显示"请求网址验证失败"

**可能原因**：
- API Gateway URL不正确
- Lambda函数未正确处理URL验证请求
- 网络连接问题

**解决方案**：
```bash
# 测试API Gateway端点
curl -X POST [API_GATEWAY_URL] \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test"}'

# 检查Lambda函数状态
aws lambda get-function \
  --function-name feishu-bot-dev-receive
```

#### 4. 消息处理失败

**问题**：机器人不回复消息

**检查步骤**：
1. 确认飞书应用权限配置正确
2. 检查SQS队列是否有消息积压
3. 查看Lambda函数执行日志
4. 验证飞书API调用是否成功

```bash
# 检查SQS队列状态
aws sqs get-queue-attributes \
  --queue-url [SQS_QUEUE_URL] \
  --attribute-names All
```

#### 5. 监控指标缺失

**问题**：CloudWatch中没有自定义指标

**解决方案**：
1. 确认Lambda函数中的监控代码正常执行
2. 检查IAM权限是否包含CloudWatch写入权限
3. 验证指标命名空间配置

### 日志分析

#### 结构化日志格式

系统使用结构化JSON日志格式：

```json
{
  "timestamp": "2023-11-28T10:30:00.000Z",
  "level": "INFO",
  "message": "Processing webhook request",
  "logger": "receive_handler",
  "function": "receive_handler",
  "request_id": "12345678-1234-1234-1234-123456789012",
  "duration_ms": 150.5,
  "metadata": {
    "batch_size": 1,
    "message_type": "text"
  }
}
```

#### 关键日志字段

- `timestamp`: 日志时间戳
- `level`: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `message`: 日志消息
- `function`: 函数名称
- `request_id`: AWS请求ID
- `duration_ms`: 执行时间（毫秒）
- `error_type`: 错误类型（如果有）
- `metadata`: 附加元数据

### 性能优化

#### 1. Lambda函数优化

- 调整内存大小以优化性能和成本
- 使用预留并发控制冷启动
- 优化代码以减少执行时间

#### 2. SQS队列优化

- 调整可见性超时时间
- 配置死信队列处理失败消息
- 使用批处理提高吞吐量

#### 3. 监控优化

- 设置合适的告警阈值
- 定期清理旧日志和指标
- 使用仪表板监控系统状态

## 安全最佳实践

### 1. 访问控制

- 使用最小权限原则配置IAM角色
- 定期轮换飞书应用密钥
- 启用CloudTrail记录API调用

### 2. 数据保护

- 使用Parameter Store存储敏感配置
- 启用传输和静态加密
- 实施数据保留策略

### 3. 网络安全

- 使用VPC端点减少公网暴露
- 配置安全组限制访问
- 启用WAF保护API Gateway

### 4. 监控和审计

- 设置安全相关告警
- 定期审查访问日志
- 监控异常活动模式

## 维护和更新

### 1. 定期维护

- 更新Lambda运行时版本
- 检查和更新依赖包
- 清理未使用的资源

### 2. 备份和恢复

- 定期备份配置和代码
- 测试灾难恢复流程
- 文档化恢复步骤

### 3. 版本管理

- 使用Git管理代码版本
- 标记稳定版本
- 维护变更日志

## 支持和联系

如果您在部署过程中遇到问题，请：

1. 查看本文档的故障排查部分
2. 检查系统日志和监控指标
3. 参考项目README文件
4. 提交Issue到项目仓库

---

**注意**：本指南假设您具有基本的AWS和飞书开发经验。如果您是初学者，建议先熟悉相关概念和工具。