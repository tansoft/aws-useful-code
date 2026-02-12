# DynamoDB 压力测试

## 测试程序

```bash
go mod tidy
go run stress-test.go

Usage of ./stress-test:
  -batchDeleteItem int
        Number of batch delete threads
  -batchGetItem int
        Number of batch read threads
  -batchWriteItem int
        Number of batch write threads
  -config string
        Configuration file path (default "package.yaml")
  -deleteItem int
        Number of delete threads
  -getItem int
        Number of read threads
  -printkey
        Print the generated key
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
  -times int
        Number of iterations (0 for unlimited)
  -updateItem int
        Number of update threads
```

### 直接测试

```bash
go run stress-test.go -getItem 100
```

### 批量起10台机器测试，脚本会通过ec2的user-data进行程序安装，并使用命令行参数进行测试

```bash
./start-stress.sh 10 -getItem 100 -t 1800
```

## 表格设计

分区键为id，统一为32字节UUID组成，为了进行读写打散测试，读写逻辑中，分别使用相同的开始索引进行随机种子确定，以确保读取命中：
```bash
4d65822107fcfd5278629a0f5f3f164f
d5104dc76695721db80704bb7b4d7c03
365a858149c6e2d157e9d1860d1d68d8
```

对应的value内容，使用package.yaml进行结构体描述，描述多列的列名，以及每列的数据大小，结构体大致如下：

```go
values := map[string][]byte{
		"data1": make([]byte, 1120),
		"data2": make([]byte, 1400),
		"data3": make([]byte, 2100),
		"data4": make([]byte, 1980),
		"data5": make([]byte, 1460),
		"data6": make([]byte, 320),
}
```

### 测试前提限制：

参照 [DDB-PATTERN.md](DDB-PATTERN.md) 说明，DynamoDB在频繁单列更新时，建议使用多行的方式进行表设计。因此在多行模式下，建表时应使用带有SortKey的方式进行建表。

为了进行高效测试，多行模式时，表格结构规定如下：

* 分区键：id
* 排序键：sk
* Item：val

* 在putItem/getItem时，会通过上述固定随机数方式，计算得出每次读写的单列名字，如： id=4d65822107fcfd5278629a0f5f3f164f sk=data2。
* 在BatchWriteItem/BatchDeleteItem逻辑中，标准模式（多列）会写入25条整条的数据，带SortKey（多行）模式会把单个package里的每列数据分别进行插入/删除，如会同时写入：

```bash
id=4d65822107fcfd5278629a0f5f3f164f sk=data1
id=4d65822107fcfd5278629a0f5f3f164f sk=data2
id=4d65822107fcfd5278629a0f5f3f164f sk=data3
id=4d65822107fcfd5278629a0f5f3f164f sk=data4
id=4d65822107fcfd5278629a0f5f3f164f sk=data5
id=4d65822107fcfd5278629a0f5f3f164f sk=data6
```

* 在query逻辑中，带SortKey（多行）模式会返回key的所有内容，如：query(id=4d65822107fcfd5278629a0f5f3f164f)，会返回data1～data6所有内容。标准模式（多列）下，query和getItem等价。

### 功能逻辑测试

#### 测试原理：进行DynamoDB的基本功能和性能测试，测试步骤包括：

* 程序会先创建 stress-test-multicolumn 和 stress-test-multirow 两个表，按需模式，分别做 标准模式（多列）和 带SortKey（多行）模式的测试。
* 写入操作统一进行10分钟，读取操作统一进行5分钟，压测程序使用单线程进行请求，压测机型是m7i.large。
* 步骤一：批量写入操作，创建条目。
* 步骤二：批量读取操作，获取条目数据。
* 步骤三：单条读取操作（全量读取），获取条目数据。
* 步骤四：query操作（全量读取），获取条目数据。
* 步骤五：单条更新操作，更新条目。
* 步骤六：批量删除操作，删除条目。
* --------------------------
* 步骤七：单条写入操作，写入数据。
* 步骤八：单条读取操作（部分读取），获取条目数据。
* 步骤九：query操作（部分读取），获取条目数据。
* 步骤十：扫描操作（部分读取），获取条目数据。
* 步骤十一：单条删除操作（部分读取），获取条目数据。
* --------------------------
* 步骤十二：单条读取操作（读取miss），获取条目数据。
* 步骤十三：query操作（读取miss），获取条目数据。

```bash
./baseline-test.sh
```

#### 标准模式（多列）测试结果：

