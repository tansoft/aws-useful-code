#!/usr/bin/env python3
import boto3
import yaml
import argparse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from datetime import datetime, timedelta
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

# 全局常量
REGION_MAP = {
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

OS_MAP = {'Linux': 'Linux', 'Windows': 'Windows', 'RHEL': 'RHEL', 'SUSE': 'SUSE'}
SPOT_OS_MAP = {'Linux': 'Linux/UNIX', 'Windows': 'Windows', 'RHEL': 'Red Hat Enterprise Linux', 'SUSE': 'SUSE Linux'}

def load_config(config_file):
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_lightsail_instances(region, config):
    client = boto3.client('lightsail', region_name=region)
    results = []
    try:
        bundles = client.get_bundles()['bundles']
        os_config = config.get('operating_system', 'Linux')
        os_platform = 'WINDOWS' if os_config == 'Windows' else 'LINUX_UNIX'
        
        for bundle in bundles:
            if not bundle.get('isActive') or os_platform not in bundle.get('supportedPlatforms', []):
                continue
            
            cpu, memory, storage = bundle.get('cpuCount', 0), bundle.get('ramSizeInGb', 0), bundle.get('diskSizeInGb', 0)
            
            storage_config = config.get('storage') or {}
            if not (check_range(cpu, config.get('cpu_min'), config.get('cpu_max')) and
                    check_range(memory, config.get('memory_min'), config.get('memory_max')) and
                    check_range(storage, storage_config.get('size_min'), storage_config.get('size_max'))):
                continue
            
            price = bundle.get('price', 0)
            result = {
                'service': 'Lightsail', 'region': region, 'instance_type': bundle['bundleId'],
                'cpu': cpu, 'memory_gb': memory, 'storage_gb': storage,
                'network_gbps': f"{bundle.get('transferPerMonthInGb', 0)}GB/月",
                'ondemand': price / 730
            }
            if config.get('public_ip'):
                result['public_ip_count'] = 1
            results.append(result)
    except Exception as e:
        print(f"Error fetching Lightsail in {region}: {e}")
    return results

def check_range(value, min_val, max_val):
    return (min_val is None or value >= min_val) and (max_val is None or value <= max_val)

def get_ec2_instances(region, config):
    client = boto3.client('ec2', region_name=region)
    results = []
    
    try:
        instance_types = fetch_instance_types(client, config)
        
        # 批量获取价格
        pricing_cache = {}
        for inst in instance_types:
            instance_type = inst['InstanceType']
            cpu, memory = inst['VCpuInfo']['DefaultVCpus'], inst['MemoryInfo']['SizeInMiB'] / 1024
            
            if not (check_range(cpu, config.get('cpu_min'), config.get('cpu_max')) and
                    check_range(memory, config.get('memory_min'), config.get('memory_max'))):
                continue
            
            if not check_architecture(inst, config):
                continue
            
            # 使用缓存的价格数据
            cache_key = (instance_type, region, config.get('operating_system', 'Linux'))
            if cache_key not in pricing_cache:
                pricing_cache[cache_key] = get_ec2_prices(instance_type, region, config.get('operating_system', 'Linux'), 
                                                          config.get('pricing_types', {'ondemand': True}))
            
            result = {
                'service': 'EC2', 'region': region, 'instance_type': instance_type,
                'cpu': cpu, 'memory_gb': memory,
                'storage_gb': inst.get('InstanceStorageInfo', {}).get('TotalSizeInGB', 0),
                'network_gbps': inst.get('NetworkInfo', {}).get('NetworkPerformance', 'N/A')
            }
            result.update(pricing_cache[cache_key])
            
            if config.get('public_ip'):
                network_info = inst.get('NetworkInfo', {})
                result['public_ip_count'] = network_info.get('MaximumNetworkInterfaces', 0) * network_info.get('Ipv4AddressesPerInterface', 0)
            
            results.append(result)
    except Exception as e:
        print(f"Error fetching EC2 in {region}: {e}")
    
    return results

def fetch_instance_types(client, config):
    instance_types = []
    if config.get('instance_type_prefix'):
        for prefix in config['instance_type_prefix']:
            paginator = client.get_paginator('describe_instance_types')
            for page in paginator.paginate(Filters=[{'Name': 'instance-type', 'Values': [f'{prefix}*']}]):
                instance_types.extend([inst for inst in page['InstanceTypes'] if check_postfix(inst['InstanceType'], config)])
    else:
        paginator = client.get_paginator('describe_instance_types')
        for page in paginator.paginate():
            instance_types.extend([inst for inst in page['InstanceTypes'] if check_postfix(inst['InstanceType'], config)])
    return instance_types

def check_postfix(instance_type, config):
    postfix_config = config.get('instance_type_postfix')
    if not postfix_config:
        return True
    
    parts = instance_type.split('.')
    if len(parts) < 2:
        return False
    
    family = parts[0]
    base_family = ''.join(c for i, c in enumerate(family) if not c.isdigit() or i == 0 or not family[i-1].isdigit())
    generation = int(''.join(c for c in family if c.isdigit()) or '0')
    suffix = family[len(base_family):]
    
    if postfix_config == '-':
        if suffix not in ['', 'i', 'a', 'g', 'i-flex', 'a-flex', 'g-flex']:
            return False
        family_prefix = ''.join(c for c in base_family if c.isalpha())
        return generation >= 5 or family_prefix.startswith('t')
    else:
        enhanced_suffix = suffix.replace('i', '').replace('a', '').replace('g', '').replace('-flex', '')
        return enhanced_suffix and any(s in enhanced_suffix for s in postfix_config)

def check_architecture(inst, config):
    if not config.get('architecture'):
        return True
    
    arch = inst['ProcessorInfo'].get('SupportedArchitectures', [])
    arch_list = config['architecture'] if isinstance(config['architecture'], list) else [config['architecture']]
    arch_map = {'x86': 'x86_64', 'arm': 'arm64', 'mac': 'x86_64_mac'}
    
    for arch_config in arch_list:
        if arch_config == 'mac' and inst['InstanceType'].startswith('mac'):
            return True
        if arch_map.get(arch_config) in arch:
            return True
    return False

def get_ec2_prices(instance_type, region, operating_system='Linux', pricing_types=None):
    if pricing_types is None:
        pricing_types = {'ondemand': True}
    prices = {}
    
    os_value = OS_MAP.get(operating_system, 'Linux')
    location = REGION_MAP.get(region, region)
    
    # 获取按需和RI价格
    if pricing_types.get('ondemand') or any(k.startswith('ri_') for k in pricing_types.keys()):
        try:
            pricing_client = boto3.client('pricing', region_name='us-east-1')
            response = pricing_client.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': os_value},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                    {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                    {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}
                ],
                MaxResults=1
            )
            
            if response['PriceList']:
                price_data = json.loads(response['PriceList'][0])
                
                if pricing_types.get('ondemand') and 'OnDemand' in price_data['terms']:
                    on_demand = list(price_data['terms']['OnDemand'].values())[0]
                    price_dim = list(on_demand['priceDimensions'].values())[0]
                    prices['ondemand'] = float(price_dim['pricePerUnit']['USD'])
                
                if 'Reserved' in price_data['terms']:
                    key_map = {
                        ('1yr', 'No Upfront'): ('ri_1y_no_upfront', 8760), 
                        ('1yr', 'Partial Upfront'): ('ri_1y_partial_upfront', 8760),
                        ('1yr', 'All Upfront'): ('ri_1y_all_upfront', 8760), 
                        ('3yr', 'No Upfront'): ('ri_3y_no_upfront', 26280),
                        ('3yr', 'Partial Upfront'): ('ri_3y_partial_upfront', 26280), 
                        ('3yr', 'All Upfront'): ('ri_3y_all_upfront', 26280)
                    }
                    for term_val in price_data['terms']['Reserved'].values():
                        attrs = term_val['termAttributes']
                        if attrs['OfferingClass'] == 'standard':
                            key_info = key_map.get((attrs['LeaseContractLength'], attrs['PurchaseOption']))
                            if key_info and pricing_types.get(key_info[0]):
                                hourly_price = 0
                                upfront_price = 0
                                for price_dim in term_val['priceDimensions'].values():
                                    if price_dim['unit'] == 'Hrs':
                                        hourly_price = float(price_dim['pricePerUnit']['USD'])
                                    elif price_dim['unit'] == 'Quantity':
                                        upfront_price = float(price_dim['pricePerUnit']['USD'])
                                prices[key_info[0]] = hourly_price + (upfront_price / key_info[1])
        except Exception as e:
            print(f"  Warning: Pricing API failed for {instance_type}: {e}")
    
    # Savings Plan价格 - 使用Pricing API
    if any(k.startswith('sp_') for k in pricing_types.keys()):
        try:
            pricing_client = boto3.client('pricing', region_name='us-east-1')
            
            # Compute Savings Plan
            for duration, sp_key in [('1yr', 'sp_compute_1y'), ('3yr', 'sp_compute_3y')]:
                if pricing_types.get(sp_key):
                    try:
                        response = pricing_client.get_products(
                            ServiceCode='ComputeSavingsPlans',
                            Filters=[
                                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'shared'},
                                {'Type': 'TERM_MATCH', 'Field': 'LeaseContractLength', 'Value': duration}
                            ],
                            MaxResults=1
                        )
                        if response['PriceList']:
                            sp_data = json.loads(response['PriceList'][0])
                            if 'terms' in sp_data and 'savingsPlan' in sp_data['terms']:
                                sp_term = list(sp_data['terms']['savingsPlan'].values())[0]
                                rate_code = list(sp_term['rates'].values())[0]
                                prices[sp_key] = float(rate_code.get('discountedRate', {}).get('price', 0))
                    except Exception as e:
                        print(f"  Warning: {sp_key} failed for {instance_type}: {e}")
            
            # Instance Savings Plan
            for duration, sp_key in [('1yr', 'sp_instance_1y'), ('3yr', 'sp_instance_3y')]:
                if pricing_types.get(sp_key):
                    try:
                        response = pricing_client.get_products(
                            ServiceCode='AmazonEC2',
                            Filters=[
                                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': os_value},
                                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}
                            ],
                            MaxResults=1
                        )
                        if response['PriceList']:
                            sp_data = json.loads(response['PriceList'][0])
                            if 'terms' in sp_data and 'savingsPlan' in sp_data['terms']:
                                for term_val in sp_data['terms']['savingsPlan'].values():
                                    if term_val.get('LeaseContractLength') == duration:
                                        rate_code = list(term_val['rates'].values())[0]
                                        prices[sp_key] = float(rate_code.get('discountedRate', {}).get('price', 0))
                                        break
                    except Exception as e:
                        print(f"  Warning: {sp_key} failed for {instance_type}: {e}")
        except Exception as e:
            print(f"  Warning: Savings Plans pricing failed: {e}")
    
    # Spot价格（优化：只查询最近1天，限制结果数）
    if pricing_types.get('spot'):
        try:
            ec2_client = boto3.client('ec2', region_name=region)
            spot_product = SPOT_OS_MAP.get(operating_system, 'Linux/UNIX')
            start_time = datetime.utcnow() - timedelta(days=1)
            
            response = ec2_client.describe_spot_price_history(
                InstanceTypes=[instance_type],
                ProductDescriptions=[spot_product],
                StartTime=start_time,
                MaxResults=100
            )
            
            if response['SpotPriceHistory']:
                spot_prices = [float(item['SpotPrice']) for item in response['SpotPriceHistory']]
                prices['spot'] = sum(spot_prices) / len(spot_prices)
        except Exception as e:
            print(f"  Warning: Spot price failed for {instance_type}: {e}")
    
    return prices

