#!/bin/bash

arch="arm64"
instance_type="c7gn.4xlarge"
instance_count=${1:-1}
shift
deploy_region="us-east-1"
# 请提前创建好这个role允许ddb的访问
instance_profile="ec2-admin"

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
while true; do
    if dnf install -y git golang; then
        if dnf list installed git golang; then
            break
        fi
    fi
    sleep 5
done
cd /usr/local/src/ && git clone https://github.com/tansoft/aws-useful-code
cd aws-useful-code/distributed-stress-test/
export GOCACHE=/root/.cache/go-build
export GOMODCACHE=/root/go/pkg/mod
./build.sh
./worker $*
"

# 运行远端脚本的方式，sed 替换 $* 目的是把运行参数替换到启动脚本中运行程序
# nohup bash -c \"curl -Ls 'http://sth/other-script' | sed 's/\$\*/$*/g' | bash\" > /tmp/init_script.log 2>&1 &
