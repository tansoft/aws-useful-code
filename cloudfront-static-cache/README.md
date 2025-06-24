# CloudFront Static Cache with Origin Fallback

这个项目实现了一个CloudFront分配，它使用S3作为主要源站，并通过异步下载机制在S3中缓存源站内容。

## 架构

1. 用户请求通过CloudFront
2. CloudFront首先尝试从S3获取内容
3. 如果S3有内容，直接返回给用户
4. 如果S3返回404，Lambda@Edge函数会：
   - 将下载任务提交到SQS队列
   - 返回302重定向到源站，让用户立即获得内容
5. 后台的Lambda函数（15分钟超时）会：
   - 从SQS队列获取下载任务
   - 从源站下载内容
   - 将内容保存到S3，供后续请求使用

## 优势

1. 避免了Lambda@Edge的限制：
   - 5秒执行时间限制
   - 响应大小限制
2. 用户可以立即获得内容（通过重定向）
3. 异步下载机制可以处理大文件
4. 使用SQS确保下载任务的可靠性
5. 失败的下载会进入死信队列(DLQ)以便监控和重试

## 部署说明

直接部署CloudFormation模板，只需要指定源站域名 OriginDomainName 即可。所有资源名称都会基于源站域名自动生成，确保多个部署之间不会冲突。需要在美东一区域部署。

```bash
aws cloudformation deploy \
   --template-file template.yaml \
   --stack-name cf-cache-for-xxx \
   --parameter-overrides \
      OriginDomainName=example.com \
   --capabilities CAPABILITY_IAM
   --region us-east-1
```

## 资源命名规则

资源会以CloudFormation名字进行区分：

1. 不同源站的缓存互相独立
2. 可以同时部署多个CloudFormation栈
3. 资源之间的关系清晰可见
4. 符合AWS资源命名规范（避免使用点号）

## 注意事项

1. Lambda@Edge函数需要在us-east-1区域创建
2. 确保源站域名是可公开访问的
3. 下载Lambda函数有15分钟的超时时间，适合大文件下载
4. 失败的下载任务会在重试3次后进入DLQ

## 自定义

您可以根据需要修改以下内容：
- Lambda@Edge函数中的重定向和缓存控制头
- 下载Lambda函数中的重试策略
- SQS队列的配置（如可见性超时、消息保留期等）
- S3存储对象的元数据和缓存控制
- CloudFront缓存行为
