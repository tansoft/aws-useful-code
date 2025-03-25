#!/bin/bash
# 脚本用于在两个 VPC 之间建立 VPC Peering 连接，自动获取 CIDR 块
# 使用方法: ./create_vpc_peering.sh <vpc1_id> <vpc2_id> <vpc1_region> <vpc2_region>

# 检查参数
if [ $# -lt 4 ]; then
    echo "用法: $0 <vpc1_id> <vpc2_id> <vpc1_region> <vpc2_region>"
    echo "示例: $0 vpc-12345678 vpc-87654321 us-east-1 us-west-2"
    exit 1
fi

# 设置参数
VPC1_ID=$1
VPC2_ID=$2
VPC1_REGION=$3
VPC2_REGION=$4

echo "开始创建 VPC Peering 连接..."
echo "VPC1: $VPC1_ID ($VPC1_REGION)"
echo "VPC2: $VPC2_ID ($VPC2_REGION)"

# 自动获取 VPC CIDR 块
echo "获取 VPC CIDR 信息..."
VPC1_CIDR=$(aws ec2 describe-vpcs --vpc-ids $VPC1_ID --query 'Vpcs[0].CidrBlock' --output text --region $VPC1_REGION)
VPC2_CIDR=$(aws ec2 describe-vpcs --vpc-ids $VPC2_ID --query 'Vpcs[0].CidrBlock' --output text --region $VPC2_REGION)

if [ -z "$VPC1_CIDR" ] || [ -z "$VPC2_CIDR" ]; then
    echo "无法获取 VPC CIDR 信息，请检查 VPC ID 和权限"
    exit 1
fi

echo "VPC1 CIDR: $VPC1_CIDR"
echo "VPC2 CIDR: $VPC2_CIDR"

# 创建 VPC Peering 连接请求
echo "步骤 1: 创建 VPC Peering 连接请求..."
if [ "$VPC1_REGION" = "$VPC2_REGION" ]; then
    # 同区域 VPC Peering
    PEERING_ID=$(aws ec2 create-vpc-peering-connection \
        --vpc-id $VPC1_ID \
        --peer-vpc-id $VPC2_ID \
        --region $VPC1_REGION \
        --query 'VpcPeeringConnection.VpcPeeringConnectionId' \
        --output text)
else
    # 跨区域 VPC Peering
    PEERING_ID=$(aws ec2 create-vpc-peering-connection \
        --vpc-id $VPC1_ID \
        --peer-vpc-id $VPC2_ID \
        --peer-region $VPC2_REGION \
        --region $VPC1_REGION \
        --query 'VpcPeeringConnection.VpcPeeringConnectionId' \
        --output text)
fi

if [ -z "$PEERING_ID" ]; then
    echo "创建 VPC Peering 连接请求失败"
    exit 1
fi

echo "VPC Peering 连接请求已创建: $PEERING_ID"

# 接受 VPC Peering 连接请求
echo "步骤 2: 接受 VPC Peering 连接请求..."
if [ "$VPC1_REGION" = "$VPC2_REGION" ]; then
    # 同区域 VPC Peering
    aws ec2 accept-vpc-peering-connection \
        --vpc-peering-connection-id $PEERING_ID \
        --region $VPC1_REGION
else
    # 跨区域 VPC Peering
    aws ec2 accept-vpc-peering-connection \
        --vpc-peering-connection-id $PEERING_ID \
        --region $VPC2_REGION
fi

echo "VPC Peering 连接请求已接受"

# 等待 VPC Peering 连接变为活动状态
echo "等待 VPC Peering 连接变为活动状态..."
sleep 10  # 给 AWS 一些时间来更新状态

# 获取 VPC1 的路由表
echo "步骤 3: 更新 VPC1 的路由表..."
VPC1_ROUTE_TABLES=$(aws ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC1_ID" \
    --query 'RouteTables[*].RouteTableId' \
    --region $VPC1_REGION \
    --output text)

# 更新 VPC1 的每个路由表
for RT_ID in $VPC1_ROUTE_TABLES; do
    echo "更新路由表 $RT_ID (VPC1)"
    aws ec2 create-route \
        --route-table-id $RT_ID \
        --destination-cidr-block $VPC2_CIDR \
        --vpc-peering-connection-id $PEERING_ID \
        --region $VPC1_REGION || echo "路由可能已存在或无法添加"
done

# 获取 VPC2 的路由表
echo "步骤 4: 更新 VPC2 的路由表..."
VPC2_ROUTE_TABLES=$(aws ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC2_ID" \
    --query 'RouteTables[*].RouteTableId' \
    --region $VPC2_REGION \
    --output text)

# 更新 VPC2 的每个路由表
for RT_ID in $VPC2_ROUTE_TABLES; do
    echo "更新路由表 $RT_ID (VPC2)"
    aws ec2 create-route \
        --route-table-id $RT_ID \
        --destination-cidr-block $VPC1_CIDR \
        --vpc-peering-connection-id $PEERING_ID \
        --region $VPC2_REGION || echo "路由可能已存在或无法添加"
done

# 验证 VPC Peering 连接状态
echo "步骤 5: 验证 VPC Peering 连接状态..."
if [ "$VPC1_REGION" = "$VPC2_REGION" ]; then
    # 同区域 VPC Peering
    STATUS=$(aws ec2 describe-vpc-peering-connections \
        --vpc-peering-connection-ids $PEERING_ID \
        --query 'VpcPeeringConnections[0].Status.Code' \
        --region $VPC1_REGION \
        --output text)
else
    # 跨区域 VPC Peering - 检查第一个区域
    STATUS=$(aws ec2 describe-vpc-peering-connections \
        --vpc-peering-connection-ids $PEERING_ID \
        --query 'VpcPeeringConnections[0].Status.Code' \
        --region $VPC1_REGION \
        --output text)
fi

if [ "$STATUS" = "active" ]; then
    echo "VPC Peering 连接已成功建立并处于活动状态!"
    echo "Peering ID: $PEERING_ID"
    echo "VPC1 ($VPC1_ID - $VPC1_CIDR) 现在可以与 VPC2 ($VPC2_ID - $VPC2_CIDR) 通信"
else
    echo "VPC Peering 连接未处于活动状态，当前状态: $STATUS"
    echo "请手动检查 AWS 控制台获取更多信息"
fi

echo "脚本执行完成"

