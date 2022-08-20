
# 用于elemental不同转码参数的测试对比

* qvbr.json是默认的转码参数分别测试qvbr在7-10时的转码效果
* tune.json是根据媒体team的建议，针对通用场景做的编码参数优化
* vmaf.json是针对vmaf分值做的转码优化，仅用于vmaf分值高的场景，实际转码效果并不是主要因素
* test.sh 生成各种文件对比和测试报告
