#!/bin/bash

set -e

# 默认配置文件
CONFIG_FILE="deployment_info.json"

# 检查配置文件是否存在
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "错误: 找不到部署配置文件 $CONFIG_FILE"
    echo "请确保在部署目录中运行此脚本"
    exit 1
fi

# 读取配置信息
REGION=$(jq -r '.region' $CONFIG_FILE)
FUNCTION_NAME=$(jq -r '.function_name' $CONFIG_FILE)
LAYER_NAME=$(jq -r '.layer_name' $CONFIG_FILE)
API_NAME=$(jq -r '.api_name' $CONFIG_FILE)
API_ID=$(jq -r '.api_id' $CONFIG_FILE)
DOMAIN_NAME=$(jq -r '.domain_name' $CONFIG_FILE)
CERT_ARN=$(jq -r '.cert_arn' $CONFIG_FILE)
ROUTE53_ZONEID=$(jq -r '.zone_id' $CONFIG_FILE)

echo "开始清理部署资源..."
echo "区域: $REGION"

# 1. 删除自定义域名配置（如果存在）
if [[ "$DOMAIN_NAME" != "null" && -n "$DOMAIN_NAME" ]]; then
    echo "删除自定义域名配置: $DOMAIN_NAME"
    
    # 删除API映射
    aws apigatewayv2 delete-api-mapping \
        --domain-name $DOMAIN_NAME \
        --api-mapping-id $(aws apigatewayv2 get-api-mappings --domain-name $DOMAIN_NAME --region $REGION --query 'Items[0].ApiMappingId' --output text) \
        --region $REGION 2>/dev/null || echo "API映射删除失败或不存在"
    
    # 删除域名
    aws apigatewayv2 delete-domain-name \
        --domain-name $DOMAIN_NAME \
        --region $REGION 2>/dev/null || echo "域名删除失败或不存在"

    # 删除ACM证书
    if [[ "$CERT_ARN" != "null" && -n "$CERT_ARN" ]]; then
        # 如果存在Route53 ZONEID，需要删除Route53的域名解释记录，和ACM证书的验证记录
        if [[ "$ROUTE53_ZONEID" != "null" && -n "$ROUTE53_ZONEID" ]]; then
            # 删除域名解析记录
            echo("删除域名记录...")
            aws route53 list-resource-record-sets \
                --hosted-zone-id $ROUTE53_ZONEID \
                --query "ResourceRecordSets[?Name == '$DOMAIN_NAME.']" \
                | jq -c '.[]' \
                | while read -r record; do
                    aws route53 change-resource-record-sets \
                        --hosted-zone-id $ROUTE53_ZONEID \
                        --change-batch "{\"Changes\":[{\"Action\":\"DELETE\",\"ResourceRecordSet\":$record}]}" \
                        --region $REGION 2>/dev/null || echo "Route53记录删除失败或不存在"
            done

            # 删除ACM证书验证记录
            echo("删除ACM验证记录...")
            aws route53 list-resource-record-sets \
                --hosted-zone-id $ROUTE53_ZONEID \
                --query "ResourceRecordSets[?contains(Name, '_acm-challenge')]" \
                | jq -c '.[]' \
                | while read -r record; do
                    aws route53 change-resource-record-sets \
                        --hosted-zone-id $ROUTE53_ZONEID \
                        --change-batch "{\"Changes\":[{\"Action\":\"DELETE\",\"ResourceRecordSet\":$record}]}" \
                        --region $REGION 2>/dev/null || echo "ACM验证记录删除失败或不存在"
            done
        fi        

        aws acm delete-certificate \
            --certificate-arn $CERT_ARN \
            --region $REGION 2>/dev/null || echo "证书删除失败或不存在"
    fi
fi

# 2. 删除API Gateway
if [[ "$API_ID" != "null" && -n "$API_ID" ]]; then
    echo "删除API Gateway: $API_ID"
    aws apigatewayv2 delete-api \
        --api-id $API_ID \
        --region $REGION 2>/dev/null || echo "API Gateway删除失败或不存在"
fi

# 3. 删除Lambda函数
echo "删除Lambda函数: $FUNCTION_NAME"
aws lambda delete-function \
    --function-name $FUNCTION_NAME \
    --region $REGION 2>/dev/null || echo "Lambda函数删除失败或不存在"

# 4. 删除Lambda Layer的所有版本
echo "删除Lambda Layer: $LAYER_NAME"
LAYER_VERSIONS=$(aws lambda list-layer-versions \
    --layer-name $LAYER_NAME \
    --region $REGION \
    --query 'LayerVersions[].Version' \
    --output text 2>/dev/null || echo "")

if [[ -n "$LAYER_VERSIONS" ]]; then
    for version in $LAYER_VERSIONS; do
        aws lambda delete-layer-version \
            --layer-name $LAYER_NAME \
            --version-number $version \
            --region $REGION 2>/dev/null || echo "Layer版本 $version 删除失败"
    done
else
    echo "未找到Layer版本或Layer不存在"
fi

# 5. 删除配置文件
echo "删除配置文件: $CONFIG_FILE"
rm -f $CONFIG_FILE

echo "清理完成！"
echo "所有相关AWS资源已删除"