# pip install dnspython maxminddb boto3
import concurrent.futures
import dns.resolver
import dns.reversename
import maxminddb
import boto3
import time
import json
import re
from botocore.exceptions import ClientError

# 使用boto3 进行 athena saved query 查询
region_name = 'ap-northeast-1'
stack_name = 'natgw-monitor'
topic_arn = 'arn:aws:sns:ap-northeast-1:675857233193:natgw-monitor-notify'
table_name = stack_name + '-table'

athena_client = boto3.client('athena', region_name=region_name)

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
     concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
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
    # 初始化 DynamoDB 客户端
    client = boto3.client('dynamodb', region_name=region_name)
    existing_ips = []
    non_existing_ips = []
    
    # 每批最多 25 个语句（PartiQL 批处理限制）
    batch_size = 25
    for i in range(0, len(ip_list), batch_size):
        batch_ips = ip_list[i:i+batch_size]
        statements = []
        for ip in batch_ips:
            statements.append({
                'Statement': f"SELECT * FROM \"{table_name}\" WHERE ip = ?",
                'Parameters': [{'S': ip}]
            })
        try:
            response = client.batch_execute_statement(Statements=statements)
            # 处理结果
            for j, result in enumerate(response['Responses']):
                ip = batch_ips[j]
                if result.get('Items'):  # 如果有返回项，则 IP 存在
                    existing_ips.append(ip)
                else:
                    non_existing_ips.append(ip)
        except ClientError as e:
            print(f"Error executing PartiQL batch: {e}")
            non_existing_ips.extend(batch_ips)
    return non_existing_ips

def fill_ip_data(rows):
    cnt = []
    ip_list = [item["dstaddr"] for item in rows]
    # 获得的ip为ddb没记录的
    new_ip_list = batch_findip_in_ddb(ip_list)
    with maxminddb.open_database('data/GeoLite2-ASN.mmdb') as reader_asn:
        with maxminddb.open_database('data/GeoLite2-Country.mmdb') as reader_country:
            results = batch_reverse_lookup(new_ip_list)
            for item in rows:
                ip = item["dstaddr"]
                hostname = results[ip]
                hostname = simplify_domains(hostname)
                total_bytes = item["total_bytes"]
                connection_count = item["connection_count"]
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
        table_name (str): DynamoDB表名
        region_name (str): AWS区域名称
        
    返回:
        bool: 是否成功写入
    """
    # 初始化DynamoDB资源
    dynamodb = boto3.resource('dynamodb', region_name=region_name)
    table = dynamodb.Table(table_name)
    
    # 准备项目数据
    item = {'ip': ip}
    
    # 添加时间戳（如果没有提供）
    if 'timestamp' not in attributes:
        item['timestamp'] = int(time.time())
    
    # 添加额外的属性（如果有）
    if attributes:
        for key, value in attributes.items():
            if callable(value):
                actual_value = value()
            else:
                actual_value = value
            # 根据值的类型确定 DynamoDB 类型
            if isinstance(actual_value, str):
                item[key] = {'S': actual_value}
            elif isinstance(actual_value, (int, float)):
                item[key] = {'N': str(actual_value)}
            elif isinstance(actual_value, bool):
                item[key] = {'BOOL': actual_value}
    
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
    query_string = '''
    SELECT
            dstaddr, SUM(bytes) as total_bytes, COUNT(*) as connection_count,
            date_format(from_unixtime(MIN("start"), 'Asia/Shanghai'),'%Y-%m-%d %H:%i:%s') as s,
            date_format(from_unixtime(MAX("end"), 'Asia/Shanghai'),'%Y-%m-%d %H:%i:%s') as e
    FROM vpc_flow_logs WHERE action = 'ACCEPT'
        AND not regexp_like(dstaddr, '^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.|127\.|169\.254\.)')
        AND start >= CAST(to_unixtime(DATE_ADD('minute', -{last_minute}, CURRENT_TIMESTAMP)) AS BIGINT)
    GROUP BY dstaddr ORDER BY total_bytes DESC;
    '''

    execution_id = start_query(stack_name + '-db', stack_name + '-workgroup', query_string)

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
        print(json.dumps(rows[:5], indent=2))  # 打印前5行数据

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
            sns_client = boto3.client('sns', region_name=region_name)
            response = sns_client.publish(
                TopicArn=topic_arn,
                Message=json.dumps(message_data),
                MessageStructure='json',
                Subject='NAT Gatway有对外访问的新IP！'
            )
            print(response)
    else:
        print("查询执行失败或被取消")

check_last_data(10)
