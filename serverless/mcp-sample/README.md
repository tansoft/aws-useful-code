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
./utils/add_gateway_target_native_lambda.sh demo_mcp
```

## Mcp Server 一键部署到 Lambda

参考 mcp2lambda 中的例子，例子可以通过 ./mcp2lambda/setup_agentcore_geteway.sh demo_mcp 进行对应项目的部署。

## 参考

* https://github.com/xina0311/amazon-quick-suite-web-search-integration/