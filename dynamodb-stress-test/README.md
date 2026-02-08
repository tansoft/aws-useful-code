# DynamoDB 压力测试

## 测试程序

```bash
go mod tidy
go run stress-test.go

Usage of stress-test:
  -batchDeleteItem int
        Number of batch delete threads
  -batchGetItem int
        Number of batch read threads
  -batchWriteItem int
        Number of batch write threads
  -deleteItem int
        Number of delete threads
  -getItem int
        Number of read threads
  -putItem int
        Number of write threads
  -query int
        Number of query threads
  -region string
        AWS region (default "us-east-1")
  -scan int
        Number of scan threads
  -sortkey
        Use sort key in table schema
  -t int
        Test duration in seconds (default 3600)
  -table string
        DynamoDB table name (default "stress-test")
  -updateItem int
        Number of update threads
```

直接测试

```bash
go run stress-test.go -getItem 100
```

批量拉机器测试，脚本会通过ec2的user-data进行程序安装，并使用命令行参数进行测试

```bash
./start-stress.sh -getItem 100 -t 1800
```

## 表格设计

分区键为id，统一为32字节UUID组成，为了进行读写打散测试，读写逻辑中，分别使用相同的开始索引进行随机种子确定，以确保读取命中：
```bash
4d65822107fcfd5278629a0f5f3f164f
d5104dc76695721db80704bb7b4d7c03
365a858149c6e2d157e9d1860d1d68d8
```

对应的value内容，使用package.yaml进行结构体描述，描述多列的列名，以及每列的数据大小

测试模式有两种：

## 标准模式测试

使用UUID进行Key生成，Value结构体由package.yaml声明，默认结构体如下：

```go
values := map[string][]byte{
		"package1": make([]byte, 1120),
		"package2": make([]byte, 1400),
		"package3": make([]byte, 2100),
		"package4": make([]byte, 1980),
		"package5": make([]byte, 1460),
		"package6": make([]byte, 320),
}
```

### 建表语句参考

```bash
#### 基础版本（按需计费）
bash
aws dynamodb create-table \
  --table-name stress-test \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --tags Key=Cost-Center,Value=stress-test \
  --billing-mode PAY_PER_REQUEST

#### 预置模式请参考
  --billing-mode PROVISIONED \
  --provisioned-throughput ReadCapacityUnits=1000,WriteCapacityUnits=1500
```

### 配置读容量自动扩展（可选）

```bash
# 读请求配置
aws application-autoscaling register-scalable-target \
  --service-namespace dynamodb \
  --resource-id table/stress-test \
  --scalable-dimension dynamodb:table:ReadCapacityUnits \
  --min-capacity 100 \
  --max-capacity 10000

aws application-autoscaling put-scaling-policy \
  --service-namespace dynamodb \
  --resource-id table/stress-test \
  --scalable-dimension dynamodb:table:ReadCapacityUnits \
  --policy-name stress-test-read-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    '{"TargetValue":70.0,"PredefinedMetricSpecification":{"PredefinedMetricType":"DynamoDBReadCapacityUtilization"}}'

# 写请求配置
aws application-autoscaling register-scalable-target \
  --service-namespace dynamodb \
  --resource-id table/stress-test \
  --scalable-dimension dynamodb:table:WriteCapacityUnits \
  --min-capacity 100 \
  --max-capacity 5000

aws application-autoscaling put-scaling-policy \
  --service-namespace dynamodb \
  --resource-id table/stress-test \
  --scalable-dimension dynamodb:table:WriteCapacityUnits \
  --policy-name stress-test-write-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    '{"TargetValue":70.0,"PredefinedMetricSpecification":{"PredefinedMetricType":"DynamoDBWriteCapacityUtilization"}}'
```

### 标准测试（多列模式）

单线程测试命令区间，DynamoDB 按需模式

