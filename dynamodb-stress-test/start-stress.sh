#!/bin/bash

arch="arm64"
instance_type="c7gn.4xlarge"
instance_count=1
deploy_region="ap-northeast-1"
# 请提前创建好这个role允许ddb的访问
instance_profile="ec2-admin"

# sed 替换 $* 目的是把运行参数替换到启动脚本中运行程序
aws ec2 run-instances \
    --image-id resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-${arch} \
    --instance-type ${instance_type} \
    --count ${instance_count} \
    --iam-instance-profile Name=${instance_profile} \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=ddb-stress-test},{Key=CostCenter,Value=ddb-stress-test}]" \
    --query 'Instances[*].InstanceId' \
    --output json \
    --region ${deploy_region} \
    --user-data "#!/bin/bash
sleep 10
nohup bash -c \"curl -Ls 'https://github.com/tansoft/aws-useful-code/raw/refs/heads/main/dynamodb-stress-test/prepare-env.sh' | sed 's/\$\*/$*/g' | bash\" > /tmp/init_script.log 2>&1 &
"
