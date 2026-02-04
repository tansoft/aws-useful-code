# DynamoDB 压力测试

## 测试信息

* c7gn.4xlarge 测试机
* DynamoDB 预置 RCU/WCU 40K（Account Quota）

## 测试样本

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

## 测试程序

```bash
go mod tidy
go run bench.go
```

## 单Item读取测试

```bash
go run bench.go --write-threads
```

## 批量Item读取测试

## 单Item写入测试

## 批量Item写入测试
