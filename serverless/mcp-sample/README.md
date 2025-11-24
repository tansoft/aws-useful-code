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
* 生成 lambda_handler.py 并实现标准 handler 函数。
* 需要依赖的库文件，填写 requirements.txt。
* 太大的库或不想写在lambda里，可以填写 requirements-layer.txt，自动制作lambda layer。
* 填写 interface.json ，包括mcp说明，输入参数，输出参数等。
* 如果需要额外的权限，生成 execution-policy.json ，赋予相关权限。

## Mcp Server 一键部署到 Lambda


## 参考

* https://github.com/xina0311/amazon-quick-suite-web-search-integration/