#https://xilinx.github.io/video-sdk/v2.0/using_ffmpeg.html#video-encoding
#https://xilinx.github.io/video-sdk/v2.0/tuning_encoding_quality.html#dyn-parameters

# 新建 VT1 实例，下载本脚本运行

#区域
region=ap-northeast-1
#转码文件保存bucket
bucket=video-transcode-202208

# 引用相关配置后，可看到转码卡信息
source /opt/xilinx/xcdr/setup.sh

cat>dynparams.txt<<EOF
300:NumB=1
600:BR=6000000
1200:sAQ=1,sAQGain=50
1800:tAQ=1
2400:NumB=0,BR=10000000,sAQ=0,sAQGain=50,tAQ=0
EOF

for num in {1..12}
do
    echo parsing ${num} ...

    # 获取源文件
    aws s3 cp s3://${bucket}/${num}.mp4 . --region $region

    # 静态参数测试
    # 注意如果源视频是h264的，-i前的配置使用mpsoc_vcu_h264，如果是h265的，-i前的配置使用mpsoc_vcu_hevc
    ffmpeg -y -c:v mpsoc_vcu_h264 -i ${num}.mp4 -c:v mpsoc_vcu_h264 -g 150 -profile:v high -b:v 350K -b:a 96K ${num}_264_vt1.mp4
    ffmpeg -y -c:v mpsoc_vcu_h264 -i ${num}.mp4 -c:v mpsoc_vcu_hevc -g 150 -profile:v main -b:v 300K -b:a 96K ${num}_265_vt1.mp4

    # 动态参数测试
    ffmpeg -y -c:v mpsoc_vcu_h264 -i ${num}.mp4 -c:v mpsoc_vcu_h264 -g 150 -profile:v high -b:v 400K -expert-options dynamic-params=dynparams.txt -b:a 96K ${num}_264_vt1d.mp4
    ffmpeg -y -c:v mpsoc_vcu_h264 -i ${num}.mp4 -c:v mpsoc_vcu_hevc -g 150 -profile:v main -b:v 400K -expert-options dynamic-params=dynparams.txt -b:a 96K ${num}_265_vt1d.mp4

    # 保存结果到bucket中
    aws s3 cp ${num}_264_vt1.mp4 s3://${bucket}/ --region $region
    aws s3 cp ${num}_265_vt1.mp4 s3://${bucket}/ --region $region
    aws s3 cp ${num}_264_vt1d.mp4 s3://${bucket}/ --region $region
    aws s3 cp ${num}_265_vt1d.mp4 s3://${bucket}/ --region $region
done