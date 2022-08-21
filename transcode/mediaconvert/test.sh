
region=ap-northeast-1
bucket=video-transcode-202208

endpoint=`aws mediaconvert describe-endpoints --region $region | jq -r .Endpoints[0].Url`

accountid=`aws sts get-caller-identity | jq -r '.Account'`

if [[ $region == cn-* ]]; then
    queue=arn:aws-cn:mediaconvert:$region:$accountid:queues/Default
    role=arn:aws-cn:iam::$accountid:role/MediaConvert_Default_Role
else
    queue=arn:aws:mediaconvert:$region:$accountid:queues/Default
    role=arn:aws:iam::$accountid:role/service-role/MediaConvert_Default_Role
fi

echo -e "mediaconvert in $region\n  account: $accountid\n  queue: $queue\n  role: $role\n  endpoint: $endpoint\n"

: << EOF
# 使用ffmpeg layer，可以轻易做出ffmpeg调用的lambda函数，方便本地没有ffmpeg的情况下测试

import boto3
import os
import json
import subprocess
import shlex
import base64

def lambda_handler(event, context):
    cmd = event['cmd']
    try:
        if isinstance(cmd, str):
            if 'encoding' in event and event['encoding'] == 'base64':
                cmd = base64.b64decode(cmd).decode()
            cmd = shlex.split(cmd)
        ret = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        return {
            'status': e.returncode,
            'body': e.output,
            'cmd': cmd
        }
    return {
        'status': 0,
        'body': ret
    }
EOF

function ffmpegrun() {
    tmpfile=`mktemp`
    #支持多种调用方式
    #aws lambda invoke --function ffmpegrun --region $region --payload '{"cmd":"ffmpeg --help"}' --cli-binary-format raw-in-base64-out outfile
    #aws lambda invoke --function ffmpegrun --region $region --payload '{"cmd": ["ffmpeg", "--help"]}' --cli-binary-format raw-in-base64-out outfile
    aws lambda invoke --function ffmpegrun --region $region --payload "{\"encoding\":\"base64\", \"cmd\":\"$1\"}" --cli-binary-format raw-in-base64-out $tmpfile
    ret=`cat $tmpfile | jq -r '.status'`
    echo "ret:$ret"
    if [ "$ret" == "0" ];then
        cat $tmpfile | jq -r '.body'
        cat $tmpfile
    else
        cat $tmpfile
    fi
}

function runjob() {
    srcfile=$1
    output=$2
    mode=$3
    tmpfile=`mktemp`
    sed "s#\[queue\]#$queue#g" $mode.json | sed "s#\[role\]#$role#g" | sed "s#\[bucket\]#$bucket#g" | sed "s#\[srcfile\]#$srcfile#g" | sed "s#\[output\]#$output#g" > $tmpfile
    #cat $tmpfile
    jobinfo=`aws --endpoint-url $endpoint --region $region mediaconvert create-job --cli-input-json file://$tmpfile`
    jobid=`echo $jobinfo | jq -r '.Job.Id'`
    echo "job:$mode,id:$jobid"
    if [ async ]; then
        return 0
    fi
    outprefix=`jq -r '.Settings.OutputGroups[0].OutputGroupSettings.FileGroupSettings.Destination' $tmpfile`
    outfiles=`jq -r '.Settings.OutputGroups[0].Outputs[].NameModifier' $tmpfile`
    while [ true ];
    do
        jobinfo=`aws --endpoint-url $endpoint --region $region mediaconvert get-job --id $jobid`
        jobstatus=`echo $jobinfo | jq -r '.Job.Status'`
        date=`date +%H:%M:%S`
        if [ "$jobstatus" == "PROGRESSING" ]; then
            echo "[$date] $jobstatus"
            sleep 20
        else
            #echo $jobinfo
            #有时这里返回是时间戳，有时返回是UTC时间
            #st=`echo $jobinfo | jq -r '.Job.Timing.StartTime | (split("+")[0] + "Z") | fromdate'`
            #et=`echo $jobinfo | jq -r '.Job.Timing.FinishTime | (split("+")[0] + "Z") | fromdate'`
            st=`echo $jobinfo | jq -r '.Job.Timing.StartTime'`
            et=`echo $jobinfo | jq -r '.Job.Timing.FinishTime'`
            time=`expr $et - $st`
            echo usetime:$time,status:$jobstatus
            if [ "$jobstatus" == "ERROR" ]; then
                echo $jobinfo
            elif [ "$jobstatus" == "COMPLETE" ]; then
                for i in $outfiles;
                do
                    file="$outprefix$output$i.mp4"
                    aws s3 ls $file --region $region
                    #s3自动触发完成vmaf分析，如果没有配置成功，则会一直等待
                    #参见：https://github.com/tansoft/aws-useful-code/tree/main/serverless/build-lambda-docker/easyvmaf
                    while [ true ];
                    do
                        score=`aws s3 cp $outprefix$output$i.txt - --region $region 2>&1 | grep "VMAF score"`
                        if [ $? == 0 ]; then
                            echo $score | grep "VMAF score"
                            break
                        else
                            echo "waiting $outprefix$output$i.txt ..."
                            sleep 20
                        fi
                    done
                    #进行本地vmaf计算
                    if [ 0 ]; then
                        infile=`aws s3 presign s3://$bucket/$srcfile --region $region`
                        outfile=`aws s3 presign $file --region $region`
                        #本地ffmpeg直接调用
                        #ffmpeg -i "$outfile" -i "$infile" -filter_complex "[0:v][1:v]libvmaf" -f null - 2>&1 | grep VMAF
                        #在线lambda调用
                        #cmd=`echo "ffmpeg -i \"$outfile\" -i \"$infile\" -filter_complex \"[0:v][1:v]libvmaf\" -f null - 2>&1 | grep VMAF" | base64`
                        #ffmpegrun $cmd
                    fi
                done
            fi
            echo mediaconvert finish
            break
        fi
    done
}

#async=0
#runjob 1.mp4 1 qvbr
#runjob 1.mp4 1 tune
#runjob 1.mp4 1 vmaf

async=1
for num in {1..12}
do
    echo runjob $num
    runjob $num.mp4 $num qvbr
    runjob $num.mp4 $num tune
    runjob $num.mp4 $num vmaf
done
