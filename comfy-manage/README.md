# ComfyUI 简单管理

这是一个简单的 ComfyUI 任务管理和弹性的Demo

* 启动ec2实例，并制作comfy环境，这里使用Ubuntu 24.04，EC2 的安全组需要开放 22 以及 8848 端口，EBS 选择 gp3, 200G。

``` bash
# 如果是 ssm 登录，先切换到 ubuntu 账号
sudo -i -u ubuntu

sudo apt-get update -y

# 安装 aws cli
sudo apt install unzip
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# 安装 nvdia driver
sudo apt-get install -y gcc make build-essential
sudo apt-get upgrade -y linux-aws
sudo reboot

# 如果是 ssm 登录，先切换到 ubuntu 账号
sudo -i -u ubuntu

# 继续安装 nvdia driver
cat << EOF | sudo tee --append /etc/modprobe.d/blacklist.conf
blacklist vga16fb
blacklist nouveau
blacklist rivafb
blacklist nvidiafb
blacklist rivatv
EOF
sudo vi /etc/default/grub
# 需要修改这一行：
# GRUB_CMDLINE_LINUX="rdblacklist=nouveau"
sudo update-grub
aws s3 cp --recursive s3://nvidia-gaming/linux/latest/ .
unzip *Gaming-Linux-Guest-Drivers.zip -d nvidia-drivers
chmod +x nvidia-drivers/NVIDIA-Linux-x86_64*-grid.run
sudo nvidia-drivers/NVIDIA-Linux-x86_64*.run
# 接受默认选项
cat << EOF | sudo tee -a /etc/nvidia/gridd.conf
vGamingMarketplace=2
EOF
sudo curl -o /etc/nvidia/GridSwCert.txt "https://nvidia-gaming.s3.amazonaws.com/GridSwCert-Archive/GridSwCertLinux_2024_02_22.cert"
sudo touch /etc/modprobe.d/nvidia.conf
echo "options nvidia NVreg_EnableGpuFirmware=0" | sudo tee --append /etc/modprobe.d/nvidia.conf
sudo reboot

# 如果是 ssm 登录，先切换到 ubuntu 账号
sudo -i -u ubuntu

sudo apt-get install -y nvidia-cuda-toolkit
sudo apt-get install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall
sudo reboot

# 如果是 ssm 登录，先切换到 ubuntu 账号
sudo -i -u ubuntu

# 安装 cloudwatch agent，用于弹性指标判断
wget https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E amazon-cloudwatch-agent.deb
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
mkdir /home/ubuntu/cloudwatch-agent
cat > /home/ubuntu/cloudwatch-agent/agent.json <<EOF
{
  "metrics": {
    "append_dimensions": {
      "InstanceId": "${INSTANCE_ID}"
    },
    "metrics_collected": {
      "nvidia_gpu": {
        "measurement": [
          "utilization_gpu",
          "utilization_memory",
          "memory_total",
          "memory_used",
          "memory_free"
        ],
        "metrics_collection_interval": 30
      }
    }
  }
}
EOF
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/home/ubuntu/cloudwatch-agent/agent.json -s

# 指定python环境
sudo apt install -y python3.12-venv
python3 -m venv venv
. venv/bin/activate
pip install comfy-cli
# 一路y即可
comfy install

# 安装 S3 驱动
wget https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.deb
sudo apt-get install ./mount-s3.deb -y

# 下载相关程序文件，注意env里的变量有多个地方使用了，如果修改需要全部替换一下
wget https://github.com/tansoft/aws-useful-code/raw/refs/heads/main/comfy-manage/env -O /home/ubuntu/comfy/env
wget https://github.com/tansoft/aws-useful-code/raw/refs/heads/main/comfy-manage/start_service.sh -O /home/ubuntu/comfy/start_service.sh
wget https://github.com/tansoft/aws-useful-code/raw/refs/heads/main/comfy-manage/create_env.sh -O /home/ubuntu/comfy/create_env.sh
wget https://github.com/tansoft/aws-useful-code/raw/refs/heads/main/comfy-manage/delete_env.sh -O /home/ubuntu/comfy/delete_env.sh
wget https://github.com/tansoft/aws-useful-code/raw/refs/heads/main/comfy-manage/comfy_utils.py -O /home/ubuntu/comfy/comfy_utils.py
wget https://github.com/tansoft/aws-useful-code/raw/refs/heads/main/comfy-manage/parse_job.py -O /home/ubuntu/comfy/parse_job.py
chmod +x /home/ubuntu/comfy/start_service.sh
chmod +x /home/ubuntu/comfy/create_env.sh
chmod +x /home/ubuntu/comfy/delete_env.sh
cd /home/ubuntu/comfy/
# 注意应该在上面的venv环境中执行
pip install boto3

# 使用默认的model数据创建 s3 基础环境 base
source /home/ubuntu/env
aws s3api create-bucket --bucket ${S3_BUCKET}
mkdir /home/ubuntu/comfy/s3
mount-s3 ${S3_BUCKET} /home/ubuntu/comfy/s3
# 注意这里会高度同步，如果s3本身有数据，会被删除
aws s3 sync /home/ubuntu/comfy/ComfyUI/models s3://${S3_BUCKET}/models --delete
aws s3 sync /home/ubuntu/comfy/ComfyUI/input s3://${S3_BUCKET}/input --delete
aws s3 sync /home/ubuntu/comfy/ComfyUI/output s3://${S3_BUCKET}/output --delete
# 这里可以把本地目录清空以节省磁盘空间，加快实例启动速度
rm -rf /home/ubuntu/comfy/ComfyUI/models /home/ubuntu/comfy/ComfyUI/input /home/ubuntu/comfy/ComfyUI/output
ln -s /home/ubuntu/comfy/s3/input /home/ubuntu/comfy/ComfyUI/
ln -s /home/ubuntu/comfy/s3/output /home/ubuntu/comfy/ComfyUI/
ln -s /home/ubuntu/comfy/s3/models /home/ubuntu/comfy/ComfyUI/

# 启动服务
 cat << EOF | sudo tee /etc/systemd/system/comfyui.service
[Unit]
Description=ComfyUI Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/comfy/ComfyUI
ExecStart=bash /home/ubuntu/comfy/start_service.sh
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable comfyui.service
sudo systemctl start comfyui.service

# 查看服务状态和日志
systemctl status comfyui
journalctl -f -u comfyui

```

