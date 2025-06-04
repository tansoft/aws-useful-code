"""
CloudFront预热脚本，请先配置config.yaml文件。
python3 prewarm.py
"""

import json
import yaml
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import urllib.error
import socket
import ssl

class PopIPHandler:
    def __init__(self, pop_ip):
        self.pop_ip = pop_ip

    def __call__(self, host, port=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (self.pop_ip, port))]

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

def create_ssl_context():
    """Create a default SSL context for HTTPS connections."""
    context = ssl.create_default_context()
    return context

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
    
    while True:
        chunk = response.read(chunk_size)
        if not chunk:
            break
            
        total_size += len(chunk)
        chunks_read += 1
        
        # Print progress every 100MB
        if chunks_read % 400 == 0:  # 400 * 256KB = 100MB
            print(f'Progress: Downloaded {total_size/1024/1024:.2f}MB', end='\r')
    
    print(' ' * 50, end='\r')  # Clear progress line
    return total_size

def warm(pop, cf_id, cf_url, file_name, host, encoding, protocol):
    try:
        # First resolve the POP domain IP
        pop_domain = f'{cf_id}.{pop}.cloudfront.net'
        pop_ip = resolve_pop_ip(pop_domain)
        
        if not pop_ip:
            raise Exception(f'Failed to resolve IP for {pop_domain}')

        try:
            # Prepare headers
            headers = {
                'Host': host,
                'Connection': 'close'  # Ensure connection is closed after request
            }
            if encoding:
                headers['Accept-encoding'] = encoding

            # Create the URL using the proper hostname
            url = f'{protocol}://{host}{file_name}'
            
            # Create request
            req = urllib.request.Request(url=url, headers=headers)
            
            # Create custom opener that uses the POP IP
            handlers = []
            if protocol == 'https':
                context = create_ssl_context()
                handlers.append(urllib.request.HTTPSHandler(context=context))
            
            # Create a custom handler that forces connections to use the POP IP
            opener = urllib.request.build_opener(*handlers)
            opener.handle_error = PopIPHandler(pop_ip)
            
            # Make the request
            response = opener.open(req)
            
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
            
        except (urllib.error.HTTPError, urllib.error.URLError, ssl.SSLError) as e:
            raise
            
    except urllib.error.HTTPError as e:
        print(f'FAILED: POP:{pop} FILE:{url} IP:{pop_ip} ENCODING:{encoding or "(none)"} '
              f'REASON:HTTPError: {e.code}')
    except urllib.error.URLError as e:
        print(f'FAILED: POP:{pop} FILE:{url} IP:{pop_ip} ENCODING:{encoding or "(none)"} '
              f'REASON:URLError: {e.reason}')
    except Exception as e:
        print(f'FAILED: POP:{pop} FILE:{url} IP:{pop_ip if "pop_ip" in locals() else "unknown"} '
              f'ENCODING:{encoding or "(none)"} REASON:{str(e)}')

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
    
    # Process files list - handle both string and list formats
    if isinstance(files_raw, str):
        # Split the text block into lines and clean them
        files = [line.strip() for line in files_raw.split('\n') if line.strip() and not line.strip().startswith('#')]
    else:
        # Handle traditional list format for backward compatibility
        files = files_raw
    
    # Get CloudFront ID from URL
    cf_id = cf_url.split('.')[0]
    
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
                        task = executor.submit(warm, pop, cf_id, cf_url, file_name, host, encoding, protocol)
                    except Exception as e:
                        print(e)

    print('All prewarming tasks completed')

if __name__ == "__main__":
    main()
