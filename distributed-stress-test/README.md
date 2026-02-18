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
* action：对应 worker 中的不同任务，worker中有对应的实现，支持以下操作：
  * **putItem**: 完整覆盖写入，替换整个item的所有列
  * **updateItem**: 部分更新，只更新指定的列，保留其他列
  * **getItem**: 读取单个item的所有列（多行模式下，DynamoDB实际使用Query进行操作）
  * **getSubItem**: 读取单个item的某几列
  * **deleteItem**: 删除单个item
  * **batchGetItem**: 批量读取多个item（DynamoDB限制最多100个，多列模式下，DynamoDB实际使用多次Query完成）
  * **batchGetSubItem**: 批量读取多个item（DynamoDB限制最多100个，多列模式下，DynamoDB实际使用batchGetItem完成）
  * **batchPutItem**: 批量写入多个item（DynamoDB限制最多25个）
* seed：给随机发生器指定种子，方便多线程统一ID生成规则，随机数统一由控制端在每个任务初始化时生成，并持续使用，确保key生成顺序，不指定或指定0则生成随机。
* seeds：给出随机种子设定几率，如：[2.2,6.6] 表示种子1的几率是25%，种子2的几率是75%，指定seed可以明确生成规律。
* qps：指定产生多少qps的任务，需要把qps拆解到10毫秒级进行redis分批插入，以把请求分散均匀。
* qpss：提供24小时内的变化数组，0表示该小时数据需要平滑生成，可能存在相邻多个小时为0的情况。
* times：表示共产生多少次执行就完成。
* duration：表示执行多长时间（秒）就完成，需要确保精确数量和固定随机值请使用times指定。
* samples：表示data数据使用seed预先生成多少份，在实际填充时，在预先生成的数据中取，加快速度，如果不指定或0表示每次都需要产生随机数据。
*         在batchGetItem 和 batchPutItem时，表示每次批量操作的item数量，如果不指定默认10。注意DynamoDB限制：batchGetItem最多100，batchPutItem最多25。
*         注意：因为samples在这个时候指定item数量，item不会预先生成，随机逻辑相当于没有指定samples。以下操作两者相等。

```json
  {
    "action": "updateItem", /* putItem 也一样 */
    "seed": 2,
    "qps": 5,
    "times": 30,
    "data": {
      "randomkey_": {"r": 16, "len": 2000}, /* 列名通过 seed=2 随机种子生成，总共生成30个key */
      "longkey": 10000
    }
  },
  {
    "action": "batchPutItem",
    "seed": 2,
    "qps": 5,
    "times": 10,
    "samples": 3, /* 这里的samples 3代表每次批量数据是3个，不会提前生成3份样本数据 */
    "data": {
      "randomkey_": {"r": 16, "len": 2000}, /* 列名通过 seed=2 随机种子生成，每批3个，生成十份数据，总计30个key */
      "longkey": 10000
    }
  }
```

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
    /* 注意：需要写入随机数据和读取随机数据生成规律一致，需要指定相同的 seed 和 samples */
    "samples": 16, /* 程序会提前生成16份随机data，在后续生成2170660028次时，随机生成key，再在这16份数据中随机选择 */
    "data":{
      "request_": {"r":16, "len":8000}, /* 按 seed=1 随机种子，生成 request_0 ～ request_15 范围的key，value为8k长度的随机数 */
      "bid_": 10000, /* 指定key，value为10k长度随机数 */
      "impression": "this is text" /* 指定key和value */
    }
  },
  {
      "action": "query",
      "qps": 3600000,
      /* qpss 主要用于模拟流量峰谷，通过指定24小时每小时的qps比例，程序到对应时间切换为对应qps进行压测，为0的小时会使用前后数据进行填充 */
      "qpss": [0.7042,0,0,0,0.7746,0,0.8451,0,0.9155,0.9718,1.0000,0.9718,0.8451,0.5493,0.4366,0.4225,0.3662,0.3380,0.3662,0.4085,0.4789,0.5634,0.6338,0.6901],
      /* seeds指定多条目的请求比例，这里分别指定了seed=1～6的数据的请求比例，既可以实现读取命中键值，也可以实现不同大小键值的读取比例 */
      "seeds": [15.38,48.58,7.36,22.58,4.82,1.29],
      "duration": 86400
  }
]
```

traffic.json 中有更详细的例子，解释详见本文末尾。

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
go build -o worker worker.go database.go dynamodb_impl.go redis_impl.go multirow_dynamodb_impl.go multirow_redis_impl.go
```