def get_lambda_info(region, config):
    results = []
    memory_sizes = [128, 256, 512, 1024, 2048, 3072, 4096, 8192, 10240]
    
    for memory in memory_sizes:
        memory_gb = memory / 1024
        if not check_range(memory_gb, config.get('memory_min'), config.get('memory_max')):
            continue
        
        cpu = memory / 1769
        price_per_ms = 0.0000166667 * memory_gb
        
        result = {
            'service': 'Lambda', 'region': region, 'instance_type': f'{memory}MB',
            'cpu': round(cpu, 2), 'memory_gb': memory_gb, 'storage_gb': 512,
            'network_gbps': 'N/A', 'ondemand': price_per_ms * 3600000
        }
        if config.get('public_ip'):
            result['public_ip_count'] = 0
        results.append(result)
    
    return results

@lru_cache(maxsize=32)
def get_dto_price(region):
    try:
        pricing_client = boto3.client('pricing', region_name='us-east-1')
        location = REGION_MAP.get(region, region)
        
        response = pricing_client.get_products(
            ServiceCode='AWSDataTransfer',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'fromLocation', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'transferType', 'Value': 'AWS Outbound'},
                {'Type': 'TERM_MATCH', 'Field': 'toLocation', 'Value': 'External'}
            ],
            MaxResults=1
        )
        
        if response['PriceList']:
            price_data = json.loads(response['PriceList'][0])
            on_demand = list(price_data['terms']['OnDemand'].values())[0]
            dimensions = sorted(on_demand['priceDimensions'].values(), 
                              key=lambda x: float(x.get('beginRange', '0')))
            tiers = [f"{pd.get('beginRange', '0')}-{pd.get('endRange', 'Inf')}GB: ${float(pd['pricePerUnit']['USD'])}/GB"
                    for pd in dimensions]
            return '; '.join(tiers) if tiers else '0'
    except Exception as e:
        print(f"  Warning: DTO price query failed for {region}: {e}")
        return 'N/A'

