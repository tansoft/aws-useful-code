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

```bash
```

## 带SortKey测试（多行模式）

参照 [DDB-PATTERN.md](DDB-PATTERN.md) 说明，DynamoDB在频繁单列更新时，建议使用多行的方式进行表设计。

在多行模式下，建表时应使用带有SortKey的方式进行建表。
为了进行高效测试，表格结构规定如下：
分区键：id
排序键：sk
取值：val
在putItem/batchPutItem/getItem/batchGetItem时，会通过上述固定随机数方式，计算得出每次读写的单列名字。

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