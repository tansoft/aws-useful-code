# 多区域部署eks

## 依赖工具

根据文档 https://docs.aws.amazon.com/zh_cn/eks/latest/userguide/setting-up.html 进行以下工具安装和配置，下述举例是 Mac 下的。

### awscli

根据文档安装 https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

```bash
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
# 设置本地使用的ak/sk
aws configure
```

### kubectl

根据文档安装 kubectl：https://docs.aws.amazon.com/zh_cn/eks/latest/userguide/install-kubectl.html#kubectl-install-update

```bash
# for Kubernetes 1.31 on Mac
curl -O https://s3.us-west-2.amazonaws.com/amazon-eks/1.31.0/2024-09-12/bin/darwin/amd64/kubectl
chmod +x ./kubectl
mkdir -p $HOME/bin && cp ./kubectl $HOME/bin/kubectl && export PATH=$HOME/bin:$PATH
echo 'export PATH=$HOME/bin:$PATH' >> ~/.bash_profile
```

### eksctl

根据文档安装 eksctl：https://eksctl.io/installation/

```bash
brew tap weaveworks/tap
brew install weaveworks/tap/eksctl
```

### helm

官网安装helm：https://github.com/helm/helm/releases

```bash
wget https://get.helm.sh/helm-v3.16.2-darwin-arm64.tar.gz
tar -zvxf helm-v3.16.2-darwin-arm64.tar.gz
sudo mv darwin-arm64/helm /usr/local/bin/
```

### 更新 eks 源

```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update eks
```

## 创建集群

* 如果需要自定义配置，请修改 new-cluster-*.yaml 为指定的配置。
* 以下例子以us-east-1为例，进行部署，其他区域分别修改参数执行即可。

```bash
eksctl create cluster -f new-cluster-us-east-1.yaml
```

该配置文件完成以下事情：

* 集群 service account aws-load-balancer-controller已经准备就绪，并且已经成功设置好权限。
* 公有子网和私有子网，以及对应的标识，都正确打好，便于后面使用service等
* 注意默认的创建，nodeGroup是放置在私有子网中的，通过指定 privateNetworking: false 来放置到公有子网中，参考：https://eksctl.io/usage/schema/#managedNodeGroups-privateNetworking
* 配置了 ebs-csi 驱动

## 配置负载均衡

在 AWS 中可以配置 Service（通过四层的NLB）或 Ingress（通过七层的ALB）进行负载均衡对外服务。

建议安装 AWS Load Balancer Controller 进行配置，参考：https://docs.aws.amazon.com/zh_cn/eks/latest/userguide/quickstart.html#quickstart-lbc

确认service account 是否已经创建：

```bash
kubectl get serviceaccount aws-load-balancer-controller -n kube-system
```

### 创建 AWS Load Balancer Controller

```
export CLUSTER_NAME=multi-region-iad
export CLUSTER_REGION=us-east-1
export CLUSTER_VPC=$(aws eks describe-cluster --name ${CLUSTER_NAME} --region ${CLUSTER_REGION} --query "cluster.resourcesVpcConfig.vpcId" --output text)

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
   --namespace kube-system --set clusterName=${CLUSTER_NAME} \
   --set serviceAccount.create=false \
   --set region=${CLUSTER_REGION} \
   --set vpcId=${CLUSTER_VPC} \
   --set serviceAccount.name=aws-load-balancer-controller

kubectl get deployments -n kube-system aws-load-balancer-controller
```

## 配置 Echo-Server

* 接下来，我们执行echo server部署，这样可以进行跨区域之间的调用测试

```bash
kubectl create namespace demo --save-config
```

### 配置 Service

```bash
kubectl apply -f demo-echo-server.yaml
```

等待 service 可用