### 测试命令

**启动 Publisher（带统计监控）：**
```bash
./task_publisher -redis localhost:6379 -prefix dst -config config.json -traffic traffic.json -stats
./task_publisher -redis elasticache-server:6379 -tls -prefix dst -config config.json -traffic traffic.json -stats
```

**启动 Worker（DynamoDB）：**
```bash
./worker -redis localhost:6379 -prefix dst -db dynamodb -stats
```

**启动 Worker（Redis/ElastiCache）：**
```bash
./worker -redis localhost:6379 -prefix dst -db redis -stats
```

**参数说明：**
- `-redis`: Redis 地址（用于任务队列和配置管理）
- `-prefix`: Redis key 前缀，默认 dst
- `-config`: 配置文件路径
- `-traffic`: 流量定义文件路径
- `-stats`: 启用统计监控
- `-db`: 数据库类型，dynamodb 或 redis（Worker）
- `-tls`: 启用 TLS 连接到 Redis

**统计输出示例：**

Publisher:
```
# 当前时间 T:经过时间 任务类型 Remind->[Gen/Batch/Redis]->Published QPS:当前QPS Q:当前消费队列[队列1 队列2 ... 队列10]
2026/02/18 02:46:10 T:3s putItem 87k->[8/6/5k]->0k QPS:8k Q:3k[2 3 4 3 4 2 2 3 2 4]
# 当前时间 W:节点名称 P:PutItem U:UpdateItem G:GetItem GS:GetSubItem D:DeleteItem BG:BatchGetItem BGS:BatchGetSubItem BP:BatchPutItem E:Error T:Total Q:Queue[详细列表]
2026/02/18 02:46:09 W:ip-10-21-2-136.ap-northeast-1.compute.internal P:0 U:0 G:0 GS:0 D:0 BG:0 BGS:0 BP:0 E:0 T:0 Q:0

```

Worker:
```
# 当前时间 T:经过时间 P:PutItem U:UpdateItem G:GetItem GS:GetSubItem D:DeleteItem BG:BatchGetItem BGS:BatchGetSubItem BP:BatchPutItem E:Error T:Total Q:Queue[详细列表]
2026/02/18 02:46:15 T:14s P:0 U:0 G:0 GS:0 D:0 BG:0 BGS:0 BP:0 E:0 T:0 Q:0[0 0 0 0 0 0 0 0 0 0]
```

- Pub: 已发布任务数
- Rem: 剩余任务数
- QPS: 当前 QPS
- Q: 总队列堆积[各线程队列长度]
- T: 运行时间
- Update/Query/Err: Worker 处理的操作数和错误数

## 多行模式实现说明

1. **multirow_dynamodb_impl.go** - DynamoDB 多行模式实现
2. **multirow_redis_impl.go** - Redis 多行模式实现

### 数据存储模式

#### DynamoDB 多行模式
- 使用复合主键：`id` (partition key) + `sk` (sort key)
- 每个列存储为单独的行
- 结构：`{id: "key", sk: "column_name", val: data}`

#### Redis 多行模式
- 使用 key 模式：`{id}:sk:{column_name}`
- 每个列存储为单独的 Redis key
- 示例：`user123:sk:request_1h_11`

### 使用方式

在 `config.json` 中，如果 `table_name` 以 `multirow` 开头，自动使用多行模式：

```json
{
  "table_name": "multirow-stress-test",
  "region": "us-east-1",
  "threads": 10
}
```

