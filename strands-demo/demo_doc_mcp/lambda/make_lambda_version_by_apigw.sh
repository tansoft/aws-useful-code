_#!/bin/bash

# 使用API GW的版本有两个问题，一是没有streaming流式返回，二是接口30秒会超时，没有返回就会报错。

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
# 用于访问授权
VALID_TOKEN=$(cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 18 | head -n 1)
# 本机python版本，用于lambda制作
PYVER=$(python -c 'import sys
ver = sys.version_info
print(str(ver.major)+"."+str(ver.minor))')
ACM_REGION=$REGION

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
LAYER_ARN1=$(make_layer fastapi-mangum-jinja2 $REGION $PYVER $TEMP_DIR fastapi mangum jinja2)
echo "Lambda Layer: $LAYER_ARN1"
echo "制作agent层..."
LAYER_ARN2=$(make_layer strands-agents $REGION $PYVER $TEMP_DIR strands-agents strands-agents-tools)
echo "Lambda Layer: $LAYER_ARN2"

# 2. 准备Lambda代码
echo "准备Lambda代码..."
cp -r ../static ../templates ../mcp_web.py run.sh $TEMP_DIR/
sed -i '1i from mangum import Mangum' $TEMP_DIR/mcp_web.py
echo '
asgi_handler = Mangum(app)

def handler(event, context):
    return asgi_handler(event, context)
' >> $TEMP_DIR/mcp_web.py
touch $TEMP_DIR/__init__.py
cd $TEMP_DIR
zip -r function.zip . -x "python/*"

# 3. 创建Lambda函数 lambda_function.lambda_handler
echo "创建/更新Lambda函数..."
FUNCTION_ARN=$(aws lambda create-function \
    --function-name $FUNCTION_NAME \
    --runtime python$PYVER \
    --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/$ROLE_NAME \
    --handler mcp_web.handler \
    --zip-file fileb://function.zip \
    --timeout 300 \
    --memory-size 256 \
    --layers "$LAYER_ARN1" "$LAYER_ARN2" \
    --region $REGION \
    --environment Variables="{VALID_TOKEN=$VALID_TOKEN,OTEL_SDK_DISABLED=true,SESSION_DIR=/tmp/sessions}" \
    --query 'FunctionArn' --output text 2>/dev/null || \
aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://function.zip \
        --region $REGION \
        --query 'FunctionArn' --output text) && \
VALID_TOKEN=$(aws lambda get-function-configuration --function-name demo-doc-mcp --query 'Environment.Variables.VALID_TOKEN' --output text)
echo "Lambda函数创建/更新完成: $FUNCTION_ARN"
cd - > /dev/null

# 4. 创建API Gateway
echo "查找 API Gateway ..."

API_ID=$(aws apigatewayv2 get-apis \
    --region $REGION \
    --query "Items[?Name=='$API_NAME'].ApiId" --output text)

if [[ -z "$API_ID" || "$API_ID" == "None" ]]; then
    echo "创建 API Gateway ..."
    API_ID=$(aws apigatewayv2 create-api \
        --name $API_NAME \
        --protocol-type HTTP \
        --region $REGION \
        --query 'ApiId' --output text)
fi
echo "API_ID: $API_ID"

# 添加Lambda权限
aws lambda remove-permission \
    --function-name $FUNCTION_NAME \
    --statement-id api-gateway-invoke \
    --region $REGION 2>/dev/null || true

aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id api-gateway-invoke \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$REGION:$(aws sts get-caller-identity --query Account --output text):$API_ID/*/*" \
    --region $REGION

# 检查并创建集成
echo "检查集成..."
INTEGRATION_ID=$(aws apigatewayv2 get-integrations --api-id $API_ID --region $REGION --query 'Items[0].IntegrationId' --output text)

if [[ -n "$INTEGRATION_ID" && "$INTEGRATION_ID" != "None" ]]; then
    echo "已存在集成ID: $INTEGRATION_ID"
    # 更新集成URI确保正确
    aws apigatewayv2 update-integration \
        --api-id $API_ID \
        --integration-id $INTEGRATION_ID \
        --integration-uri $FUNCTION_ARN \
        --integration-type AWS_PROXY \
        --payload-format-version "2.0" \
        --region $REGION
else
    # 创建新集成
    echo "创建新集成..."
    INTEGRATION_ID=$(aws apigatewayv2 create-integration \
        --api-id $API_ID \
        --integration-type AWS_PROXY \
        --integration-uri $FUNCTION_ARN \
        --payload-format-version "2.0" \
        --region $REGION \
        --query 'IntegrationId' --output text)
fi
echo "集成ID: $INTEGRATION_ID"

# 检查并创建默认路由
DEFAULT_ROUTE=$(aws apigatewayv2 get-routes --api-id $API_ID --region $REGION --query 'Items[?RouteKey==`$default`].RouteId' --output text)
if [[ -n "$DEFAULT_ROUTE" && "$DEFAULT_ROUTE" != "None" ]]; then
    echo "更新默认路由: $DEFAULT_ROUTE"
    aws apigatewayv2 update-route \
        --api-id $API_ID \
        --route-id $DEFAULT_ROUTE \
        --target "integrations/$INTEGRATION_ID" \
        --region $REGION
else
    echo "创建默认路由"
    aws apigatewayv2 create-route \
        --api-id $API_ID \
        --route-key '$default' \
        --target "integrations/$INTEGRATION_ID" \
        --region $REGION
fi

# 创建或更新stage
echo "创建/更新阶段..."
STAGE_EXISTS=$(aws apigatewayv2 get-stages --api-id $API_ID --region $REGION --query 'Items[?StageName==`$default`].StageName' --output text 2>/dev/null || echo "None")
if [[ "$STAGE_EXISTS" == "None" || -z "$STAGE_EXISTS" ]]; then
    aws apigatewayv2 create-stage \
        --api-id $API_ID \
        --stage-name '$default' \
        --auto-deploy \
        --region $REGION
    echo "Stage创建完成"
else
    echo "Stage已存在: $STAGE_EXISTS"
fi

API_ENDPOINT=$(aws apigatewayv2 get-api \
    --api-id $API_ID \
    --region $REGION \
    --query 'ApiEndpoint' --output text)

echo "API Gateway: $API_ENDPOINT"

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

        # 检查API Gateway是否已绑定自定义域名
        EXISTING_DOMAIN=$(aws apigatewayv2 get-domain-names \
            --region $REGION \
            --query "Items[?DomainName=='$DOMAIN_NAME'].DomainName" \
            --output text)

        if [[ -n "$EXISTING_DOMAIN" && "$EXISTING_DOMAIN" != "None" ]]; then
            echo "API Gateway已绑定自定义域名: $EXISTING_DOMAIN"
        else
            # 创建自定义域名
            aws apigatewayv2 create-domain-name \
                --domain-name $DOMAIN_NAME \
                --domain-name-configurations CertificateArn=$CERT_ARN \
                --region $REGION
        fi

        # 获取现有映射
        EXISTING_MAPPING=$(aws apigatewayv2 get-api-mappings \
            --domain-name $DOMAIN_NAME \
            --region $REGION \
            --query "Items[?ApiId=='$API_ID'].ApiId" \
            --output text 2>/dev/null || echo "None")
        
        if [[ -n "$EXISTING_MAPPING" && "$EXISTING_MAPPING" != "None" ]]; then
            echo "API映射已存在"
        else
            # 等待stage创建完成
            sleep 2
            # 创建API映射
            echo "创建API映射..."
            aws apigatewayv2 create-api-mapping \
                --domain-name $DOMAIN_NAME \
                --api-id $API_ID \
                --stage '$default' \
                --region $REGION
            echo "API映射创建完成"
        fi

        # 检查Route53上是否存在该域名的记录
        EXISTING_RECORD=$(aws route53 list-resource-record-sets \
            --hosted-zone-id $ROUTE53_ZONEID \
            --region us-east-1 \
            --query "ResourceRecordSets[?Name=='${DOMAIN_NAME}.'].Name" \
            --output text)

        if [[ -n "$EXISTING_RECORD" && "$EXISTING_RECORD" != "None" ]]; then
            echo "域名 $DOMAIN_NAME 在Route53上已有解析记录"
        else
            # 获取自定义域名的目标域名
            TARGET_DOMAIN=$(aws apigatewayv2 get-domain-name \
                --domain-name $DOMAIN_NAME \
                --region $REGION \
                --query 'DomainNameConfigurations[0].ApiGatewayDomainName' \
                --output text)

            if [[ -z "$TARGET_DOMAIN" ]]; then
                echo "无法获取自定义域名的目标域名"
                exit 1
            fi

            APIGW_ZONEID=$(echo '#us-east-2#ZOJJZC49E0EPZ#
#us-east-1#Z1UJRXOUMOOFQ8#
#us-west-1#Z2MUQ32089INYE#
#us-west-2#Z2OJLYMUO9EFXC#
#af-south-1#Z2DHW2332DAMTN#
#ap-east-1#Z3FD1VL90ND7K5#
#ap-south-2#Z0853509Q1135NJ66RUH#
#ap-southeast-3#Z10132843TYUYSLUG4HA3#
#ap-southeast-5#Z0314042F0KBUTZ3X5HF#
#ap-southeast-4#Z092189423Y7RJK61311D#
#ap-south-1#Z3VO1THU9YC4UR#
#ap-northeast-3#Z22ILHG95FLSZ2#
#ap-northeast-2#Z20JF4UZKIW1U8#
#ap-southeast-1#ZL327KTPIQFUL#
#ap-southeast-2#Z2RPCDW04V8134#
#ap-east-2#Z02909591O7FG9Q56HWB1#
#ap-southeast-7#Z048508712PZLK5NKG8R0#
#ap-northeast-1#Z1YSHQZHG15GKL#
#ca-central-1#Z19DQILCV0OWEC#
#ca-west-1#Z04745493436AWVTG1OQY#
#eu-central-1#Z1U9ULNL0V5AJ3#
#eu-west-1#ZLY8HYME6SFDD#
#eu-west-2#ZJ5UAJN8Y3Z2Q#
#eu-south-1#Z3BT4WSQ9TDYZV#
#eu-west-3#Z3KY65QIEKYHQQ#
#eu-south-2#Z02499852UI5HEQ5JVWX3#
#eu-north-1#Z3UWIKFBOOGXPP#
#eu-central-2#Z09222482MK253X48U76H#
#il-central-1#Z07264553HBI44N5X2CKP#
#mx-central-1#Z00020171WIGL5M88SHRM#
#me-south-1#Z20ZBPC0SS8806#
#me-central-1#Z08780021BKYYY8U0YHTV#
#sa-east-1#ZCMLWB8V5SYIT#
' | grep "#$REGION#" | awk -F# '{print $3}')

            if [[ -z "$APIGW_ZONEID" ]]; then
                echo "无法获取自定义域名的目标域名的Route53托管ZoneID，请查看官方文档进行补充：https://docs.aws.amazon.com/general/latest/gr/apigateway.html"
                exit 1
            fi

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
                                "HostedZoneId": "'$APIGW_ZONEID'",
                                "DNSName": "'$TARGET_DOMAIN'",
                                "EvaluateTargetHealth": false
                            }
                        }
                    }]
                }'
        fi
        echo "自定义域名配置完成: https://$DOMAIN_NAME"
    else
        echo "ACM证书申请完成: $CERT_ARN"
        echo "请在DNS中添加验证记录以完成证书验证"
        
        # 等待证书验证（简化版本，实际使用时需要手动验证）
        echo "等待证书验证完成..."
        echo "请手动验证证书后，运行以下命令完成域名配置，并增加域名的cname记录："
        echo "aws apigatewayv2 create-domain-name --domain-name $DOMAIN_NAME --domain-name-configurations CertificateArn=$CERT_ARN --region $REGION"
        echo "aws apigatewayv2 create-api-mapping --domain-name $DOMAIN_NAME --api-id $API_ID --stage '\$default' --region $REGION"
    fi
fi

echo "部署完成！"
echo "API端点: $API_ENDPOINT"
if [[ -n "$DOMAIN_NAME" ]]; then
    echo "访问URL: https://${DOMAIN_NAME}/?token=${VALID_TOKEN}"
else
    echo "访问URL: ${API_ENDPOINT}/?token=${VALID_TOKEN}"
fi

# 保存配置信息
cat > deployment_info.json << EOF
{
    "region": "$REGION",
    "function_name": "$FUNCTION_NAME",
    "layer_name": "$LAYER_ARN1 $LAYER_ARN2",
    "api_id": "$API_ID",
    "domain_name": "$DOMAIN_NAME",
    "cert_arn": "${CERT_ARN:-}",
    "zone_id": "${ROUTE53_ZONEID}"
}
EOF

echo "部署信息已保存到 deployment_info.json"