#!/bin/bash

# NAT Gateway Security Monitor 部署脚本

# 检查参数
if [ $# -lt 5 ]; then
    echo "用法: $0 <stack-name> <nat-gateway-id> <email> <region> <threshold-bytesmin>"
    echo "示例: $0 natgw-monitor nat-12345678 user@example.com us-east-1 10000000"
    exit 1
fi

STACK_NAME=$1
NAT_GW_ID=$2
EMAIL=$3
REGION=$4
THRESHOLD=$5

echo "开始部署 NAT Gateway Security Monitor..."
echo "Stack Name: $STACK_NAME"
echo "NAT Gateway ID: $NAT_GW_ID"
echo "Email: $EMAIL"
echo "Region: $REGION"
echo "Threshold: $THRESHOLD MB/s"

# 部署CloudFormation堆栈
aws cloudformation deploy \
    --template-file natgw-security-monitor.yaml \
    --stack-name $STACK_NAME \
    --parameter-overrides \
        NatGwId=$NAT_GW_ID \
        RefreshInterval=10 \
        OutDataAlertThreshold=$THRESHOLD \
        NotifyEmail=$EMAIL \
        LogsRetainDays=7 \
    --capabilities CAPABILITY_IAM \
    --region $REGION

if [ $? -eq 0 ]; then
    echo "CloudFormation堆栈部署成功！"

    ./update_lambda.sh $STACK_NAME $REGION

    echo "部署完成！请检查邮箱确认SNS订阅。"
else
    echo "CloudFormation堆栈部署失败！"
    exit 1
fi
