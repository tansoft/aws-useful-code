# DynamoDB 费用计算工具 (ddb_calc.py)

## 功能概述

精确计算 DynamoDB 在不同存储模式和计费模式下的费用，支持多个 traffic 文件合并分析。

## 使用方法

```bash
# 单个文件
python ddb_calc.py traffic_write.json

# 多个文件合并计算
python ddb_calc.py traffic_write.json traffic_read.json

# 输出
# - 生成 traffic_write.xlsx（以第一个文件名命名）
# - 包含两个标签页：多列模式 和 多行模式
```

## 核心实现要点

### 1. 两种存储模式对比

#### 多列模式 (Multi-Column)
- **存储结构**：`{id: "key", col1: data1, col2: data2, ...}`
- **实现文件**：`dynamodb_impl.go`
- **操作特点**：
  - PutItem/UpdateItem：一次操作写入所有列
  - GetItem：一次操作返回所有列
  - GetSubItem：使用 ProjectionExpression 只返回指定列
  - BatchGetItem/BatchPutItem：直接使用 DynamoDB API
  - DeleteItem：一次 DeleteItem 操作
- **适用场景**：频繁读取完整记录，列数较少

#### 多行模式 (Multi-Row)
- **存储结构**：`{id: "key", sk: "col1", val: data1}`, `{id: "key", sk: "col2", val: data2}`
- **实现文件**：`multirow_dynamodb_impl.go`
- **操作特点**：
  - PutItem/UpdateItem：使用 BatchWriteItem，每列一个 item
  - GetItem：使用 Query 操作，读取所有行
  - GetSubItem：使用 BatchGetItem，指定每个列的复合键
  - BatchGetItem：需要多次 Query（代码中用并发 goroutine）
  - BatchPutItem：多次 BatchWriteItem（每批最多25个，需分批）
  - DeleteItem：先 Query 再逐行 DeleteItem
- **适用场景**：稀疏数据，频繁部分更新，列数较多

### 2. 费用计算差异

#### 多列模式费用
- **写入 WCU**：操作数 × ROUNDUP(item_size_kb, 1)
- **读取 RCU**：操作数 × ROUNDUP(item_size_kb/4, 1) × 0.5（最终一致性）
- **峰值容量**：峰值 QPS
- **存储**：总数据量（GB）

#### 多行模式费用（关键差异）
- **写入 WCU**：操作数 × 平均列数 × ROUNDUP(item_size_kb, 1)
  - 原因：每列一行，需要多次写入
- **读取 RCU**：操作数 × 平均列数 × ROUNDUP(item_size_kb/4, 1) × 0.5
  - 原因：GetItem 使用 Query，需读取所有列的行
- **峰值容量**：峰值 QPS × 平均列数
  - 原因：并发操作需要更高的预置容量
- **存储**：总数据量（GB）× 平均列数
  - 原因：每行有额外的 id、sk 字段开销

### 3. 数据统计逻辑

#### 标签页1：基础数据
1. Seed数据定义表（每个seed一行）
   • Seed编号
   • 列名
   • 单列大小(KB)
   • 列数
   • Item总大小(KB)
   • 多列WCU/次 = ROUNDUP(Item总大小, 0)
   • 多行WCU/次 = ROUNDUP(单列大小, 0)
   • 多行RCU/次 = ROUNDUP(单列大小/4, 0) × 0.5
   • 多列RCU/次 = ROUNDUP(Item总大小/4, 0) × 0.5

2. 写入操作明细（每个操作一行，qpss+seeds会展开为多行）
   • 操作类型、Seed、小时、QPS、操作次数、列数、Item大小、数据量

3. 读取操作明细（每个操作一行，qpss+seeds会展开为多行）
   • 操作类型、Seed、小时、QPS、操作次数、列数、Item大小

#### 标签页2：多列模式计算
引用基础数据，计算：
• 写入：操作次数 × 多列WCU/次（VLOOKUP seed定义表）
• 读取：操作次数 × 多列RCU/次（VLOOKUP seed定义表）
• 存储：数据量汇总
• 费用汇总

#### 标签页3：多行模式计算
引用基础数据，计算：
• 写入：操作次数 × 列数 × 多行WCU/次
• 读取：操作次数 × 列数 × 多行RCU/次
• 存储：数据量 × 列数
• 费用汇总

这个设计确保了：
1. 所有原始数据在"基础数据"表中，可以手动修改
2. 两个模式的计算表通过公式引用基础数据
3. 修改基础数据后，两个模式的费用自动重新计算

```python
# 从 traffic.json 提取的关键指标
stats = {
    'write_ops': [],              # 写操作列表
    'read_ops': [],               # 读操作列表
    'peak_write_qps': 0,          # 峰值写 QPS
    'peak_read_qps': 0,           # 峰值读 QPS
    'avg_columns': 1,             # 平均每项的列数
    'total_data_size_gb': 0,      # 总数据量（GB）
}

# 操作类型映射
写操作：putItem, updateItem, deleteItem, batchPutItem
读操作：getItem, getSubItem, batchGetItem, batchGetSubItem

# 列数计算
num_columns = len(data)  # data 字段中的键数量
avg_columns = total_columns / total_ops

# 数据量计算
item_size_kb = sum(所有列的数据长度) / 1024
total_data_size_gb = sum(所有写操作的数据量) / (1024 * 1024)
```

