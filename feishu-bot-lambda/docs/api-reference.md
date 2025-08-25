# 飞书机器人系统 API 参考

本文档描述了飞书机器人系统的API接口、数据模型和使用示例。

## 目录

1. [概述](#概述)
2. [认证和安全](#认证和安全)
3. [Webhook API](#webhook-api)
4. [数据模型](#数据模型)
5. [错误处理](#错误处理)
6. [使用示例](#使用示例)
7. [SDK和工具](#sdk和工具)

## 概述

飞书机器人系统提供以下主要功能：

- **消息接收**：处理来自飞书的webhook消息
- **消息处理**：异步处理和回复消息
- **监控告警**：处理系统监控告警并推送到飞书
- **健康检查**：提供系统健康状态查询

### 系统架构

```
飞书平台 → API Gateway → Lambda (接收) → SQS → Lambda (处理) → 飞书API
                                                ↓
                                        CloudWatch (监控)
```

## 认证和安全

### Webhook签名验证

所有来自飞书的webhook请求都必须通过签名验证：

#### 签名算法

```python
import hashlib
import hmac

def verify_signature(timestamp, nonce, encrypt_key, body, signature):
    """验证飞书webhook签名"""
    string_to_sign = f"{timestamp}{nonce}{encrypt_key}{body}"
    expected_signature = hashlib.sha256(
        string_to_sign.encode('utf-8')
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)
```

#### 请求头要求

```http
X-Lark-Request-Timestamp: 1640995200
X-Lark-Request-Nonce: random_string
X-Lark-Signature: calculated_signature
Content-Type: application/json
```

### 时效性验证

请求时间戳必须在5分钟内，防止重放攻击：

```python
import time

def is_request_fresh(timestamp, max_age=300):
    """检查请求时效性"""
    current_time = int(time.time())
    request_time = int(timestamp)
    return abs(current_time - request_time) <= max_age
```

## Webhook API

### 基础信息

- **Base URL**: `https://your-api-gateway-url.amazonaws.com/dev`
- **Content-Type**: `application/json`
- **Method**: `POST`

### 端点

#### POST /webhook

接收飞书平台的webhook事件。

**请求示例**：

```http
POST /webhook HTTP/1.1
Host: your-api-gateway-url.amazonaws.com
Content-Type: application/json
X-Lark-Request-Timestamp: 1640995200
X-Lark-Request-Nonce: random_nonce
X-Lark-Signature: signature_hash

{
  "header": {
    "event_id": "event_12345",
    "event_type": "im.message.receive_v1",
    "create_time": "1640995200000",
    "token": "verification_token",
    "app_id": "cli_app_id",
    "tenant_key": "tenant_key"
  },
  "event": {
    "sender": {
      "sender_id": {
        "user_id": "user_12345",
        "open_id": "ou_open_id"
      },
      "sender_type": "user",
      "tenant_key": "tenant_key"
    },
    "message": {
      "message_id": "om_message_id",
      "root_id": "om_root_id",
      "parent_id": "om_parent_id",
      "create_time": "1640995200000",
      "chat_id": "oc_chat_id",
      "chat_type": "group",
      "message_type": "text",
      "content": "{\"text\":\"Hello bot\"}",
      "mentions": [
        {
          "key": "@_user_1",
          "id": {
            "user_id": "user_12345",
            "open_id": "ou_open_id"
          },
          "name": "User Name"
        }
      ]
    }
  }
}
```

**响应示例**：

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "success": true,
  "timestamp": 1640995200,
  "data": {
    "message": "Event processed successfully"
  }
}
```

### 支持的事件类型

#### 1. URL验证事件

**事件类型**: `url_verification`

**请求示例**：
```json
{
  "header": {
    "event_type": "url_verification"
  },
  "challenge": "challenge_string",
  "token": "verification_token",
  "type": "url_verification"
}
```

**响应示例**：
```json
{
  "success": true,
  "timestamp": 1640995200,
  "data": {
    "challenge": "challenge_string"
  }
}
```

#### 2. 消息接收事件

**事件类型**: `im.message.receive_v1`

支持的消息类型：
- `text`: 文本消息
- `image`: 图片消息
- `file`: 文件消息
- `audio`: 音频消息
- `video`: 视频消息
- `sticker`: 表情包消息

**文本消息示例**：
```json
{
  "header": {
    "event_type": "im.message.receive_v1"
  },
  "event": {
    "message": {
      "message_type": "text",
      "content": "{\"text\":\"Hello world\"}"
    }
  }
}
```

**图片消息示例**：
```json
{
  "header": {
    "event_type": "im.message.receive_v1"
  },
  "event": {
    "message": {
      "message_type": "image",
      "content": "{\"image_key\":\"img_v2_12345\"}"
    }
  }
}
```

## 数据模型

### FeishuMessage

飞书消息数据模型：

```python
@dataclass
class FeishuMessage:
    message_id: str          # 消息ID
    user_id: str            # 发送用户ID
    chat_id: str            # 聊天ID
    message_type: str       # 消息类型
    content: str            # 消息内容
    timestamp: int          # 时间戳
    app_id: str            # 应用ID
    mentions: Optional[List[str]] = None  # @用户列表
```

**JSON示例**：
```json
{
  "message_id": "om_12345",
  "user_id": "user_12345",
  "chat_id": "oc_chat_12345",
  "message_type": "text",
  "content": "Hello world",
  "timestamp": 1640995200000,
  "app_id": "cli_app_12345",
  "mentions": ["user_67890"]
}
```

### MonitorAlert

监控告警数据模型：

```python
@dataclass
class MonitorAlert:
    alert_id: str           # 告警ID
    service_name: str       # 服务名称
    alert_type: str         # 告警类型 (error, warning, info)
    message: str            # 告警消息
    timestamp: int          # 时间戳
    severity: str           # 严重程度 (critical, high, medium, low)
    metadata: Dict[str, Any] # 元数据
```

**JSON示例**：
```json
{
  "alert_id": "alert_12345",
  "service_name": "user-service",
  "alert_type": "error",
  "message": "Database connection failed",
  "timestamp": 1640995200,
  "severity": "critical",
  "metadata": {
    "region": "us-east-1",
    "instance_id": "i-12345",
    "error_count": 5
  }
}
```

### BotConfig

机器人配置数据模型：

```python
@dataclass
class BotConfig:
    app_id: str             # 应用ID
    app_secret: str         # 应用密钥
    verification_token: str # 验证Token
    encrypt_key: str        # 加密密钥
    bot_name: str          # 机器人名称
    webhook_url: str       # Webhook URL
```

## 错误处理

### 标准错误响应

```json
{
  "success": false,
  "timestamp": 1640995200,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": {
      "field": "Additional error details"
    }
  }
}
```

### 错误代码

| 错误代码 | HTTP状态码 | 描述 |
|---------|-----------|------|
| `EMPTY_BODY` | 400 | 请求体为空 |
| `INVALID_JSON` | 400 | 无效的JSON格式 |
| `INVALID_SIGNATURE` | 401 | 签名验证失败 |
| `REQUEST_EXPIRED` | 401 | 请求已过期 |
| `INTERNAL_ERROR` | 500 | 内部服务器错误 |
| `SERVICE_UNAVAILABLE` | 503 | 服务不可用 |

### 重试策略

对于临时性错误，建议使用指数退避重试：

```python
import time
import random

def retry_with_backoff(func, max_retries=3, base_delay=1.0):
    """带指数退避的重试函数"""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries:
                raise e
            
            # 计算延迟时间（指数退避 + 随机抖动）
            delay = base_delay * (2 ** attempt)
            jitter = random.uniform(0, delay * 0.1)
            time.sleep(delay + jitter)
```

## 使用示例

### Python SDK示例

```python
import requests
import json
import hashlib
import hmac
import time

class FeishuBotClient:
    def __init__(self, webhook_url, encrypt_key):
        self.webhook_url = webhook_url
        self.encrypt_key = encrypt_key
    
    def send_webhook(self, event_data):
        """发送webhook事件"""
        timestamp = str(int(time.time()))
        nonce = "random_nonce_12345"
        body = json.dumps(event_data)
        
        # 计算签名
        string_to_sign = f"{timestamp}{nonce}{self.encrypt_key}{body}"
        signature = hashlib.sha256(string_to_sign.encode()).hexdigest()
        
        headers = {
            'Content-Type': 'application/json',
            'X-Lark-Request-Timestamp': timestamp,
            'X-Lark-Request-Nonce': nonce,
            'X-Lark-Signature': signature
        }
        
        response = requests.post(
            self.webhook_url,
            headers=headers,
            data=body,
            timeout=10
        )
        
        return response.json()

# 使用示例
client = FeishuBotClient(
    webhook_url="https://your-api-gateway-url.amazonaws.com/dev/webhook",
    encrypt_key="your_encrypt_key"
)

# 发送文本消息事件
message_event = {
    "header": {
        "event_type": "im.message.receive_v1",
        "app_id": "cli_your_app_id"
    },
    "event": {
        "sender": {
            "sender_type": "user",
            "sender_id": {"user_id": "user_12345"}
        },
        "message": {
            "message_id": "om_12345",
            "chat_id": "oc_chat_12345",
            "message_type": "text",
            "content": "{\"text\":\"Hello bot\"}"
        }
    }
}

result = client.send_webhook(message_event)
print(result)
```

### cURL示例

```bash
#!/bin/bash

# 配置变量
WEBHOOK_URL="https://your-api-gateway-url.amazonaws.com/dev/webhook"
ENCRYPT_KEY="your_encrypt_key"
TIMESTAMP=$(date +%s)
NONCE="random_nonce_12345"

# 消息内容
BODY='{
  "header": {
    "event_type": "im.message.receive_v1",
    "app_id": "cli_your_app_id"
  },
  "event": {
    "sender": {
      "sender_type": "user",
      "sender_id": {"user_id": "user_12345"}
    },
    "message": {
      "message_id": "om_12345",
      "chat_id": "oc_chat_12345",
      "message_type": "text",
      "content": "{\"text\":\"Hello bot\"}"
    }
  }
}'

# 计算签名
STRING_TO_SIGN="${TIMESTAMP}${NONCE}${ENCRYPT_KEY}${BODY}"
SIGNATURE=$(echo -n "$STRING_TO_SIGN" | sha256sum | cut -d' ' -f1)

# 发送请求
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Lark-Request-Timestamp: $TIMESTAMP" \
  -H "X-Lark-Request-Nonce: $NONCE" \
  -H "X-Lark-Signature: $SIGNATURE" \
  -d "$BODY"
```

### JavaScript/Node.js示例

```javascript
const crypto = require('crypto');
const axios = require('axios');

class FeishuBotClient {
    constructor(webhookUrl, encryptKey) {
        this.webhookUrl = webhookUrl;
        this.encryptKey = encryptKey;
    }
    
    async sendWebhook(eventData) {
        const timestamp = Math.floor(Date.now() / 1000).toString();
        const nonce = 'random_nonce_' + Math.random().toString(36).substr(2, 9);
        const body = JSON.stringify(eventData);
        
        // 计算签名
        const stringToSign = `${timestamp}${nonce}${this.encryptKey}${body}`;
        const signature = crypto.createHash('sha256').update(stringToSign).digest('hex');
        
        const headers = {
            'Content-Type': 'application/json',
            'X-Lark-Request-Timestamp': timestamp,
            'X-Lark-Request-Nonce': nonce,
            'X-Lark-Signature': signature
        };
        
        try {
            const response = await axios.post(this.webhookUrl, eventData, {
                headers: headers,
                timeout: 10000
            });
            return response.data;
        } catch (error) {
            throw new Error(`Webhook request failed: ${error.message}`);
        }
    }
}

// 使用示例
const client = new FeishuBotClient(
    'https://your-api-gateway-url.amazonaws.com/dev/webhook',
    'your_encrypt_key'
);

const messageEvent = {
    header: {
        event_type: 'im.message.receive_v1',
        app_id: 'cli_your_app_id'
    },
    event: {
        sender: {
            sender_type: 'user',
            sender_id: { user_id: 'user_12345' }
        },
        message: {
            message_id: 'om_12345',
            chat_id: 'oc_chat_12345',
            message_type: 'text',
            content: '{"text":"Hello bot"}'
        }
    }
};

client.sendWebhook(messageEvent)
    .then(result => console.log(result))
    .catch(error => console.error(error));
```

## SDK和工具

### 官方工具

- **监控工具**: `scripts/monitoring_tools.py`
  - 系统健康检查
  - 性能指标查询
  - 日志分析
  - 仪表板创建

- **部署工具**: `deployment/deploy.py`
  - 自动化部署
  - 配置验证
  - 环境管理

- **测试工具**: `scripts/run_tests.py`
  - 单元测试
  - 集成测试
  - 性能测试
  - 安全测试

### 第三方集成

#### Postman集合

可以导入以下Postman集合进行API测试：

```json
{
  "info": {
    "name": "飞书机器人API",
    "description": "飞书机器人系统API测试集合"
  },
  "item": [
    {
      "name": "URL验证",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"header\": {\n    \"event_type\": \"url_verification\"\n  },\n  \"challenge\": \"test_challenge\",\n  \"token\": \"verification_token\",\n  \"type\": \"url_verification\"\n}"
        },
        "url": {
          "raw": "{{webhook_url}}/webhook",
          "host": ["{{webhook_url}}"],
          "path": ["webhook"]
        }
      }
    }
  ],
  "variable": [
    {
      "key": "webhook_url",
      "value": "https://your-api-gateway-url.amazonaws.com/dev"
    }
  ]
}
```

#### Swagger/OpenAPI规范

系统提供OpenAPI 3.0规范文档，可用于生成客户端SDK：

```yaml
openapi: 3.0.0
info:
  title: 飞书机器人API
  version: 1.0.0
  description: 飞书机器人系统API接口文档

servers:
  - url: https://your-api-gateway-url.amazonaws.com/dev
    description: 开发环境

paths:
  /webhook:
    post:
      summary: 接收飞书Webhook事件
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/WebhookEvent'
      responses:
        '200':
          description: 成功处理事件
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SuccessResponse'
        '400':
          description: 请求错误
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

components:
  schemas:
    WebhookEvent:
      type: object
      properties:
        header:
          type: object
        event:
          type: object
    
    SuccessResponse:
      type: object
      properties:
        success:
          type: boolean
        timestamp:
          type: integer
        data:
          type: object
    
    ErrorResponse:
      type: object
      properties:
        success:
          type: boolean
        timestamp:
          type: integer
        error:
          type: object
```

## 最佳实践

### 1. 性能优化

- 使用连接池复用HTTP连接
- 实施请求缓存减少重复调用
- 合理设置超时时间
- 使用异步处理提高并发能力

### 2. 错误处理

- 实施完整的错误处理策略
- 记录详细的错误日志
- 提供有意义的错误消息
- 实施重试机制处理临时性错误

### 3. 安全考虑

- 始终验证webhook签名
- 检查请求时效性
- 实施速率限制
- 记录安全相关事件

### 4. 监控和调试

- 启用详细日志记录
- 设置关键指标监控
- 配置告警通知
- 定期检查系统健康状态

---

如需更多信息，请参考：
- [部署指南](deployment-guide.md)
- [故障排查指南](troubleshooting-guide.md)
- [最佳实践指南](best-practices.md)