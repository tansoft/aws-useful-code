#!/bin/bash
# 删除 AgentCore Gateway 及其所有资源

PROJECT=${1:-"base-auth"}

set -e

CURPATH=$(cd `dirname "${BASH_SOURCE[0]}"`;pwd)
CONFIG_FILE="${CURPATH}/../.${PROJECT}-cognito-s2s.txt"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "错误: 配置文件 $CONFIG_FILE 不存在"
    exit 1
fi

source "$CONFIG_FILE"

if [[ -z "$REGION" || -z "$GATEWAY_ID" ]]; then
    echo "错误: 配置文件中缺少 REGION 或 GATEWAY_ID"
    exit 1
fi

echo "============================================================"
echo "删除 AgentCore Gateway: $PROJECT"
echo "============================================================"
echo "Gateway ID: $GATEWAY_ID"
echo "Region: $REGION"
echo

# 删除所有 Gateway Targets
echo "步骤 1: 删除 Gateway Targets..."
TARGETS=$(aws bedrock-agentcore-control list-gateway-targets \
    --gateway-identifier "$GATEWAY_ID" \
    --region "$REGION" \
    --query 'items[].targetId' --output text 2>/dev/null || echo "")

if [[ -n "$TARGETS" ]]; then
    for target_id in $TARGETS; do
        echo "  删除 Target: $target_id"
        aws bedrock-agentcore-control delete-gateway-target \
            --gateway-identifier "$GATEWAY_ID" \
            --target-identifier "$target_id" \
            --region "$REGION" >/dev/null 2>&1 || echo "    ⚠ Target 删除失败或已不存在"
    done
    echo "✓ 所有 Targets 已删除"
else
    echo "✓ 未找到 Targets"
fi
echo

# 删除 Gateway
echo "步骤 2: 删除 Gateway..."
aws bedrock-agentcore-control delete-gateway \
    --gateway-identifier "$GATEWAY_ID" \
    --region "$REGION" >/dev/null 2>&1 && echo "✓ Gateway 已删除" || echo "⚠ Gateway 删除失败或已不存在"
echo

# 不删除 IAM 角色了，IAM角色是全局共用的
# 删除 IAM 角色
# echo "步骤 3: 删除 IAM 角色..."
#ROLE_NAME="agentcore-gateway-lambda-target-default-role"
#aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name "AgentCoreGatewayPolicy" >/dev/null 2>&1 || echo "  ⚠ 角色策略删除失败或已不存在"
#aws iam delete-role --role-name "$ROLE_NAME" >/dev/null 2>&1 && echo "✓ IAM 角色已删除" || echo "⚠ IAM 角色删除失败或已不存在"
#echo

# 清理配置文件中的 GATEWAY_ 设置
echo "步骤 4: 清理配置文件..."
sed -i '/^# Gateway 配置$/,/^GATEWAY_/d' "$CONFIG_FILE"
sed -i '/^GATEWAY_/d' "$CONFIG_FILE"
echo "✓ 配置文件已清理"
echo

echo "============================================================"
echo "Gateway 删除完成！"
echo "============================================================"