## 测试Comfy工作流

下载模型可以看到直接保存models目录后，文件就保存在s3上了

``` bash
wget "https://huggingface.co/linsg/AWPainting_v1.5.safetensors/resolve/main/AWPainting_v1.5.safetensors?download=true" -O /home/ubuntu/comfy/ComfyUI/models/checkpoints/AWPainting_v1.5.safetensors
wget "https://huggingface.co/hakurei/waifu-diffusion-v1-4/resolve/main/vae/kl-f8-anime2.ckpt?download=true" -O /home/ubuntu/comfy/ComfyUI/models/vae/kl-f8-anime2.ckpt
wget "https://huggingface.co/ac-pill/upscale_models/resolve/main/RealESRGAN_x4plus_anime_6B.pth?download=true" -O /home/ubuntu/comfy/ComfyUI/models/upscale_models/RealESRGAN_x4plus_anime_6B.pth
wget "https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11f1e_sd15_tile.pth?download=true" -O /home/ubuntu/comfy/ComfyUI/models/controlnet/control_v11f1e_sd15_tile.pth
wget "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly-fp16.safetensors?download=true" -O /home/ubuntu/comfy/ComfyUI/models/checkpoints/v1-5-pruned-emaonly-fp16.safetensors
```

* 测试工作流通过后，可以下载工作流API json，后面测试使用。
* （可选）可以通过配置 input 和 output 目录的事件触发，来定制自己的工作流。

## 上线部署

从现在的ec2，创建对应线上环境，注意环境名只能使用小写：

```bash
# 如果脚本在 ec2 上运行，注意需要给ec2机器创建ami，autoscaling，s3，sqs等权限
# 包括：AmazonEC2FullAccess AmazonS3FullAccess AmazonSQSFullAccess AutoScalingFullAccess CloudWatchFullAccessV2
./create_env.sh pro
# 如果是在本地运行，增加机器的instance_id，注意profile指定的region
./create_env.sh pro i-06fxxxxx
```

注意，由于创建镜像时，没有强制重启机器，建议检查文件是否都已经生效。
创建环境后，镜像制作需要一段时间，虽然这个时候已经可以测试，但是弹性伸缩组还是会等到镜像制作完成才开始启动机器。

## 测试提交任务

* 发送任务环境依赖 comfy_utils.py 和 send_job.py，修改 send_job.py 中的变量，进行测试。

```bash
python send_job.py

Message sent successfully: c29f8168-8e7e-428a-a936-f76a6d287567
Job submitted successfully
Current queue size: 1
Current instance count: 0
Starting first instance...
Adjusted ASG capacity to 1

# 可以看到机器已经启动
```

* 观察机器启动后的处理日志：

```bash
```

*（可选）可以在parse_job中增加处理完成的通知代码

* 可以直接调整弹性伸缩组的设置：

```bash
aws autoscaling update-auto-scaling-group --auto-scaling-group-name simple-comfy-<ENV> --min-size 0 --max-size 5 --desired-capacity 1
```

## 删除环境

```bash
# 需要注意弹性伸缩组是异步删除的，如果刚删除完，又马上创建相同的名字的环境，会冲突，需要先等待原来的环境删除完成。
./delete_env.sh pro
```

## 参考链接：

* https://aws.amazon.com/cn/blogs/china/using-ec2-to-build-comfyui-and-combine-it-with-krita-practice/
* https://docs.aws.amazon.com/zh_cn/AmazonCloudWatch/latest/monitoring/download-cloudwatch-agent-commandline.html
* https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/install-nvidia-driver.html#nvidia-gaming-driver
* https://docs.aws.amazon.com/zh_cn/AmazonS3/latest/userguide/mountpoint-installation.html#mountpoint.install.deb

实现create_env.sh，功能是通过env文件获取参数，指定镜像AMI创建弹性伸缩组、S3、sqs队列
实现parse_job.py，功能是从sqs中获取任务，并进行http post提交，成功后删除sqs队列。
实现send_job.py，功能是把json任务往sqs进行提交，并判断sqs中队列数，和ec2的弹性伸缩组当前实例数，如果sqs有队列，实例为0，需要修改实例数为1，另外判断队列中个数/实例数如果大于3，则扩容，小于3则缩容，扩展冷却时间60秒，缩容冷却时间120秒
