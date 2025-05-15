#!/bin/bash
# run in ubuntu, need: jq base64
# ./create_env.sh PRO <i-06fxxxxx>
set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <instance_id> <environment>"
    exit 1
fi

INSTANCE_ID=${1:-}
ENV=${2:base}

if [ -z "$INSTANCE_ID" ]; then
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
    if [ -z "$INSTANCE_ID" ]; then
    echo instance_id not found
    exit 1
fi

# 因为 ENV 是单独指定的，所以其他对应的值不使用env文件取
PREFIX=simple-comfy
ACCOUNT_ID=`aws sts get-caller-identity --query "Account" --output text`
S3_BUCKET=${PREFIX}-${ACCOUNT_ID}-${ENV}

echo "Creating AWS resources for environment: $ENV with instance: $INSTANCE_ID"

# 使用aws 命令行，给instance 创建AMI
AMI_ID=$(aws ec2 create-image --instance-id $INSTANCE_ID --name "${ENV_NAME}-ami" --no-reboot --description "AMI for ${ENV}" --query ImageId --output text)

# 获取当前的安全组
SECURITY_GROUP_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].SecurityGroups[].GroupId" --output json --output json | jq -c .)
# 获取当前subnet，这里最好是多个需要的subnet进行代入，如：SUBNET_ID="subnet-5ea0c127,subnet-6194ea3b,subnet-c934b782"
SUBNET_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].SubnetId" --output text)

# 镜像启动时切换到环境
USER_DATA=`cat | base64 --wrap 0 <<EOF
#!/bin/bash
sed -i 's/^ENV=.*$/ENV=PRO/' /home/ubuntu/env
EOF
`

# 创建启动模板
TEMPLATE_VERSION=$(aws ec2 create-launch-template --launch-template-name "${ENV_NAME}" \
    --version-description "Initial version" \
    --launch-template-data "{\"ImageId\":\"${AMI_ID}\",\"InstanceType\":\"g5.2xlarge\",\"SecurityGroupIds\":[\"${SECURITY_GROUP_ID}\"],\"UserData\": \"${USER_DATA}\"}" \
    --query "LaunchTemplate.LatestVersionNumber" --output text)

# 创建Auto Scaling Group
aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name "${ENV_NAME}-asg" \
    --launch-template "LaunchTemplateName="${ENV_NAME}",Version=$TEMPLATE_VERSION" \
    --min-size 0 \
    --max-size 5 \
    --desired-capacity 0 \
    --vpc-zone-identifier "${SUBNET_ID}" \
    --default-cooldown 60

# 设置扩展策略
# aws autoscaling put-scaling-policy --auto-scaling-group-name "${ENV_NAME}" --policy-name "ScaleOutPolicy" --scaling-adjustment 1 --adjustment-type "ChangeInCapacity" --cooldown 60
# aws autoscaling put-scaling-policy --auto-scaling-group-name "${ENV_NAME}" --policy-name "ScaleInPolicy" --scaling-adjustment -1 --adjustment-type "ChangeInCapacity" --cooldown 120

# 创建S3存储桶
aws s3api create-bucket --bucket $S3_BUCKET

# 使用当前环境进行全量复制
aws s3 sync s3://${PREFIX}-${ACCOUNT_ID}-base/ s3://${S3_BUCKET}/ --delete

# 创建SQS队列
aws sqs create-queue --queue-name "${ENV_NAME}-queue"

echo "AWS resources creation completed!"
echo "S3 Bucket: ${ENV_NAME}"
echo "Auto Scaling Group: ${ENV_NAME}-asg"
echo "SQS Queue: ${ENV_NAME}-queue"