或者多列模式（默认）：

```json
{
  "table_name": "stress-test",
  "region": "us-east-1",
  "threads": 10
}
```

### 操作对应关系

| 操作 | 多列模式 (DynamoDB) | 多行模式 (DynamoDB) | 多列模式 (Redis) | 多行模式 (Redis) |
|------|---------|---------|-------------------|-----------------|
| putItem | 单行多列 PutItem | 多行单列 (每列一行) BatchWriteItem | SET | 多个 key (每列一个) 多次SET |
| updateItem | 单行多列 UpdateItem | 多行单列 (每列一行) BatchWriteItem | GET+SET | 多个 key (每列一个) 多次SET |
| getItem | 返回所有列 GetItem | Id查询返回所有行，Query | GET | Keys + GET 多个 key |
| getSubItem | 返回指定列 GetItem + Projection | BatchGetItem | GET+过滤(无法节省流量) | 多次GET |
| deleteItem | 单行删除 DeleteItem | 删除多行 Query+DeleteItem | DEL | Keys + DEL 多个key |
| batchGetItem | BatchGetItem | 多次Query | 多次GET | 多次getItem |
| batchGetSubItem | BatchGetItem + Projection | BatchGetItem | 多次GET+过滤(无法节省流量) | 多次getSubItem |
| batchPutItem | BatchWriteItem | 多次BatchWriteItem | 多次SET | 双循环多次SET |

* 注意：在多行模式下，putItem和updateItem实现是一样的，假设是putItem的时候，是全列进行更新。严格情况下，putItem语义应考虑需要把多余的行删除（或先进行整个删除再写）。
* Redis使用多列模式比较合适，但是需要考虑只获取单列的场景，获取流量是无法节省的（多行模式可以节省），可以考虑 多列+多行混合的模式。

### 性能特点

#### 多列模式
- 优点：单次操作获取完整数据，适合频繁读取完整记录
- 缺点：更新单列需要读取整行，列数过多影响性能

#### 多行模式
- 优点：更新单列高效，适合稀疏数据和频繁部分更新
- 缺点：读取完整记录需要多次操作或 Query

## traffic.json 例子解释

以下使用 DynamoDB 多行例子进行测试

### 写入-更新-读取

* 步骤一：写入两条数据，value也全部生成（randomkey_1和randomkey_15）

```json
{
  "action": "putItem",
  "seed": 1,
  "qps": 2,
  "times": 2,
  "data": {
    "randomkey_": {"r": 16, "len": 10},
    "sthkey": 5
  }
}
```

```bash
2026/02/18 02:46:09 Publishing list task: action=putItem, qps=2
dst_q0 {"action":"putItem","key":"52fdfc072182654f163f5f0f9a621d72","data":{"randomkey_1":10,"sthkey":5}}
dst_q1 {"action":"putItem","key":"9566c74d10037c4d7bbb0407d1e2c649","data":{"randomkey_15":10,"sthkey":5}}

2026/02/18 02:46:09 [DEBUG] putItem key=52fdfc072182654f163f5f0f9a621d72 data=map[randomkey_1:10 sthkey:5]
2026/02/18 02:46:09 [DEBUG] putItem key=9566c74d10037c4d7bbb0407d1e2c649 data=map[randomkey_15:10 sthkey:5]
```

* 步骤二：更新2条数据，使用一个固定的sample（randomkey_1）

```json
{
  "action": "updateItem",
  "seed": 1,
  "qps": 2,
  "times": 2,
  "samples": 1,
  "data": {
    "randomkey_": {"r": 16, "len": 5},
    "sthkey": 5
  }
}
```

