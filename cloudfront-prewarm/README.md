## CloudFront 预热脚本

这是一个简便的 CloudFront 预热脚本。

### 准备工作

* 下载脚本 [prewarm.py](https://github.com/tansoft/aws-useful-code/blob/main/cloudfront-prewarm/prewarm.py)

```bash
wget https://github.com/tansoft/aws-useful-code/blob/main/cloudfront-prewarm/prewarm.py -O prewarm.py
pip install requests dnspython
```

* 根据预热需求，在目录中生成 config.yaml 配置文件

```yaml
# 你的cloudfront域名
cloudfront_url: "xxxx.cloudfront.net"
# 考虑有些源站需要用指定host访问，这时可以指定 CloudFront的备用域名host
host: "myhost.com"
# 考虑有些配置是 http 直接 302 到 https，这里默认使用 https 访问
protocol: "https" # Protocol to use: "http" or "https"
files: |
  /something.js
  /%E7%9B%B8%E5%85%B3%E4%BF%A1%E6%81%AF.zip
  # 多文件预热每个文件一行，以#开头的行会被忽略，中文文件请进行UrlEncode
  # 脚本同时支持上述格式和传统的YAML列表格式（使用'-'前缀）

# 是否在预热前，先刷新旧缓存（如果需要新内容替换同名文件）
# !!! 如果使用这个选项，请确认环境中需要配置调用CloudFront Invalidation API的权限 ！！！
invalidation: false

encodings:
  - "gzip, br" # 浏览器常用设置，如常用的“gzip, deflate, br, zstd” 就是这个，cloudfront会把不支持的格式排除，先后顺序无关
  #- "gzip" # 兼容只支持gzip的旧浏览器，可以单独再进行一次请求
  #- "br" # 同理，只支持 Brotli 的浏览器请求
  - "" # 没有指定Accept-Encoding字段，如客户端程序直接请求

# 需要预热的 POP 点选择，可以是region名字和pop点名称，建议使用region名字。
# 如果需要指定更多的POP点IP，可以在三方网站上，找到维护的 POP 点信息，再加以选择。
# 这里可以查到比较全的pop点信息，https://www.feitsui.com/en/article/3
# 注意由于pop点信息不是官方的，有可能会有pop点下线失效的情况，更推荐使用上面的指定region的方式。
# 默认建议以下少数几个即可，对主要的区域性边缘缓存（Regional Edge Cache）做预热：https://aws.amazon.com/cloudfront/features/
pops:
  # 指定region的方式：
  - "us-east-1" # North America (N.Virginia)
  - "us-east-2" # North America (Ohio)
  - "us-west-1" # North America (California)
  - "us-west-2" # North America (Oregon)
  - "sa-east-1" # South America (São Paulo)
  - "eu-central-1" # Germany (Frankfurt)
  - "eu-west-1" # Ireland (Dublin)
  - "eu-west-2" # UK (London)
  - "ap-south-1" # India (Mumbai)
  - "ap-southeast-1" # Asia (Singapore)
  - "ap-northeast-1" # Japan (Tokyo)
  - "ap-northeast-2" # South Korea (Seoul)
  - "ap-southeast-2" # Australia (Sydney)
  - "me-central-1" # Middle East (Dubai)
  - "ap-east-1" # China/Hong Kong (Hong Kong)
  # 指定pop点的方式：
  # - "IAD89-C1" # North America (N.Virginia)
  # - "CMH68-P1" # North America (Ohio)
  # - "SFO53-C1" # North America (California)
  # - "HIO50-C1" # North America (Oregon)
  # - "GRU1-C2" # South America (São Paulo)
  # - "FRA50-C1" # Germany (Frankfurt)
  # - "DUB56-P1" # Ireland (Dublin)
  # - "LHR61-C2" # UK (London)
  # - "BOM54-P2" # India (Mumbai)
  # - "SIN2-P6" # Asia (Singapore)
  # - "NRT20-P2" # Japan (Tokyo)
  # - "ICN55-C1" # South Korea (Seoul)
  # - "SYD1-C1" # Australia (Sydney)
  # - "DXB52-P1" # Middle East (Dubai)
  # - "HKG62-C1" # China/Hong Kong (Hong Kong)
```

### 执行预热

```bash
python3 prewarm.py
```
