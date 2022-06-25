# 使用 Selenium 制作 Connect 机器人

制作 Selenium 镜像和启动脚本，可以方便地创建机器人账号，然后登录Amazon Connect。

这里使用 c5.xlarge 机型进行镜像制作，使用Amazon Linux2系统，如：amzn2-ami-kernel-5.10-hvm-2.0.20220606.1-x86_64-gp2

## 安装相应软件

### 安装 Chrome

```bash
sudo curl https://intoli.com/install-google-chrome.sh | bash
sudo mv /usr/bin/google-chrome-stable /usr/bin/google-chrome
```

### 安装 chromedriver

```bash
#current version is 103.0.5060.53
#last version can be get from `curl https://chromedriver.storage.googleapis.com/LATEST_RELEASE`
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

### 安装相关脚本

```bash

```

## 参考链接

* https://understandingdata.com/install-google-chrome-selenium-ec2-aws

