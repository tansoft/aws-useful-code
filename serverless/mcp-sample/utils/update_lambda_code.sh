#!/bin/bash
# ============================================================================
# 通用脚本：更新lambda代码
# ============================================================================
# 
# 使用方法：
# ./update_lambda_code.sh <mcp_name> [<project>]
#
# 示例：
# ./update_lambda_code.sh <mcp_name> [<project>]
#
# ============================================================================

set -e

if [ $# -lt 1 ]; then
    echo "./update_lambda_code.sh <mcp_name> [<project>]"
    exit 1
fi

MCP_SERVER=${1}
PROJECT=${2:-"base-auth"}

CURPATHCURPATH=$(cd `dirname "${BASH_SOURCE[0]}"`;pwd)
source "${CURPATHCURPATH}/../.${PROJECT}-config.txt"

if [[ -z "$REGION" || -z "$GATEWAY_ID" ]]; then
    echo "错误: .${PROJECT}-config.txt 配置文件中缺少必要参数，请先配置 cognito，再配置 agentcore_gateway，再运行本程序！"
    exit 1
fi

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "Gateway ID: $GATEWAY_ID"
echo ""

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

    EXISTING_LAYER=$(aws lambda list-layer-versions \
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
      echo "Layer创建完成: ${LAYER_ARN}"
    else
      LAYER_ARN=${EXISTING_LAYER}
      echo "Layer已存在: ${LAYER_ARN}"
    fi
  LAYER_CMD="--layers ${LAYER_ARN}"
else
  LAYER_CMD=
fi

cp -r ${MCPPROJECTPATH}/* $TEMP_DIR
cd $TEMP_DIR
# 使用 requirements.txt，安装python的依赖
if [ -f "requirements.txt" ]; then
  pip install --only-binary=:all: -t . -r requirements.txt
fi
zip -9 -r function.zip . -x "python/*" -x "interface.json" -x "requirements*.txt" -x "execution-policy.json"

echo "更新Lambda函数..."
FUNCTION_ARN=$(aws lambda update-function-code \
        --function-name mcp-${MCP_SERVER} \
        --zip-file fileb://function.zip \
        --region $REGION \
        --query 'FunctionArn' --output text )
echo "Lambda函数创建/更新完成: $FUNCTION_ARN"
cd - > /dev/null