|  | 成功 | 失败 | QPS | 延迟ms | 参数 |
|-----|-----|-----|-----|-----|-----|
| 批量写 | 525450 | 0 | 875.75 | 1.14 | -t 600 -batchWriteItem 1 |
| 批量读 | 2184800 | 0 | 7282.67 | 0.14 | -t 300 -batchGetItem 1 |
| 单条取（全量） | 133574 | 0 | 445.25 | 2.25 | -t 300 -getItem 1 |
| Query（全量） | 125022 | 0 | 416.74 | 2.40 | -t 300 -query 1 |
| 单条更新 | 131380 | 0 | 218.97 | 4.57 | -t 600 -updateItem 1 |
| 批量删除 | 3072925 | 0 | 5121.54 | 0.20 | -t 600 -batchDeleteItem 1 |
| 单条写入 | 137682 | 0 | 229.47 | 4.36 | -t 600 -putItem 1 |
| ---- | ---- | ---- | ---- | ---- | ---- |
| 单条取（部分） | 130268 | 0 | 434.23 | 2.30 | -t 300 -getItem 1 |
| Query（部分） | 98292 | 0 | 327.64 | 3.05 | -t 300 -query 1 |
| Scan | 15287 | 0 | 50.96 | 19.62 | -t 300 -scan 1 |
| 单条删除 | 127795 | 0 | 212.99 | 4.70 | -t 600 -deleteItem 1 |
| ---- | ---- | ---- | ---- | ---- | ---- |
| 单条取（Miss） | 124576 | 0 | 415.25 | 2.41 | -t 300 -getItem 1 |
| Query（Miss） | 121633 | 0 | 405.44 | 2.47 | -t 300 -query 1 |

#### 带SortKey（多行）测试结果：

|  | 成功 | 失败 | QPS | 延迟ms | 参数 |
|-----|-----|-----|-----|-----|-----|
| 批量写 | 712068 | 0 | 1186.78 | 0.84 | -t 600 -batchWriteItem 1 |
| 批量读 | 2463000 | 0 | 8210.00 | 0.12 | -t 300 -batchGetItem 1 |
| 单条取（全量） | 191208 | 0 | 637.36 | 1.57 | -t 300 -getItem 1 |
| Query（全量） | 114354 | 0 | 381.18 | 2.62 | -t 300 -query 1 |
| 单条更新 | 179801 | 0 | 299.67 | 3.34 | -t 600 -updateItem 1 |
| 批量删除 | 705852 | 0 | 1176.42 | 0.85 | -t 600 -batchDeleteItem 1 |
| 单条写入 | 132483 | 0 | 220.81 | 4.53 | -t 600 -putItem 1 |
| ---- | ---- | ---- | ---- | ---- | ---- |
| 单条取（部分） | 146544 | 0 | 488.48 | 2.05 | -t 300 -getItem 1 |
| Query（部分） | 117981 | 0 | 393.27 | 2.54 | -t 300 -query 1 |
| Scan | 45773 | 0 | 152.58 | 6.55 | -t 300 -scan 1 |
| 单条删除 | 208119 | 0 | 346.87 | 2.88 | -t 600 -deleteItem 1 |
| ---- | ---- | ---- | ---- | ---- | ---- |
| 单条取（Miss） | 148865 | 0 | 496.22 | 2.02 | -t 300 -getItem 1 |
| Query（Miss） | 126858 | 0 | 422.86 | 2.36 | -t 300 -query 1 |

#### 测试结论：

* 所有带分区读写操作延迟都在5ms以下，Scan操作较重，应避免生产使用。
* 单条获取数据，无论数据是多列/多行，单列/单行，还是Miss情况下，延时都基本一致。
* 批量获取数据，性能会更高，如单次获取100条数据，平均延时只有0.14ms，是单条获取的16倍。
* Query在多行模式下，因为要聚合多条数据，延迟会有上升，如单id只有多条数据的情况下，单条获取是1.57ms，query会到2.62ms。

### 占用空间测试

#### 测试原理：相同数据，使用 标准模式（多列）和 带SortKey（多行）进行存储的对比

```bash
./space-test.sh
```

#### 测试结果

* 多列模式，写入是一批25，写400次，等于1万条记录，使用命令：-times 40000

* 多行模式，写入1次是5份记录，写10000次，等于5万条记录，使用命令：-sortkey -times 1000000

* 多轮测试信息如下：

| 标准模式（多列） |  |  |
|-----|-----|-----|
| Item数量 | 空间大小 | 平均Item大小 |
| 728,174 | 3.7 gigabytes | 5,059 bytes |
| 190,535,308 | 963.9 gigabytes | 5,059 bytes |
| 680,699,567 | 3.4 terabytes | 5,059 bytes |
| 786,804,601 | 4 terabytes | 5,059 bytes |
|-----|-----|-----|
| 带SortKey（多行）表 |  |  |
| 5,000,000 | 5.2 gigabytes | 1,044 bytes |
| 658,143,766 | 687.1 gigabytes | 1,044 bytes |
| 855,965,739 | 893.6 gigabytes | 1,044 bytes |

* 可见，两种模式下存储大小基本一致，多行模式会多了一些排序键的空间，平均1k内容情况下多出3%的空间消耗。

### 压力测试

可以使用 ./create-ddb-dashboard.sh 创建监控ddb和压测机的cloudwatch dashboard

测试数据量1TB，100K 预置 WCU/RCU 的性能 

测试数据量10TB，100K 预置 WCU/RCU 的性能 

测试数据量10TB，1M 预置 WCU/RCU 的性能 

写测试：验证整行更新场景

读测试：验证单条查询，多条查询（5个查询，20个查询）性能是否一致

### 标准模式（多列）建表语句参考

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

### 带SortKey（多行）建表语句参考

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
