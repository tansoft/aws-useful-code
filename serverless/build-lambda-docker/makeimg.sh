#/bin/bash

#./makeimg.sh app-iplist

region=ap-northeast-1
accountid=`aws sts get-caller-identity | jq -r '.Account'`
project=$1
ecr=${accountid}.dkr.ecr.${region}.amazonaws.com
pushurl=${ecr}/${project}:latest

cd ${project}
docker build -t ${project} .
aws ecr get-login-password --region ${region} | docker login --username AWS --password-stdin ${ecr}
aws ecr create-repository --repository-name ${project} --image-scanning-configuration scanOnPush=true --image-tag-mutability MUTABLE
docker tag ${project}:latest ${pushurl}
docker push ${pushurl}
echo url is ${pushurl}