```bash
2026/02/18 02:46:10 Publishing list task: action=updateItem, qps=2
dst_q0 {"data":{"sthkey":5,"randomkey_1":5},"action":"updateItem","key":"52fdfc072182654f163f5f0f9a621d72"}
dst_q1 {"data":{"sthkey":5,"randomkey_1":5},"action":"updateItem","key":"9566c74d10037c4d7bbb0407d1e2c649"}

2026/02/18 02:46:10 [DEBUG] updateItem key=9566c74d10037c4d7bbb0407d1e2c649 data=map[randomkey_1:5 sthkey:5]
2026/02/18 02:46:10 [DEBUG] updateItem key=52fdfc072182654f163f5f0f9a621d72 data=map[randomkey_1:5 sthkey:5]
```

* 步骤三：使用相同的随机种子获取这两个key内容，可以看到前面putItem的randomkey_15依然存在，randomkey_1已覆盖，长度已经更新为5

```json
{
  "action": "getItem",
  "seed": 1,
  "qps": 2,
  "times": 2
}
```

```bash
2026/02/18 02:46:11 Publishing list task: action=getItem, qps=2
dst_q0 {"action":"getItem","key":"52fdfc072182654f163f5f0f9a621d72"}
dst_q1 {"action":"getItem","key":"9566c74d10037c4d7bbb0407d1e2c649"}

2026/02/18 02:46:11 [DEBUG] getItem key=9566c74d10037c4d7bbb0407d1e2c649
2026/02/18 02:46:11 [DEBUG] getItem key=52fdfc072182654f163f5f0f9a621d72
2026/02/18 02:46:11 [DEBUG] getItem result=map[randomkey_1:[0 62 38 31 197] randomkey_15:[54 36 36 215 175 235 134 94 203 80] sthkey:[102 225 182 195 78]]
2026/02/18 02:46:11 [DEBUG] getItem result=map[randomkey_1:[181 1 154 168 126] sthkey:[219 61 127 34 106]]
```

* 步骤四：使用相同的随机种子获取这两个key的子键内容，value配置生成的键值（randomkey_1和randomkey_15），可以得到对应的列值

```json
{
  "action": "getSubItem",
  "seed": 1,
  "qps": 2,
  "times": 2,
  "data": {
    "randomkey_": {"r": 16, "len": 5},
    "sthkey": 5
  }
}
```

```bash
2026/02/18 02:46:12 Publishing list task: action=getSubItem, qps=2
dst_q0 {"action":"getSubItem","key":"52fdfc072182654f163f5f0f9a621d72","data":{"sthkey":5,"randomkey_1":5}}
dst_q1 {"action":"getSubItem","key":"9566c74d10037c4d7bbb0407d1e2c649","data":{"sthkey":5,"randomkey_15":5}}

2026/02/18 02:46:12 [DEBUG] getSubItem key=9566c74d10037c4d7bbb0407d1e2c649 columns=[sthkey randomkey_15]
2026/02/18 02:46:12 [DEBUG] getSubItem key=52fdfc072182654f163f5f0f9a621d72 columns=[sthkey randomkey_1]
2026/02/18 02:46:13 [DEBUG] getSubItem result=map[randomkey_1:[181 1 154 168 126] sthkey:[219 61 127 34 106]]
2026/02/18 02:46:13 [DEBUG] getSubItem result=map[randomkey_15:[54 36 36 215 175 235 134 94 203 80] sthkey:[102 225 182 195 78]]
```

* 步骤五：使用相同的随机种子获取这两个key的子键内容，使用一个固定的sample（randomkey_1），获取对应列值成功

```bash
{
  "action": "getSubItem",
  "seed": 1,
  "qps": 2,
  "times": 2,
  "samples": 1,
  "data": {
    "randomkey_": {"r": 16, "len": 5}
  }
}
```

```bash
2026/02/18 02:46:13 Publishing list task: action=getSubItem, qps=2
dst_q0 {"action":"getSubItem","key":"52fdfc072182654f163f5f0f9a621d72","data":{"randomkey_1":5}}
dst_q1 {"action":"getSubItem","key":"9566c74d10037c4d7bbb0407d1e2c649","data":{"randomkey_1":5}}

2026/02/18 02:46:13 [DEBUG] getSubItem key=52fdfc072182654f163f5f0f9a621d72 columns=[randomkey_1]
2026/02/18 02:46:13 [DEBUG] getSubItem key=9566c74d10037c4d7bbb0407d1e2c649 columns=[randomkey_1]
2026/02/18 02:46:13 [DEBUG] getSubItem result=map[randomkey_1:[0 62 38 31 197]]
2026/02/18 02:46:13 [DEBUG] getSubItem result=map[randomkey_1:[181 1 154 168 126]]
```

