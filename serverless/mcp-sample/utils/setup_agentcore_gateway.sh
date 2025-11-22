#!/bin/bash
# "Usage: ./setup_agentcore_gateway.sh <name>"
# 创建 AgentCore Gateway（不包含 Target）
# Target 将由各个 Provider 单独添加

PROJECT=${1:-"base-auth"}

CURPATHCURPATH=$(cd `dirname "${BASH_SOURCE[0]}"`;pwd)
source "${CURPATHCURPATH}/../.${PROJECT}-cognito-s2s.txt"

if [[ -z "$REGION" || -z "$POOL_ID" || -z "$CLIENT_ID" || -z "$DISCOVERY_URL" ]]; then
    echo "错误: .${PROJECT}-cognito-s2s.txt 配置文件中缺少必要参数"
    exit 1
fi

DEFAULT_ROLE="agentcore-gateway-lambda-target-default-role"

create_gateway_role() {
    local account_id=$(aws sts get-caller-identity --query Account --output text)
    
    local assume_role_policy=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "AssumeRolePolicy",
        "Effect": "Allow",
        "Principal": {
            "Service": "bedrock-agentcore.amazonaws.com"
        },
        "Action": "sts:AssumeRole",
        "Condition": {
            "StringEquals": {
                "aws:SourceAccount": "${account_id}"
            },
            "ArnLike": {
                "aws:SourceArn": "arn:aws:bedrock-agentcore:*:${account_id}:*"
            }
        }
    }]
}
EOF
)

    local role_policy=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "VisualEditor0",
        "Effect": "Allow",
        "Action": [
            "lambda:InvokeFunction"
        ],
        "Resource": "*"
    }]
}
EOF
)

    if aws iam get-role --role-name "${DEFAULT_ROLE}" >/dev/null 2>&1; then
        echo "⚠ 角色已存在，使用现有角色: ${DEFAULT_ROLE}"
    else
        aws iam create-role \
            --role-name "${DEFAULT_ROLE}" \
            --assume-role-policy-document "$assume_role_policy" >/dev/null
        echo "✓ 创建 IAM 角色: ${DEFAULT_ROLE}"
        sleep 10
    fi
    
    aws iam put-role-policy \
        --role-name "${DEFAULT_ROLE}" \
        --policy-name "agentcore-gateway-lambda-policy" \
        --policy-document "$role_policy" >/dev/null
}

