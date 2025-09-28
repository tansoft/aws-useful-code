#!/bin/bash

set -e

# 默认配置
FUNCTION_NAME="demo-doc-mcp"
REGION="us-east-1"
# 如果需要指定自定义域名，在这里增加
DOMAIN_NAME=""
# 如果需要指定自定义域名托管的Route53 Zone ID，在这里指定，ACM证书申请会自动完成
ROUTE53_ZONEID=""

LAYER_NAME="${FUNCTION_NAME}-layer"
API_NAME="${FUNCTION_NAME}-api"
ROLE_NAME="${FUNCTION_NAME}-role"
POLICY_NAME="${FUNCTION_NAME}-policy"
# 用于访问授权
VALID_TOKEN=$(cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 18 | head -n 1)
PYVER=$(python -c 'import sys
ver = sys.version_info
print(str(ver.major)+"."+str(ver.minor))')


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
    --assume-role-policy-document file://trust-policy.json 2>/dev/null || \
    echo "角色已存在，跳过创建"

# 创建并附加自定义策略
aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name $POLICY_NAME \
    --policy-document file://execution-policy.json || echo '附加策略已经存在，跳过'

# 附加AWS管理的基本执行策略
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole || echo '默认策略已经存在，跳过'

# 1. 创建Lambda Layer
# 查询layer是否存在
# 查询layer是否存在
EXISTING_LAYER=$(aws lambda list-layer-versions \
    --layer-name $LAYER_NAME \
    --region $REGION \
    --query 'LayerVersions[0].LayerVersionArn' \
    --output text 2>/dev/null || echo "")

if [[ -n "$EXISTING_LAYER" ]]; then
    echo "Layer已存在: $EXISTING_LAYER"
    LAYER_ARN=$EXISTING_LAYER
else
    echo "Layer不存在,开始创建..."
    mkdir -p $TEMP_DIR/python
    pip install -r ../requirements.txt -t $TEMP_DIR/python/
    cd $TEMP_DIR
    zip -r layer.zip python/

    LAYER_ARN=$(aws lambda publish-layer-version \
        --layer-name $LAYER_NAME \
        --zip-file fileb://layer.zip \
        --compatible-runtimes python$PYVER \
        --region $REGION \
        --query 'LayerVersionArn' --output text)

    echo "Layer创建完成: $LAYER_ARN"
fi

# 2. 准备Lambda代码
echo "准备Lambda代码..."
cd - > /dev/null
cp -r ../static ../templates ../mcp_web.py $TEMP_DIR/
cd $TEMP_DIR
zip -r function.zip . -x "python/*"

# 3. 创建Lambda函数 lambda_function.lambda_handler
echo "创建/更新Lambda函数..."
FUNCTION_ARN=$(aws lambda create-function \
    --function-name $FUNCTION_NAME \
    --runtime python$PYVER \
    --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/$ROLE_NAME \
    --handler run.sh \
    --zip-file fileb://function.zip \
    --timeout 300 \
    --memory-size 256 \
    --layers "$LAYER_ARN" "arn:aws:lambda:$REGION:753240598075:layer:LambdaAdapterLayerArm64:24" \
    --region $REGION \
    --environment Variables="{AWS_LAMBDA_EXEC_WRAPPER='/opt/bootstrap',AWS_LWA_INVOKE_MODE='response_stream',PORT=9000,VALID_TOKEN=$VALID_TOKEN}" \
    --query 'FunctionArn' --output text 2>/dev/null || \
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://function.zip \
    --region $REGION \
    --query 'FunctionArn' --output text)

echo "Lambda函数创建/更新完成: $FUNCTION_ARN"

# 4. 创建API Gateway
echo "处理 API Gateway ..."

API_ID=$(aws apigatewayv2 create-api \
    --name $API_NAME \
    --protocol-type HTTP \
    --target $FUNCTION_ARN \
    --region $REGION \
    --query 'ApiId' --output text 2>/dev/null || \
aws apigatewayv2 get-apis \
    --region $REGION \
    --query "Items[?Name=='$API_NAME'].ApiId" --output text)

# 添加Lambda权限
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id api-gateway-invoke \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$REGION:$(aws sts get-caller-identity --query Account --output text):$API_ID/*/*" \
    --region $REGION 2>/dev/null || true

API_ENDPOINT=$(aws apigatewayv2 get-api \
    --api-id $API_ID \
    --region $REGION \
    --query 'ApiEndpoint' --output text)

echo "API Gateway: $API_ENDPOINT"

# 5. 配置自定义域名（如果提供）
if [[ -n "$DOMAIN_NAME" ]]; then
    echo "配置自定义域名: $DOMAIN_NAME"
    
    # 申请ACM证书
    CERT_ARN=$(aws acm request-certificate \
        --domain-name $DOMAIN_NAME \
        --validation-method DNS \
        --region $REGION \
        --query 'CertificateArn' --output text)

    if [[ -n "$ROUTE53_ZONEID" ]]; then
        echo "等待证书验证记录生成..."
        sleep 10

        # 获取证书验证记录
        CERT_VALIDATION=$(aws acm describe-certificate \
            --certificate-arn $CERT_ARN \
            --region $REGION \
            --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
            --output text)

        if [[ -n "$CERT_VALIDATION" ]]; then
            # 解析验证记录
            VALIDATION_NAME=$(echo $CERT_VALIDATION | cut -f1)
            VALIDATION_VALUE=$(echo $CERT_VALIDATION | cut -f2)
            
            # 创建Route53验证记录
            aws route53 change-resource-record-sets \
                --hosted-zone-id $ROUTE53_ZONEID \
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
                --region $REGION
                
            echo "证书验证完成"
            
            # 创建自定义域名
            aws apigatewayv2 create-domain-name \
                --domain-name $DOMAIN_NAME \
                --domain-name-configurations CertificateArn=$CERT_ARN \
                --region $REGION
                
            # 创建API映射
            aws apigatewayv2 create-api-mapping \
                --domain-name $DOMAIN_NAME \
                --api-id $API_ID \
                --stage '$default' \
                --region $REGION
                
            # 获取自定义域名的目标域名
            TARGET_DOMAIN=$(aws apigatewayv2 get-domain-name \
                --domain-name $DOMAIN_NAME \
                --region $REGION \
                --query 'DomainNameConfigurations[0].ApiGatewayDomainName' \
                --output text)
                
            # 创建Route53别名记录
            aws route53 change-resource-record-sets \
                --hosted-zone-id $ROUTE53_ZONEID \
                --change-batch '{
                    "Changes": [{
                        "Action": "UPSERT",
                        "ResourceRecordSet": {
                            "Name": "'$DOMAIN_NAME'",
                            "Type": "A",
                            "AliasTarget": {
                                "HostedZoneId": "Z1UJRXOUMOOFQ8",
                                "DNSName": "'$TARGET_DOMAIN'",
                                "EvaluateTargetHealth": false
                            }
                        }
                    }]
                }'
                
            echo "自定义域名配置完成: https://$DOMAIN_NAME"
        fi    
    else
        echo "ACM证书申请完成: $CERT_ARN"
        echo "请在DNS中添加验证记录以完成证书验证"
        
        # 等待证书验证（简化版本，实际使用时需要手动验证）
        echo "等待证书验证完成..."
        echo "请手动验证证书后，运行以下命令完成域名配置："
        echo "aws apigatewayv2 create-domain-name --domain-name $DOMAIN_NAME --domain-name-configurations CertificateArn=$CERT_ARN --region $REGION"
        echo "aws apigatewayv2 create-api-mapping --domain-name $DOMAIN_NAME --api-id $API_ID --stage '\$default' --region $REGION"
    fi
fi

echo "部署完成！"
echo "API端点: $API_ENDPOINT"
if [[ -n "$DOMAIN_NAME" ]]; then
    echo "访问URL: https://${DOMAIN_NAME}?token=${VALID_TOKEN}"
else
    echo "访问URL: ${API_ENDPOINT}?token=${VALID_TOKEN}"
fi

# 保存配置信息
cat > deployment_info.json << EOF
{
    "region": "$REGION",
    "function_name": "$FUNCTION_NAME",
    "layer_name": "$LAYER_NAME",
    "api_name": "$API_NAME",
    "api_id": "$API_ID",
    "api_endpoint": "$API_ENDPOINT",
    "domain_name": "$DOMAIN_NAME",
    "cert_arn": "${CERT_ARN:-}",
    "zone_id": "${ROUTE53_ZONEID}"
}
EOF

echo "部署信息已保存到 deployment_info.json"