### 批写-批读

* 步骤六：使用相同的随机种子批量写入内容，可见key和列名，都和步骤一的putItem一致，并新写入了两条数据。

```json
{
  "action": "batchPutItem",
  "seed": 1,
  "qps": 2,
  "times": 2,
  "samples": 2,
  "data": {
    "randomkey_": {"r": 16, "len": 2}
  }
}
```

```bash
2026/02/18 06:58:52 Publishing list task: action=batchPutItem, qps=2
dst_q0 {"action":"batchPutItem","items":{"52fdfc072182654f163f5f0f9a621d72":{"randomkey_1":2},"9566c74d10037c4d7bbb0407d1e2c649":{"randomkey_15":2}}}
dst_q1 {"action":"batchPutItem","items":{"81855ad8681d0d86d1e91e00167939cb":{"randomkey_7":2},"6694d2c422acd208a0072939487f6999":{"randomkey_11":2}}}

2026/02/18 06:58:52 [DEBUG] batchPutItem items=map[52fdfc072182654f163f5f0f9a621d72:map[randomkey_1:2] 9566c74d10037c4d7bbb0407d1e2c649:map[randomkey_15:2]]
2026/02/18 06:58:52 [DEBUG] batchPutItem items=map[6694d2c422acd208a0072939487f6999:map[randomkey_11:2] 81855ad8681d0d86d1e91e00167939cb:map[randomkey_7:2]]
```

* 步骤七：使用相同的随机种子批量读取内容，可见key和列名，内容都和步骤三的getItem一致，步骤六新写的两条数据也能正确读取，对应键值长度也更新为2。

```json
{
  "action": "batchGetItem",
  "seed": 1,
  "qps": 2,
  "times": 2,
  "samples": 2
}
```

```bash
2026/02/18 06:58:53 Publishing list task: action=batchGetItem, qps=2
dst_q0 {"action":"batchGetItem","items":["52fdfc072182654f163f5f0f9a621d72","9566c74d10037c4d7bbb0407d1e2c649"]}
dst_q1 {"action":"batchGetItem","items":["81855ad8681d0d86d1e91e00167939cb","6694d2c422acd208a0072939487f6999"]}

2026/02/18 06:58:53 [DEBUG] batchGetItem keys=[81855ad8681d0d86d1e91e00167939cb 6694d2c422acd208a0072939487f6999]
2026/02/18 06:58:53 [DEBUG] batchGetItem keys=[52fdfc072182654f163f5f0f9a621d72 9566c74d10037c4d7bbb0407d1e2c649]
2026/02/18 06:58:53 [DEBUG] batchGetItem result=[map[randomkey_7:[138 74]] map[randomkey_11:[66 58]]]
2026/02/18 06:58:53 [DEBUG] batchGetItem result=[map[randomkey_1:[61 59] sthkey:[159 97 125 224 246]] map[randomkey_1:[159 136 34 42 150] randomkey_15:[50 42] sthkey:[32 79 38 245 222]]]
```

* 步骤八：使用相同的随机种子批量读取内容，可见key和列名，内容都和步骤三的getItem一致，且列名已经进行了混合。

```json
{
  "action": "batchGetSubItem",
  "seed": 1,
  "qps": 2,
  "times": 2,
  "samples": 2,
  "data": {
    "randomkey_": {"r": 16, "len": 2}
  }
}
```

