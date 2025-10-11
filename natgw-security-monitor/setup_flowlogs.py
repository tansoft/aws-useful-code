import boto3
import json

def setup_nat_gateway_flowlogs(nat_gateway_id, s3_bucket, s3_prefix, flow_logs_role_arn):
    """为NAT Gateway设置VPC Flow Logs"""
    ec2 = boto3.client('ec2')
    
    try:
        # 获取NAT Gateway信息
        response = ec2.describe_nat_gateways(NatGatewayIds=[nat_gateway_id])
        if not response['NatGateways']:
            raise Exception(f"NAT Gateway {nat_gateway_id} not found")
        
        nat_gateway = response['NatGateways'][0]
        subnet_id = nat_gateway['SubnetId']
        
        # 获取子网信息以找到VPC ID
        subnet_response = ec2.describe_subnets(SubnetIds=[subnet_id])
        vpc_id = subnet_response['Subnets'][0]['VpcId']
        
        # 获取NAT Gateway的网络接口
        network_interfaces = nat_gateway.get('NetworkInterfaces', [])
        if not network_interfaces:
            raise Exception(f"No network interfaces found for NAT Gateway {nat_gateway_id}")
        
        eni_id = network_interfaces[0]['NetworkInterfaceId']
        
        # 创建Flow Logs
        flow_log_response = ec2.create_flow_logs(
            ResourceIds=[eni_id],
            ResourceType='NetworkInterface',
            TrafficType='ALL',
            LogDestinationType='s3',
            LogDestination=f'arn:aws:s3:::{s3_bucket}/{s3_prefix}',
            LogFormat='${version} ${account-id} ${interface-id} ${srcaddr} ${dstaddr} ${srcport} ${dstport} ${protocol} ${packets} ${bytes} ${windowstart} ${windowend} ${action} ${flowlogstatus}',
            MaxAggregationInterval=60,  # 1分钟聚合
            DeliverLogsPermissionArn=flow_logs_role_arn
        )
        
        print(f"Flow Logs created successfully: {flow_log_response['FlowLogIds']}")
        return flow_log_response['FlowLogIds'][0]
        
    except Exception as e:
        print(f"Error setting up Flow Logs: {str(e)}")
        raise

if __name__ == "__main__":
    # 示例用法
    nat_gw_id = "nat-xxxxxx"  # 替换为实际的NAT Gateway ID
    s3_bucket = "my-natgw-data"
    s3_prefix = "flowlogs"
    role_arn = "arn:aws:iam::123456789012:role/flowlogsRole"  # 替换为实际的角色ARN
    
    flow_log_id = setup_nat_gateway_flowlogs(nat_gw_id, s3_bucket, s3_prefix, role_arn)