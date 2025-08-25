# 飞书机器人系统故障排查指南

本指南帮助您诊断和解决飞书机器人系统的常见问题。

## 目录

1. [快速诊断](#快速诊断)
2. [部署相关问题](#部署相关问题)
3. [消息处理问题](#消息处理问题)
4. [监控和告警问题](#监控和告警问题)
5. [性能问题](#性能问题)
6. [安全问题](#安全问题)
7. [日志分析](#日志分析)
8. [工具和命令](#工具和命令)

## 快速诊断

### 系统健康检查

首先运行系统健康检查来获取整体状态：

```bash
python scripts/monitoring_tools.py health \
  --project feishu-bot \
  --environment dev \
  --region us-east-1
```

### 检查关键组件

1. **Lambda函数状态**
```bash
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `feishu-bot`)].{Name:FunctionName,State:State,Runtime:Runtime}'
```

2. **SQS队列状态**
```bash
aws sqs list-queues \
  --queue-name-prefix feishu-bot
```

3. **API Gateway状态**
```bash
aws apigateway get-rest-apis \
  --query 'items[?contains(name, `feishu-bot`)].{Name:name,Id:id,CreatedDate:createdDate}'
```

4. **CloudWatch告警状态**
```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix feishu-bot \
  --state-value ALARM
```

## 部署相关问题

### 问题1：CloudFormation栈创建失败

**症状**：
- 部署脚本报错
- CloudFormation栈状态为 `CREATE_FAILED` 或 `ROLLBACK_COMPLETE`

**诊断步骤**：

1. 查看栈事件：
```bash
aws cloudformation describe-stack-events \
  --stack-name feishu-bot-dev \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

2. 检查IAM权限：
```bash
aws iam simulate-principal-policy \
  --policy-source-arn $(aws sts get-caller-identity --query Arn --output text) \
  --action-names cloudformation:CreateStack \
  --resource-arns "*"
```

**常见原因和解决方案**：

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `User is not authorized to perform: iam:CreateRole` | IAM权限不足 | 添加IAM管理权限 |
| `Parameter validation failed` | 参数格式错误 | 检查配置文件格式 |
| `Resource already exists` | 资源名称冲突 | 更改栈名称或删除现有资源 |
| `Limit exceeded` | 达到AWS服务限制 | 请求提高限制或清理资源 |

**解决步骤**：

1. 删除失败的栈：
```bash
aws cloudformation delete-stack --stack-name feishu-bot-dev
```

2. 等待删除完成：
```bash
aws cloudformation wait stack-delete-complete --stack-name feishu-bot-dev
```

3. 修复问题后重新部署：
```bash
python deployment/deploy.py --stack-name feishu-bot-dev --environment dev
```

### 问题2：Lambda函数部署失败

**症状**：
- Lambda函数创建失败
- 函数状态为 `Failed`

**诊断步骤**：

1. 检查函数配置：
```bash
aws lambda get-function --function-name feishu-bot-dev-receive
```

2. 查看函数日志：
```bash
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/feishu-bot-dev
```

**解决方案**：

1. 检查部署包大小：
```bash
ls -lh deployment-package.zip
```

2. 验证依赖包：
```bash
python -c "import boto3, requests; print('Dependencies OK')"
```

3. 重新打包和部署：
```bash
python deployment/package_lambda.py
python deployment/deploy.py --stack-name feishu-bot-dev
```

### 问题3：API Gateway配置错误

**症状**：
- 无法访问webhook URL
- 返回403或404错误

**诊断步骤**：

1. 测试API Gateway端点：
```bash
curl -X POST https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/webhook \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

2. 检查API Gateway配置：
```bash
aws apigateway get-rest-api --rest-api-id your-api-id
```

**解决方案**：

1. 重新部署API：
```bash
aws apigateway create-deployment \
  --rest-api-id your-api-id \
  --stage-name dev
```

2. 检查Lambda权限：
```bash
aws lambda get-policy --function-name feishu-bot-dev-receive
```

## 消息处理问题

### 问题1：飞书Webhook验证失败

**症状**：
- 飞书平台显示"请求网址验证失败"
- 收到401或403响应

**诊断步骤**：

1. 测试URL验证：
```bash
curl -X POST https://your-api-gateway-url/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "header": {"event_type": "url_verification"},
    "challenge": "test_challenge",
    "token": "your_verification_token",
    "type": "url_verification"
  }'
```

2. 检查签名验证逻辑：
```python
# 在Lambda函数中添加调试日志
import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def verify_signature(timestamp, nonce, body, signature):
    logger.debug(f"Timestamp: {timestamp}")
    logger.debug(f"Nonce: {nonce}")
    logger.debug(f"Body length: {len(body)}")
    logger.debug(f"Signature: {signature}")
    # ... 验证逻辑
```

**解决方案**：

1. 验证加密密钥配置：
```bash
aws ssm get-parameter --name /feishu-bot/dev/encrypt_key --with-decryption
```

2. 检查时间同步：
```bash
date -u
```

3. 更新Lambda函数代码：
```bash
python deployment/update_lambda_code.py
```

### 问题2：消息无法处理

**症状**：
- 机器人不回复消息
- SQS队列有积压消息

**诊断步骤**：

1. 检查SQS队列状态：
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/account/feishu-bot-dev-messages \
  --attribute-names All
```

2. 查看处理Lambda函数日志：
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/feishu-bot-dev-process \
  --start-time $(date -d '1 hour ago' +%s)000
```

3. 检查死信队列：
```bash
aws sqs receive-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/account/feishu-bot-dev-messages-dlq
```

**解决方案**：

1. 手动触发处理函数：
```bash
aws lambda invoke \
  --function-name feishu-bot-dev-process \
  --payload '{"Records":[{"body":"{\"test\":\"message\"}"}]}' \
  response.json
```

2. 增加Lambda并发限制：
```bash
aws lambda put-provisioned-concurrency-config \
  --function-name feishu-bot-dev-process \
  --provisioned-concurrency-config AllocatedProvisionedConcurrencyUnits=5
```

3. 调整SQS可见性超时：
```bash
aws sqs set-queue-attributes \
  --queue-url your-queue-url \
  --attributes VisibilityTimeoutSeconds=300
```

### 问题3：飞书API调用失败

**症状**：
- 无法发送消息到飞书
- 收到飞书API错误响应

**诊断步骤**：

1. 测试飞书API连接：
```python
import requests

def test_feishu_api():
    url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
    payload = {
        "app_id": "your_app_id",
        "app_secret": "your_app_secret"
    }
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

test_feishu_api()
```

2. 检查应用权限：
- 登录飞书开放平台
- 检查应用权限配置
- 确认应用已发布

**解决方案**：

1. 更新飞书应用凭证：
```bash
aws ssm put-parameter \
  --name /feishu-bot/dev/app_secret \
  --value "new_app_secret" \
  --type SecureString \
  --overwrite
```

2. 重启Lambda函数（清除缓存）：
```bash
aws lambda update-function-configuration \
  --function-name feishu-bot-dev-process \
  --environment Variables='{CACHE_CLEAR="true"}'
```

## 监控和告警问题

### 问题1：CloudWatch指标缺失

**症状**：
- 仪表板显示无数据
- 自定义指标未出现

**诊断步骤**：

1. 检查指标命名空间：
```bash
aws cloudwatch list-metrics --namespace FeishuBot
```

2. 查看Lambda函数执行日志：
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/feishu-bot-dev-receive \
  --filter-pattern "metrics"
```

**解决方案**：

1. 验证IAM权限：
```bash
aws iam simulate-principal-policy \
  --policy-source-arn $(aws lambda get-function --function-name feishu-bot-dev-receive --query Configuration.Role --output text) \
  --action-names cloudwatch:PutMetricData \
  --resource-arns "*"
```

2. 手动发送测试指标：
```python
import boto3

cloudwatch = boto3.client('cloudwatch')
cloudwatch.put_metric_data(
    Namespace='FeishuBot',
    MetricData=[
        {
            'MetricName': 'test.metric',
            'Value': 1.0,
            'Unit': 'Count'
        }
    ]
)
```

### 问题2：告警未触发

**症状**：
- 系统出现问题但未收到告警
- 告警状态显示INSUFFICIENT_DATA

**诊断步骤**：

1. 检查告警配置：
```bash
aws cloudwatch describe-alarms \
  --alarm-names feishu-bot-dev-receive-lambda-errors
```

2. 查看告警历史：
```bash
aws cloudwatch describe-alarm-history \
  --alarm-name feishu-bot-dev-receive-lambda-errors
```

**解决方案**：

1. 调整告警阈值：
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name feishu-bot-dev-receive-lambda-errors \
  --alarm-description "Lambda function errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1
```

2. 测试告警：
```bash
aws cloudwatch set-alarm-state \
  --alarm-name feishu-bot-dev-receive-lambda-errors \
  --state-value ALARM \
  --state-reason "Testing alarm"
```

## 性能问题

### 问题1：Lambda函数超时

**症状**：
- 函数执行时间过长
- 收到超时错误

**诊断步骤**：

1. 查看函数执行时间：
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/feishu-bot-dev-process \
  --filter-pattern "REPORT" \
  --start-time $(date -d '1 hour ago' +%s)000
```

2. 分析性能指标：
```bash
python scripts/monitoring_tools.py metrics \
  --project feishu-bot \
  --environment dev \
  --hours 24
```

**解决方案**：

1. 增加函数超时时间：
```bash
aws lambda update-function-configuration \
  --function-name feishu-bot-dev-process \
  --timeout 300
```

2. 增加内存分配：
```bash
aws lambda update-function-configuration \
  --function-name feishu-bot-dev-process \
  --memory-size 512
```

3. 优化代码性能：
```python
# 使用连接池
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry_strategy = Retry(total=3, backoff_factor=1)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)
```

### 问题2：SQS队列积压

**症状**：
- 队列中消息数量持续增长
- 消息处理延迟

**诊断步骤**：

1. 检查队列深度：
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfVisibleMessages \
  --dimensions Name=QueueName,Value=feishu-bot-dev-messages \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

2. 检查处理速率：
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=feishu-bot-dev-process \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

**解决方案**：

1. 增加批处理大小：
```bash
aws lambda update-event-source-mapping \
  --uuid your-event-source-mapping-uuid \
  --batch-size 10
```

2. 增加并发执行数：
```bash
aws lambda put-reserved-concurrency-config \
  --function-name feishu-bot-dev-process \
  --reserved-concurrency-units 20
```

3. 优化消息处理逻辑：
```python
# 并行处理消息
import asyncio
import aiohttp

async def process_messages_parallel(messages):
    async with aiohttp.ClientSession() as session:
        tasks = [process_single_message(msg, session) for msg in messages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

## 安全问题

### 问题1：签名验证失败

**症状**：
- 大量401错误
- 合法请求被拒绝

**诊断步骤**：

1. 检查签名计算逻辑：
```python
def debug_signature_verification(timestamp, nonce, body, signature, encrypt_key):
    import hashlib
    import hmac
    
    string_to_sign = f"{timestamp}{nonce}{encrypt_key}{body}"
    expected_signature = hashlib.sha256(string_to_sign.encode()).hexdigest()
    
    print(f"Timestamp: {timestamp}")
    print(f"Nonce: {nonce}")
    print(f"Body: {body[:100]}...")
    print(f"String to sign: {string_to_sign[:100]}...")
    print(f"Expected: {expected_signature}")
    print(f"Received: {signature}")
    print(f"Match: {hmac.compare_digest(expected_signature, signature)}")
```

2. 检查时间同步：
```bash
# 检查系统时间
date
# 检查NTP同步状态
timedatectl status
```

**解决方案**：

1. 更新加密密钥：
```bash
# 从飞书平台获取最新的encrypt_key
aws ssm put-parameter \
  --name /feishu-bot/dev/encrypt_key \
  --value "new_encrypt_key" \
  --type SecureString \
  --overwrite
```

2. 调整时间容忍度：
```python
def is_request_fresh(timestamp, max_age=600):  # 增加到10分钟
    current_time = int(time.time())
    request_time = int(timestamp)
    return abs(current_time - request_time) <= max_age
```

### 问题2：权限错误

**症状**：
- Lambda函数无法访问AWS服务
- 收到AccessDenied错误

**诊断步骤**：

1. 检查Lambda执行角色：
```bash
aws lambda get-function \
  --function-name feishu-bot-dev-receive \
  --query Configuration.Role
```

2. 检查角色权限：
```bash
aws iam list-attached-role-policies \
  --role-name feishu-bot-dev-lambda-role
```

**解决方案**：

1. 添加缺失权限：
```bash
aws iam attach-role-policy \
  --role-name feishu-bot-dev-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

2. 创建自定义权限策略：
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "ssm:GetParameter",
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    }
  ]
}
```

## 日志分析

### 结构化日志查询

系统使用结构化JSON日志，可以使用CloudWatch Insights进行查询：

1. **查找错误日志**：
```sql
fields @timestamp, level, message, error_type, function
| filter level = "ERROR"
| sort @timestamp desc
| limit 20
```

2. **分析性能问题**：
```sql
fields @timestamp, function, duration_ms
| filter duration_ms > 5000
| sort duration_ms desc
| limit 10
```

3. **监控特定用户**：
```sql
fields @timestamp, message, user_id, chat_id
| filter user_id = "specific_user_id"
| sort @timestamp desc
```

4. **分析错误趋势**：
```sql
fields @timestamp, error_type
| filter level = "ERROR"
| stats count() by error_type
| sort count desc
```

### 日志级别说明

- **DEBUG**: 详细的调试信息
- **INFO**: 一般信息，如请求处理开始/结束
- **WARNING**: 警告信息，如重试操作
- **ERROR**: 错误信息，如处理失败
- **CRITICAL**: 严重错误，如系统不可用

### 常见日志模式

1. **成功处理**：
```json
{
  "level": "INFO",
  "message": "Webhook request processed successfully",
  "duration_ms": 150.5,
  "function": "receive_handler"
}
```

2. **处理错误**：
```json
{
  "level": "ERROR",
  "message": "Failed to process SQS record",
  "error_type": "ValidationError",
  "function": "process_handler",
  "metadata": {"record_id": "12345"}
}
```

3. **性能警告**：
```json
{
  "level": "WARNING",
  "message": "Function execution time exceeded threshold",
  "duration_ms": 8500,
  "function": "process_handler"
}
```

## 工具和命令

### 监控工具

```bash
# 系统健康检查
python scripts/monitoring_tools.py health

# 获取性能指标
python scripts/monitoring_tools.py metrics --hours 24

# 查看错误日志
python scripts/monitoring_tools.py logs --level ERROR --hours 1

# 创建监控仪表板
python scripts/monitoring_tools.py dashboard
```

### AWS CLI命令

```bash
# Lambda函数管理
aws lambda list-functions --query 'Functions[?contains(FunctionName, `feishu-bot`)]'
aws lambda get-function --function-name feishu-bot-dev-receive
aws lambda invoke --function-name feishu-bot-dev-receive --payload '{}' response.json

# SQS队列管理
aws sqs list-queues --queue-name-prefix feishu-bot
aws sqs get-queue-attributes --queue-url [QUEUE_URL] --attribute-names All
aws sqs purge-queue --queue-url [QUEUE_URL]

# CloudWatch管理
aws cloudwatch describe-alarms --alarm-name-prefix feishu-bot
aws cloudwatch get-metric-statistics --namespace FeishuBot --metric-name function.calls

# Parameter Store管理
aws ssm get-parameters-by-path --path /feishu-bot/dev --recursive --with-decryption
aws ssm put-parameter --name /feishu-bot/dev/test --value "test_value"
```

### 测试命令

```bash
# 运行单元测试
python scripts/run_tests.py --type unit

# 运行集成测试
python scripts/run_tests.py --type integration

# 运行性能测试
python scripts/run_tests.py --type performance

# 运行安全测试
python scripts/run_tests.py --type security
```

### 部署命令

```bash
# 验证配置
python deployment/validate_config.py --config-file .env

# 部署系统
python deployment/deploy.py --stack-name feishu-bot-dev --environment dev

# 更新Lambda代码
python deployment/update_lambda_code.py

# 删除部署
python deployment/deploy.py --delete --stack-name feishu-bot-dev
```

## 紧急响应流程

### 1. 系统完全不可用

1. **立即检查**：
   - AWS服务状态页面
   - CloudFormation栈状态
   - Lambda函数状态

2. **快速恢复**：
   ```bash
   # 重新部署系统
   python deployment/deploy.py --stack-name feishu-bot-dev --environment dev
   ```

3. **通知相关人员**：
   - 发送系统状态通知
   - 更新事件状态页面

### 2. 部分功能异常

1. **隔离问题**：
   - 确定影响范围
   - 检查相关组件

2. **临时修复**：
   ```bash
   # 重启有问题的Lambda函数
   aws lambda update-function-configuration \
     --function-name feishu-bot-dev-process \
     --environment Variables='{RESTART="true"}'
   ```

3. **监控恢复**：
   - 观察关键指标
   - 验证功能正常

### 3. 性能下降

1. **扩容资源**：
   ```bash
   # 增加Lambda并发
   aws lambda put-reserved-concurrency-config \
     --function-name feishu-bot-dev-process \
     --reserved-concurrency-units 50
   ```

2. **优化配置**：
   ```bash
   # 增加内存和超时时间
   aws lambda update-function-configuration \
     --function-name feishu-bot-dev-process \
     --memory-size 1024 \
     --timeout 300
   ```

## 预防措施

### 1. 定期维护

- 每周检查系统健康状态
- 每月更新依赖包
- 每季度审查配置和权限

### 2. 监控设置

- 配置关键指标告警
- 设置日志保留策略
- 定期检查告警有效性

### 3. 备份策略

- 定期备份配置文件
- 保存部署脚本版本
- 维护回滚计划

### 4. 文档更新

- 及时更新故障排查文档
- 记录新发现的问题和解决方案
- 分享最佳实践

---

如果本指南未能解决您的问题，请：
1. 收集相关日志和错误信息
2. 记录重现步骤
3. 联系技术支持团队