```bash
2026/02/18 07:15:45 Publishing list task: action=batchGetSubItem, qps=2
dst_q0 {"items":["52fdfc072182654f163f5f0f9a621d72","9566c74d10037c4d7bbb0407d1e2c649"],"data":{"randomkey_1":2,"randomkey_15":2},"action":"batchGetSubItem"}
dst_q1 {"items":["81855ad8681d0d86d1e91e00167939cb","6694d2c422acd208a0072939487f6999"],"data":{"randomkey_7":2,"randomkey_11":2},"action":"batchGetSubItem"}

2026/02/18 07:15:45 [DEBUG] batchGetSubItem keys=[81855ad8681d0d86d1e91e00167939cb 6694d2c422acd208a0072939487f6999] columns=[randomkey_11 randomkey_7]
2026/02/18 07:15:45 [DEBUG] batchGetSubItem keys=[52fdfc072182654f163f5f0f9a621d72 9566c74d10037c4d7bbb0407d1e2c649] columns=[randomkey_1 randomkey_15]
2026/02/18 07:15:45 [DEBUG] batchGetSubItem result=[map[randomkey_7:[202 150]] map[randomkey_11:[253 56]]]
2026/02/18 07:15:45 [DEBUG] batchGetSubItem result=[map[randomkey_1:[201 89]] map[randomkey_1:[150 214 96 97 103] randomkey_15:[179 219]]]
```

* 步骤九：使用相同的随机种子选择这两个key内容，进行删除，所有测试内容已经清空

```json
{
  "action": "deleteItem",
  "seed": 1,
  "qps": 2,
  "times": 4
}
```

```bash
2026/02/18 07:32:38 Publishing list task: action=deleteItem, qps=2
dst_q0 {"action":"deleteItem","key":"52fdfc072182654f163f5f0f9a621d72"}
dst_q1 {"action":"deleteItem","key":"9566c74d10037c4d7bbb0407d1e2c649"}
dst_q2 {"action":"deleteItem","key":"81855ad8681d0d86d1e91e00167939cb"}
dst_q3 {"action":"deleteItem","key":"6694d2c422acd208a0072939487f6999"}

2026/02/18 07:32:38 [DEBUG] deleteItem key=9566c74d10037c4d7bbb0407d1e2c649
2026/02/18 07:32:38 [DEBUG] deleteItem key=81855ad8681d0d86d1e91e00167939cb
2026/02/18 07:32:38 [DEBUG] deleteItem key=6694d2c422acd208a0072939487f6999
2026/02/18 07:32:38 [DEBUG] deleteItem key=52fdfc072182654f163f5f0f9a621d72
```

以下使用 DynamoDB 多列例子进行测试

