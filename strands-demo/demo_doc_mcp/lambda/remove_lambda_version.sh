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
API_ID=$(jq -r '.api_id' $CONFIG_FILE)
DISTRIBUTION_ID=$(jq -r '.distribution_id' $CONFIG_FILE)
OAC_ID=$(jq -r '.oac_id' $CONFIG_FILE)
DOMAIN_NAME=$(jq -r '.domain_name' $CONFIG_FILE)
CERT_ARN=$(jq -r '.cert_arn' $CONFIG_FILE)
ROUTE53_ZONEID=$(jq -r '.zone_id' $CONFIG_FILE)

echo "开始清理部署资源..."
echo "区域: $REGION"

# 0. 删除Cloudfront
if [[ "$DISTRIBUTION_ID" != "null" && -n "$DISTRIBUTION_ID" ]]; then
    echo "删除CloudFront分发配置: $DISTRIBUTION_ID"
    aws cloudfront delete-distribution --region us-east-1 \
        --id $DISTRIBUTION_ID 2>/dev/null || echo "CloudFront分发配置删除失败或不存在"
fi
if [[ "$OAC_ID" != "null" && -n "$OAC_ID" ]]; then
    echo "删除OAC配置：$OAC_ID"
    aws cloudfront delete-origin-access-control \
        --id $OAC_ID \
        --region us-east-1 2>/dev/null || echo "OAC配置删除失败或不存在"
fi

# 1. 删除自定义域名配置（如果存在）
if [[ "$DOMAIN_NAME" != "null" && -n "$DOMAIN_NAME" ]]; then
    echo "删除自定义域名配置: $DOMAIN_NAME"

    if [[ "$API_ID" != "null" && -n "$API_ID" ]]; then
        # 删除API映射
        echo "删除API映射..."
        aws apigatewayv2 delete-api-mapping \
            --domain-name $DOMAIN_NAME \
            --api-mapping-id $(aws apigatewayv2 get-api-mappings --domain-name $DOMAIN_NAME --region $REGION --query 'Items[0].ApiMappingId' --output text) \
            --region $REGION 2>/dev/null || echo "API映射删除失败或不存在"
        
        # 删除域名
        echo "删除API GW自定义域名..."
        aws apigatewayv2 delete-domain-name \
            --domain-name $DOMAIN_NAME \
            --region $REGION 2>/dev/null || echo "域名删除失败或不存在"
        
        ACM_REGION=$REGION
    else
        ACM_REGION=us-east-1
    fi

    # 删除ACM证书
    if [[ "$CERT_ARN" != "null" && -n "$CERT_ARN" ]]; then
        # 如果存在Route53 ZONEID，需要删除Route53的域名解释记录，和ACM证书的验证记录
        if [[ "$ROUTE53_ZONEID" != "null" && -n "$ROUTE53_ZONEID" ]]; then
            # 删除域名解析记录
            echo "删除域名记录..."
            aws route53 list-resource-record-sets \
                --hosted-zone-id $ROUTE53_ZONEID \
                --region us-east-1 \
                --query "ResourceRecordSets[?Name == '$DOMAIN_NAME.']" \
                | jq -c '.[]' \
                | while read -r record; do
                    aws route53 change-resource-record-sets \
                        --hosted-zone-id $ROUTE53_ZONEID \
                        --region us-east-1 \
                        --change-batch "{\"Changes\":[{\"Action\":\"DELETE\",\"ResourceRecordSet\":$record}]}" \
                        2>/dev/null || echo "Route53记录删除失败或不存在"
            done

            # 删除ACM证书验证记录
            echo "删除ACM验证记录..."
            aws route53 list-resource-record-sets \
                --hosted-zone-id $ROUTE53_ZONEID \
                --region us-east-1 \
                --query "ResourceRecordSets[?contains(Name, '_acm-challenge')]" \
                | jq -c '.[]' \
                | while read -r record; do
                    aws route53 change-resource-record-sets \
                        --hosted-zone-id $ROUTE53_ZONEID \
                        --region us-east-1 \
                        --change-batch "{\"Changes\":[{\"Action\":\"DELETE\",\"ResourceRecordSet\":$record}]}" \
                        2>/dev/null || echo "ACM验证记录删除失败或不存在"
            done
        fi        

        echo "删除证书..."
        aws acm delete-certificate \
            --certificate-arn $CERT_ARN \
            --region $ACM_REGION 2>/dev/null || echo "证书删除失败或不存在"
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

function delete_layer() {
    local LAYER_NAME=$1
    local REGION=$2
    local version=
    local LAYER_VERSIONS=$(aws lambda list-layer-versions \
        --layer-name $LAYER_NAME \
        --region $REGION \
        --query 'LayerVersions[].Version' \
        --output text 2>/dev/null || echo "")

    if [[ -n "$LAYER_VERSIONS" ]]; then
        for version in $LAYER_VERSIONS; do
            echo "删除Lambda Layer版本: $LAYER_NAME $version"
            aws lambda delete-layer-version \
                --layer-name $LAYER_NAME \
                --version-number $version \
                --region $REGION 2>/dev/null || echo "Layer版本 $version 删除失败"
        done
    else
        echo "未找到Layer版本或Layer不存在"
    fi
}

# 4. 删除Lambda Layer的所有版本
echo "删除Lambda Layer: $LAYER_NAME"
for pattern in $LAYER_NAME; do
    delete_layer $pattern $REGION

# 5. 删除策略和角色
aws iam list-role-policies \
    --role-name $ROLE_NAME \
    --region $REGION \
    | jq -r '.PolicyNames[]' \
    | while read -r policy_name; do
        echo "删除策略：$policy_name"
        aws iam delete-role-policy \
            --role-name $ROLE_NAME \
            --policy-name $policy_name \
            --region $REGION 2>/dev/null || echo "策略 $policy_name 删除失败或不存在"
    done

echo "删除角色：$ROLE_NAME"
aws iam delete-role \
        --role-name $ROLE_NAME \
        --region $REGION 2>/dev/null || echo "角色 $ROLE_NAME 删除失败或不存在"

# 6. 删除配置文件
echo "删除配置文件: $CONFIG_FILE"
read -p "确认删除配置文件吗？(y/n) " -n 1 -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "取消删除配置文件"
    exit 0
fi
rm -f $CONFIG_FILE

echo "清理完成！"
echo "所有相关AWS资源已删除"