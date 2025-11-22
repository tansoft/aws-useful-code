#!/bin/bash

if [ $# -lt 3 ]; then
    echo "build layer with local python env. e.g.:"
    echo " ./build-lambda-layer.sh mcp-base-layer us-east-1 mcp strands-agents strands-agents-tools"
    echo " ./build-lambda-layer.sh fastapi-base-layer us-east-1 fastapi uvicorn pydantic python-multipart jinja2"
    echo " ./build-lambda-layer.sh my-layer-by-requirements-file us-east-1 -r sthdir/requirements.txt"
    exit 1
fi
LAYER_NAME=$1
REGION=$2
shift 2

# 本机python版本
PYVER=$(python -c 'import sys
ver = sys.version_info
print(str(ver.major)+"."+str(ver.minor))')
# 本机是 x86 还是 arm
ARCH=$(uname -m)
# 默认会在名字后增加python版本和架构，如果需要去掉屏蔽这一行
LAYER_NAME="${LAYER_NAME}-python${PYVER//./}-${ARCH}"

TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

mkdir -p $TEMP_DIR/python
pip install --only-binary=:all: -t $TEMP_DIR/python/ $@
cd $TEMP_DIR
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
