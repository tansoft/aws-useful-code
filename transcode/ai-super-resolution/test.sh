

region=ap-northeast-1
bucket=video-transcode-202208
aibucket=superresolution-superresolutionstoragexxx
aiendpoint=https://xxx.execute-api.ap-northeast-1.amazonaws.com/prod/

function transcode() {
    aws s3 cp s3://${bucket}/$1 s3://${aibucket}/$1
    curl --location --request POST "$aiendpoint" \
        --header 'Content-Type: application/json' \
        --data-raw "{\"key\": \"$1\",\"scale\":2}"
}

for num in {1..12}
do
    #ai重建
    transcode ${num}.mp4
    #拷贝生成文件
    #aws s3 cp s3://${aibucket}/${num}_BSR_x2.mp4 s3://${bucket}/${num}_264_ai.mp4
done
