#!/bin/bash

wsec=600
rsec=300

ctable=stress-test-multicolumn
rtable=stress-test-multirow

region=us-east-1

go build -o stress-test stress-test.go

# 测试数据量1TB，100K 预置 WCU/RCU 的性能
aws dynamodb create-table \
  --table-name ${ctable} \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --tags Key=Cost-Center,Value=stress-test \
  --billing-mode PROVISIONED \
  --provisioned-throughput ReadCapacityUnits=100000,WriteCapacityUnits=100000 \
  --region ${region}

aws dynamodb wait table-exists --table-name ${ctable} --region ${region}

# 确保表预热完成
sleep 600

# 插入1TB数据
# times = 1000000000 KB / 5KB item-size / 25 batch / 20 threads / 1 ec2
./start-stress.sh 1 -table ${ctable} -t 86400 -batchWriteItem 20 -region ${region} -config package-size.yaml -times 400000
