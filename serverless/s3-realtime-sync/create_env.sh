#!/bin/bash

# 以下参数根据实际情况修改
src_profile=zhy
dist_profile=sin
src_bucket="dth-zhy-test"
dist_bucket="dth-sin-test"
storage_class="STANDARD"

# 以下参数在冲突时才需要修改
prefix="s3_migration_"
ddb_name="${prefix}table"
ssm_credentials="${prefix}credentials"
lambda_name="${prefix}worker"
sqs_name="${prefix}s3event"

# 文件 s3_migration_worker.zip 由以下代码生成
# wget https://github.com/aws-samples/amazon-s3-resumable-upload/raw/refs/heads/v1/serverless/cdk-serverless/lambda/lambda_function_worker.py
# wget https://github.com/aws-samples/amazon-s3-resumable-upload/raw/refs/heads/v1/serverless/cdk-serverless/lambda/s3_migration_lib.py
# zip s3_migration_worker_code.zip lambda_function_worker.py s3_migration_lib.py

src_aws_access_key_id=$(sed -n "/\\[${src_profile}\\]/,/aws_access_key_id/p" ~/.aws/credentials | grep aws_access_key_id | cut -d'=' -f2 | sed 's/^[[:space:]]*//')
src_aws_secret_access_key=$(sed -n "/\\[${src_profile}\\]/,/aws_secret_access_key/p" ~/.aws/credentials | grep aws_secret_access_key | cut -d'=' -f2 | sed 's/^[[:space:]]*//')
src_aws_region=$(sed -n "/\\[profile ${src_profile}\\]/,/region/p" ~/.aws/config | grep region | cut -d'=' -f2 | sed 's/^[[:space:]]*//')

src_account_id=$(aws sts get-caller-identity --query Account --output text --profile ${src_profile})

if [ -z "${src_aws_access_key_id}" ] || [ -z "${src_aws_secret_access_key}" ] || [ -z "${src_aws_region}" ] || [ -z "${src_account_id}"] ]; then
    echo src profile not found!
    exit 1
fi

if [[ "${src_aws_region:0:3}" == "cn-" ]]; then
    aws_prefix="aws-cn"
else
    aws_prefix="aws"
fi

dist_aws_access_key_id=$(sed -n "/\\[${dist_profile}\\]/,/aws_access_key_id/p" ~/.aws/credentials | grep aws_access_key_id | cut -d'=' -f2 | sed 's/^[[:space:]]*//')
dist_aws_secret_access_key=$(sed -n "/\\[${dist_profile}\\]/,/aws_secret_access_key/p" ~/.aws/credentials | grep aws_secret_access_key | cut -d'=' -f2 | sed 's/^[[:space:]]*//')
dist_aws_region=$(sed -n "/\\[profile ${dist_profile}\\]/,/region/p" ~/.aws/config | grep region | cut -d'=' -f2 | sed 's/^[[:space:]]*//')

if [ -z "${dist_aws_access_key_id}" ] || [ -z "${dist_aws_secret_access_key}" ] || [ -z "${dist_aws_region}" ]; then
    echo dist profile not found!
    exit 1
fi

if [ "$1" == "--delete" ]; then
    # 执行删除操作
    echo "Performing delete action..."

    aws s3api put-bucket-notification-configuration --bucket "${src_bucket}" --notification-configuration "{}" --profile ${src_profile}

    UUID=$(aws lambda list-event-source-mappings --function-name "${lambda_name}" --event-source-arn arn:${aws_prefix}:sqs:${src_aws_region}:${src_account_id}:${sqs_name} --query EventSourceMappings[0].UUID --output text --profile ${src_profile})
    aws lambda delete-event-source-mapping --uuid ${UUID} --profile ${src_profile}
    aws lambda delete-function --function-name "${lambda_name}" --profile ${src_profile}

    aws sqs delete-queue --queue-url https://sqs.${src_aws_region}.amazonaws.com/${src_account_id}/${sqs_name} --profile ${src_profile}
    aws sqs delete-queue --queue-url https://sqs.${src_aws_region}.amazonaws.com/${src_account_id}/${sqs_name}_DLQ --profile ${src_profile}

    aws dynamodb delete-table --table-name ${ddb_name} --profile ${src_profile}

    aws iam detach-role-policy --role-name ${lambda_name}_role --policy-arn arn:${aws_prefix}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --profile ${src_profile}
    aws iam detach-role-policy --role-name ${lambda_name}_role --policy-arn arn:${aws_prefix}:iam::${src_account_id}:policy/${lambda_name}_policy --profile ${src_profile}
    aws iam delete-role --role-name ${lambda_name}_role --profile ${src_profile}
    aws iam delete-policy --policy-arn arn:${aws_prefix}:iam::${src_account_id}:policy/${lambda_name}_policy --profile ${src_profile}

    aws ssm delete-parameter --name "${ssm_credentials}" --profile "${src_profile}"

    exit 0
fi

aws ssm put-parameter --name "${ssm_credentials}" \
    --value "{\"aws_access_key_id\":\"$aws_access_key_id\",\"aws_secret_access_key\":\"$aws_secret_access_key\",\"region\":\"$aws_region\"}" \
    --type "SecureString" --tier "Standard" \
    --key-id "alias/aws/ssm" --profile "${src_profile}"

