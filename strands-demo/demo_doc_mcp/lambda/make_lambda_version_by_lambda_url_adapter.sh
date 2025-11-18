#!/bin/bash

# 该版本是使用 LambdaAdapterLayer 实现，配合 lambda url 实现流式返回

set -e

# 默认配置
FUNCTION_NAME="demo-doc-mcp"
REGION="us-east-1"
# 如果需要指定自定义域名，在这里增加
DOMAIN_NAME=""
# 如果需要指定自定义域名托管的Route53 Zone ID，在这里指定，ACM证书申请会自动完成
ROUTE53_ZONEID=""

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --domain)
            DOMAIN_NAME="$2"
            shift 2
            ;;
        --zoneid)
            ROUTE53_ZONEID="$2"
            shift 2
            ;;
        --help)
            echo "用法: $0 [--region REGION] [--domain DOMAIN_NAME] [--zoneid ROUTE53_ZONEID]"
            echo "  --region: AWS区域 (默认: us-east-1)"
            echo "  --domain: 自定义域名 (可选)"
            echo "  --zoneid: 自定义域名的Route53的托管ZoneID (可选)"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

API_NAME="${FUNCTION_NAME}-api"
ROLE_NAME="${FUNCTION_NAME}-role"
POLICY_NAME="${FUNCTION_NAME}-policy"
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
S3_BUCKET="strands-session-${FUNCTION_NAME}-${ACCOUNT_ID}"
# 用于访问授权
VALID_TOKEN=$(cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 18 | head -n 1)
# 本机python版本，用于lambda制作
PYVER=$(python -c 'import sys
ver = sys.version_info
print(str(ver.major)+"."+str(ver.minor))')
# 本机是 x86 还是 arm
ARCH=$(uname -m)
if [[ "$ARCH" == "x86_64" ]]; then
    ADAPTER_ARCH="arn:aws:lambda:$REGION:753240598075:layer:LambdaAdapterLayerX86:25"
else
    ADAPTER_ARCH="arn:aws:lambda:$REGION:753240598075:layer:LambdaAdapterLayerArm64:24"
fi
ACM_REGION=us-east-1

echo "开始部署到区域: $REGION"
if [[ -n "$DOMAIN_NAME" ]]; then
    echo "自定义域名: $DOMAIN_NAME"
fi

# 创建临时目录
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# 0. 创建IAM角色
aws iam create-role \
    --role-name $ROLE_NAME \
    --region us-east-1 \
    --assume-role-policy-document file://trust-policy.json 2>/dev/null || \
    echo "角色已存在，跳过创建"

# 创建并附加自定义策略
aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name $POLICY_NAME \
    --region us-east-1 \
    --policy-document file://execution-policy.json || echo '附加策略已经存在，跳过'

# 附加AWS管理的基本执行策略
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --region us-east-1 \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole || echo '默认策略已经存在，跳过'

# 生成一个函数
function make_layer() {
    local LAYER_NAME=$1
    local REGION=$2
    local PYVER=$3
    local TEMP_DIR=$4
    local LAYER_ARN=
    shift 4
    # 查询layer是否存在
    local EXISTING_LAYER=$(aws lambda list-layer-versions \
        --layer-name $LAYER_NAME \
        --region $REGION \
        --query 'LayerVersions[0].LayerVersionArn' \
        --output text 2>/dev/null)
    if [[ -z "$EXISTING_LAYER" ]]; then
        echo "制作Lambda Layer出错！！"
    fi
    if [[ "$EXISTING_LAYER" == "None" ]]; then
        #echo "Layer不存在,开始创建..."
        mkdir -p $TEMP_DIR/python
        pip install --only-binary=:all: -t $TEMP_DIR/python/ $@ 2>/tmp/pip.txt 1>&2
        cd $TEMP_DIR
        # for pattern in "__pycache__" "dist-info" "tests" "benchmarks"; do
        for pattern in "__pycache__"; do
            find . -type d -name "$pattern" -exec rm -rf {} + 2>/dev/null 1>&2
        done
        # 如果
        zip -9 -r $LAYER_NAME-layer.zip python/ 2>/dev/null 1>&2

        LAYER_ARN=$(aws lambda publish-layer-version \
            --layer-name $LAYER_NAME \
            --zip-file fileb://$LAYER_NAME-layer.zip \
            --compatible-runtimes python$PYVER \
            --region $REGION \
            --query 'LayerVersionArn' --output text 2>/dev/null)

        rm -f $LAYER_NAME-layer.zip
        #echo "Layer创建完成: $LAYER_ARN"
        cd - > /dev/null
    else
        #echo "Layer已存在: $EXISTING_LAYER"
        LAYER_ARN=$EXISTING_LAYER
    fi
    echo $LAYER_ARN
}

# 1. 创建Lambda Layer
# 单layer超过 70M，分为多个layer，--no-deps xxx
# LAYER_ARN=$(make_layer $FUNCTION_NAME-layer $REGION $PYVER $TEMP_DIR -r ../requirements.txt)
echo "制作web框架层..."
LAYER_ARN1=$(make_layer fastapi-uvicorn-jinja2 $REGION $PYVER $TEMP_DIR fastapi uvicorn pydantic python-multipart jinja2)
echo "Lambda Layer: $LAYER_ARN1"
echo "制作strands-agents层..."
LAYER_ARN2=$(make_layer strands-agents $REGION $PYVER $TEMP_DIR mcp strands-agents strands-agents-tools)
echo "Lambda Layer: $LAYER_ARN2"

# 2. 准备Lambda代码
echo "准备Lambda代码..."
cp -r ../static ../templates ../mcp_web.py ../role_config.py run.sh $TEMP_DIR/
touch $TEMP_DIR/__init__.py
cd $TEMP_DIR
zip -r function.zip . -x "python/*"

# 3. 创建Lambda函数 lambda_function.lambda_handler
if aws s3 ls "s3://$S3_BUCKET" --region $REGION >/dev/null 2>&1; then
    echo "S3桶 $S3_BUCKET 已经创建"
else
    echo "创建保存session的S3桶 $S3_BUCKET"
    # 兼容美东一的创建s3桶方法
    ([ "$REGION" == "us-east-1" ] && aws s3api create-bucket --bucket "$S3_BUCKET" --region $REGION || aws s3api create-bucket --bucket "$S3_BUCKET" --region $REGION --create-bucket-configuration LocationConstraint="$REGION")
fi

echo "创建/更新Lambda函数..."
FUNCTION_ARN=$(aws lambda create-function \
    --function-name $FUNCTION_NAME \
    --runtime python$PYVER \
    --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/$ROLE_NAME \
    --handler run.sh \
    --zip-file fileb://function.zip \
    --timeout 300 \
    --memory-size 256 \
    --layers "$LAYER_ARN1" "$LAYER_ARN2" "$ADAPTER_ARCH" \
    --region $REGION \
    --environment Variables="{AWS_LAMBDA_EXEC_WRAPPER='/opt/bootstrap',AWS_LWA_INVOKE_MODE='response_stream',PORT=9000,VALID_TOKEN=$VALID_TOKEN,OTEL_SDK_DISABLED=true,SESSION_DIR=s3://$S3_BUCKET}/" \
    --query 'FunctionArn' --output text 2>/dev/null || \
aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://function.zip \
        --region $REGION \
        --query 'FunctionArn' --output text) && \
VALID_TOKEN=$(aws lambda get-function-configuration --function-name demo-doc-mcp --query 'Environment.Variables.VALID_TOKEN' --output text)
echo "Lambda函数创建/更新完成: $FUNCTION_ARN"
cd - > /dev/null

# 4. 创建Lambda URL
echo "获取 Lambda URL..."
LAMBDA_URL=$(aws lambda get-function-url-config \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query 'FunctionUrl' \
    --output text 2>/dev/null || echo "")
if [[ -z "$LAMBDA_URL" || "$LAMBDA_URL" == "None" ]]; then
    echo "Lambda URL 不存在，正在创建..."
    LAMBDA_URL=$(aws lambda create-function-url-config \
        --function-name $FUNCTION_NAME \
        --auth-type AWS_IAM \
        --invoke-mode RESPONSE_STREAM \
        --region $REGION \
        --query 'FunctionUrl' \
        --output text)
fi
echo "Lambda URL: $LAMBDA_URL"

# 提取域名部分（去掉 https:// 和路径）
LAMBDA_DOMAIN=$(echo $LAMBDA_URL | sed 's|https://||' | sed 's|/.*||')

# 5. 配置自定义域名（如果提供）
if [[ -n "$DOMAIN_NAME" ]]; then
    echo "配置自定义域名: $DOMAIN_NAME"
    # 判断是否已经有该域名的ACM证书
    EXISTING_CERT_ARN=$(aws acm list-certificates \
        --region $ACM_REGION \
        --query "CertificateSummaryList[?DomainName=='$DOMAIN_NAME'].CertificateArn" \
        --output text)

    if [[ -n "$EXISTING_CERT_ARN" && "$EXISTING_CERT_ARN" != "None" ]]; then
        echo "已存在该域名的ACM证书: $EXISTING_CERT_ARN"
        CERT_ARN=$EXISTING_CERT_ARN
    else
        # 申请ACM证书
        CERT_ARN=$(aws acm request-certificate \
            --domain-name $DOMAIN_NAME \
            --validation-method DNS \
            --region $ACM_REGION \
            --query 'CertificateArn' --output text)
    fi

    if [[ -n "$ROUTE53_ZONEID" ]]; then
        # 获取证书状态
        CERT_STATUS=$(aws acm describe-certificate \
            --certificate-arn $CERT_ARN \
            --region $ACM_REGION \
            --query 'Certificate.Status' \
            --output text)

        if [[ "$CERT_STATUS" == "PENDING_VALIDATION" ]]; then
            echo "证书状态: 待验证，等待证书验证记录生成..."
            sleep 2
            # 获取证书验证记录
            CERT_VALIDATION=$(aws acm describe-certificate \
                --certificate-arn $CERT_ARN \
                --region $ACM_REGION \
                --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
                --output text)

            if [[ -n "$CERT_VALIDATION" ]]; then
                # 解析验证记录
                VALIDATION_NAME=$(echo $CERT_VALIDATION | awk '{print $1}')
                VALIDATION_VALUE=$(echo $CERT_VALIDATION | awk '{print $3}')
                echo "证书验证信息: $VALIDATION_NAME CNAME $VALIDATION_VALUE"

                # 创建Route53验证记录
                aws route53 change-resource-record-sets \
                    --hosted-zone-id $ROUTE53_ZONEID \
                    --region us-east-1 \
                    --change-batch '{
                        "Changes": [{
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "Name": "'$VALIDATION_NAME'",
                                "Type": "CNAME",
                                "TTL": 300,
                                "ResourceRecords": [{
                                    "Value": "'$VALIDATION_VALUE'"
                                }]
                            }
                        }]
                    }'
                    
                echo "DNS验证记录已添加,等待验证完成..."
                
                # 等待证书验证完成
                aws acm wait certificate-validated \
                    --certificate-arn $CERT_ARN \
                    --region $ACM_REGION
                    
                echo "证书验证完成"
            fi
        else
            echo "证书状态: $CERT_STATUS"
            # 证书已验证,跳过验证流程
        fi
    fi
