# 概述

本项目用于视频转码测试，在 AWS 平台上，分别进行MediaConvert，EC2，VT1，AI高清重建方案等测试。

## 配置

* 创建 s3 桶，用于存放源文件和各种方式转码的文件。
* 源文件建议都使用.mp4后缀，以数字命名，如：1.mp4，2.mp4，3.mp4
* 不同方式生成的转码文件，以前面文件名_转码信息组成，如：1_vt1_static.mp4，1_vt1_1080p.mp4 等。
* s3 桶配置自动生成vmaf结果，参见：[https://github.com/tansoft/aws-useful-code/blob/main/serverless/build-lambda-docker/easyvmaf/readme.md](https://github.com/tansoft/aws-useful-code/blob/main/serverless/build-lambda-docker/easyvmaf/readme.md)

## 测试内容

* 通过 mediaconvert/test.sh 测试 AWS MediaConvert 相关参数。
* 通过 tools/base_encode.sh 进行不同转码参数，不同ffmpeg版本，不同编码器等测试，如GPU，脚本放置在EC2机器上运行，也可以部署lambda函数，异步提交批量转码任务测试。
* 通过 ai-super-resolution/test.sh，进行AI超分重建测试。
* 通过 VT1/xlix.sh 进行 VT1 实例测试。

## tools 常用脚本

### base_encode.sh

批量进行转码测试脚本

* 86行，指定要测试转码的文件名，不带后缀名，默认mp4文件，如：arr=("2" "10" "11" "12")，测试2.mp4 10.mp4 11.mp4 12.mp4
* 92行，默认使用本地的ffmpeg命令直接转码，因此可以把脚本放到需要测试的机型进行测试即可
* 批量处理，可以使用lambda函数（详情查看base_encode.sh开头部分代码），部署ffmpeg layer，然后批量进行测试，修改不使用encodetestlocal函数，使用encodetest函数，默认使用ffmpegasync进行异步调用，也可以使用ffmpegrun函数进行同步阻塞调用

```bash
./bash_encode.sh
```

### diff_lr.sh

左右同框同时对比观察质量，支持url和本地文件，依赖ffmpeg和ffplay

```bash
./diff_lr.sh left.mp4 right.mp4
```

### vmaf.sh

通过对比源视频和目标视频，输出vmaf得分，依赖带libvmaf的ffmpeg

```bash
./vmaf.sh 源视频 目标视频 <缩放比例，用于源视频和目标视频高宽不一样的情况，请参见脚本中的注释命令行，如：640x480>
```

### print_result.py

获取所有对比结果汇总，需要依赖boto3，该脚本读取s3上，与视频文件同名的vmaf(.txt)文件进行，文件中包含vmaf跑分信息。
