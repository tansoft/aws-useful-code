"""
CloudFront预热脚本，请先配置config.yaml文件。
python3 prewarm.py
"""

import json
import yaml
import time
from concurrent.futures import ThreadPoolExecutor
import socket
import socket
import functools
import threading
import contextlib
import requests

def load_config():
    with open('config.yaml', 'r') as file:
        return yaml.safe_load(file)

def resolve_pop_ip(pop_domain):
    """Resolve the IP address of a POP domain."""
    try:
        return socket.gethostbyname(pop_domain)
    except socket.gaierror as e:
        print(f'Failed to resolve IP for {pop_domain}: {e}')
        return None

def stream_response(response, chunk_size=262144):  # 256KB chunks
    """Stream response in chunks and return total size.
    Args:
        response: The response object to stream
        chunk_size: Size of each chunk to read
    
    Returns:
        total_size: Total bytes read
    """
    total_size = 0
    chunks_read = 0
    for chunk in response.iter_content(chunk_size=chunk_size):
        if not chunk:
            break
        total_size += len(chunk)
        chunks_read += 1
        # Print progress every 100MB
        if chunks_read % 400 == 0:  # 400 * 256KB = 100MB
            print(f'Progress: Downloaded {total_size/1024/1024:.2f}MB', end='\r')
    print(' ' * 50, end='\r')  # Clear progress line
    return total_size

# 保存原始的getaddrinfo函数
original_getaddrinfo = socket.getaddrinfo

# 创建线程本地存储
thread_local = threading.local()

# 上下文管理器
@contextlib.contextmanager
def custom_ip_mapping(ip_map):
    # 保存旧的映射
    old_ip_map = getattr(thread_local, 'ip_map', {})
    # 设置新的映射
    thread_local.ip_map = ip_map
    try:
        yield
    finally:
        # 恢复旧的映射
        thread_local.ip_map = old_ip_map

# 创建新的getaddrinfo函数
@functools.wraps(original_getaddrinfo)
def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    # 获取当前线程特定的IP映射
    current_thread = threading.current_thread()
    thread_ip_map = getattr(thread_local, 'ip_map', {})
    if host in thread_ip_map:
        target_ip = thread_ip_map[host]
        # print(f'Thread {current_thread.name}: Resolving {host} to custom IP: {target_ip}')
        return original_getaddrinfo(target_ip, port, family, type, proto, flags)
    # 如果没有任何映射，使用原始函数
    return original_getaddrinfo(host, port, family, type, proto, flags)

# 替换socket.getaddrinfo
socket.getaddrinfo = custom_getaddrinfo

def warm(pop, cf_id, file_name, host, encoding, protocol):
    try:
        # First resolve the POP domain IP
        pop_ip = resolve_pop_ip(f'{cf_id}.{pop}.cloudfront.net')
        if not pop_ip:
            raise Exception(f'Failed to resolve IP for {pop}')
        headers = {
            'Host': host,
            'Connection': 'close'  # Ensure connection is closed after request
        }
        if encoding:
            headers['Accept-encoding'] = encoding
        url = f'{protocol}://{host}{file_name}'
        with custom_ip_mapping({host:pop_ip}):
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            # Get content length if available
            content_length = response.headers.get('content-length')
            if content_length:
                content_length = int(content_length)
                print(f'Starting download of {content_length/1024/1024:.2f}MB')

            # Stream the entire response in chunks to avoid memory issues
            bytes_read = stream_response(response)
            
            # If we get here, the request was successful
            resp_headers = response.headers
            x_cache = resp_headers.get('x-cache', 'No X-Cache header')
            content_encoding = resp_headers.get('content-encoding', 'none')
            cf_id = resp_headers.get('x-amz-cf-id', '')
            etag = resp_headers.get('etag', '')
            
            # Prepare size information
            if content_length:
                size_info = f'{bytes_read/1024/1024:.2f}MB/{content_length/1024/1024:.2f}MB'
                if bytes_read < content_length:
                    size_info += ' (Incomplete)'
            else:
                size_info = f'{bytes_read/1024/1024:.2f}MB/unknown'
            
            print(f'SUCCESS: POP:{pop} PROTOCOL:{protocol.upper()} FILE:{url} IP:{pop_ip} '
                  f'ENCODING:{encoding or "(none)"} RECEIVED:{content_encoding} '
                  f'SIZE:{size_info} etag:{etag} cf-id:{cf_id} X-Cache:{x_cache}')

    except Exception as e:
        print(f'FAILED: POP:{pop} FILE:{url} IP:{pop_ip} '
              f'ENCODING:{encoding or "(none)"} REASON:{str(e)}')

