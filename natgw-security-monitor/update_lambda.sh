#!/bin/bash

# NAT Gateway Security Monitor Lambda 更新脚本

# 检查参数
if [ $# -lt 2 ]; then
    echo "用法: $0 <stack-name> <region>"
    echo "示例: $0 natgw-monitor us-east-1"
    exit 1
fi

STACK_NAME=$1
REGION=$2

# 获取输出值
LAMBDA_FUNCTION=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
    --output text)
    
# 更新Lambda函数代码
echo "更新Lambda函数代码..."
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
cp lambda_function.py "$TEMP_DIR/"
cp -r data "$TEMP_DIR/"
pip install --target "$TEMP_DIR/" dnspython maxminddb
cd "$TEMP_DIR"
zip -r lambda_function.zip .

aws lambda update-function-code \
    --function-name $LAMBDA_FUNCTION \
    --zip-file fileb://lambda_function.zip \
    --region $REGION

rm -f lambda_function.zip