fi

# 6. 创建 CloudFront
echo "获取 Origin Access Control..."
OAC_NAME="oac-${FUNCTION_NAME}"
OAC_ID=$(aws cloudfront list-origin-access-controls \
    --query "OriginAccessControlList.Items[?Name=='$OAC_NAME'].Id" \
    --region us-east-1 \
    --output text 2>/dev/null || echo "")
if [[ -z "$OAC_ID" || "$OAC_ID" == "None" ]]; then
    echo "OAC 不存在，正在创建..."
    cat > /tmp/oac-config.json << EOF
{
    "Name": "$OAC_NAME",
    "Description": "OAC for Lambda URL $FUNCTION_NAME",
    "OriginAccessControlOriginType": "lambda",
    "SigningBehavior": "always",
    "SigningProtocol": "sigv4"
}
EOF
    OAC_ID=$(aws cloudfront create-origin-access-control \
        --origin-access-control-config file:///tmp/oac-config.json \
        --query 'OriginAccessControl.Id' \
        --region us-east-1 \
        --output text)
    rm -f /tmp/oac-config.json
fi
echo "OAC ID: $OAC_ID"

echo "创建 CloudFront 分发..."
CALLER_REFERENCE="cf-${FUNCTION_NAME}-$(date +%s)"

# 构建分发配置
cat > /tmp/distribution-config.json << EOF
{
    "CallerReference": "$CALLER_REFERENCE",
    "Comment": "CloudFront distribution for Lambda URL $FUNCTION_NAME",
    "DefaultCacheBehavior": {
        "TargetOriginId": "lambda-origin",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": {
            "Quantity": 7,
            "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
            "CachedMethods": {
                "Quantity": 2,
                "Items": ["GET", "HEAD"]
            }
        },
        "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
        "OriginRequestPolicyId": "b689b0a8-53d0-40ab-baf2-68738e2966ac",
        "Compress": true
    },
    "Origins": {
        "Quantity": 1,
        "Items": [
            {
                "Id": "lambda-origin",
                "DomainName": "$LAMBDA_DOMAIN",
                "CustomOriginConfig": {
                    "HTTPPort": 80,
                    "HTTPSPort": 443,
                    "OriginProtocolPolicy": "https-only",
                    "OriginSslProtocols": {
                        "Quantity": 1,
                        "Items": ["TLSv1.2"]
                    }
                },
                "OriginAccessControlId": "$OAC_ID"
            }
        ]
    },
    "Enabled": true,
    "PriceClass": "PriceClass_All"
}
EOF

