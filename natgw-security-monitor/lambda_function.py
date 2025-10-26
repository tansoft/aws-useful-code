# pip install dnspython maxminddb boto3
import concurrent.futures
import dns.resolver
import dns.reversename
import maxminddb
import boto3
from datetime import datetime, timezone
import time
import json
import re
import os
from botocore.exceptions import ClientError

# 环境变量
STACK_NAME = os.environ['STACK_NAME']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
REFRESH_INTERVAL = int(os.environ['REFRESH_INTERVAL'])
AWS_REGION = os.environ['AWS_REGION']
if not STACK_NAME or not SNS_TOPIC_ARN or not REFRESH_INTERVAL or not AWS_REGION:
    raise ValueError("environment variable is required")

# 使用boto3 进行 athena saved query 查询
table_name = STACK_NAME + '-table'
athena_db = STACK_NAME + '-db'
athena_workgroup = STACK_NAME + '-workgroup'

ddb_resource = boto3.resource('dynamodb', region_name=AWS_REGION)
athena_client = boto3.client('athena', region_name=AWS_REGION)
sns_client = boto3.client('sns', region_name=AWS_REGION)

def reverse_dns_lookup(ip_address):
    try:
        addr = dns.reversename.from_address(ip_address)
        resolver = dns.resolver.Resolver()
        resolver.timeout = 1
        resolver.lifetime = 1
        answers = resolver.resolve(addr, "PTR")
        return (ip_address, str(answers[0]).rstrip('.'))
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout, dns.exception.DNSException):
        return (ip_address, None)

def batch_reverse_lookup(ip_list, max_workers=20):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ip = {executor.submit(reverse_dns_lookup, ip): ip for ip in ip_list}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip, hostname = future.result()
            results[ip] = hostname
    return results

def simplify_domains(domain):
    """
    将 AWS 相关域名替换为简化的标识符    
    参数:
        domain (str): 原始域名
    返回:
        str: 简化后的域名标识符
    """
    if domain is None:
        return 'N/A'
    # 处理 EC2 实例域名
    elif re.match(r'ec2-[0-9-]+\..*\.compute\.amazonaws\.com', domain):
        return 'aws-ec2'
    # 处理 S3 域名
    elif re.match(r's3[.-].*\.amazonaws\.com', domain):
        return 'aws-s3'
    # 处理 CloudFront 域名
    elif re.match(r'.*\.r\.cloudfront\.net', domain):
        return 'aws-cloudfront'
    # 未匹配的域名保持不变
    else:
        return domain

def batch_findip_in_ddb(ip_list):
    existing_ips = []
    non_existing_ips = []
    
    table = ddb_resource.Table(table_name)
    
    # 每批最多 100 个项目（batch_get_item 限制）
    batch_size = 100
    for i in range(0, len(ip_list), batch_size):
        batch_ips = ip_list[i:i+batch_size]
        
        try:
            response = ddb_resource.batch_get_item(
                RequestItems={
                    table_name: {
                        'Keys': [{'ip': ip} for ip in batch_ips]
                    }
                }
            )
            
            # 获取返回的项目
            returned_items = response.get('Responses', {}).get(table_name, [])
            returned_ips = {item['ip'] for item in returned_items}
            
            for ip in batch_ips:
                if ip in returned_ips:
                    # 找到对应的项目并检查action
                    item = next(item for item in returned_items if item['ip'] == ip)
                    action = item.get('action', '')
                    if action.startswith('slient-'):
                        existing_ips.append(ip)
                    else:
                        non_existing_ips.append(ip)
                else:
                    non_existing_ips.append(ip)
                    
        except ClientError as e:
            print(f"Error executing batch_get_item: {e}")
            non_existing_ips.extend(batch_ips)
            
    return non_existing_ips

def fill_ip_data(rows):
    cnt = []
    ip_list = [item["dstaddr"] for item in rows]
    # 获得的ip为ddb没记录的
    new_ip_list = batch_findip_in_ddb(ip_list)
    print(f"找到{len(new_ip_list)}个新ip")
    with maxminddb.open_database('data/GeoLite2-ASN.mmdb') as reader_asn:
        with maxminddb.open_database('data/GeoLite2-Country.mmdb') as reader_country:
            results = batch_reverse_lookup(new_ip_list)
            for item in rows:
                ip = item["dstaddr"]
                if ip in new_ip_list:
                    hostname = results[ip]
                    hostname = simplify_domains(hostname)
                    total_bytes = int(item["total_bytes"])
                    connection_count = int(item["connection_count"])
                    asn = reader_asn.get_with_prefix_len(ip)
                    country = reader_country.get_with_prefix_len(ip)
                    asn_no = 'ASN' + str(asn[0]['autonomous_system_number'])
                    asn_name = asn[0]['autonomous_system_organization']
                    asn_prefix = asn[1]
                    country_code = country[0]['country']['iso_code'] if 'country' in country[0] else country[0]['registered_country']['iso_code']
                    # print(ip, hostname, asn_no, asn_name, asn_prefix, country_code)
                    cnt.append({
                        "ip": ip,
                        "host": hostname,
                        "bytes": total_bytes,
                        "connection": connection_count,
                        "asn": asn_no,
                        "asn_name": asn_name,
                        "asn_prefix": asn_prefix,
                        "country_code": country_code})
    return cnt