### 4. DynamoDB 定价（us-east-1）

```python
PRICING = {
    'on_demand_write': 1.25,              # $/百万 WRU
    'on_demand_read': 0.25,               # $/百万 RRU
    'provisioned_wcu_hour': 0.00065,      # $/WCU-小时
    'provisioned_rcu_hour': 0.00013,      # $/RCU-小时
    'reserved_wcu_hour_1y': 0.000403,     # $/WCU-小时（1年预留）
    'reserved_rcu_hour_1y': 0.0000806,    # $/RCU-小时（1年预留）
    'reserved_wcu_hour_3y': 0.000260,     # $/WCU-小时（3年预留）
    'reserved_rcu_hour_3y': 0.0000520,    # $/RCU-小时（3年预留）
    'reserved_upfront_wcu_100_1y': 197,   # 每100 WCU 预付费（1年）
    'reserved_upfront_rcu_100_1y': 39,    # 每100 RCU 预付费（1年）
    'reserved_upfront_wcu_100_3y': 380,   # 每100 WCU 预付费（3年）
    'reserved_upfront_rcu_100_3y': 76,    # 每100 RCU 预付费（3年）
    'storage_gb_month': 0.25,             # $/GB-月
}
```

### 5. Excel 报表结构

每个标签页包含：

1. **模式说明**：存储结构和特点
2. **流量摘要**：时长、峰值 QPS、平均列数
3. **写入费用分析**：
   - 总写入操作数
   - WCU 消耗计算
   - 峰值 WCU 和 WCU-小时
   - 按需/预置/预留费用
4. **存储费用分析**：
   - 总数据量
   - 多行模式存储开销（× 平均列数）
   - 存储费用
5. **读取费用分析**：
   - 总读取操作数
   - RCU 消耗计算
   - 峰值 RCU 和 RCU-小时
   - 按需/预置/预留费用
6. **月度费用对比**：
   - 按需模式
   - 预置模式（按峰值）
   - 1年预留（含预付费月均摊）
   - 3年预留（含预付费月均摊）
   - 总计 = 写入 + 读取 + 存储

### 6. 关键公式

```python
# WCU 计算（1KB = 1 WCU）
wcu_per_write = ROUNDUP(item_size_kb, 1)
total_wcu = operations × wcu_per_write

# 多行模式 WCU
total_wcu_multirow = operations × avg_columns × wcu_per_write

# RCU 计算（4KB = 1 RCU，最终一致性 × 0.5）
rcu_per_read = ROUNDUP(item_size_kb / 4, 1) × 0.5
total_rcu = operations × rcu_per_read

# 多行模式 RCU
total_rcu_multirow = operations × avg_columns × rcu_per_read

# 峰值容量（预置/预留模式）
peak_wcu_hours = peak_wcu × 730  # 每月 730 小时

# 预留费用（含预付）
reserved_cost = (peak_capacity_hours × hourly_rate) + 
                (ROUNDUP(peak_capacity/100, 0) × upfront_fee / months)

# 存储费用
storage_cost = data_size_gb × 0.25  # 多行模式需 × avg_columns
```

## 多文件合并逻辑

```python
# 支持多个 traffic 文件
python ddb_calc.py traffic1.json traffic2.json traffic3.json

# 合并规则
- 操作数：累加所有文件的操作
- 峰值 QPS：取所有文件的最大值
- 平均列数：所有操作的加权平均
- 数据量：累加所有写操作的数据量
```

## 扩展建议

### 添加新的计费模式
在 `add_cost_sheet()` 函数中添加新的定价行。

### 支持其他区域定价
修改 `PRICING` 字典，或添加命令行参数 `--region`。

### 添加备份费用
在存储费用部分添加备份相关计算。

### 支持 Global Tables
考虑跨区域复制的写入放大（2倍 WCU）。

### 添加流式导出费用
计算 DynamoDB Streams 或 Kinesis Data Streams 费用。

## 依赖

```bash
pip install openpyxl
```

## 注意事项

1. **多行模式开销**：每列一行会显著增加操作次数和存储空间
2. **峰值容量**：预置/预留模式按峰值计费，需考虑流量波动
3. **预留容量**：按 100 为单位购买，需向上取整
4. **预付费摊销**：1年预留分12个月，3年预留分36个月
5. **最终一致性**：读取 RCU 计算使用 0.5 倍率，强一致性需改为 1.0
6. **BatchWriteItem 限制**：最多 25 个 item，多行模式需分批
7. **BatchGetItem 限制**：最多 100 个 item

## 文件关系

```
ddb_calc.py              # 费用计算工具
├── 读取 traffic.json    # 流量定义
├── 生成 .xlsx           # Excel 报表
│   ├── 多列模式标签页
│   └── 多行模式标签页
└── 参考实现
    ├── dynamodb_impl.go        # 多列模式实现
    └── multirow_dynamodb_impl.go  # 多行模式实现
```
