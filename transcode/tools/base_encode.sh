
#local ffmpeg
#ffmpeg -i 1.mp4 -c:v libx264 -crf 26 -profile:v high -b:a 96K 1_264_base.mp4
#ffmpeg -i 1.mp4 -c:v hevc -crf 26 -profile:v main -b:a 96K 1_265_base.mp4

region=ap-northeast-1
bucket=video-transcode-202208

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
    # --cli-binary-format raw-in-base64-out
    aws lambda invoke --function ffmpegrun --region ${region} --payload "{\"encoding\":\"base64\", \"cmd\":\"$3\", \"bucket\":\"${bucket}\", \"infile\":\"$1\", \"outfile\":\"$2\"}" $tmpfile
    cat $tmpfile
    ret=`cat $tmpfile | jq -r '.status'`
    echo "ret:$ret"
    if [ "$ret" == "0" ];then
        cat $tmpfile | jq -r '.body'
        cat $tmpfile
    else
        cat $tmpfile
    fi
}

function ffmpegasync() {
    tmpfile=`mktemp`
    echo "{\"encoding\":\"base64\", \"cmd\":\"$3\", \"bucket\":\"${bucket}\", \"infile\":\"$1\", \"outfile\":\"$2\"}" > $tmpfile
    aws lambda invoke-async --function ffmpegrun --region ${region} --invoke-args $tmpfile
}

function encodetestlocal() {
    num=$1
    echo parsing ${num} ...
    aws s3 cp s3://${bucket}/${num}.mp4 .
    ffmpeg -i ${num}.mp4 -c:v libx264 -crf 26 -profile:v high -b:a 96K ${num}_264_base.mp4
    ffmpeg -i ${num}.mp4 -c:v hevc -crf 26 -profile:v main -b:a 96K ${num}_265_base.mp4
    aws s3 cp ${num}_264_base.mp4 s3://${bucket}/
    aws s3 cp ${num}_265_base.mp4 s3://${bucket}/
    rm -f ${num}.mp4
}

function encodetest() {
    num=$1
    echo parsing ${num} ...

    cmd=`echo "ffmpeg -i ${num}.mp4 -c:v libx264 -crf 26 -profile:v high -b:a 96K ${num}_264_base.mp4" | base64 -w 0`
    ffmpegasync "${num}.mp4" "${num}_264_base.mp4" $cmd

    cmd=`echo "ffmpeg -i ${num}.mp4 -c:v hevc -crf 26 -profile:v main -b:a 96K ${num}_265_base.mp4" | base64 -w 0`
    ffmpegasync "${num}.mp4" "${num}_265_base.mp4" $cmd
}

#指定文件转码
arr=("2" "10" "11" "12")
for num in ${arr[@]}
#循环所有文件转码
#for num in {1..12}
do
    #本地ffmpeg调用
    encodetestlocal $num
    #在线lambda调用
    #encodetest $num
done
