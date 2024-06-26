#!/bin/bash

# 创建按需模式的表 test-table-1
#create_table test-table-1 od
# 创建 RCU 200, WCU 300 的表 test-table-2
#create_table test-table-2 200,300
#echo 执行成功返回 table arn: ${RESULT_STRING}
create_table() {
    table=$1
    if [ "$2" == 'od' ]; then
        mode=' --billing-mode PAY_PER_REQUEST'
    else
        array=(${2//,/ })
        mode=" --provisioned-throughput ReadCapacityUnits=${array[0]},WriteCapacityUnits=${array[1]}"
    fi
    RESULT_STRING=
    tablearn=`aws dynamodb create-table --table-name ${table} \
                --attribute-definitions AttributeName=id,AttributeType=S AttributeName=name,AttributeType=S \
                --key-schema AttributeName=id,KeyType=HASH AttributeName=name,KeyType=RANGE \
                ${mode} \
                --output json --query 'TableDescription.TableArn'`

    echo table arn is ${tablearn}

    echo -n waiting for table ready ...
    while :
    do
        status=`aws dynamodb describe-table --table-name ${table} --output json --query 'Table.TableStatus'`
        if [ "$status" == '"ACTIVE"' ]; then
            echo ok
            RESULT_STRING=${tablearn}
            return 0
        fi
        sleep 1
        echo -n .
    done
    return 1
}

# 产生大概 1GB 数据，value 1k大小，9w个key
#generate_data test-table-2 1G
generate_data() {
    table=$1
    if [ "$2" == '1G' ]; then
        st=100000
        et=999999
    elif [ "$2" == '10G' ]; then
        st=1000000
        et=9999999
    elif [ "$2" == '100G' ]; then
        st=10000000
        et=99999999
    else # default 100M
        st=10000
        et=99999
    fi

    TMPFILE=$(mktemp)
    trap 'rm -f "${TMPFILE}"' EXIT

    PART_START='{"PutRequest":{"Item":{"id":{"S":"'
    # name with 1k length
    PART_END='"},"name":{"S":"abcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghijabcdefghij"}}}}'

    echo ${st} ${et}
    while [ ${st} -le ${et} ];
    do
        if [ $((${st} % 25)) -eq 0 ]; then
            if [ -s "${TMPFILE}" ]; then
                echo "]}" >> ${TMPFILE}
                aws dynamodb batch-write-item --request-items file://${TMPFILE}
            fi
            echo Generating data ${st} ...
            echo "{\"${table}\": [${PART_START}${st}${PART_END}" > ${TMPFILE}
            st=$(($st+1))
        fi
        echo ",${PART_START}${st}${PART_END}" >> ${TMPFILE}
        st=$(($st+1))
    done
    return 0
}

# 创建表的备份
#create_backup test-table-2 test-backup-22
#echo 执行成功返回备份的 backup arn：${RESULT_STRING}
create_backup() {
    table=$1
    backup=$2
    backuparn=`aws dynamodb create-backup --table-name ${table} \
        --backup-name ${backup} --output text --query 'BackupDetails.BackupArn'`
    RESULT_STRING=
    echo backup arn for table ${table} is ${backuparn}

    echo -n waiting for backup ready ...
    while :
    do
        status=`aws dynamodb describe-backup --backup-arn ${backuparn} --output json --query 'BackupDescription.BackupDetails.BackupStatus'`
        if [ "$status" == '"AVAILABLE"' ]; then
            echo ok
            RESULT_STRING=${backuparn}
            return 0
        fi
        sleep 1
        echo -n .
    done
    return 1
}

# 删除表
#delete_table test-table-2
delete_table() {
    table=$1
    RESULT_STRING=`aws dynamodb delete-table --table-name ${table} --output text --query 'TableDescription.TableArn'`

    echo -n waiting for table deleted ...
    while :
    do
        command_output=$(aws dynamodb describe-table --table-name ${table} 2>&1)
        if [[ "${command_output}" =~ "An error occurred (ResourceNotFoundException)" ]]; then
            echo ok
            return 0
        fi
        sleep 1
        echo -n .
    done
    return 1
}

# 还原备份
#restore_table_from_backup "arn:aws:dynamodb:ap-northeast-1:xxxxx:table/table-val1k/backup/01719378462010-72e45d58" test-table-2od
# 注意设置修改按需和预置模式，还需要一并修改全局索引的设置
# 还原备份，设置按需
#restore_table_from_backup "arn:aws:dynamodb:ap-northeast-1:xxxxx:table/table-val1k/backup/01719378462010-72e45d58" test-table-2od od
# 还原备份，设置rcu 200，wcu 300
#restore_table_from_backup "arn:aws:dynamodb:ap-northeast-1:xxxxx:table/table-val1k/backup/01719378462010-72e45d58" test-table-2 200,300
restore_table_from_backup() {
    backuparn=$1
    table=$2
    if [ "$3" == 'od' ]; then
        mode=' --billing-mode-override PAY_PER_REQUEST'
    elif [ "$3" == '' ]; then
        mode=''
    else
        array=(${3//,/ })
        mode=" --provisioned-throughput-override ReadCapacityUnits=${array[0]},WriteCapacityUnits=${array[1]} --billing-mode-override PROVISIONED"
    fi
    RESULT_STRING=

    tablearn=`aws dynamodb restore-table-from-backup --target-table-name ${table} \
        --backup-arn ${backuparn}${mode} --output text --query 'TableDescription.TableArn'`

    echo restore table ${table} with ${backuparn}

    echo -n waiting for restore ready ...
    while :
    do
        status=`aws dynamodb describe-table --table-name ${table} --output json --query 'Table.TableStatus'`
        if [ "$status" == '"ACTIVE"' ]; then
            echo ok
            RESULT_STRING=${tablearn}
            return 0
        fi
        sleep 1
        echo -n .
    done
    return 1
}

# 删除备份
#delete_backup "arn:aws:dynamodb:ap-northeast-1:xxxxx:table/test-table-2/backup/01719382255514-7e791e85"
delete_backup() {
    backuparn=$1
    RESULT_STRING=`aws dynamodb delete-backup --backup-arn ${backuparn} --output text --query 'BackupDescription.BackupDetails.BackupStatus'`

    echo -n waiting for backup deleted ...
    while :
    do
        command_output=$(aws dynamodb describe-backup --backup-arn ${backuparn} 2>&1)
        if [[ "${command_output}" =~ "An error occurred (BackupNotFoundException)" ]]; then
            echo ok
            return 0
        fi
        sleep 1
        echo -n .
    done
    return 1
}

# 进行性能测试，通过指定的备份恢复Table
#performance_test "100M-OD" "arn:aws:dynamodb:ap-northeast-1:xxxxx:table/table-val1k-1w/backup/01719386594009-1af2e264"
performance_test() {
    table=$1
    backuparn=$2
    # 建立用于测试的表
    restore_table_from_backup ${backuparn} ${table}
    st=`date +%s`
    # 建立初始备份
    create_backup ${table} ${table}-backup
    bakarn=${RESULT_STRING}
    st1=`date +%s`
    # 开始回滚
    delete_table ${table}
    st2=`date +%s`
    restore_table_from_backup ${bakarn} ${table}
    st3=`date +%s`
    # 这里可以保留最后恢复的table，如果只是测试性能，也可以直接删除
    #delete_table ${table}
    delete_backup ${bakarn}
    baktime=`expr ${st1} - ${st}`
    rollbak=`expr ${st3} - ${st1}`
    rollbakdel=`expr ${st2} - ${st1}`
    rollbakreal=`expr ${st3} - ${st2}`
    echo "任务：${table}"
    echo " 创建备份使用时间：${baktime} 秒"
    echo " 回滚总用时：${rollbak} 秒"
    echo "  其中删除表：${rollbakdel} 秒"
    echo "  其中还原表：${rollbakreal} 秒"
}

# add your test code here
