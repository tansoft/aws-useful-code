# easyVMAF for lambda

VMAF https://github.com/gdavila/easyVMAF 是在libvmaf基础上，进行视频帧对齐等修复设置，以使得vmaf计算更准确，该项目通过在lambda中调用该项目进行计算，实现通过事件触发，自动生成vmaf对比测试的功能。

curl -XPOST http://localhost:9000/2015-03-31/functions/function/invocations -d '{"Records":[{"awsRegion":"ap-northeast-1","s3":{"bucket":{"name":"xxxx"},"object":{"key":"xxxx.mp4"}}}]}'
