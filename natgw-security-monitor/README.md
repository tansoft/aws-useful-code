# Nat Gateway 安全监测程序

提供 natgw-security-monitor.yaml ，可以直接进行CloudFormation部署。其中模版参数如下：
* natgw-id 选择本区域的natgw，如：nat-xxxxxx
* refresh-intval 汇总计算间隔，默认：5分钟，定期调用流量分析lambda
* flowlog-s3-path 保存日志的s3桶和路径，如：s3://my-natgw-data/flowlogs/
* outdata-alert-threshold 出流量报警阈值，如：300MB/s
* notify-sns 报警通知SNS，如：natgw-sec-monitor-sns
* notify-email 报警通知邮箱，如：abc@mail.com
* logs-retain-days 原始日志保存天数，默认：7天
* dynamodb-prefix DynamoDB前缀，用于数据分析和标记，默认：natgw-sec-monitor-

程序逻辑如下：
* 配置notify-sns到notify-email邮件通知。
* 根据流量阈值outdata-alert-threshold，配置natgw的cloudwatch报警，通知到notify-sns。
* 找到natgw对应的主eni网卡，开启vpc flowlog，捕捉natgw的访问数据，日志保存在flowlog-s3-path指定的s3桶中，需要兼容hive格式路径保存，按小时进行分区，1分钟进行聚合。
* s3桶路径配置生命周期规则，按logs-retain-days天数进行日志删除，需要考虑更新hive metadata。
* 以dynamodb-prefix为前缀配置，创建iptable表，包括字段：cidr,hour-outdata,total-outdata,purpose,status,其中purpose用于区分ip用途，status包括normal,unknown,alart（正常，未知，报警）几种状态，cidr是ip段的定义，先按/24区分。
* 配置event-bridge，配置refresh-intval间隔，调用流量分析lambda，函数分析dynamodb表，找出iptable表中没有登记的ip段，进行ip录入并发SNS通知，已知的ip段进行流量汇总，并判断流量是否异常，和status是否需要立即报警来进行报警。

## 部署方法

```bash
./deploy.sh natgw-monitor nat-12345678 my-bucket user@example.com us-east-1 300
```