create_gateway() {
    echo "============================================================"
    echo "创建 AgentCore Gateway"
    echo "============================================================"
    echo
    echo "Region: $REGION"
    echo "Cognito Pool ID: $POOL_ID"
    echo "Client ID: $CLIENT_ID"
    echo

    echo "步骤 1: 创建 Gateway IAM 角色..."
    create_gateway_role
    role_arn=$(aws iam get-role --role-name "${DEFAULT_ROLE}" --query 'Role.Arn' --output text)
    
    echo "步骤 2: 创建 Gateway..."
    
    local gateway_id
    local create_output
    local create_error
    
    # 尝试创建 Gateway，捕获输出和错误
    create_error=$(aws bedrock-agentcore-control create-gateway \
        --name "$PROJECT" \
        --role-arn "$role_arn" \
        --protocol-type "MCP" \
        --authorizer-type "CUSTOM_JWT" \
        --authorizer-configuration "{\"customJWTAuthorizer\":{\"allowedClients\":[\"${CLIENT_ID}\"],\"discoveryUrl\":\"${DISCOVERY_URL}\"}}" \
        --description "Gateway for $PROJECT" \
        --region "$REGION" \
        --query 'gatewayId' --output text 2>&1)
    
    local create_exit_code=$?
    
    if [[ $create_exit_code -eq 0 ]] && [[ -n "$create_error" ]] && [[ "$create_error" != "None" ]]; then
        # 创建成功
        gateway_id="$create_error"
        echo "✓ Gateway 创建成功!"
        echo "  Gateway ID: $gateway_id"
    else
        # 创建失败，检查是否是因为已存在
        if echo "$create_error" | grep -q -i "already exists\|AlreadyExists\|ConflictException"; then
            echo "⚠ Gateway 名称已存在，正在获取现有 Gateway 信息..."
        elif echo "$create_error" | grep -q -i "AccessDeniedException\|not authorized"; then
            echo "✗ 权限不足，无法创建 Gateway"
            echo "  错误信息: $create_error"
            #exit 1
        else
            echo "⚠ Gateway 创建失败，尝试获取现有 Gateway 信息..."
            echo "  错误信息: $create_error"
            exit 1
        fi
        
        local gateways=$(aws bedrock-agentcore-control list-gateways --region "$REGION" --output json 2>&1)
        
        if [[ $? -ne 0 ]]; then
            echo "✗ 无法列出 Gateway: $gateways"
            exit 1
        fi
        
        local gateway_count=$(echo "$gateways" | jq '.items | length' 2>/dev/null)
        
        if [[ -z "$gateway_count" ]] || [[ $gateway_count -eq 0 ]]; then
            echo "✗ 未找到任何 Gateway，且创建失败"
            echo "  请检查权限和配置，或手动创建 Gateway"
            exit 1
        fi
        
        echo "找到 $gateway_count 个 Gateway:"
        echo "$gateways" | jq -r '.items[] | "\(.name // "N/A") - \(.gatewayId // "N/A")"' | nl
        
        gateway_id=$(echo "$gateways" | jq -r --arg project "$PROJECT" '(.items[] | select(.name == $project)) | .gatewayId // "null"')

        if [[ -z "$gateway_id" ]] || [[ "$gateway_id" == "null" ]]; then
            echo "✗ 无法获取有效的 Gateway ID"
            exit 1
        fi
        
        local gateway_name=$(echo "$gateways" | jq -r --arg id "$gateway_id" '.items[] | select(.gatewayId == $id) | .name // "N/A"')
        echo
        echo "✓ 使用现有 Gateway: $gateway_name"
        echo "  Gateway ID: $gateway_id"
    fi
    echo
    
    echo "步骤 3: 等待 Gateway 就绪..."
    local max_attempts=30
    for ((i=1; i<=max_attempts; i++)); do
        local status=$(aws bedrock-agentcore-control get-gateway \
            --gateway-identifier "$gateway_id" \
            --region "$REGION" \
            --query 'status' --output text)
        echo "  当前状态: $status ($i/$max_attempts)"
        
        if [[ "$status" == "AVAILABLE" || "$status" == "READY" ]]; then
            echo "✓ Gateway 已就绪!"
            break
        elif [[ "$status" == "FAILED" || "$status" == "DELETING" ]]; then
            echo "✗ Gateway 状态异常: $status"
            exit 1
        fi
        
        if [[ $i -eq $max_attempts ]]; then
            echo "✗ 等待超时，Gateway 未就绪"
            exit 1
        fi
        
        sleep 5
    done
    echo
    
    echo "步骤 4: 获取 Gateway 信息..."
    local gateway_url=$(aws bedrock-agentcore-control get-gateway \
        --gateway-identifier "$gateway_id" \
        --query 'gatewayUrl' --region "$REGION" --output text)
    echo "✓ Gateway URL: $gateway_url"
    echo
    
    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local gateway_arn="arn:aws:bedrock-agentcore:$REGION:$account_id:gateway/$gateway_id"
    
    echo "步骤 5: 保存配置..."
    cat >> ${CURPATHCURPATH}/../.${PROJECT}-cognito-s2s.txt <<EOF

# Gateway 配置
GATEWAY_ARN=$gateway_arn
GATEWAY_ID=$gateway_id
GATEWAY_URL=$gateway_url
EOF
    echo "✓ 配置已保存到 .${PROJECT}-cognito-s2s.txt"
    echo
    
    echo "============================================================"
    echo "Gateway 创建完成！"
    echo "============================================================"
    echo
    echo "Gateway 信息:"
    echo "  ARN: $gateway_arn"
    echo "  ID: $gateway_id"
    echo "  URL: $gateway_url"
    echo
    echo "下一步可以尝试:"
    echo "  1. 部署 mcp server（Lambda 函数）"
    echo "  2. 将 Lambda 添加为 Gateway Targets"
    echo "  3. 在 Amazon Quick Suite 中配置 MCP Integration"
    echo
    echo "部署 Provider 示例:"
    echo "  ./utils/add_gateway_target_native_lambda.sh demo_mcp"
}

if ! command -v aws &> /dev/null; then
    echo "错误: AWS CLI 未安装"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "错误: jq 未安装"
    exit 1
fi

create_gateway
