# EKS 简便创建流程

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

## 创建集群

### 全新创建（推荐）

复制以下配置保存到文件 cluster.yaml ，使用 eksctl 进行创建。

```yaml
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig

metadata:
  name: new-private-vpc
  region: us-east-1

managedNodeGroups:
  - name: eks-mng
    instanceType: m6i.large
    desiredCapacity: 2
    minSize: 2
    maxSize: 5
    privateNetworking: true
    volumeSize: 100
    tags:
      ENV: PRD

iam:
  withOIDC: true
  serviceAccounts:
  - metadata:
      name: aws-load-balancer-controller
      namespace: kube-system
    wellKnownPolicies:
      awsLoadBalancerController: true

addons:
  - name: aws-ebs-csi-driver
    wellKnownPolicies:
      ebsCSIController: true

cloudWatch:
 clusterLogging:
   enableTypes: ["*"]
   logRetentionInDays: 30
```

```bash
eksctl create cluster -f cluster.yaml
```

该配置文件完成以下事情：

* 集群 service account aws-load-balancer-controller已经准备就绪，并且已经成功设置好权限。
* 公有子网和私有子网，以及对应的标识，都正确打好，便于后面使用service等
* 注意默认的创建，nodeGroup是放置在公有子网中的，通过指定 privateNetworking: false 来放置到私有子网中，参考：https://eksctl.io/usage/schema/#managedNodeGroups-privateNetworking
* 配置了 ebs-csi 驱动

### 在已有VPC中创建

如果希望在已有VPC中创建，```cluster.yaml``` 中添加以下信息，填入对应的子网信息：

```yaml
vpc:
  subnets:
    private:
      us-east-1a:
        id: "subnet-0123456"
      us-east-1c:
        id: "subnet-0123457"
    public:
      us-east-1a:
        id: "subnet-0123458"
      us-east-1c:
        id: "subnet-0123459"
```

## 配置负载均衡

在 AWS 中可以配置 Service（通过四层的NLB）或 Ingress（通过七层的ALB）进行负载均衡对外服务。

建议安装 AWS Load Balancer Controller 进行配置，参考：https://docs.aws.amazon.com/zh_cn/eks/latest/userguide/quickstart.html#quickstart-lbc

确认service account 是否已经创建：

```bash
kubectl get serviceaccount aws-load-balancer-controller -n kube-system
```

### 更新 eks 源

```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update eks
```

### 创建 AWS Load Balancer Controller

```
export CLUSTER_NAME=new-private-vpc
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

### 配置 Service

```bash
kubectl create namespace demo --save-config
```

### 配置 Ingress



### 删除集群

```bash
kubectl config delete-cluster arn:aws:eks:ap-northeast-1:675857233193:cluster/exist-vpc-cluster
kubectl config delete-context arn:aws:eks:ap-northeast-1:675857233193:cluster/exist-vpc-cluster

eksctl delete cluster --name eks-cluster-name
eksctl delete cluster -f ./cluster-config.yaml
```

### 使用控制台创建

有几个点是需要注意的：

* node group建议建立在私有子网
* service account aws-load-balancer-controller需要自行创建
* LoadBalancer 创建错误的话，需要先检查：集群详情→资源→service中对应的部署名字里，最下方“事件”查看出错原因：
* [Image: image.png]
* 需要配置子网的tag，才可以正常工作（遇到错误：Failed build model due to unable to resolve at least one subnet (0 match VPC and tags: [[kubernetes.io/role/internal-elb](http://kubernetes.io/role/internal-elb)])）
    * 公有子网：
    * [Image: image.png]
    * 私有子网：
    * [Image: image.png]
    * 其中必填的标签是：

```
# 公网：
kubernetes.io/role/elb 1
# 私网：
kubernetes.io/role/internal-elb 1
```

* 需要指定控制alb创建的权限：（遇到错误：Failed deploy model due to operation error Elastic Load Balancing v2: DescribeListenerAttributes, https response error StatusCode: 403, RequestID: 65277d83-e4bb-4d90-98a3-4143d7a09b12, api error AccessDenied: User: arn:aws:sts::675857233193:assumed-role/AmazonEKSLoadBalancerControllerRole/1730390912713101073 is not authorized to perform: elasticloadbalancing:DescribeListenerAttributes because no identity-based policy allows the elasticloadbalancing:DescribeListenerAttributes action）

## 创建AWS Load Balancer Controller

### 设置变量：

```

export CLUSTER_NAME=test
export CLUSTER_REGION=ap-northeast-1

aws eks update-kubeconfig --region ${CLUSTER_REGION} --name ${CLUSTER_NAME}
```

### 创建service account：（控制台方式）

如果没有创建，按以下进行配置：
https://docs.aws.amazon.com/zh_cn/eks/latest/userguide/lbc-helm.html

```
curl -O https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.2/docs/install/iam_policy.json

aws iam create-policy \
    --policy-name AWSLoadBalancerControllerIAMPolicy \
    --policy-document file://iam_policy.json

export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# 如果遇到错误Error: unable to create iamserviceaccount(s) without IAM OIDC provider enabled，运行：
# eksctl utils associate-iam-oidc-provider --region=${CLUSTER_REGION} --cluster=${CLUSTER_NAME} --approve
eksctl create iamserviceaccount \
  --cluster=${CLUSTER_NAME} \
  --region=${CLUSTER_REGION} \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --role-name AmazonEKSLoadBalancerControllerRole \
  --attach-policy-arn=arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy \
  --approve
```

