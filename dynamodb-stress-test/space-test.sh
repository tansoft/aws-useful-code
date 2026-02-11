#!/bin/bash

ctable=space-usage-multicolumn
rtable=space-usage-multirow

region=us-east-1

function test_function() {
    echo "test table $1 ..."
    table=$1
    shift
    # 使用固定size是因为多列和多行模式生成的id序列不一样，怕造成影响
    ./stress-test -table ${table} -t 86400 -batchWriteItem 1 -config package-size.yaml -region ${region} "$@"
}

go build -o stress-test stress-test.go

aws dynamodb create-table \
  --table-name ${ctable} \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --tags Key=Cost-Center,Value=stress-test \
  --billing-mode PAY_PER_REQUEST \
  --region ${region}

aws dynamodb create-table \
  --table-name ${rtable} \
  --attribute-definitions AttributeName=id,AttributeType=S \
      AttributeName=sk,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
      AttributeName=sk,KeyType=RANGE \
  --tags Key=Cost-Center,Value=stress-test \
  --billing-mode PAY_PER_REQUEST \
  --region ${region}

aws dynamodb wait table-exists --table-name ${ctable} --region ${region}

aws dynamodb wait table-exists --table-name ${rtable} --region ${region}

# 多列模式，写入是一批25，写400次，等于1万条记录
# test_function ${ctable} -times 40000

# 多行模式，写入1次是5份记录，写10000次，等于5万条记录
test_function ${rtable} -sortkey -times 1000000

echo aws dynamodb delete-table --table-name ${ctable} --region ${region}

echo aws dynamodb delete-table --table-name ${rtable} --region ${region}