|  | 测试时间s | 成功 | 失败 | QPS | 延迟ms | 参数 |
|-----|-----|-----|-----|-----|-----|-----|
| 批量写 | 30 | 13725 | 0 | 457.5 | 2.18 | -t 30 -batchWriteItem 1 |
| 批量读 | 10 | 47800 | 0 | 4780 | 0.21 | -t 10 -batchGetItem 1 |
| 批量删除 | 30 | 26250 | 0 | 875 | 1.14 | -t 30 -batchDeleteItem 1 |
| 单条写入 | 30 | 6083 | 0 | 202.77 | 4.93 | -t 30 -putItem 1 |
| 单条更新 | 30 | 6862 | 0 | 228.73 | 4.37 | -t 30 -updateItem 1 |
| 单条取（命中） | 10 | 4216 | 0 | 421.6 | 2.37 | -t 10 -getItem 1 |
| Query（无需） | 10 | 3330 | 0 | 333 | 3.0 | -t 10 -query 1 |
| Scan | 10 | 727 | 0 | 72.7 | 13.75 | -t 10 -scan 1 |
| 单条删除 | 30 | 5909 | 0 | 196.97 | 5.08 | -t 30 -deleteItem 1 |
| 单条取（Miss） | 10 | 8325 | 0 | 832.5 | 1.20 | -t 10 -getItem 1 |
Total Reads: 4686 / 0
Read QPS: 468.60

column
Total Batch Writes: 12600 / 0, QPS: 420.00, Latency: 2.38ms
Total Batch Reads: 53900 / 0, QPS: 5390.00, Latency: 0.19ms
Total Reads: 3797 / 0, QPS: 379.70, Latency: 2.63ms
Total Queries: 4536 / 0, QPS: 453.60, Latency: 2.20ms
Total Updates: 7312 / 0, QPS: 243.73, Latency: 4.10ms
Total Batch Deletes: 30825 / 0, QPS: 1027.50, Latency: 0.97ms
Total Writes: 6082 / 0, QPS: 202.73, Latency: 4.93ms
Total Reads: 5749 / 0, QPS: 574.90, Latency: 1.74ms
Total Queries: 3380 / 0, QPS: 338.00, Latency: 2.96ms
Total Scans: 680 / 0, QPS: 68.00, Latency: 14.71ms
Total Deletes: 6034 / 0, QPS: 201.13, Latency: 4.97ms
Total Reads: 3909 / 0, QPS: 390.90, Latency: 2.56ms
Total Queries: 4201 / 0, QPS: 420.10, Latency: 2.38ms

row
Total Batch Writes: 35928 / 0, QPS: 1197.60, Latency: 0.84ms
Total Batch Reads: 61000 / 0, QPS: 6100.00, Latency: 0.16ms
Total Reads: 4483 / 0, QPS: 448.30, Latency: 2.23ms
Total Queries: 3921 / 0, QPS: 392.10, Latency: 2.55ms
Total Updates: 9216 / 0, QPS: 307.20, Latency: 3.26ms
Total Batch Deletes: 37008 / 0, QPS: 1233.60, Latency: 0.81ms
Total Writes: 6665 / 0, QPS: 222.17, Latency: 4.50ms
Total Reads: 7956 / 0, QPS: 795.60, Latency: 1.26ms
Total Queries: 4497 / 0, QPS: 449.70, Latency: 2.22ms
Total Scans: 1196 / 0, QPS: 119.60, Latency: 8.36ms
Total Deletes: 6212 / 0, QPS: 207.07, Latency: 4.83ms
Total Reads: 4286 / 0, QPS: 428.60, Latency: 2.33ms
Total Queries: 3762 / 0, QPS: 376.20, Latency: 2.66ms

## 带SortKey测试（多行模式）

参照 [DDB-PATTERN.md](DDB-PATTERN.md) 说明，DynamoDB在频繁单列更新时，建议使用多行的方式进行表设计。

在多行模式下，建表时应使用带有SortKey的方式进行建表。
为了进行高效测试，表格结构规定如下：
分区键：id
排序键：sk
取值：val
在putItem/getItem时，会通过上述固定随机数方式，计算得出每次读写的单列名字。
在BatchWriteItem/BatchDeleteItem逻辑中，会把key对应的所有package进行写入/删除。
在query逻辑中，会返回key的所有内容。

### 建表语句参考

```bash
#### 基础版本（按需计费）
bash
aws dynamodb create-table \
  --table-name stress-test \
  --attribute-definitions AttributeName=id,AttributeType=S \
      AttributeName=sk,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
      AttributeName=sk,KeyType=RANGE \
  --tags Key=Cost-Center,Value=stress-test \
  --billing-mode PAY_PER_REQUEST

#### 预置模式请参考
  --billing-mode PROVISIONED \
  --provisioned-throughput ReadCapacityUnits=1000,WriteCapacityUnits=1500
```

### 多行测试

由于多行是为了验证单列更新的性能，因此putItem时，会

```bash
```