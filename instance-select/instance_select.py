#!/usr/bin/env python3
import boto3
import yaml
import argparse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from datetime import datetime
import json

def load_config(config_file):
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_lightsail_instances(region, config):
    client = boto3.client('lightsail', region_name=region)
    results = []
    try:
        bundles = client.get_bundles()['bundles']
        for bundle in bundles:
            if bundle.get('isActive'):
                cpu = bundle.get('cpuCount', 0)
                memory = bundle.get('ramSizeInGb', 0)
                storage = bundle.get('diskSizeInGb', 0)
                
                if config.get('cpu_min') and cpu < config['cpu_min']:
                    continue
                if config.get('cpu_max') and cpu > config['cpu_max']:
                    continue
                if config.get('memory_min') and memory < config['memory_min']:
                    continue
                if config.get('memory_max') and memory > config['memory_max']:
                    continue
                if config.get('storage', {}).get('size_min') and storage < config['storage']['size_min']:
                    continue
                if config.get('storage', {}).get('size_max') and storage > config['storage']['size_max']:
                    continue
                
                results.append({
                    'service': 'Lightsail',
                    'region': region,
                    'instance_type': bundle['bundleId'],
                    'cpu': cpu,
                    'memory_gb': memory,
                    'storage_gb': storage,
                    'network_gbps': bundle.get('transferPerMonthInGb', 0) / 730 / 3600 * 8 / 1024,
                    'price_monthly': bundle.get('price', 0),
                    'price_hourly': bundle.get('price', 0) / 730
                })
    except Exception as e:
        print(f"Error fetching Lightsail in {region}: {e}")
    return results

def get_ec2_instances(region, config):
    client = boto3.client('ec2', region_name=region)
    results = []
    
    try:
        response = client.describe_instance_types()
        instance_types = response['InstanceTypes']
        
        while 'NextToken' in response:
            response = client.describe_instance_types(NextToken=response['NextToken'])
            instance_types.extend(response['InstanceTypes'])
        
        for inst in instance_types:
            cpu = inst['VCpuInfo']['DefaultVCpus']
            memory = inst['MemoryInfo']['SizeInMiB'] / 1024
            
            if config.get('cpu_min') and cpu < config['cpu_min']:
                continue
            if config.get('cpu_max') and cpu > config['cpu_max']:
                continue
            if config.get('memory_min') and memory < config['memory_min']:
                continue
            if config.get('memory_max') and memory > config['memory_max']:
                continue
            
            arch = inst['ProcessorInfo'].get('SupportedArchitectures', [])
            if config.get('architecture'):
                arch_map = {'x86': 'x86_64', 'arm': 'arm64'}
                if arch_map.get(config['architecture']) not in arch:
                    continue
            
            prices = get_ec2_prices(inst['InstanceType'], region)
            
            results.append({
                'service': 'EC2',
                'region': region,
                'instance_type': inst['InstanceType'],
                'cpu': cpu,
                'memory_gb': memory,
                'storage_gb': inst.get('InstanceStorageInfo', {}).get('TotalSizeInGB', 0),
                'network_gbps': inst.get('NetworkInfo', {}).get('NetworkPerformance', 'N/A'),
                'price_ondemand': prices['ondemand'],
                'price_ri_1y': prices['ri_1y'],
                'price_ri_3y': prices['ri_3y'],
                'price_sp_1y': prices['sp_1y'],
                'price_sp_3y': prices['sp_3y'],
                'price_spot_avg': prices['spot_avg']
            })
    except Exception as e:
        print(f"Error fetching EC2 in {region}: {e}")
    
    return results

def get_ec2_prices(instance_type, region):
    prices = {
        'ondemand': 0,
        'ri_1y': 0,
        'ri_3y': 0,
        'sp_1y': 0,
        'sp_3y': 0,
        'spot_avg': 0
    }
    
    # 区域名称映射
    region_map = {
        'us-east-1': 'US East (N. Virginia)',
        'us-east-2': 'US East (Ohio)',
        'us-west-1': 'US West (N. California)',
        'us-west-2': 'US West (Oregon)',
        'ap-south-1': 'Asia Pacific (Mumbai)',
        'ap-northeast-1': 'Asia Pacific (Tokyo)',
        'ap-northeast-2': 'Asia Pacific (Seoul)',
        'ap-northeast-3': 'Asia Pacific (Osaka)',
        'ap-southeast-1': 'Asia Pacific (Singapore)',
        'ap-southeast-2': 'Asia Pacific (Sydney)',
        'ca-central-1': 'Canada (Central)',
        'eu-central-1': 'Europe (Frankfurt)',
        'eu-west-1': 'Europe (Ireland)',
        'eu-west-2': 'Europe (London)',
        'eu-west-3': 'Europe (Paris)',
        'eu-north-1': 'Europe (Stockholm)',
        'sa-east-1': 'South America (Sao Paulo)'
    }
    
    location = region_map.get(region, region)
    
    # 获取按需价格
    try:
        pricing_client = boto3.client('pricing', region_name='us-east-1')
        response = pricing_client.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}
            ],
            MaxResults=1
        )
        
        if response['PriceList']:
            price_data = json.loads(response['PriceList'][0])
            
            # 按需价格
            if 'OnDemand' in price_data['terms']:
                on_demand = list(price_data['terms']['OnDemand'].values())[0]
                price_dim = list(on_demand['priceDimensions'].values())[0]
                prices['ondemand'] = float(price_dim['pricePerUnit']['USD'])
            
            # RI价格
            if 'Reserved' in price_data['terms']:
                for term_key, term_val in price_data['terms']['Reserved'].items():
                    attrs = term_val['termAttributes']
                    if attrs['OfferingClass'] == 'standard' and attrs['PurchaseOption'] == 'No Upfront':
                        lease_term = attrs['LeaseContractLength']
                        price_dim = list(term_val['priceDimensions'].values())[0]
                        hourly_price = float(price_dim['pricePerUnit']['USD'])
                        
                        if lease_term == '1yr':
                            prices['ri_1y'] = hourly_price
                        elif lease_term == '3yr':
                            prices['ri_3y'] = hourly_price
    except Exception as e:
        print(f"  Warning: Pricing API failed for {instance_type}: {e}")
    
    # 获取Savings Plan价格（使用RI价格的90%作为估算）
    if prices['ri_1y'] > 0:
        prices['sp_1y'] = prices['ri_1y'] * 0.9
    if prices['ri_3y'] > 0:
        prices['sp_3y'] = prices['ri_3y'] * 0.85
    
    # 获取Spot价格（最近7天多AZ平均）
    try:
        ec2_client = boto3.client('ec2', region_name=region)
        from datetime import datetime, timedelta
        
        start_time = datetime.utcnow() - timedelta(days=7)
        response = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            ProductDescriptions=['Linux/UNIX'],
            StartTime=start_time
        )
        
        if response['SpotPriceHistory']:
            spot_prices = [float(item['SpotPrice']) for item in response['SpotPriceHistory']]
            prices['spot_avg'] = sum(spot_prices) / len(spot_prices)
    except Exception as e:
        print(f"  Warning: Spot price failed for {instance_type}: {e}")
    
    return prices

