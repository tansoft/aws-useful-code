# CloudFront Static Cache with Origin Fallback

这个项目实现了一个CloudFront分配，它使用S3作为主要源站，并通过Lambda@Edge 在“源返回”阶段判断当S3返回404时从真正源站获取内容并缓存到S3的功能。

## 架构

1. 用户请求通过CloudFront
2. CloudFront首先尝试从S3获取内容
3. 如果S3有内容，直接返回给用户
4. 如果S3返回404，Lambda@Edge函数会：
   - 从配置的源站获取内容
   - 将内容保存到S3
   - 将内容返回给用户

## 部署说明

直接部署CloudFormation模板，只需要指定源站域名 OriginDomainName 和存储文件的s3桶名字 BucketName 即可。

也可以通过命令行调用

```bash
aws cloudformation deploy \
   --template-file template.yaml \
   --stack-name cloudfront-static-cache \
   --parameter-overrides \
      OriginDomainName=example.com \
      BucketName=my-static-cache-bucket \
   --capabilities CAPABILITY_IAM
```

## 注意事项

1. Lambda@Edge函数需要在us-east-1区域创建
2. 确保S3桶名称全局唯一
3. 源站域名需要是可公开访问的
4. Lambda@Edge函数有大小限制（1MB）和超时限制（5秒）

## 自定义

您可以根据需要修改以下内容：
- Lambda函数中的缓存控制头
- 源站请求的头信息
- S3存储对象的元数据
- CloudFront缓存行为