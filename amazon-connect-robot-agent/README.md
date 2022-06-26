# 使用 Selenium 制作 Amazon Connect 机器人

制作 Selenium 镜像和启动脚本，可以方便地创建机器人账号，然后登录Amazon Connect。

通过使用 c5.xlarge 机型，标准Amazon Linux2系统，进行镜像制作，安装软件和相关程序后，制作成基础 AMI 镜像。

## 安装相应软件

使用 ec2-user 账号登录机器进行配置。

### 安装 Chrome

```bash
sudo curl https://intoli.com/install-google-chrome.sh | bash
sudo mv /usr/bin/google-chrome-stable /usr/bin/google-chrome
```

### 安装 chromedriver

* 目前使用版本 103.0.5060.53
* 获取最新版本 https://chromedriver.storage.googleapis.com/LATEST_RELEASE
* Drvier 需要和 Chrome 使用一致的版本

```bash
version=`google-chrome --version | awk '{print $3}'`
wget "https://chromedriver.storage.googleapis.com/${version}/chromedriver_linux64.zip"
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/bin/chromedriver
rm -f chromedriver_linux64.zip
chromedriver --version
```

### 安装 selenium

```bash
sudo pip3 install selenium
```

### 安装最新 awscli

```bash
sudo yum -y remove awscli
cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install -b /usr/bin
rm -rf aws awscliv2.zip
aws --version
```

### 安装相关脚本

```bash
sudo yum -y install jq
sudo wget https://github.com/tansoft/aws-useful-code/raw/main/amazon-connect-robot-agent/createuser.sh -O /usr/local/src/createuser.sh
sudo wget https://github.com/tansoft/aws-useful-code/raw/main/amazon-connect-robot-agent/robotagent.py -O /usr/local/src/robotagent.py
sudo wget https://github.com/tansoft/aws-useful-code/raw/main/amazon-connect-robot-agent/runssh.sh -O /usr/local/src/runssh.sh
sudo chmod +x /usr/local/src/createuser.sh /usr/local/src/runssh.sh /etc/rc.d/rc.local
```

### 设置本地ssh登录环境

```bash
sudo sed -i '/PermitRootLogin /c PermitRootLogin yes' /etc/ssh/sshd_config
sudo rm -rf /root/.ssh/{known_hosts,id_rsa*}
sudo service sshd restart
```

## 制作 AMI 镜像

* 打开 EC2 控制台 https://console.aws.amazon.com/ec2/v2/home，左侧选择“实例->实例”
* 选中对应实例，操作 -> 映像和模版 -> 创建映像
* 映像名称 connect-robot，选择“无重启”，创建映像
* 打开 IAM 控制台 https://console.aws.amazon.com/iamv2/home，左侧选择“角色”
* 创建角色，下方选择 EC2，下一步，通过搜索，选择 AmazonConnect_FullAccess 策略，下一步
* 角色名称：ec2-role-for-connect，创建角色
* 打开 EC2 控制台 https://console.aws.amazon.com/ec2/v2/home，左侧选择“映像->AMI”，等待映像制作完毕
* 左侧选择“实例->启动模版”，创建启动模版
* 启动模版名称 connect-robot，系统映像选择 我的AMI，选择connect-robot；密钥对、VPC、网口、安全组等，选择自己常用的
* 展开高级详细信息，IAM实例配置文件，选择ec2-role-for-connect；用户数据user-data中，填入以下启动脚本，其中 connect-alias 是您对应的 Connect 实例别名：

```bash
#!/bin/bash
/usr/local/src/runssh.sh <connect-alias>
```

* 以后修改了镜像，可以选择修改模版（创建新版本）实现，并重新设置默认版本

## 实例测试

* 如果简单启动实例，可以直接以模版启动实例，也可以配置弹性伸缩组自动启动实例。
* 使用管理员登录connect管理台，查看robot动态： https://<connect-alias>.my.connect.aws/real-time-metrics?tableType=user
* 可以看到机器人上线可用状态，这时拨打电话，机器人就会进行接听
* 通话结束后，可以在s3上看到录音文件

## 创建弹性伸缩

* EC2 控制台左侧选择“Auto Scaling->Auto Scaling组”，创建Auto Scaling组
* 名称 asg-connect-robot，启动模版connect-robot，选择VPC和子网
* 选择机型和spot比例，其他设置也可根据实际情况自行设置

## （可选）使用 EC2 Image Builder 制作 AMI

* 也可以使用 EC2 Image Builder进行 AMI 镜像制作。好处是操作系统更新了之后，可以比较方便重新制作。
* 打开 EC2 Image Builder 控制台，创建映像管道，构建计划：手动
* 创建新配方，名称 connect-robot，版本：1.0.0，托管镜像，Amazon Linux 2 Kernel 5 x86
* 测试组件选择reboot-linux，用户数据 里填入上面各步骤安装的代码
* 创建新的基础设施配置，名称：robot-connect-infra，选择IAM角色ec2-role-for-connect和对应实例类型，创建SNS提醒队列，建议设置邮件通知。

## 原理和排错

* 执行原理，因为模拟 connect 机器人登录需要虚拟屏幕和Mic资源，因此需要通过X11的方式进行，在runssh.sh脚本里，是通过ssh连接本机后，然后执行创建账号的脚本createuser.sh，并通过robotagent.py控制启动chrome浏览器进行登录操作
* 如果运行出错，可以查看 /var/log/cloud-init-output.log 观察init脚本运行情况，查看 /usr/local/src/robotagent.log 观察脚本运行情况
* 如果chrome启动环境有误，可以尝试在运行python脚本之前，调用screen进行显示初始化
* 如果screen提示Must be connected to a terminal.错误，可以先运行 script -a log.txt 或 script /dev/null，进行输入输出初始化

## 参考链接

* https://understandingdata.com/install-google-chrome-selenium-ec2-aws
* https://docs.aws.amazon.com/zh_cn/AWSEC2/latest/UserGuide/user-data.html