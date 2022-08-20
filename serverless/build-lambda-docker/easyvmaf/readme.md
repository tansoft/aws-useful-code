# easyVMAF for lambda

VMAF https://github.com/gdavila/easyVMAF 是在libvmaf基础上，进行视频帧对齐等修复设置，以使得vmaf计算更准确。

本项目通过在lambda中调用该项目进行计算，实现通过事件触发，自动生成vmaf对比测试的功能。

由于lambda目录的只读特性，因此对文件生成位置进行替换，详见Dockerfile

## 测试步骤

## 构建并推送docker

./makeimg.sh easyvmaf

## 本地测试

docker rm -f -v test-easyvmaf

docker run -d -p 9000:8080 -e AWS_LAMBDA_FUNCTION_TIMEOUT=900 -e AWS_LAMBDA_FUNCTION_MEMORY_SIZE=1024  -e AWS_ACCESS_KEY_ID=xxx -e AWS_SECRET_ACCESS_KEY=xxx --name test-easyvmaf easyvmaf:latest

### 测试
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"Records":[{"awsRegion":"ap-northeast-1","s3":{"bucket":{"name":"video-xxx"},"object":{"key":"aaa.mp4"}}}]}'

### 登录环境进行查看

docker exec -it -t test-easyvmaf /bin/bash

apt install inotify-tools vim procps
