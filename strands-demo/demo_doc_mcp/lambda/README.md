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
./make_lambda_version_by_lambda_url_adapter.sh

# 指定区域
./make_lambda_version_by_lambda_url_adapter.sh --region ap-northeast-1

# 指定区域和自定义域名
./make_lambda_version_by_lambda_url_adapter.sh --region ap-northeast-1 --domain example.com

# 指定区域和自定义域名和Route53 ZoneID（ACM证书会自动完成申请）
./make_lambda_version_by_lambda_url_adapter.sh --region ap-northeast-1 --domain example.com --zoneid XXXX

```

## 访问应用
部署完成后，脚本会输出访问URL，格式如下：
```
https://xxxxxxxx.cloudfront.net/?token=secret_token
```

## 更新资源

脚本在大部分情况都会判断资源是否存在，存在则跳过创建。

lambda修改后可以直接运行部署更新，layer建议修改脚本增加对应库后，在控制台删除原layer，会自动重新创建。

## 清理资源

删除所有部署的资源：
```bash
./remove_lambda_version.sh
```

## 脚本功能

脚本 make_lambda_version_by_lambda_url_adapter.sh 包含以下功能：

* 可以指定部署区域和指定自定义域名，实现上级目录相关文件和 mcp_web.py 在 lambda 上部署运行
* 脚本会对python所需要的依赖，制作合适的lambda layer，并使用aws命令行进行发布
* 脚本会把对应的python代码，使用aws命令行发布lambda
* 脚本会创建带IAM授权的Lambda Url，配置CloudFront，可以配置自定义域名，自动申请acm证书，并绑定到CloudFront

脚本 remov_lambda_version.sh 完成上述环境的删除

脚本 *by_apigw* 的版本不推荐，因为没有流式输出，会超时