```bash
kubectl get deployments -n demo
kubectl get pods -n demo
kubectl get services -n demo

# 这样拿到 nlb 对外域名
HOSTNAME=`kubectl get service echo-server-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'`
# k8s-demo-echoserv-xxxx-xxxx.elb.us-east-1.amazonaws.com
curl http://${HOSTNAME}/
```

可以看到输出的echo

```json
{"host":{"hostname":"k8s-demo-echoserv-xxxx-xxxx.elb.us-east-1.amazonaws.com","ip":"::ffff:10.11.13.220","ips":[]},"http":{"method":"GET","baseUrl":"","originalUrl":"/","protocol":"http"},"request":{"params":{"0":"/"},"query":{},"cookies":{},"body":{},"headers":{"host":"k8s-demo-echoserv-xxxx-xxxx.elb.us-east-1.amazonaws.com","user-agent":"curl/8.7.1","accept":"*/*"}},"environment":{"PATH":"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin","HOSTNAME":"echo-server-5bc4794d5-f2t28","NODE_VERSION":"20.11.0","YARN_VERSION":"1.22.19","KUBERNETES_PORT":"tcp://172.20.0.1:443","ECHO_SERVER_SERVICE_SERVICE_PORT":"80","ECHO_SERVER_SERVICE_PORT_80_TCP_PROTO":"tcp","KUBERNETES_PORT_443_TCP_PORT":"443","ECHO_SERVER_SERVICE_SERVICE_HOST":"172.20.176.48","ECHO_SERVER_SERVICE_PORT_80_TCP":"tcp://172.20.176.48:80","KUBERNETES_SERVICE_HOST":"172.20.0.1","KUBERNETES_SERVICE_PORT":"443","KUBERNETES_SERVICE_PORT_HTTPS":"443","ECHO_SERVER_SERVICE_SERVICE_PORT_HTTP":"80","ECHO_SERVER_SERVICE_PORT_80_TCP_PORT":"80","ECHO_SERVER_SERVICE_PORT_80_TCP_ADDR":"172.20.176.48","KUBERNETES_PORT_443_TCP":"tcp://172.20.0.1:443","KUBERNETES_PORT_443_TCP_PROTO":"tcp","KUBERNETES_PORT_443_TCP_ADDR":"172.20.0.1","ECHO_SERVER_SERVICE_PORT":"tcp://172.20.176.48:80","HOME":"/root"}}
```

### 安装VSCode 中的 Kubernetes 插件（可选）

在VSCode中安装 Kubernetes 插件，可以方便地选择管理的集群，查看集群信息等

### 测试pod ip

```bash
# 获取 Pod IP
kubectl get pods -n demo -l app=echo-server -o jsonpath='{.items[*].status.podIP}'
# 10.11.71.162 10.11.124.92
# 在控制台中创建 CloudShell，指定 eks 的 vpc，选择安全组 eksctl-multi-region-iad-cluster-ClusterSharedNodeSecurityGroup-xxxx，进行测试（或创建跳板机进行测试也是可以的）
~ $ curl 10.11.71.162
{"host":{"hostname":"10.11.71.162","ip":"::ffff:10.11.89.255","ips":[]},"http":{"method":"GET","baseUrl":"","originalUrl":"/","protocol":"http"},"request":{"params":{"0":"/"},"query":{},"cookies":{},"body":{},"headers":{"host":"10.11.71.162","user-agent":"curl/8.5.0","accept":"*/*"}},"environment":{"PATH":"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin","HOSTNAME":"echo-server-5bc4794d5-f2t28","NODE_VERSION":"20.11.0","YARN_VERSION":"1.22.19","KUBERNETES_PORT":"tcp://172.20.0.1:443","ECHO_SERVER_SERVICE_SERVICE_PORT":"80","ECHO_SERVER_SERVICE_PORT_80_TCP_PROTO":"tcp","KUBERNETES_PORT_443_TCP_PORT":"443","ECHO_SERVER_SERVICE_SERVICE_HOST":"172.20.176.48","ECHO_SERVER_SERVICE_PORT_80_TCP":"tcp://172.20.176.48:80","KUBERNETES_SERVICE_HOST":"172.20.0.1","KUBERNETES_SERVICE_PORT":"443","KUBERNETES_SERVICE_PORT_HTTPS":"443","ECHO_SERVER_SERVICE_SERVICE_PORT_HTTP":"80","ECHO_SERVER_SERVICE_PORT_80_TCP_PORT":"80","ECHO_SERVER_SERVICE_PORT_80_TCP_ADDR":"172.20.176.48","KUBERNETES_PORT_443_TCP":"tcp://172.20.0.1:443","KUBERNETES_PORT_443_TCP_PROTO":"tcp","KUBERNETES_PORT_443_TCP_ADDR":"172.20.0.1","ECHO_SERVER_SERVICE_PORT":"tcp://172.20.176.48:80","HOME":"/root"}}
```

### 多区域进行网络打通

```bash
# 获取eks集群的vpcid
IADVPC=`aws eks describe-cluster --name multi-region-iad --query "cluster.resourcesVpcConfig.vpcId" --output text --region us-east-1`
SINVPC=`aws eks describe-cluster --name multi-region-sin --query "cluster.resourcesVpcConfig.vpcId" --output text --region ap-southeast-1`
./create-vpc-peering.sh ${IADVPC} ${SINVPC} us-east-1 ap-southeast-1
#可以看到以下输出信息，两个vpc已经互通了
开始创建 VPC Peering 连接...
VPC1: vpc-0c0832bxxx (us-east-1)
VPC2: vpc-0b16c7bxxx (ap-southeast-1)
获取 VPC CIDR 信息...
VPC1 CIDR: 10.11.0.0/16
VPC2 CIDR: 10.12.0.0/16
步骤 1: 创建 VPC Peering 连接请求...
VPC Peering 连接请求已创建: pcx-06898da38bxxx
步骤 2: 接受 VPC Peering 连接请求...
VPC Peering 连接请求已接受
等待 VPC Peering 连接变为活动状态...
步骤 3: 更新 VPC1 的路由表...
更新路由表 rtb-032fce670xxx (VPC1)
步骤 4: 更新 VPC2 的路由表...
更新路由表 rtb-026f5ff7ebxxx (VPC2)
步骤 5: 验证 VPC Peering 连接状态...
VPC Peering 连接已成功建立并处于活动状态!
Peering ID: pcx-06898da38bxxx
VPC1 (vpc-0c0832bxxx - 10.11.0.0/16) 现在可以与 VPC2 (vpc-0b16cxxx - 10.12.0.0/16) 通信
脚本执行完成
```

### 修改集群安全组，允许内网之间直接访问

```bash
# iad集群
SGID=`aws eks describe-cluster --name multi-region-iad --query cluster.resourcesVpcConfig.clusterSecurityGroupId --output text --region us-east-1`
aws ec2 authorize-security-group-ingress --group-id ${SGID} --protocol all --port -1 --cidr "10.0.0.0/8" --region us-east-1