def parse_invalidation(cf_id, paths):
    """
    Create a CloudFront invalidation for the specified paths
    Args:
        cf_id: The CloudFron ID part in hostname
        paths: List of paths to invalidate
        
    Returns:
        invalidation_id: The ID of the created invalidation
    """
    import boto3
    cloudfront = boto3.client('cloudfront')
    try:
        # use cf_id to find distribution_id
        distribution_id = None
        next_marker = None
        domain_name = cf_id + '.cloudfront.net'
        while distribution_id == None:
            print(f"Finding distribution with {next_marker} ...")
            params = {}
            if next_marker:
                params['Marker'] = next_marker
            response = cloudfront.list_distributions(**params)
            # 检查是否有分发项目
            distribution_list = response.get('DistributionList', {})
            items = distribution_list.get('Items', [])
            # 搜索匹配的域名
            for distribution in items:
                if distribution.get('DomainName') == domain_name:
                    distribution_id = distribution.get('Id')
                    break
            # 检查是否有更多页
            is_truncated = distribution_list.get('IsTruncated', False)
            if not is_truncated:
                break
            # 获取下一页的标记
            next_marker = distribution_list.get('NextMarker')
            if not next_marker:
                break
        if distribution_id == None:
            print(f"Failed to find distribution ID for {cf_id}")
            return None

        response = cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(paths),
                    'Items': paths
                },
                'CallerReference': str(time.time())
            }
        )
        invalidation_id = response['Invalidation']['Id']
        print(f"Created invalidation with ID: {invalidation_id}")
    except Exception as e:
        print(f"Failed to create invalidation: {e}")
        return None
    # wait for invalidation to complete
    try:
        print(f"Waiting for invalidation {invalidation_id} to complete...")
        while True:
            response = cloudfront.get_invalidation(
                DistributionId=distribution_id,
                Id=invalidation_id
            )
            status = response['Invalidation']['Status']
            if status == 'Completed':
                print(f"Invalidation {invalidation_id} completed successfully")
                break          
            print(f"Invalidation status: {status}. Waiting 5 seconds...")
            time.sleep(5)
    except Exception as e:
        print(f"Error checking invalidation status: {e}")
        return False
    return True

def main():
    # Load configuration
    config = load_config()
    
    # Extract configuration values
    cf_url = config['cloudfront_url']
    host = config['host']
    protocol = config.get('protocol', 'https')  # Default to https if not specified
    files_raw = config['files']
    pops = config['pops']
    encodings = config['encodings']
    invalidation_enabled = config.get('invalidation', False)
    
    # Process files list - handle both string and list formats
    if isinstance(files_raw, str):
        # Split the text block into lines and clean them
        files = [line.strip() for line in files_raw.split('\n') if line.strip() and not line.strip().startswith('#')]
    else:
        # Handle traditional list format for backward compatibility
        files = files_raw
    
    # Get CloudFront ID from URL
    cf_id = cf_url.split('.')[0]
    
    # Create invalidation if enabled
    if invalidation_enabled and files:
        print("Invalidation is enabled. Creating CloudFront invalidation before prewarming...")
        parse_invalidation(cf_id, files)
    
    # Create thread pool
    with ThreadPoolExecutor(100) as executor:
        # For each file that needs to be prewarmed
        for file_name in files:
            print(f"\nStarting to prewarm file: {file_name}")
            # For each encoding
            for encoding in encodings:
                print(f"\nUsing encoding: {encoding or '(none)'}")
                # For each POP point
                for pop in pops:
                    try:
                        task = executor.submit(warm, pop, cf_id, file_name, host, encoding, protocol)
                    except Exception as e:
                        print(e)

    print('All prewarming tasks completed')

if __name__ == "__main__":
    main()
