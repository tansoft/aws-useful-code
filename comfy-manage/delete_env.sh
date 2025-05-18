#!/bin/bash
# run in ubuntu, need: jq base64
# ./delete_env.sh PRO
#set -e

if [ -z "$1" ]; then
    echo "Please specify an environment name. usage: ./delete_env.sh PRO"
    exit 1
fi

ENV=$1

sed 's/^ENV=.*$/ENV=${ENV}/' /home/ubuntu/comfy/env > /tmp/env-${ENV}
source /tmp/env-${ENV}
rm -f /tmp/env-${ENV}

echo "Deleting AWS resources for environment $ENV ..."

# 删除指定名字的sqs
QUEUE_URL=$(aws sqs get-queue-url --queue-name "${SQS_NAME}" --query 'QueueUrl' --output text --region ${REGION})
if [ -n "$QUEUE_URL" ]; then
    echo "Deleting queue $QUEUE_URL ..."
    aws sqs delete-queue --queue-url $QUEUE_URL
fi

aws autoscaling delete-lifecycle-hook --lifecycle-hook-name "${ASG_NAME}" --auto-scaling-group-name "${ASG_NAME}" --region ${REGION}

aws autoscaling delete-auto-scaling-group --auto-scaling-group-name "${ASG_NAME}" --force-delete --region ${REGION}

aws ec2 delete-launch-template --launch-template-name "${ASG_NAME}" --region ${REGION}

AMI_ID=$(aws ec2 describe-images --filters "Name=name,Values=${ASG_NAME}" --query 'Images[*].ImageId' --output text --region ${REGION})
if [ -n "$AMI_ID" ]; then
    echo "Deregistering AMI $AMI_ID ..."
    aws ec2 deregister-image --image-id $AMI_ID --region ${REGION}
    # 删除对应的快照
    SNAPSHOTS=$(aws ec2 describe-snapshots --filters "Name=description, Values=*${AMI_ID}*" --query 'Snapshots[*].SnapshotId' --output text --region ${REGION})
    for snapshot in $SNAPSHOTS; do
        echo "Deleting snapshot $snapshot ..."
        aws ec2 delete-snapshot --snapshot-id $snapshot --region ${REGION}
    done
fi

#aws s3api put-bucket-versioning --bucket ${S3_BUCKET} --versioning-configuration Status=Suspended --region ${REGION}
aws s3 rm s3://${S3_BUCKET} --recursive --region ${REGION}
aws s3 rb s3://${S3_BUCKET} --force --region ${REGION}