#envsubst '$aws_prefix,$src_aws_region,$src_account_id,$aws_access_key_id,$src_bucket,$ssm_credentials,$ddb_name' < s3_migration_worker_policy.template > s3_migration_worker_policy.tmp
sed -e "s/\${aws_prefix}/${aws_prefix}/" \
    -e "s/\${src_aws_region}/${src_aws_region}/" \
    -e "s/\${src_account_id}/${src_account_id}/" \
    -e "s/\${aws_access_key_id}/${aws_access_key_id}/" \
    -e "s/\${src_bucket}/${src_bucket}/" \
    -e "s/\${ssm_credentials}/${ssm_credentials}/" \
    -e "s/\${ddb_name}/${ddb_name}/" \
    -e "s/\${sqs_name}/${sqs_name}/" \
    s3_migration_worker_policy.template > s3_migration_worker_policy.tmp
aws iam create-policy --policy-name ${lambda_name}_policy --policy-document file://s3_migration_worker_policy.tmp --profile "${src_profile}"
rm s3_migration_worker_policy.tmp
aws iam create-role --role-name ${lambda_name}_role --assume-role-policy-document file://s3_migration_worker_trust_policy.json --profile "${src_profile}"
aws iam attach-role-policy --role-name ${lambda_name}_role --policy-arn arn:${aws_prefix}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --profile "${src_profile}"
aws iam attach-role-policy --role-name ${lambda_name}_role --policy-arn arn:${aws_prefix}:iam::${src_account_id}:policy/${lambda_name}_policy --profile "${src_profile}"

aws dynamodb create-table --table-name ${ddb_name} --attribute-definitions AttributeName=Key,AttributeType=S --key-schema AttributeName=Key,KeyType=HASH --billing-mode PAY_PER_REQUEST --query TableDescription.TableStatus --profile "${src_profile}"
while :
do
  status=$(aws dynamodb describe-table --table-name ${ddb_name} --query Table.TableStatus --output text --profile "${src_profile}")
  if [ "$status" == 'ACTIVE' ]; then
    break
  fi
  sleep 1
  echo -n .
done
aws dynamodb update-table --table-name ${ddb_name} --attribute-definitions AttributeName=desBucket,AttributeType=S --profile "${src_profile}" --global-secondary-index-updates --query TableDescription.TableStatus \
    '[{"Create":{"IndexName":"desBucket-index","KeySchema":[{"AttributeName": "desBucket","KeyType": "HASH"}],"Projection":{"ProjectionType":"INCLUDE","NonKeyAttributes":["desKey","versionId"]}}}]'

aws sqs create-queue --queue-name ${sqs_name}_DLQ  --profile "${src_profile}" --attributes "{\"VisibilityTimeout\":\"900\",\"MessageRetentionPeriod\":\"1209600\"}"
# https://docs.aws.amazon.com/zh_cn/AmazonS3/latest/userguide/ways-to-add-notification-config-to-bucket.html#step2-enable-notification
aws sqs create-queue --queue-name ${sqs_name}  --profile "${src_profile}" --attributes "{\"VisibilityTimeout\":\"900\",\"MessageRetentionPeriod\":\"1209600\",\"RedrivePolicy\":\"{\\\"maxReceiveCount\\\":\\\"60\\\",\\\"deadLetterTargetArn\\\":\\\"arn:${aws_prefix}:sqs:${src_aws_region}:${src_account_id}:${sqs_name}_DLQ\\\"}\",\"Policy\":\"{\\\"Version\\\":\\\"2012-10-17\\\",\\\"Id\\\":\\\"SQSQueuePermissions\\\",\\\"Statement\\\":[{\\\"Sid\\\":\\\"SQSQueuePermissions\\\",\\\"Effect\\\":\\\"Allow\\\",\\\"Principal\\\":{\\\"Service\\\":\\\"s3.amazonaws.com\\\"},\\\"Action\\\":\\\"sqs:SendMessage\\\",\\\"Resource\\\":\\\"arn:${aws_prefix}:sqs:${src_aws_region}:${src_account_id}:${sqs_name}\\\",\\\"Condition\\\":{\\\"ArnLike\\\":{\\\"aws:SourceArn\\\":\\\"arn:${aws_prefix}:s3:::${src_bucket}\\\"},\\\"StringEquals\\\":{\\\"aws:SourceAccount\\\":\\\"${src_account_id}\\\"}}}]}\"}"

aws lambda create-function --function-name "${lambda_name}" --runtime python3.12 \
    --zip-file fileb://s3_migration_worker_code.zip --handler lambda_function_worker.lambda_handler \
    --memory-size 1024 --timeout 900 --query State --profile "${src_profile}" \
    --role arn:${aws_prefix}:iam::${src_account_id}:role/${lambda_name}_role \
    --environment "{\"Variables\":{\"Des_bucket_default\":\"${dist_bucket}\",\"Des_prefix_default\":\"\",\"StorageClass\":\"${storage_class}\",\"table_queue_name\":\"${ddb_name}\",\"checkip_url\":\"https://checkip.amazonaws.com/\",\"ssm_parameter_credentials\":\"${ssm_credentials}\",\"JobType\":\"PUT\",\"MaxRetry\":\"20\",\"MaxThread\":\"50\",\"MaxParallelFile\":\"1\",\"JobTimeout\":\"870\",\"UpdateVersionId\":\"False\",\"GetObjectWithVersionId\":\"False\"}}"

aws lambda create-event-source-mapping --function-name "${lambda_name}" \
    --batch-size 1 --event-source-arn arn:${aws_prefix}:sqs:${src_aws_region}:${src_account_id}:${sqs_name} --profile "${src_profile}"

aws s3api put-bucket-notification-configuration \
    --bucket "${src_bucket}" --notification-configuration "{\"QueueConfigurations\":[{\"QueueArn\": \"arn:aws:sqs:${src_aws_region}:${src_account_id}:${sqs_name}\",\"Events\": [\"s3:ObjectCreated:*\",\"s3:ObjectRemoved:*\"]}]}" --profile "${src_profile}"
