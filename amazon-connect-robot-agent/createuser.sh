#!/bin/bash

region=`curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone | sed -e 's/.$//'`
curpath=$(cd "$(dirname "$0")";pwd)

#alias2arn
alias=$1
instanceid=`aws connect list-instances --region ${region} | jq -r '.InstanceSummaryList[]|select(.InstanceAlias=="${alias}").Arn'`

#arn2alias
#instanceid=arn:aws:connect:us-east-1:xxx:instance/xxx
#region=`echo ${instanceid} | awk -F: '{print $4}'`
#alias=`aws connect describe-instance --instance-id ${instanceid} --region ${region} | jq -r '.Instance.InstanceAlias'`

#username is ec2 instance id
user=`curl http://169.254.169.254/latest/meta-data/instance-id`
#ensure password meets complexity policy
pass=`echo $user | md5`
pass=`echo "${pass:0:6}Ab1"`

alias=`aws connect describe-instance --instance-id ${instanceid} --region ${region} | jq -r '.Instance.InstanceAlias'`
securityId=`aws connect list-security-profiles --instance-id ${instanceid} --region ${region} | jq -r '.SecurityProfileSummaryList[]|select(.Name=="Agent").Id'`
routingId=`aws connect list-routing-profiles --instance-id ${instanceid} --region ${region} | jq -r '.RoutingProfileSummaryList[]|select(.Name=="Basic Routing Profile").Id'`

echo "create User ${user} in ${alias} with Pass: ${pass} SecurityId: ${securityId} RoutingId: ${routingId} ..."

aws connect create-user --username ${user} --password Pass@Word1 \
  --identity-info FirstName=${user},LastName=robot \
  --phone-config PhoneType=SOFT_PHONE,AutoAccept=true,AfterContactWorkTimeLimit=1 \
  --security-profile-id ${securityId} --routing-profile-id ${routingId} \
  --instance-id ${instanceid} --region ${region}

screen

python3 ${curpath}/robotagent.py -a ${alias} -u ${user} -p ${pass}
