# Lambda部署脚本使用说明

## 前置要求

1. 安装并配置AWS CLI
2. 确保有足够的AWS权限
3. 安装jq命令行工具（用于JSON处理）

## 部署资源

```bash
# 建议使用单独的python环境进行部署
python3 -m venv env
source env/bin/activate

# 使用默认区域 (us-east-1)
./make_lambda_version.sh

# 指定区域
./make_lambda_version.sh --region ap-northeast-1

# 指定区域和自定义域名
./make_lambda_version.sh --region ap-northeast-1 --domain example.com

# 指定区域和自定义域名和Route53 ZoneID（ACM证书会自动完成申请）
./make_lambda_version.sh --region ap-northeast-1 --domain example.com --zoneid XXXX

```

## 访问应用
部署完成后，脚本会输出访问URL，格式如下：
```
https://xxxxxxxxxx.execute-api.region.amazonaws.com?token=secret_token
```

## 清理资源

删除所有部署的资源：
```bash
./remove_lambda_version.sh
```

## 脚本功能

脚本 make_lambda_version.sh 包含以下功能：

* 可以指定部署区域和指定自定义域名，实现上级目录相关文件和 mcp_web.py 在 lambda 上部署运行
* 脚本会对python所需要的依赖，制作合适的lambda layer，并使用aws命令行进行发布
* 脚本会把对应的python代码，使用aws命令行发布lambda
* 脚本会创建api gateway，配置自定义域名，申请acm证书，并绑定到lambda

脚本 remov_lambda_version.sh 完成上述环境的删除