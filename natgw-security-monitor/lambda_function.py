import json
import boto3
import os
from datetime import datetime, timedelta
import ipaddress
from decimal import Decimal

# 初始化AWS客户端
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
s3 = boto3.client('s3')
ec2 = boto3.client('ec2')

# 环境变量
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
S3_BUCKET = os.environ['S3_BUCKET']
S3_PREFIX = os.environ['S3_PREFIX']
THRESHOLD_MBPS = float(os.environ['THRESHOLD_MBPS'])

def lambda_handler(event, context):
    """主处理函数"""
    try:
        # 获取DynamoDB表
        table = dynamodb.Table(DYNAMODB_TABLE)

        # 分析流量数据
        traffic_data = analyze_traffic_logs()
        
        # 处理IP段数据
        process_ip_segments(table, traffic_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Traffic analysis completed successfully')
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        send_notification(f"流量分析失败: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }

def analyze_traffic_logs():
    """分析S3中的流量日志"""
    traffic_data = {}
    current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    
    # 构建S3路径 (Hive格式: year=2023/month=12/day=15/hour=14/)
    s3_path = f"{S3_PREFIX}year={current_hour.year}/month={current_hour.month:02d}/day={current_hour.day:02d}/hour={current_hour.hour:02d}/"
    
    try:
        # 列出S3对象
        response = s3.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=s3_path
        )
        
        if 'Contents' not in response:
            print(f"No flow logs found for path: {s3_path}")
            return traffic_data
        
        # 处理每个日志文件
        for obj in response['Contents']:
            process_flow_log_file(obj['Key'], traffic_data)
            
    except Exception as e:
        print(f"Error analyzing traffic logs: {str(e)}")
    
    return traffic_data

def process_flow_log_file(s3_key, traffic_data):
    """处理单个流量日志文件"""
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = response['Body'].read().decode('utf-8')
        
        for line in content.strip().split('\n'):
            if line.startswith('version') or not line.strip():
                continue
                
            fields = line.split(' ')
            if len(fields) >= 14:
                srcaddr = fields[3]
                dstaddr = fields[4]
                bytes_transferred = int(fields[10]) if fields[10].isdigit() else 0
                
                # 只关注出站流量
                if is_private_ip(srcaddr) and not is_private_ip(dstaddr):
                    cidr = get_cidr_24(dstaddr)
                    if cidr not in traffic_data:
                        traffic_data[cidr] = 0
                    traffic_data[cidr] += bytes_transferred
                    
    except Exception as e:
        print(f"Error processing file {s3_key}: {str(e)}")

def is_private_ip(ip):
    """判断是否为私有IP"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except:
        return False

def get_cidr_24(ip):
    """获取/24网段"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        network = ipaddress.ip_network(f"{ip}/24", strict=False)
        return str(network)
    except:
        return None

def process_ip_segments(table, traffic_data):
    """处理IP段数据"""
    current_hour = datetime.utcnow().strftime('%Y-%m-%d-%H')
    
    for cidr, bytes_count in traffic_data.items():
        if not cidr:
            continue
            
        mbps = bytes_count / (1024 * 1024 * 60)  # 转换为MB/分钟，近似MB/s
        
        try:
            # 查询现有记录
            response = table.get_item(Key={'cidr': cidr})
            
            if 'Item' in response:
                # 更新现有记录
                item = response['Item']
                update_existing_record(table, item, cidr, current_hour, mbps)
            else:
                # 新IP段，创建记录并发送通知
                create_new_record(table, cidr, current_hour, mbps)
                send_notification(f"发现新IP段: {cidr}, 流量: {mbps:.2f} MB/s")
                
        except Exception as e:
            print(f"Error processing CIDR {cidr}: {str(e)}")

def update_existing_record(table, item, cidr, current_hour, mbps):
    """更新现有记录"""
    hour_outdata = item.get('hour-outdata', {})
    hour_outdata[current_hour] = Decimal(str(mbps))
    
    total_outdata = float(item.get('total-outdata', 0)) + mbps
    status = item.get('status', 'normal')
    
    # 检查是否需要报警
    if mbps > THRESHOLD_MBPS and status != 'alert':
        status = 'alert'
        send_notification(f"IP段 {cidr} 流量异常: {mbps:.2f} MB/s (阈值: {THRESHOLD_MBPS} MB/s)")
    elif mbps <= THRESHOLD_MBPS and status == 'alert':
        status = 'normal'
    
    # 更新记录
    table.update_item(
        Key={'cidr': cidr},
        UpdateExpression='SET #ho = :ho, #to = :to, #st = :st',
        ExpressionAttributeNames={
            '#ho': 'hour-outdata',
            '#to': 'total-outdata',
            '#st': 'status'
        },
        ExpressionAttributeValues={
            ':ho': hour_outdata,
            ':to': Decimal(str(total_outdata)),
            ':st': status
        }
    )

def create_new_record(table, cidr, current_hour, mbps):
    """创建新记录"""
    status = 'alert' if mbps > THRESHOLD_MBPS else 'unknown'
    
    table.put_item(
        Item={
            'cidr': cidr,
            'hour-outdata': {current_hour: Decimal(str(mbps))},
            'total-outdata': Decimal(str(mbps)),
            'purpose': 'unknown',
            'status': status
        }
    )

def send_notification(message):
    """发送SNS通知"""
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject='NAT Gateway Security Monitor Alert'
        )
        print(f"Notification sent: {message}")
    except Exception as e:
        print(f"Error sending notification: {str(e)}")