# AWS 机型选择程序

该程序实现根据需求选择最合适aws服务和机型。

## 实现逻辑

* 程序使用python实现。
* 通过命令行参数指定配置文件yaml，文件中描述cpu，内存，存储大小，存储iops和带宽，网络pps和带宽，公网ip，x86/arm/mac，区域列表等的最小需求，某些属性也可以不指定。
* 默认是当前目录的config.yaml文件，文件中给出各个部分的详细设置和注释。
* 根据提供的配置，从lightsail、EC2、Lambda服务中进行选择，只要符合要求都进行选择。
* 根据需求进行boto3 sdk调用，实时查询对应机型和价格等信息，确保信息可靠性。
* 生成excel报告，报告中详细描述机型和各种参数信息，以及各区域价格信息，包括Saving Plan、Spot、RI对应信息，磁盘，网络等价格信息，关联信息尽量使用excel公式配置，方便修改调整。

## 使用方法

程序会生成带时间戳的Excel报告，包含所有符合条件的实例配置和价格信息。

```bash
# 安装依赖
pip install -r requirements.txt

# 使用默认配置运行
python instance_select.py

# 指定配置文件
python instance_select.py -c my_config.yaml
```
