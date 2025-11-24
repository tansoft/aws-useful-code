#!/bin/bash
# ============================================================================
# 通用脚本：添加新的 MCP Server 到 AgentCore Gateway
# ============================================================================
# 
# 使用方法：
# ./add_gateway_target_native_lambda.sh <mcp_name> [<project>]
#
# 示例：
# ./add_gateway_target_native_lambda.sh whats_news
#
# ============================================================================

set -e

if [ $# -lt 1 ]; then
    echo "./add_gateway_target_native_lambda.sh <mcp_name> [<project>]"
    exit 1
fi

MCP_SERVER=${1}
PROJECT=${2:-"base-auth"}

CURPATHCURPATH=$(cd `dirname "${BASH_SOURCE[0]}"`;pwd)
source "${CURPATHCURPATH}/../.${PROJECT}-cognito-s2s.txt"

if [[ -z "$REGION" || -z "$GATEWAY_ID" ]]; then
    echo "错误: .${PROJECT}-cognito-s2s.txt 配置文件中缺少必要参数，请先配置 cognito，再配置 agentcore_gateway，再运行本程序！"
    exit 1
fi

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "Gateway ID: $GATEWAY_ID"
echo ""

echo ""
echo "[步骤 1/3] 验证 Lambda 函数..."

TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

MCPPROJECTPATH="${CURPATHCURPATH}/../native_lambda/${MCP_SERVER}"

# 本机python版本
PYVER=$(python -c 'import sys
ver = sys.version_info
print(str(ver.major)+"."+str(ver.minor))')
# 本机是 x86 还是 arm
ARCH=$(uname -m)

# 判断目录中是否有 requirements-layer.txt，如果有需要先制作层文件
if [ -f "${MCPPROJECTPATH}/requirements-layer.txt" ]; then
    echo "制作依赖层 requirements-layer.txt"

    # 默认会在名字后增加python版本和架构，如果需要去掉屏蔽这一行
    LAYER_NAME="${MCP_SERVER}-layer-py${PYVER//./}-${ARCH}"

    local EXISTING_LAYER=$(aws lambda list-layer-versions \
        --layer-name $LAYER_NAME \
        --region $REGION \
        --query 'LayerVersions[0].LayerVersionArn' \
        --output text 2>/dev/null)
    if [[ -z "$EXISTING_LAYER" ]]; then
        echo "制作Lambda Layer出错！！"
        exit 1
    fi
    if [[ "$EXISTING_LAYER" == "None" ]]; then
      mkdir -p $TEMP_DIR/python
      pip install --only-binary=:all: -t $TEMP_DIR/python/ -r ${MCPPROJECTPATH}/requirements-layer.txt
      cd $TEMP_DIR/
      # 考虑删减库的总体积，lambda layer有大小要求
      # for pattern in "__pycache__" "dist-info" "tests" "benchmarks"; do
      for pattern in "__pycache__"; do
          find . -type d -name "$pattern" -exec rm -rf {} + 2>/dev/null 1>&2
      done
      zip -9 -r $LAYER_NAME-layer.zip python/ 2>/dev/null 1>&2

      LAYER_ARN=$(aws lambda publish-layer-version \
          --layer-name "${LAYER_NAME}" \
          --zip-file "fileb://${LAYER_NAME}-layer.zip" \
          --compatible-runtimes "python${PYVER}" \
          --compatible-architectures "${ARCH}" \
          --region "${REGION}" \
          --query "LayerVersionArn" --output text)

      rm -f $LAYER_NAME-layer.zip
      cd - > /dev/null
    else
      LAYER_ARN=${EXISTING_LAYER}
    fi
    echo "Layer创建完成: ${LAYER_ARN}"
  LAYER_CMD="--layers ${LAYER_ARN}"
else
  LAYER_CMD=
fi

ROLE_NAME=${MCP_SERVER}-role
POLICY_NAME=${MCP_SERVER}-policy

# 0. 创建IAM角色
aws iam create-role \
    --role-name $ROLE_NAME \
    --region us-east-1 --no-cli-pager \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' 2>/dev/null || \
    echo "角色已存在，跳过创建"

# 创建并附加自定义策略
if [ -f "${MCPPROJECTPATH}/execution-policy.json" ]; then
  aws iam put-role-policy \
      --role-name $ROLE_NAME \
      --policy-name $POLICY_NAME \
      --region us-east-1 \
      --policy-document "file://${MCPPROJECTPATH}/execution-policy.json" || echo '附加策略已经存在，跳过'
fi

# 附加AWS管理的基本执行策略
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --region us-east-1 \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole || echo '默认策略已经存在，跳过'

cp -r ${MCPPROJECTPATH} $TEMP_DIR
cd $TEMP_DIR
# 使用 requirements.txt，安装python的依赖
if [ -f "requirements.txt" ]; then
  pip install --only-binary=:all: -t . -r requirements.txt
fi
zip -r function.zip . -x "python/*" -x "interface.json" -x "requirements*.json" -x "execution-policy.json"

echo "创建/更新Lambda函数..."
FUNCTION_ARN=$(aws lambda create-function \
    --function-name mcp-${MCP_SERVER} \
    --runtime python$PYVER \
    --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/$ROLE_NAME \
    --handler lambda_handler.handler \
    --zip-file fileb://function.zip \
    --timeout 300 --memory-size 256 ${LAYER_CMD} \
    --region $REGION \
    --query 'FunctionArn' --output text 2>/dev/null || \
aws lambda update-function-code \
        --function-name mcp-${MCP_SERVER} \
        --zip-file fileb://function.zip \
        --region $REGION \
        --query 'FunctionArn' --output text )
echo "Lambda函数创建/更新完成: $FUNCTION_ARN"
cd - > /dev/null

# ============================================================================
# 创建 Gateway Target
# ============================================================================

echo ""
echo "[步骤 2/3] 创建 Gateway Target..."

# 定义工具 Schema（可根据需求自定义）
TOOL_SCHEMA=$(cat ${MCPPROJECTPATH}/interface.json)

# 创建 Target 配置
TARGET_CONFIG=$(cat <<EOF
{
  "mcp": {
    "lambda": {
      "lambdaArn": "$FUNCTION_ARN",
      "toolSchema": {
        "inlinePayload": $TOOL_SCHEMA
      }
    }
  }
}
EOF
)

# 凭证配置
CREDENTIAL_CONFIG='[{
  "credentialProviderType": "GATEWAY_IAM_ROLE"
}]'

