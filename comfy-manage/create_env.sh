#!/bin/bash
# run in ubuntu, need: jq base64
# ./create_env.sh pro <i-06fxxxxx>
# 注意环境名只能小写
set -e

if [ -z "$1" ]; then
    echo "Please specify an environment name. usage: ./create_env.sh PRO <i-06fxxxxx>"
    exit 1
fi

# 需要从当前配置读取默认S3_BUCKET
source /home/ubuntu/comfy/env
BASE_S3_BUCKET=${S3_BUCKET}

ENV=$1
INSTANCE_ID=${2:-}

if [ -z "$INSTANCE_ID" ]; then
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
    if [ -z "$INSTANCE_ID" ]; then
        echo instance_id not found
        exit 1
    fi
fi

sed 's/^ENV=.*$/ENV=${ENV}/' /home/ubuntu/comfy/env > /tmp/env-${ENV}
source /tmp/env-${ENV}
rm -f /tmp/env-${ENV}

echo "Creating AWS resources for environment $ENV with instance $INSTANCE_ID ..."

# 使用aws 命令行，给instance 创建AMI
AMI_ID=$(aws ec2 describe-images --filters "Name=name,Values=${ASG_NAME}" --query 'Images[*].ImageId' --output text --region ${REGION})
if [ -n "$AMI_ID" ]; then
    echo "AMD_ID: $AMI_ID , AMI already exist."
    # aws ec2 deregister-image --image-id $IMAGE_ID
else
    AMI_ID=$(aws ec2 create-image --instance-id $INSTANCE_ID --name "${ASG_NAME}" --no-reboot --description "AMI for ${ENV}" --query ImageId --output text --region ${REGION})
    echo "AMD_ID: ${AMI_ID}"
fi

# 获取当前的安全组
SECURITY_GROUP_IDS=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].SecurityGroups[].GroupId" --output json --region ${REGION} | jq -c .)
echo "SECURITY_GROUP_IDS: ${SECURITY_GROUP_IDS}"

# 获取当前实例的subnet，这里只有单个子网
#SUBNET_IDS=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].SubnetId" --output text --region ${REGION})
# 获取当前实例所在VPC的所有私有子网
VPC_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].VpcId' --output text --region ${REGION})
# 该命令找出该vpc中所有私有子网
SUBNET_IDS=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" --output json --region ${REGION}| \
jq -r '[.RouteTables[] | 
    select((.Routes | map(select(
        .DestinationCidrBlock=="0.0.0.0/0" and (
            (has("GatewayId") and (.GatewayId | startswith("igw-")))
        )
    )) | length) == 0) |
    .Associations[] |
    select(.SubnetId != null) |
    .SubnetId] | join(",")')
# 判断如果SUBNET_ID为空，表示该vpc中只有公有子网，这时使用所有子网
if [ -z "$SUBNET_IDS" ]; then
    SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[*].SubnetId' --output json --region ${REGION}| jq -r '. | join(",")')
fi
echo "SUBNET_IDS: ${SUBNET_IDS}"

# 获取当前role
INSTANCE_PROFILE_ARN=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query "Reservations[0].Instances[0].IamInstanceProfile.Arn" --output text --region ${REGION})
INSTANCE_PROFILE_NAME=$(echo $INSTANCE_PROFILE_ARN | awk -F/ '{print $NF}')
echo "INSTANCE_PROFILE_ARN: ${INSTANCE_PROFILE_ARN}"
echo "INSTANCE_PROFILE_NAME: ${INSTANCE_PROFILE_NAME}"

# 镜像启动时切换到环境
USER_DATA=`cat << EOF | base64 --wrap 0
#!/bin/bash
sed -i 's/^ENV=.*$/ENV=${ENV}/' /home/ubuntu/comfy/env
EOF`

# 创建启动模板
TEMPLATE_VERSION=$(aws ec2 create-launch-template --launch-template-name "${ASG_NAME}" \
    --version-description "Initial version" \
    --launch-template-data "{\"ImageId\":\"${AMI_ID}\",\"InstanceType\":\"${INSTANCE_TYPE}\",\"SecurityGroupIds\":${SECURITY_GROUP_IDS},\"UserData\": \"${USER_DATA}\",\"IamInstanceProfile\": {\"Name\":\"${INSTANCE_PROFILE_NAME}\"}}" \
    --query "LaunchTemplate.LatestVersionNumber" --output text --region ${REGION})
echo "TEMPLATE_VERSION: ${TEMPLATE_VERSION}"

# 创建Auto Scaling Group
aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name "${ASG_NAME}" \
    --launch-template "LaunchTemplateName=${ASG_NAME},Version=$TEMPLATE_VERSION" \
    --min-size ${MIN_INSTANCES} \
    --max-size ${MAX_INSTANCES} \
    --desired-capacity ${MIN_INSTANCES} \
    --vpc-zone-identifier "${SUBNET_IDS}" \
    --default-cooldown ${SCALE_COOLDOWN} \
    --region ${REGION}

# 设置扩展策略
# aws autoscaling put-scaling-policy --auto-scaling-group-name "${ASG_NAME}" --policy-name "ScaleOutPolicy" --scaling-adjustment 1 --adjustment-type "ChangeInCapacity" --cooldown 60 --region ${REGION}
# aws autoscaling put-scaling-policy --auto-scaling-group-name "${ASG_NAME}" --policy-name "ScaleInPolicy" --scaling-adjustment -1 --adjustment-type "ChangeInCapacity" --cooldown 120 --region ${REGION}

# 设置生命周期钩子，超时五分钟后释放机器，parse_job.py 会做退出准备工作
aws autoscaling put-lifecycle-hook \
  --lifecycle-hook-name "${ASG_NAME}" \
  --auto-scaling-group-name "${ASG_NAME}" \
  --lifecycle-transition autoscaling:EC2_INSTANCE_TERMINATING \
  --default-result CONTINUE \
  --heartbeat-timeout 300 \
  --region ${REGION} \

# 创建S3存储桶
aws s3api create-bucket --bucket $S3_BUCKET --region ${REGION} \
    --create-bucket-configuration LocationConstraint=${REGION}

# 使用当前环境进行全量复制
aws s3 sync s3://${BASE_S3_BUCKET}/ s3://${S3_BUCKET}/ --delete --region ${REGION}

# 创建SQS队列
aws sqs create-queue --queue-name "${SQS_NAME}" --region ${REGION}

echo "AWS resources creation completed!"
echo "S3 Bucket: ${S3_BUCKET}"
echo "Auto Scaling Group: ${ASG_NAME}"
echo "SQS Queue: ${SQS_NAME}"
