# 本项目提供快速部署mcp运行环境的演示

## 安装

依赖 jq aws 命令行

### 配置 Cognito 身份验证池

```bash
#./utils/setup_cognito_s2s.sh <region> <name>
./utils/setup_cognito_s2s.sh us-east-1 my-auth
```

### 测试授权

```bash
./utils/test_cognito_s2s.sh my-auth
```

## 清理

```bash
./utils/delete_cognito_s2s.sh my-auth
```