# sin集群
SGID=`aws eks describe-cluster --name multi-region-sin --query cluster.resourcesVpcConfig.clusterSecurityGroupId --output text --region ap-southeast-1`
aws ec2 authorize-security-group-ingress --group-id ${SGID} --protocol all --port -1 --cidr "10.0.0.0/8" --region ap-southeast-1
```

### 测试联通性

获取 sin 集群的 pod ip，在 iad 中进行访问：

```bash
kubectl get pods -n demo -l app=echo-server -o jsonpath='{.items[*].status.podIP}'
10.12.188.209 10.12.98.0
curl 10.12.188.209
# 成功访问
{"host":{"hostname":"10.12.188.209","ip":"::ffff:10.11.89.255","ips":[]},"http":{"method":"GET","baseUrl":"","originalUrl":"/","protocol":"http"},"request":{"params":{"0":"/"},"query":{},"cookies":{},"body":{},"headers":{"host":"10.12.188.209","user-agent":"curl/8.5.0","accept":"*/*"}},"environment":{"PATH":"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin","HOSTNAME":"echo-server-5bc4794d5-8cscw","NODE_VERSION":"20.11.0","YARN_VERSION":"1.22.19","ECHO_SERVER_SERVICE_SERVICE_PORT_HTTP":"80","KUBERNETES_PORT_443_TCP_PORT":"443","ECHO_SERVER_SERVICE_PORT":"tcp://172.20.243.4:80","ECHO_SERVER_SERVICE_PORT_80_TCP_PROTO":"tcp","KUBERNETES_PORT_443_TCP_PROTO":"tcp","KUBERNETES_SERVICE_HOST":"172.20.0.1","KUBERNETES_SERVICE_PORT_HTTPS":"443","KUBERNETES_PORT_443_TCP":"tcp://172.20.0.1:443","KUBERNETES_PORT_443_TCP_ADDR":"172.20.0.1","ECHO_SERVER_SERVICE_SERVICE_HOST":"172.20.243.4","ECHO_SERVER_SERVICE_SERVICE_PORT":"80","ECHO_SERVER_SERVICE_PORT_80_TCP":"tcp://172.20.243.4:80","ECHO_SERVER_SERVICE_PORT_80_TCP_PORT":"80","ECHO_SERVER_SERVICE_PORT_80_TCP_ADDR":"172.20.243.4","KUBERNETES_SERVICE_PORT":"443","KUBERNETES_PORT":"tcp://172.20.0.1:443","HOME":"/root"}}~ $ 
```

## 删除集群

```bash
ACCOUNTID=`aws sts get-caller-identity --query Account --output text`
kubectl config delete-cluster arn:aws:eks:us-east-1:${ACCOUNTID}:cluster/multi-region-iad

eksctl delete cluster --name multi-region-iad --region us-east-1
# or
eksctl delete cluster -f ./new-cluster-us-east-1.yaml
```

## 参考链接

* https://eksctl.io/getting-started/