# 如果有自定义域名，添加 CNAME 配置
if [[ -n "$DOMAIN_NAME" ]]; then
    # 更新分发配置以包含自定义域名
    jq --arg domain "$DOMAIN_NAME" --arg cert "$CERT_ARN" \
        '.Aliases = {"Quantity": 1, "Items": [$domain]} | 
         .ViewerCertificate = {
            "ACMCertificateArn": $cert,
            "SSLSupportMethod": "sni-only",
            "MinimumProtocolVersion": "TLSv1.2_2021"
         }' /tmp/distribution-config.json > /tmp/distribution-config-updated.json
    mv /tmp/distribution-config-updated.json /tmp/distribution-config.json
fi

# 创建分发
DISTRIBUTION_ID=$(aws cloudfront create-distribution \
    --distribution-config file:///tmp/distribution-config.json \
    --query 'Distribution.Id' \
    --region us-east-1 \
    --output text)
rm -f /tmp/distribution-config.json

echo "CloudFront 分发 ID: $DISTRIBUTION_ID"

# 获取分发域名
DISTRIBUTION_DOMAIN=$(aws cloudfront get-distribution \
    --id $DISTRIBUTION_ID \
    --query 'Distribution.DomainName' \
    --region us-east-1 \
    --output text)

# 添加 DNS 解释
if [[ -n "$DOMAIN_NAME" ]]; then
    # 检查Route53上是否存在该域名的记录
    EXISTING_RECORD=$(aws route53 list-resource-record-sets \
        --hosted-zone-id $ROUTE53_ZONEID \
        --query "ResourceRecordSets[?Name=='${DOMAIN_NAME}.'].Name" \
        --output text)

    if [[ -n "$EXISTING_RECORD" && "$EXISTING_RECORD" != "None" ]]; then
        echo "域名 $DOMAIN_NAME 在Route53上已有解析记录"
    else
        # 创建Route53别名记录
        aws route53 change-resource-record-sets \
            --hosted-zone-id $ROUTE53_ZONEID \
            --region us-east-1 \
            --change-batch '{
                "Changes": [{
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": "'$DOMAIN_NAME'",
                        "Type": "A",
                        "AliasTarget": {
                            "HostedZoneId": "Z2FDTNDATAQYW2",
                            "DNSName": "'$DISTRIBUTION_DOMAIN'",
                            "EvaluateTargetHealth": false
                        }
                    }
                }]
            }'
    fi
    echo "自定义域名配置完成: https://$DOMAIN_NAME"