```bash
2026/02/18 07:35:03 Publishing list task: action=putItem, qps=2
dst_q0 {"action":"putItem","key":"52fdfc072182654f163f5f0f9a621d72","data":{"randomkey_1":10,"sthkey":5}}
dst_q1 {"action":"putItem","key":"9566c74d10037c4d7bbb0407d1e2c649","data":{"sthkey":5,"randomkey_15":10}}

2026/02/18 07:35:03 [DEBUG] putItem key=52fdfc072182654f163f5f0f9a621d72 data=map[randomkey_1:10 sthkey:5]
2026/02/18 07:35:03 [DEBUG] putItem key=9566c74d10037c4d7bbb0407d1e2c649 data=map[randomkey_15:10 sthkey:5]
-----------------------------------------------------------------------------------------------------------
2026/02/18 07:35:04 Publishing list task: action=updateItem, qps=2
dst_q0 {"action":"updateItem","key":"52fdfc072182654f163f5f0f9a621d72","data":{"randomkey_1":5,"sthkey":5}}
dst_q1 {"action":"updateItem","key":"9566c74d10037c4d7bbb0407d1e2c649","data":{"randomkey_1":5,"sthkey":5}}

2026/02/18 07:35:04 [DEBUG] updateItem key=9566c74d10037c4d7bbb0407d1e2c649 data=map[randomkey_1:5 sthkey:5]
2026/02/18 07:35:04 [DEBUG] updateItem key=52fdfc072182654f163f5f0f9a621d72 data=map[randomkey_1:5 sthkey:5]
-----------------------------------------------------------------------------------------------------------
2026/02/18 07:35:05 Publishing list task: action=getItem, qps=2
dst_q0 {"action":"getItem","key":"52fdfc072182654f163f5f0f9a621d72"}
dst_q1 {"action":"getItem","key":"9566c74d10037c4d7bbb0407d1e2c649"}

2026/02/18 07:35:05 [DEBUG] getItem key=52fdfc072182654f163f5f0f9a621d72
2026/02/18 07:35:05 [DEBUG] getItem key=9566c74d10037c4d7bbb0407d1e2c649
2026/02/18 07:35:05 [DEBUG] getItem result=map[randomkey_1:[178 186 74 100 11] randomkey_15:[88 52 70 62 108 247 108 233 147 239] sthkey:[177 25 123 208 67]]
2026/02/18 07:35:05 [DEBUG] getItem result=map[randomkey_1:[52 78 204 234 246] sthkey:[239 203 62 196 214]]
-----------------------------------------------------------------------------------------------------------
2026/02/18 07:35:06 Publishing list task: action=getSubItem, qps=2
dst_q0 {"key":"52fdfc072182654f163f5f0f9a621d72","data":{"randomkey_1":5,"sthkey":5},"action":"getSubItem"}
dst_q1 {"action":"getSubItem","key":"9566c74d10037c4d7bbb0407d1e2c649","data":{"randomkey_15":5,"sthkey":5}}

2026/02/18 07:35:06 [DEBUG] getSubItem key=9566c74d10037c4d7bbb0407d1e2c649 columns=[randomkey_15 sthkey]
2026/02/18 07:35:06 [DEBUG] getSubItem key=52fdfc072182654f163f5f0f9a621d72 columns=[randomkey_1 sthkey]
2026/02/18 07:35:06 [DEBUG] getSubItem result=map[randomkey_1:[52 78 204 234 246] sthkey:[239 203 62 196 214]]
2026/02/18 07:35:06 [DEBUG] getSubItem result=map[randomkey_15:[88 52 70 62 108 247 108 233 147 239] sthkey:[177 25 123 208 67]]
-----------------------------------------------------------------------------------------------------------
2026/02/18 07:35:07 Publishing list task: action=getSubItem, qps=2
dst_q0 {"data":{"randomkey_1":5},"action":"getSubItem","key":"52fdfc072182654f163f5f0f9a621d72"}
dst_q1 {"data":{"randomkey_1":5},"action":"getSubItem","key":"9566c74d10037c4d7bbb0407d1e2c649"}

2026/02/18 07:35:07 [DEBUG] getSubItem key=9566c74d10037c4d7bbb0407d1e2c649 columns=[randomkey_1]
2026/02/18 07:35:07 [DEBUG] getSubItem key=52fdfc072182654f163f5f0f9a621d72 columns=[randomkey_1]
2026/02/18 07:35:07 [DEBUG] getSubItem result=map[randomkey_1:[52 78 204 234 246]]
2026/02/18 07:35:07 [DEBUG] getSubItem result=map[randomkey_1:[178 186 74 100 11]]
-----------------------------------------------------------------------------------------------------------
2026/02/18 07:35:08 Publishing list task: action=batchPutItem, qps=2
dst_q0 {"action":"batchPutItem","items":{"52fdfc072182654f163f5f0f9a621d72":{"randomkey_1":2},"9566c74d10037c4d7bbb0407d1e2c649":{"randomkey_15":2}}}
dst_q1 {"action":"batchPutItem","items":{"81855ad8681d0d86d1e91e00167939cb":{"randomkey_7":2},"6694d2c422acd208a0072939487f6999":{"randomkey_11":2}}}

2026/02/18 07:35:08 [DEBUG] batchPutItem items=map[6694d2c422acd208a0072939487f6999:map[randomkey_11:2] 81855ad8681d0d86d1e91e00167939cb:map[randomkey_7:2]]
2026/02/18 07:35:08 [DEBUG] batchPutItem items=map[52fdfc072182654f163f5f0f9a621d72:map[randomkey_1:2] 9566c74d10037c4d7bbb0407d1e2c649:map[randomkey_15:2]]
-----------------------------------------------------------------------------------------------------------
2026/02/18 07:35:09 Publishing list task: action=batchGetItem, qps=2
dst_q0 {"action":"batchGetItem","items":["52fdfc072182654f163f5f0f9a621d72","9566c74d10037c4d7bbb0407d1e2c649"]}
dst_q1 {"action":"batchGetItem","items":["81855ad8681d0d86d1e91e00167939cb","6694d2c422acd208a0072939487f6999"]}

2026/02/18 07:35:09 [DEBUG] batchGetItem keys=[81855ad8681d0d86d1e91e00167939cb 6694d2c422acd208a0072939487f6999]
2026/02/18 07:35:09 [DEBUG] batchGetItem keys=[52fdfc072182654f163f5f0f9a621d72 9566c74d10037c4d7bbb0407d1e2c649]
2026/02/18 07:35:09 [DEBUG] batchGetItem result=[map[randomkey_7:[193 115]] map[randomkey_11:[147 224]]]
2026/02/18 07:35:09 [DEBUG] batchGetItem result=[map[randomkey_1:[243 119] sthkey:[239 203 62 196 214]] map[randomkey_1:[178 186 74 100 11] randomkey_15:[79 106] sthkey:[177 25 123 208 67]]]
-----------------------------------------------------------------------------------------------------------
2026/02/18 07:35:10 Publishing list task: action=batchGetSubItem, qps=2
dst_q0 {"action":"batchGetSubItem","items":["52fdfc072182654f163f5f0f9a621d72","9566c74d10037c4d7bbb0407d1e2c649"],"data":{"randomkey_1":2,"randomkey_15":2}}
dst_q1 {"action":"batchGetSubItem","items":["81855ad8681d0d86d1e91e00167939cb","6694d2c422acd208a0072939487f6999"],"data":{"randomkey_7":2,"randomkey_11":2}}

2026/02/18 07:35:10 [DEBUG] batchGetSubItem keys=[81855ad8681d0d86d1e91e00167939cb 6694d2c422acd208a0072939487f6999] columns=[randomkey_7 randomkey_11]
2026/02/18 07:35:10 [DEBUG] batchGetSubItem keys=[52fdfc072182654f163f5f0f9a621d72 9566c74d10037c4d7bbb0407d1e2c649] columns=[randomkey_1 randomkey_15]
2026/02/18 07:35:10 [DEBUG] batchGetSubItem result=[map[randomkey_7:[193 115]] map[randomkey_11:[147 224]]]
2026/02/18 07:35:10 [DEBUG] batchGetSubItem result=[map[randomkey_1:[243 119]] map[randomkey_1:[178 186 74 100 11] randomkey_15:[79 106]]]
-----------------------------------------------------------------------------------------------------------
2026/02/18 07:35:11 Publishing list task: action=deleteItem, qps=2
dst_q0 {"action":"deleteItem","key":"52fdfc072182654f163f5f0f9a621d72"}
dst_q1 {"action":"deleteItem","key":"9566c74d10037c4d7bbb0407d1e2c649"}
dst_q2 {"key":"81855ad8681d0d86d1e91e00167939cb","action":"deleteItem"}
dst_q3 {"key":"6694d2c422acd208a0072939487f6999","action":"deleteItem"}

2026/02/18 07:35:11 [DEBUG] deleteItem key=81855ad8681d0d86d1e91e00167939cb
2026/02/18 07:35:11 [DEBUG] deleteItem key=6694d2c422acd208a0072939487f6999
2026/02/18 07:35:11 [DEBUG] deleteItem key=52fdfc072182654f163f5f0f9a621d72
2026/02/18 07:35:11 [DEBUG] deleteItem key=9566c74d10037c4d7bbb0407d1e2c649
```