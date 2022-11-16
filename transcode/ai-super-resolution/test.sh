
# AI 超分辨率重建
# 先进行ai-super-resolution的CloudFormation部署
# https://www.amazonaws.cn/solutions/ai-super-resolution-on-aws/
# https://aws-gcr-solutions.s3.amazonaws.com/Aws-gcr-ai-super-resolution/v2.0.0/docs.pdf

# 修改以下相关的调用配置信息

#AI重建方案部署区域
region=ap-northeast-1
#AI重建方案输出bucket
aibucket=superresolution-storagexxx
#AI重建方案调用API
aiendpoint=https://xxx.execute-api.ap-northeast-1.amazonaws.com/prod/

#拷贝到最终的收集对比bucket
bucket=video-transcode-202208

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
done

sleep 3600

for num in {1..12}
do
    #拷贝生成文件
    aws s3 cp s3://${aibucket}/${num}_BSR_x2.mp4 s3://${bucket}/${num}_264_ai.mp4
done