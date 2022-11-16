# easyVMAF for lambda

VMAF https://github.com/gdavila/easyVMAF 是在libvmaf基础上，进行视频帧对齐等修复设置，以使得vmaf计算更准确。

本项目通过在lambda中调用该项目进行计算，实现通过事件触发，自动生成vmaf对比测试的功能。

由于lambda目录的只读特性，因此对文件生成位置进行替换，详见Dockerfile

## 部署步骤

### 构建并推送docker

```bash
cd ..
./makeimg.sh easyvmaf
```

### 使用镜像创建 lambda 函数

* 创建Lambda函数，选择 Container Image，输入函数名称
* 选择镜像，ECR 里的 easyvmaf，latest 版本
* 展开 修改默认执行角色(Change default execution role)，选择 从 AWS 策略模板创建新角色(Create a new role from AWS policy templates)
* 选择 S3 只读权限（Amazon S3 object read-only permissions）（可选：建议选择部署在可访问外网的私有子网中）。
* 创建Lambda后，在IAM控制台中找到刚才新建的权限，修改Action为s3:*，这样lambda可以把新文件上传到s3中。

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:*"
            ],
            "Resource": "arn:aws:s3:::*"
        }
    ]
}
```

* 修改Lambda执行超时15分钟，内存1024M。(根据实际视频大小选择合适参数)

### 处理视频的s3桶设置事件响应

* s3桶的属性里，创建事件通知，选择 所有对象创建事件（All object create events）
* 选择上面创建的Lambda函数

### 进行测试

* 上传原始视频文件，如 org.mp4 文件
* 上传各种参数生成的文件，如：org_264_qvbr7test.mp4 文件
* 程序会通过第一个“_”查找源文件是否存在（org.mp4），如果存在，就开始对比，生成对比报告
* 报告1：org_264_qvbr7test.txt，文件格式如下：

```txt
... 此处省略详细内容
=======================================
Computing VMAF...
=======================================
Distorted: /tmp/vmaf_wc8x52x.mp4 @ 30.0 fps | 720 960
Reference: /tmp/vmafl7uq2mph.mp4 @ 30.0 fps | 720 960
Offset: 0.0
Model: HD
Phone: False
loglevel: info
subsample: 1
output_fmt: json
=======================================
... 此处省略详细内容
=======================================
VMAF computed
=======================================
offset:  0.0  | psnr:  43.394366
VMAF score (arithmetic mean):  82.820526359375
VMAF score (harmonic mean):  82.52820738222769
VMAF output File Path:  /tmp/vmaf.json
```

* 报告2: org_264_qvbr7test.json，文件格式如下：

```json
{
  "version": "2.3.1",
  "fps": 8.04,
  "frames": [
    {
      "frameNum": 0,
      "metrics": {
        "integer_motion2": 0.000000,
        "integer_motion": 0.000000,
        "integer_vif_scale0": 0.846442,
        "integer_vif_scale1": 0.967883,
        "integer_vif_scale2": 0.984473,
        "integer_vif_scale3": 0.991336,
        "integer_adm2": 0.994498,
        "integer_adm_scale0": 0.997513,
        "integer_adm_scale1": 0.988829,
        "integer_adm_scale2": 0.994176,
        "integer_adm_scale3": 0.995735,
        "vmaf": 94.667208
      }
    },
    ... 此处省略其他帧
    ],
  "pooled_metrics": {
    ... 此处省略其他键值 integer_motion2，integer_adm2，integer_vif_scale0 ～ integer_vif_scale3，integer_adm_scale0 ～ integer_adm_scale3
    "integer_motion": {
      "min": 0.000000,
      "max": 13.401610,
      "mean": 0.733629,
      "harmonic_mean": 0.399399
    },
    "vmaf": {
      "min": 68.987699,
      "max": 100.000000,
      "mean": 82.820526,
      "harmonic_mean": 82.531661
    }
  },
  "aggregate_metrics": {
  }
}
```

* 报告1的汇总值，可以通过报告2原始json文件计算所得：

```python
import json
from statistics import mean, harmonic_mean

vmafScore = []
with open("vmaf.json") as jsonFile:
    jsonData = json.load(jsonFile)
    for frame in jsonData['frames']:
    vmafScore.append(frame["metrics"]["vmaf"])

print("VMAF score (arithmetic mean): ", mean(vmafScore))
print("VMAF score (harmonic mean): ", harmonic_mean(vmafScore))
```

### 查看测试报告

### 本地调试

#### 本地运行实例

```bash
docker rm -f -v test-easyvmaf
docker run -d -p 9000:8080 -e AWS_LAMBDA_FUNCTION_TIMEOUT=900 -e AWS_LAMBDA_FUNCTION_MEMORY_SIZE=1024  -e AWS_ACCESS_KEY_ID=xxx -e AWS_SECRET_ACCESS_KEY=xxx --name test-easyvmaf easyvmaf:latest
```

#### 本地提交测试

```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"Records":[{"awsRegion":"ap-northeast-1","s3":{"bucket":{"name":"video-xxx"},"object":{"key":"aaa.mp4"}}}]}'
```

#### 登录环境进行查看

```bash
docker exec -it -t test-easyvmaf /bin/bash
apt install inotify-tools vim procps
```
