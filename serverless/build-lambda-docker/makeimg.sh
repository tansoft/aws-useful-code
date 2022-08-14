#/bin/bash

#./makeimg.sh app-iplist

region=ap-northeast-1
accountid=`aws sts get-caller-identity | jq -r '.Account'`
project=$1
ecr=${accountid}.dkr.ecr.${region}.amazonaws.com
pushurl=${ecr}/${project}:latest

cd ${project}
docker build -t ${project}:latest .
aws ecr get-login-password --region ${region} | docker login --username AWS --password-stdin ${ecr}
aws ecr create-repository --repository-name ${project} --image-scanning-configuration scanOnPush=true --image-tag-mutability MUTABLE
docker tag ${project}:latest ${pushurl}
docker push ${pushurl}
#curpath=`pwd`
#workdir=`grep "ARG FUNCTION_DIR=" Dockerfile | awk -F\" '{print $2}'`
#-v ${curpath}/${project}/app.py:${workdir}/app.py
echo ecr url is ${pushurl}
echo -e "for local debug:\n    docker run -d -p 9000:8080 -e AWS_LAMBDA_FUNCTION_TIMEOUT=900 -e AWS_LAMBDA_FUNCTION_MEMORY_SIZE=1024 --name test-${project} ${project}:latest"
echo -e "  for test:\n    curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{}'"
echo -e "  for kill:\n    docker rm -f -v test-${project}"
echo -e "  for debug:\n    docker exec -it -t test-${project} /bin/sh\n    docker logs -t test-${project}"