# 执行创建
aws bedrock-agentcore-control create-gateway-target \
  --gateway-identifier "$GATEWAY_ID" \
  --name "${MCP_SERVER}" \
  --description "${MCP_SERVER} Target" \
  --target-configuration "$TARGET_CONFIG" \
  --credential-provider-configurations "$CREDENTIAL_CONFIG" \
  --region "$REGION" \
  > /dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Gateway Target 创建成功${NC}"
else
    echo -e "${RED}✗ Gateway Target 创建失败${NC}"
    exit 1
fi

# ============================================================================
# 验证创建
# ============================================================================

echo ""
echo "[步骤 3/3] 验证 Target 状态..."

sleep 3

# 列出 Gateway 的所有 Targets
TARGET_LIST=$(aws bedrock-agentcore-control list-gateway-targets \
  --gateway-identifier "$GATEWAY_ID" \
  --region "$REGION" \
  --query "items[?name=='${MCP_SERVER}'].{Name:name,ID:targetId,Status:status}" \
  --output table)

echo "$TARGET_LIST"

# ============================================================================
# 完成
# ============================================================================

echo ""
echo "================================================"
echo -e "${GREEN}✅ 成功添加新的 Lambda Provider！${NC}"
echo "================================================"
echo ""
echo "MCP Provider 名称: ${MCP_SERVER}"
echo "Gateway ID: $GATEWAY_ID"
echo ""
echo -e "${YELLOW}下一步：${NC}"
echo "1. Quick Suite 会自动发现新工具（约1-2分钟）"
echo "2. 使用以下参数配置认证"
echo "    MCP Server: ${GATEWAY_URL}"
echo "    Server-to-Server authorized with:"
echo "      ClientID: ${CLIENT_ID}"
echo "      ClientSecret: ${CLIENT_SECRET}"
echo "      Token URL: ${TOKEN_ENDPOINT}"
echo "3. 在 Chat Agent 中测试新工具"
echo ""
echo "    测试命令示例："
echo "       AWS 有什么新消息？"
echo "       使用 mcp server ${MCP_SERVER} 进行XXXX"
echo ""
