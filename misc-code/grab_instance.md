# grab_instance.py — 抢占 GPU 实例

支持三种模式获取 GPU 资源：On-Demand 重试抢占、EC2 Capacity Blocks 预留、SageMaker Training Plans 预留。默认机型 `p5.4xlarge`，可通过 `--instance-type` 指定其他机型。

## 前置条件

```bash
pip install boto3
aws configure  # 确保 AWS credentials 已配置
```

确认目标机型的 Service Quota 足够（EC2 控制台 → Service Quotas → Running On-Demand P instances）。

## 通用参数

| 参数 | 说明 |
|------|------|
| `--region` | AWS 区域（必填，如 `us-east-1`） |
| `--az` | 可用区名称或 ID（如 `us-east-1e` 或 `use1-az6`）。不指定则遍历所有 AZ |
| `--instance-type` | EC2 实例类型（默认 `p5.4xlarge`，如 `p5e.48xlarge`、`p4d.24xlarge`） |
| `--interval N` | 重试间隔秒数（默认 10） |
| `--max-retries N` | 最大重试次数，0 为无限（默认 0） |
| `--dry-run` | 仅搜索/验证，不实际执行 |

## 模式 1：On-Demand（重试抢占）

容量不足时持续重试，直到成功启动实例。

```bash
# 基本用法（默认 p5.4xlarge，指定 AZ）
python grab_instance.py --region us-east-1 --az use1-az6 ondemand

# 指定机型，遍历所有 AZ
python grab_instance.py --region us-east-1 --instance-type p5e.48xlarge ondemand

# 指定 key pair，3 秒间隔快速重试
python grab_instance.py --region us-east-1 --az use1-az6 --interval 3 ondemand --key-name mykey

# dry-run 验证参数
python grab_instance.py --region us-east-1 --instance-type p5.48xlarge --dry-run ondemand
```

子命令参数：

| 参数 | 说明 |
|------|------|
| `--ami` | AMI ID（不指定则自动查找 Amazon Linux 2023） |
| `--subnet` | Subnet ID（不指定则自动查找该 AZ 下的 subnet） |
| `--key-name` | EC2 Key Pair 名称 |

## 模式 2：EC2 Capacity Blocks

预留未来时段的 GPU 容量（1 天 ~ 182 天），需提前购买，到时间后启动实例并指定 reservation ID。

```bash
# 搜索可用 offering（只看不买）
python grab_instance.py --region us-east-1 --az use1-az6 --dry-run capacity-block --duration 24

# 指定机型，遍历所有 AZ
python grab_instance.py --region us-east-1 --instance-type p5e.48xlarge --dry-run capacity-block --duration 48

# 自动购买第一个可用 offering（配合重试循环抢资源）
python grab_instance.py --region us-east-1 --interval 30 capacity-block --duration 24 --auto-purchase

# 后台持续抢，最多重试 500 次
python grab_instance.py --region us-east-1 --instance-type p5.48xlarge --interval 60 --max-retries 500 capacity-block --duration 24 --auto-purchase
```

子命令参数：

| 参数 | 说明 |
|------|------|
| `--instance-count N` | 实例数量（默认 1） |
| `--duration N` | 预留时长，单位小时（默认 24） |
| `--auto-purchase` | 自动购买第一个可用 offering，不交互确认 |

## 模式 3：SageMaker Training Plans

预留 SageMaker 层面的 GPU 容量，用于 Training Job 或 HyperPod 集群。脚本自动为机型添加 `ml.` 前缀（如 `p5.4xlarge` → `ml.p5.4xlarge`）。

```bash
# 搜索可用 Training Plan offering
python grab_instance.py --region us-east-1 --dry-run training-plan --duration 48

# 指定机型
python grab_instance.py --region us-east-1 --instance-type p5.48xlarge --dry-run training-plan --duration 72

# 为 HyperPod 集群购买，指定 plan 名称
python grab_instance.py --region us-east-1 --instance-type p5e.48xlarge training-plan --duration 168 --sm-target hyperpod-cluster --plan-name my-plan

# 持续重试抢 plan
python grab_instance.py --region us-east-1 --interval 30 --max-retries 200 training-plan --duration 24 --auto-purchase
```

子命令参数：

| 参数 | 说明 |
|------|------|
| `--instance-count N` | 实例数量（默认 1） |
| `--duration N` | 预留时长，单位小时（默认 24） |
| `--sm-target` | 目标资源：`training-job`（默认）或 `hyperpod-cluster` |
| `--plan-name` | Training Plan 名称（不指定则自动生成） |
| `--auto-purchase` | 自动购买第一个可用 offering |

## 三种模式对比

| | On-Demand | Capacity Block | Training Plan |
|---|---|---|---|
| 获取方式 | 立即启动，容量不足重试 | 预留未来时段 | 预留 SageMaker 容量 |
| 计费 | 按秒计费 | 预付整段费用 | 预付整段费用 |
| 适用场景 | 临时需求、短期任务 | 确定性短期 GPU 需求 | SageMaker 训练/HyperPod |
| 预留时长 | 无 | 1 天 ~ 182 天 | 1 天 ~ 182 天 |
| 可取消 | 随时终止 | 不可取消 | 不可取消 |

## Tips

- 抢资源建议调小 `--interval`（如 3-5 秒），配合 `--auto-purchase` 全自动
- 先用 `--dry-run` 确认参数和可用 offering 再正式购买
- 不指定 `--az` 时会搜索/尝试所有可用区，增加命中概率
- Capacity Block 和 Training Plan 购买后不可取消，注意确认
- 可用 `nohup` 或 `screen` 后台运行长时间重试