fi

# 6. 为 Lambda 添加 CloudFront 调用权限
echo "添加 CloudFront 调用权限..."
DISTRIBUTION_ARN="arn:aws:cloudfront::$ACCOUNT_ID:distribution/$DISTRIBUTION_ID"
echo "DISTRIBUTION_ID: ${DISTRIBUTION_ID}"

aws lambda add-permission \
    --statement-id "AllowCloudFrontServicePrincipal" \
    --action "lambda:InvokeFunctionUrl" \
    --principal "cloudfront.amazonaws.com" \
    --source-arn "$DISTRIBUTION_ARN" \
    --region $REGION \
    --function-name $FUNCTION_NAME || echo "权限可能已存在"

# 等待分发部署完成
echo "等待 CloudFront 分发部署完成..."
echo "这可能需要 10-15 分钟..."

aws cloudfront wait distribution-deployed --id $DISTRIBUTION_ID --region us-east-1

echo "部署完成！"
echo "  Lambda 函数: $FUNCTION_NAME"
echo "  Lambda URL: $LAMBDA_URL"
echo "  OAC ID: $OAC_ID"
echo "  CloudFront 分发 ID: $DISTRIBUTION_ID"

echo " CloudFront域名: $DISTRIBUTION_DOMAIN"
if [[ -n "$DOMAIN_NAME" ]]; then
    echo "访问URL: https://${DOMAIN_NAME}/?token=${VALID_TOKEN}"
else
    echo "访问URL: https://${DISTRIBUTION_DOMAIN}/?token=${VALID_TOKEN}"
fi

# 保存配置信息
cat > deployment_info.json << EOF
{
    "region": "$REGION",
    "function_name": "$FUNCTION_NAME",
    "s3_bucket": "$S3_BUCKET",
    "layer_name": "$LAYER_ARN1 $LAYER_ARN2",
    "distribution_id": "$DISTRIBUTION_ID",
    "oac_id": "$OAC_ID",
    "domain_name": "$DOMAIN_NAME",
    "cert_arn": "${CERT_ARN:-}",
    "zone_id": "${ROUTE53_ZONEID}"
}
EOF

echo "部署信息已保存到 deployment_info.json"