def write_ip_with_put_item(ip, attributes):
    """
    使用PutItem将单个IP地址及其属性写入DynamoDB表
    
    参数:
        ip (str): 要写入的IP地址
        attributes (dict): IP地址的属性       
    返回:
        bool: 是否成功写入
    """
    table = ddb_resource.Table(table_name)
    
    # 准备项目数据
    item = {'ip': ip, 'action': 'slient-by-insert'}
    item['record_time'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    # 添加额外的属性（如果有）
    if attributes:
        for key, value in attributes.items():
            if key == "ip":
                continue
            if callable(value):
                item[key] = value()
            else:
                item[key] = value
    try:
        # 写入项目
        response = table.put_item(Item=item)
        return True
    except ClientError as e:
        print(f"Error writing IP {ip}: {e}")
        return False

def wait_for_query_completion(execution_id, max_wait_time=300):
    """
    等待查询完成并返回结果
    
    参数:
        execution_id (str): 查询执行ID
        max_wait_time (int): 最大等待时间(秒)
    
    返回:
        dict: 查询执行状态和结果
    """
    wait_time = 0
    check_interval = 2  # 每2秒检查一次
    
    while wait_time < max_wait_time:
        response = athena_client.get_query_execution(QueryExecutionId=execution_id)
        state = response['QueryExecution']['Status']['State']
        
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            print(f"查询执行完成，状态: {state}")
            if state != 'SUCCEEDED':
                print(response)
            return response
        
        print(f"查询正在执行中，状态: {state}，已等待 {wait_time} 秒...")
        time.sleep(check_interval)
        wait_time += check_interval
    
    print(f"查询执行超时，已等待 {max_wait_time} 秒")
    return None

def get_query_results(execution_id, max_results=1000):
    """
    获取查询结果
    
    参数:
        execution_id (str): 查询执行ID
        max_results (int): 返回的最大结果行数
    
    返回:
        dict: 查询结果
    """
    response = athena_client.get_query_results(
        QueryExecutionId=execution_id,
        MaxResults=max_results
    )
    return response

def start_query(data_base, workgroup, query_string):
    '''
    query_id = 'eb8709b2-9f74-4fae-a56d-9b6c381a9cf7'
    query_details = athena_client.get_named_query(
        NamedQueryId=query_id
    )
    query_string = query_details['NamedQuery']['QueryString']
    data_base = query_details['NamedQuery']['Database']
    '''
    # 设置查询执行参数
    params = {
        'QueryString': query_string,
        'QueryExecutionContext': {
            'Database': data_base
        },
        'WorkGroup': workgroup,
    }
    '''
        'ResultConfiguration': {
            'OutputLocation': output_location or s3_output_location
        }
    '''

    # 启动查询执行
    response = athena_client.start_query_execution(**params)
    return response['QueryExecutionId']

def check_last_data(last_minute):
    query_string = f'''
    SELECT
        dstaddr, SUM(bytes) as total_bytes, COUNT(*) as connection_count,
        date_format(from_unixtime(MIN("start"), 'Asia/Shanghai'),'%Y-%m-%d %H:%i:%s') as s,
        date_format(from_unixtime(MAX("end"), 'Asia/Shanghai'),'%Y-%m-%d %H:%i:%s') as e
    FROM vpc_flow_logs WHERE action = 'ACCEPT'
        AND not regexp_like(dstaddr, '^(10\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.|192\\.168\\.|127\\.|169\\.254\\.)')
        AND start >= CAST(to_unixtime(DATE_ADD('minute', -{last_minute}, CURRENT_TIMESTAMP)) AS BIGINT)
    GROUP BY dstaddr ORDER BY total_bytes DESC;
    '''

    wait_for_query_completion(start_query(athena_db, athena_workgroup, 'MSCK REPAIR TABLE `vpc_flow_logs`;'))

    execution_id = start_query(athena_db, athena_workgroup, query_string)

    execution_status = wait_for_query_completion(execution_id)
    if execution_status and execution_status['QueryExecution']['Status']['State'] == 'SUCCEEDED':
        results = get_query_results(execution_id)

        # 处理结果
        columns = [col['Label'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        print("查询结果列: ", columns)
        
        rows = []
        for row in results['ResultSet']['Rows'][1:]:  # 跳过标题行
            values = [field.get('VarCharValue', '') for field in row['Data']]
            rows.append(dict(zip(columns, values)))
        
        print(f"查询返回了 {len(rows)} 行数据")
        # print(json.dumps(rows[:5], indent=2))  # 打印前5行数据

        cnt = fill_ip_data(rows)
        email = ""
        for obj in cnt:
            write_ip_with_put_item(obj['ip'], obj)
            if email == "":
                email = "发现以下新IP：\nip/段 | 流量 | 链接数 | 域名 | 国家 | ASN | ASN名称\n"
            email += f"{obj['ip']}/{obj['asn_prefix']} | {obj['bytes']} | {obj['connection']} | {obj['host']} | {obj['country_code']} | {obj['asn']} | {obj['asn_name']}\n"
        if email != "":
            message_data = {
                "default": json.dumps(cnt),
                "email": email,
            }
            try:
                response = sns_client.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=json.dumps(message_data),
                    MessageStructure='json',
                    Subject='NAT Gatway有对外访问的新IP！'
                )
                print(response)
            except ClientError as e:
                print(f"Error publish: {e}")
    else:
        print("查询执行失败或被取消")

def lambda_handler(event, context):
    check_last_data(REFRESH_INTERVAL+5)
    return {
        'statusCode': 200,
        'body': 'finish'
    }

if __name__ == "__main__":
    lambda_handler(null, null)