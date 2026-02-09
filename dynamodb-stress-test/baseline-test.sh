#!/bin/bash

wsec=600
rsec=300

ctable=baseline-test-multicolumn
rtable=baseline-test-multirow

region=us-east-1

function test_function() {
    echo "test table $1 ..."
    table=$1
    shift
    ./stress-test -table ${table} -t ${wsec} -batchWriteItem 1 -region ${region} "$@"
    ./stress-test -table ${table} -t ${rsec} -batchGetItem 1 -region ${region} "$@"
    # full get
    ./stress-test -table ${table} -t ${rsec} -getItem 1 -region ${region} "$@"
    ./stress-test -table ${table} -t ${rsec} -query 1 -region ${region} "$@"
    ./stress-test -table ${table} -t ${wsec} -updateItem 1 -region ${region} "$@"
    ./stress-test -table ${table} -t ${wsec} -batchDeleteItem 1 -region ${region} "$@"
    ./stress-test -table ${table} -t ${wsec} -putItem 1 -region ${region} "$@"
    # hit part get
    ./stress-test -table ${table} -t ${rsec} -getItem 1 -region ${region} "$@"
    ./stress-test -table ${table} -t ${rsec} -query 1 -region ${region} "$@"
    ./stress-test -table ${table} -t ${rsec} -scan 1 -region ${region} "$@"
    ./stress-test -table ${table} -t ${wsec} -deleteItem 1 -region ${region} "$@"
    # miss get
    ./stress-test -table ${table} -t ${rsec} -getItem 1 -region ${region} "$@"
    ./stress-test -table ${table} -t ${rsec} -query 1 -region ${region} "$@"
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

test_function ${ctable}

test_function ${rtable} -sortkey

aws dynamodb delete-table --table-name ${ctable} --region ${region}

aws dynamodb delete-table --table-name ${rtable} --region ${region}
