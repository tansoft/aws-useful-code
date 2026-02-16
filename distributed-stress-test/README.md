# 分布式压力测试框架

## 架构说明

该框架主要解决进行流量精准模拟的时候，很难进行分布式程序的统一调度和管理，因此通过Redis订阅的方式实现配置的管理和任务分发：

### Redis设计

* prefix默认为dst，可以通过启动参数指定
* {prefix}_cfg：存储配置信息，各个worker启动时需要获取配置信息
* {prefix}_notify：订阅控制端消息，默认支持的消息包括：重新获取配置信息 update_config，执行bash脚本 execute_bash，重启机器 reboot_instance，终止机器 terminate_instance 等，可针对不同场景可自行实现扩充。
* {prefix}_q{n}：压测任务队列，各worker按顺序进行订阅和消费，获取任务后进行具体操作。
* {prefix}_stats：worker可以把状态进行上报，控制端订阅该消息，可以获取到worker的工作情况。

### 配置文件设计

* config.json 配置文件

```json
{
  "table_name": "stress-test",
  "region": "us-east-1",
  "threads": 10,
  "sample_data":
[
  {
    "bid_feedback_1h_16": 140,
    "bid_feedback_1h_2": 139
  },
  {
    "request_1h_11": 154,
    "request_1h_3": 231,
    "request_1h_6": 77,
    "request_1h_7": 77
  },
  {
    "request_1h_13": 83
  },
  {
    "request_1h_16": 186,
    "request_1h_2": 77,
    "request_1h_4": 376,
    "request_1h_6": 77
  }
]
}
```

* traffic.json 流量定义，供发布端使用

文件格式为列表，顺序完成各个任务，顺序执行列表中的对象，对象中有任务的详细说明；如果对象为列表，说明该对象里是需要同时进行的子任务，这时为子任务新建线程处理，同时执行。

* 字段说明：
* action：对应 worker 中的不同任务，worker中有对应的实现，如updateItem，query。
* seed：给随机发生器指定种子，方便多线程统一ID生成规则，随机数统一由控制端在每个任务初始化时生成，并持续使用，确保key生成顺序，不指定或指定0则生成随机。
* seeds：给出随机种子设定几率，如：[2.2,6.6] 表示种子1的几率是25%，种子2的几率是75%，指定seed可以明确生成规律。
* qps：指定产生多少qps的任务，需要把qps拆解到10毫秒级进行redis分批插入，以把请求分散均匀。
* qpss：提供24小时内的变化数组，0表示该小时数据需要平滑生成，可能存在相邻多个小时为0的情况。
* times：表示共产生多少次执行就完成。
* duration：表示执行多长时间（秒）就完成。
* samples：表示data数据使用seed预先生成多少份，在实际填充时，在预先生成的数据中取，加快速度，如果不指定或0表示每次都需要产生随机数据。
* data：表示对应要设置的value，data中可能存在多列，语义是整行多列一起更新。data中列名对应的value有不同含义：
  * 如果是字符串，表示是实际内容
  * 如果是数字表示是二进制数据的长度
  * 如果是对象，说明列名需要用随机数余r生成，len表示数据长度。

```json
[
  {
    "action": "updateItem",
    "seed": 1,
    "qps": 5000000,
    "times": 2170660028,
    "samples": 16,
    "data":{
      "request_": {"r":16, "len":8000},
      "bid_feedback_2": 10000,
      "impression": "this is text"
    }
  },
  {
      "action": "query",
      "qps": 3600000,
      "qpss": [0.7042,0,0,0,0.7746,0,0.8451,0,0.9155,0.9718,1.0000,0.9718,0.8451,0.5493,0.4366,0.4225,0.3662,0.3380,0.3662,0.4085,0.4789,0.5634,0.6338,0.6901],
      "seeds": [15.38,48.58,7.36,22.58,4.82,1.29],
      "duration": 86400
  },
  {
    ...
  }
]
```

### 控制端

task_publisher.go 根据traffic.json定义，进行流量精确控制，把任务发送到redis队列中，供worker消费

* 命令行参数可以设置prefix，指定config.json，和指定traffic.json。
* 控制端启动后，先检查 {prefix}_cfg 的配置，和目录中的 config.json 是否一致，如果不一样，按 config.json 更新 redis 里的 {prefix}_cfg，然后向 {prefix}_notify 发送配置更新信息。
* 根据 traffic.json 定义，进行流量精确控制，把任务发送到redis队列 {prefix}_q{n} 中，供 worker 消费
* 需要考虑生成qps比较大，投递redis比较繁忙，需要确保时间的精确性，考虑Sleep精度是否足够，考虑长期运行下来的误差修复。

### worker端

* 通过命令行参数传入redis地址和prefix，启动后，先从redis获取配置{prefix}_cfg，并进行通知{prefix}_notify监听，根据配置threads启动线程，线程订阅对应的{prefix}_q{n}，获取任务并执行。
* {prefix}_notify 监听中，进行常用命令的处理。

## 快速开始

### 编译

```bash
go mod tidy
go build -o task_publisher task_publisher.go
go build -o worker worker.go database.go dynamodb_impl.go redis_impl.go
```

### 测试命令

**启动 Publisher（带统计监控）：**
```bash
./task_publisher -redis localhost:6379 -prefix dst -config config.json -traffic traffic.json -stats
./task_publisher -redis elasticache-server:6379 -tls -prefix dst -config config.json -traffic traffic.json -stats
```

**启动 Worker（DynamoDB）：**
```bash
./worker -redis localhost:6379 -prefix dst -db dynamodb
```

**启动 Worker（Redis/ElastiCache）：**
```bash
./worker -redis localhost:6379 -prefix dst -db redis
```

**参数说明：**
- `-redis`: Redis 地址（用于任务队列和配置管理）
- `-prefix`: Redis key 前缀，默认 dst
- `-config`: 配置文件路径
- `-traffic`: 流量定义文件路径
- `-stats`: 启用统计监控（Publisher）
- `-db`: 数据库类型，dynamodb 或 redis（Worker）

**统计输出示例：**
```
[STATS] updateItem | Pub:12345 Rem:87655 QPS:5000 Q:234[45 52 48 43 46] T:2s
```
- Pub: 已发布任务数
- Rem: 剩余任务数
- QPS: 当前 QPS
- Q: 总队列堆积[各线程队列长度]
- T: 运行时间