def get_lambda_info(region, config):
    results = []
    memory_sizes = [128, 256, 512, 1024, 2048, 3072, 4096, 8192, 10240]
    
    for memory in memory_sizes:
        if config.get('memory_min') and memory / 1024 < config['memory_min']:
            continue
        if config.get('memory_max') and memory / 1024 > config['memory_max']:
            continue
        
        cpu = memory / 1769
        price_per_ms = 0.0000166667 * (memory / 1024)
        
        results.append({
            'service': 'Lambda',
            'region': region,
            'instance_type': f'{memory}MB',
            'cpu': round(cpu, 2),
            'memory_gb': memory / 1024,
            'storage_gb': 512,
            'network_gbps': 'N/A',
            'price_hourly': price_per_ms * 3600000,
            'price_monthly': price_per_ms * 3600000 * 730
        })
    
    return results

def generate_excel(results, output_file):
    wb = Workbook()
    ws = wb.active
    ws.title = "Instance Selection"
    
    headers = ['服务', '区域', '实例类型', 'CPU核心数', '内存(GB)', '存储(GB)', 
               '网络性能', '按需价格/小时', '按需价格/月', 'RI-1年/小时', 'RI-1年/月',
               'RI-3年/小时', 'RI-3年/月', 'SP-1年/小时', 'SP-1年/月', 
               'SP-3年/小时', 'SP-3年/月', 'Spot均价/小时', 'Spot均价/月']
    
    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF')
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
    
    for row, result in enumerate(results, 2):
        ws.cell(row=row, column=1, value=result['service'])
        ws.cell(row=row, column=2, value=result['region'])
        ws.cell(row=row, column=3, value=result['instance_type'])
        ws.cell(row=row, column=4, value=result['cpu'])
        ws.cell(row=row, column=5, value=result['memory_gb'])
        ws.cell(row=row, column=6, value=result['storage_gb'])
        ws.cell(row=row, column=7, value=str(result['network_gbps']))
        
        if result['service'] == 'EC2':
            ws.cell(row=row, column=8, value=result['price_ondemand'])
            ws.cell(row=row, column=9, value=f"=H{row}*730")
            ws.cell(row=row, column=10, value=result['price_ri_1y'])
            ws.cell(row=row, column=11, value=f"=J{row}*730")
            ws.cell(row=row, column=12, value=result['price_ri_3y'])
            ws.cell(row=row, column=13, value=f"=L{row}*730")
            ws.cell(row=row, column=14, value=result['price_sp_1y'])
            ws.cell(row=row, column=15, value=f"=N{row}*730")
            ws.cell(row=row, column=16, value=result['price_sp_3y'])
            ws.cell(row=row, column=17, value=f"=P{row}*730")
            ws.cell(row=row, column=18, value=result['price_spot_avg'])
            ws.cell(row=row, column=19, value=f"=R{row}*730")
        else:
            ws.cell(row=row, column=8, value=result.get('price_hourly', 0))
            ws.cell(row=row, column=9, value=f"=H{row}*730")
    
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + col) if col <= 26 else f"A{chr(64 + col - 26)}"].width = 14
    
    wb.save(output_file)
    print(f"报告已生成: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='AWS机型选择程序')
    parser.add_argument('-c', '--config', default='config.yaml', help='配置文件路径')
    args = parser.parse_args()
    
    config = load_config(args.config)
    regions = config.get('regions', ['us-east-1'])
    services = config.get('services', ['lightsail', 'ec2', 'lambda'])
    
    all_results = []
    
    for region in regions:
        print(f"正在查询区域: {region}")
        
        if 'lightsail' in services:
            print(f"  - 查询 Lightsail...")
            all_results.extend(get_lightsail_instances(region, config))
        
        if 'ec2' in services:
            print(f"  - 查询 EC2...")
            all_results.extend(get_ec2_instances(region, config))
        
        if 'lambda' in services:
            print(f"  - 查询 Lambda...")
            all_results.extend(get_lambda_info(region, config))
    
    output_file = f"aws_instance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    generate_excel(all_results, output_file)
    print(f"\n共找到 {len(all_results)} 个符合条件的配置")

if __name__ == '__main__':
    main()
