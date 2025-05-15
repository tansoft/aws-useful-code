#!/bin/bash
# run in ubuntu, need: jq base64
# ./delete_env.sh PRO
set -e

if [ -z "$1" ]; then
    echo "Please specify an environment name. usage: ./delete_env.sh PRO"
    exit 1
fi

ENV=$1

# 因为 ENV 是单独指定的，所以其他对应的值不使用env文件取
PREFIX=simple-comfy
ACCOUNT_ID=`aws sts get-caller-identity --query "Account" --output text`
ENV_NAME=${PREFIX}-${ENV}
S3_BUCKET=${PREFIX}-${ACCOUNT_ID}-${ENV}

echo "Deleting AWS resources for environment $ENV ..."

aws sqs delete-queue --queue-name "${ENV_NAME}-queue"

aws autoscaling delete-auto-scaling-group \
    --auto-scaling-group-name "${ENV_NAME}-asg"

aws ec2 delete-launch-template --launch-template-name "${ENV_NAME}"

AMI_ID=$(aws ec2 describe-images --filters "Name=name,Values=${ENV_NAME}-ami" --query 'Images[*].ImageId' --output text)
if [ -n "$AMI_ID" ]; then
    echo "Deregistering AMI $AMI_ID ..."
    aws ec2 deregister-image --image-id $AMI_ID
    # 删除对应的快照
    SNAPSHOTS=$(aws ec2 describe-snapshots --filters "Name=description, Values=*${AMI_ID}*" --query 'Snapshots[*].SnapshotId' --output text)
    for snapshot in $SNAPSHOTS; do
        echo "Deleting snapshot $snapshot ..."
        aws ec2 delete-snapshot --snapshot-id $snapshot
    done
fi

#aws s3api put-bucket-versioning --bucket ${S3_BUCKET} --versioning-configuration Status=Suspended
aws s3 rm s3://${S3_BUCKET} --recursive
aws s3 rb s3://${S3_BUCKET} --force
