# 本项目提供快速部署mcp运行环境的演示

## 基础依赖

依赖以下组件：

* aws-cli/2.27.57
* jq
* python3
* pip install boto3

### 配置 Cognito 身份验证

#### 安装

```bash
#./utils/setup_cognito_s2s.sh <region> <name>
./utils/setup_cognito_s2s.sh us-east-1 my-auth
```

#### 测试授权

```bash
./utils/test_cognito_s2s.sh my-auth
```

#### 清理

```bash
./utils/delete_cognito_s2s.sh my-auth
```

### 配置 Agentcore Gateway

```bash
./utils/setup_agentcore_gateway.sh 
```

## 原生 Lambda 函数改造为 Mcp

参考 native_lambda 中的例子，部署对应的测试MCP Server：

```bash
./utils/add_gateway_target_native_lambda.sh whats-news
```

### 开发一个原生 Lambda MCP

* 在 mcp-sample/native_lambda 中创建一个目录，如 my-test，注意gateway的名字不支持_，因此名字中不要带上_ ：
* 生成 lambda_functions.py 并实现标准 lambda_handler 函数。
* 需要依赖的库文件，填写 requirements.txt。
* 太大的库或不想写在lambda里，可以填写 requirements-layer.txt，自动制作lambda layer。
* 填写 interface.json ，包括mcp说明，输入参数，输出参数等。
* 如果需要额外的权限，生成 execution-policy.json ，赋予相关权限。

### 配置 CloudPerf MCP 查询工具

* 使用以下步骤配置agentcore gateway，可以使用aws_iam或s2s认证方式。

```bash
# 1.init env
python3 -m venv .venv
source .venv/bin/activate

# 2.use aws_iam gateway

./utils/setup_agentcore_gateway_iam.sh s2s-gw
./utils/add_gateway_target_native_lambda.sh cloudperf-mcp s2s-gw

# or 2.use s2s gateway

./utils/setup_cognito_s2s.sh us-east-1 s2s-gw
./utils/setup_agentcore_gateway.sh s2s-gw
./utils/add_gateway_target_native_lambda.sh cloudperf-mcp s2s-gw

# 3.update code if mcp lambda need update
./utils/update_lambda_code.sh cloudperf-mcp s2s-gw

```

* 在 Secret Manager 中，创建 cloudperf- 开头的密钥信息，保存你Cloudperf中的登录账号。如果您有长效的token可以配置cptoken项。

```json
{
  "username": "your-username",
  "password": "your-password",
  "cptoken": ""
}
```

* 在 Lambda mcp-cloudperf-mcp 中，增加以下环境变量，其中 CLOUDPERF_API_LAMBDA 指向您的 CloudPerf 部署的 API Lambda函数名字，如：

```text
键：                     值：
CLOUDPERF_API_LAMBDA     CloudperfStack-apiC855xxx-XlWqxxxxxx
CLOUDPERF_SECRET         cloudperf-mcp
```

* aws_iam 认证方式的 mcp 使用配置（通常给mcp工具使用比较方便）：

```json
    "cloudperf-iam": {
      "command": "uvx",
      "args": [
        "mcp-proxy-for-aws",
        "https://cloudperf-xxxxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        "--service",
        "bedrock-agentcore",
        "--region",
        "us-east-1"
      ],
      "disabled": false
    }
```

* s2s 认证方式的 mcp 使用配置举例（通常给Quick Suite等s2s对接比较方便）：

```json
    "cloudperf-mcp": {
      "command": "bash",
      "args": [
        "/Users/xxxx/mcp-scripts/cloudperf-mcp-proxy.sh"
      ],
      "disabled": false
    }
```

其中刷新s2s脚本 cloudperf-mcp-proxy.sh 如下，参照您的环境配置：

```sh
#!/bin/bash
# Auto-fetch Cognito token and proxy MCP via mcp-remote

TOKEN_ENDPOINT="https://cloudperf-xxxx.auth.us-east-1.amazoncognito.com/oauth2/token"
CLIENT_ID="b1bl5xxxx"
CLIENT_SECRET="19no8uxxxx"
SCOPES="cloudperf-api/read%20cloudperf-api/write"
MCP_URL="https://cloudperf-xxxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"

ACCESS_TOKEN=$(curl -s -X POST "$TOKEN_ENDPOINT" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}&scope=${SCOPES}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

if [ -z "$ACCESS_TOKEN" ]; then
  echo "Failed to obtain access token" >&2
  exit 1
fi

exec npx -y mcp-remote "$MCP_URL" --header "Authorization:Bearer ${ACCESS_TOKEN}"
```

## Mcp Server 一键部署到 Lambda


## 参考

* https://github.com/xina0311/amazon-quick-suite-web-search-integration/