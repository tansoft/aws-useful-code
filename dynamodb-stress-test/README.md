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
go run stress-test.go

Usage of stress-test:
  -r int
        Number of read threads (default 10)
  -w int
        Number of write threads (default 10)
  -br int
        Number of batch read threads (default 10)
  -bw int
        Number of batch write threads (default 10)
  -region string
        AWS region (default "ap-northeast-1")
  -t int
        Test duration in seconds (default 3600)
  -table string
        DynamoDB table name (default "xuf")
```

## 单Item读取测试

```bash
go run stress-test.go -r 100 -w 0 -br 0 -bw 0 -t 3600
```

## 批量Item读取测试

## 单Item写入测试

## 批量Item写入测试
