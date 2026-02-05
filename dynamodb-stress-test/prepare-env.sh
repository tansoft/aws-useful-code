#!/bin/bash

while true; do
    timeout 300 bash -c 'while sudo fuser /var/lib/dnf/lock.pid 2>/dev/null; do echo \"Waiting for dnf lock...\"; sleep 5; done'
    if dnf install -y git golang; then
        if dnf list installed git golang; then
            break
        fi
    fi
done

# 新建环境，确保git变量正确
/bin/bash << 'EOF'

cd /usr/local/src/ && git clone https://github.com/tansoft/aws-useful-code
cd aws-useful-code/dynamodb-stress-test/
go mod tidy
go build -o stress-test stress-test.go
./stress-test $*

EOF