def query_region(region, config, services):
    print(f"正在查询区域: {region}")
    results = []
    
    if 'lightsail' in services:
        print(f"  - 查询 Lightsail...")
        results.extend(get_lightsail_instances(region, config))
    
    if 'ec2' in services:
        print(f"  - 查询 EC2...")
        results.extend(get_ec2_instances(region, config))
    
    if 'lambda' in services:
        print(f"  - 查询 Lambda...")
        results.extend(get_lambda_info(region, config))
    
    return results

def generate_excel(results, output_file, config):
    wb = Workbook()
    wb.remove(wb.active)
    
    pricing_types = config.get('pricing_types', {'ondemand': True})
    base_headers = ['服务', '实例类型', 'CPU核心数', '内存(GB)', '存储(GB)', '网络性能']
    if config.get('public_ip'):
        base_headers.append('公网IP数量')
    
    price_keys, hourly_headers, monthly_headers = [], [], []
    
    if pricing_types.get('ondemand'):
        price_keys.append('ondemand')
        hourly_headers.append('按需/小时')
        monthly_headers.append('按需/月')
    
    ri_labels = {
        'ri_1y_no_upfront': 'RI-1年NoUp', 'ri_1y_partial_upfront': 'RI-1年PartUp', 'ri_1y_all_upfront': 'RI-1年AllUp',
        'ri_3y_no_upfront': 'RI-3年NoUp', 'ri_3y_partial_upfront': 'RI-3年PartUp', 'ri_3y_all_upfront': 'RI-3年AllUp'
    }
    
    for key, label in ri_labels.items():
        if pricing_types.get(key):
            price_keys.append(key)
            hourly_headers.extend([f'{label}/小时'])
            monthly_headers.extend([f'{label}/月'])
    
    for sp_key, sp_label in [('sp_compute_1y', 'SP-Compute-1年'), ('sp_compute_3y', 'SP-Compute-3年'),
                              ('sp_instance_1y', 'SP-Instance-1年'), ('sp_instance_3y', 'SP-Instance-3年')]:
        if pricing_types.get(sp_key):
            price_keys.append(sp_key)
            hourly_headers.append(f'{sp_label}/小时')
            monthly_headers.append(f'{sp_label}/月')
    
    if pricing_types.get('spot'):
        price_keys.append('spot')
        hourly_headers.extend(['Spot均价/小时'])
        monthly_headers.extend(['Spot均价/月'])
    
    headers = base_headers + hourly_headers + monthly_headers
    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF')
    
    region_results = {}
    for result in results:
        region_results.setdefault(result['region'], []).append(result)
    
    for region, region_data in region_results.items():
        ws = wb.create_sheet(title=region)
        start_row = 1
        
        if config.get('public_ip'):
            ws.cell(row=1, column=1, value=f"DTO价格: {get_dto_price(region)}")
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
            start_row = 3
        
        # 批量写入表头
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=start_row, column=col, value=header)
            cell.fill, cell.font = header_fill, header_font
        
        # 批量写入数据
        for row_idx, result in enumerate(region_data, start_row + 1):
            col = 1
            for field in ['service', 'instance_type', 'cpu', 'memory_gb', 'storage_gb']:
                ws.cell(row=row_idx, column=col, value=result[field])
                col += 1
            ws.cell(row=row_idx, column=col, value=str(result['network_gbps']))
            col += 1
            
            if config.get('public_ip'):
                ws.cell(row=row_idx, column=col, value=result.get('public_ip_count', 0))
                col += 1
            
            hourly_col_start = col
            for price_key in price_keys:
                ws.cell(row=row_idx, column=col, value=result.get(price_key, 0))
                col += 1
            
            for i in range(len(price_keys)):
                col_letter = chr(64 + hourly_col_start + i) if hourly_col_start + i <= 26 else f"A{chr(64 + hourly_col_start + i - 26)}"
                ws.cell(row=row_idx, column=col, value=f"={col_letter}{row_idx}*730")
                col += 1
        
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
    
    # 并发查询多个区域
    all_results = []
    with ThreadPoolExecutor(max_workers=min(len(regions), 5)) as executor:
        futures = {executor.submit(query_region, region, config, services): region for region in regions}
        for future in as_completed(futures):
            try:
                all_results.extend(future.result())
            except Exception as e:
                print(f"区域查询失败: {e}")
    
    output_file = f"aws_instance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    generate_excel(all_results, output_file, config)
    print(f"\n共找到 {len(all_results)} 个符合条件的配置")

if __name__ == '__main__':
    main()
