"""
Utility functions for Feishu Bot System
Contains helper functions for common operations
"""

import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional


def verify_feishu_signature(timestamp: str, nonce: str, encrypt_key: str, 
                           body: str, signature: str) -> bool:
    """
    验证飞书webhook签名
    
    Args:
        timestamp: 时间戳
        nonce: 随机数
        encrypt_key: 加密密钥
        body: 请求体
        signature: 签名
        
    Returns:
        bool: 签名验证结果
    """
    # 按照飞书文档要求构造签名字符串
    string_to_sign = f"{timestamp}{nonce}{encrypt_key}{body}"
    
    # 使用SHA256计算签名
    expected_signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
    
    # 比较签名
    return hmac.compare_digest(signature, expected_signature)


def format_timestamp(timestamp: int, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化时间戳
    
    Args:
        timestamp: Unix时间戳
        format_str: 格式化字符串
        
    Returns:
        str: 格式化后的时间字符串
    """
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime(format_str)


def sanitize_log_data(data: Dict[str, Any], 
                     sensitive_keys: Optional[list] = None) -> Dict[str, Any]:
    """
    清理日志数据，移除敏感信息
    
    Args:
        data: 原始数据
        sensitive_keys: 敏感字段列表
        
    Returns:
        Dict[str, Any]: 清理后的数据
    """
    if sensitive_keys is None:
        sensitive_keys = [
            'app_secret', 'encrypt_key', 'verification_token', 
            'password', 'token', 'key', 'secret'
        ]
    
    def _sanitize_value(key: str, value: Any) -> Any:
        if isinstance(key, str):
            key_lower = key.lower()
            if any(sensitive_key in key_lower for sensitive_key in sensitive_keys):
                return "***REDACTED***"
        
        if isinstance(value, dict):
            return {k: _sanitize_value(k, v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_sanitize_value("", item) for item in value]
        else:
            return value
    
    return {k: _sanitize_value(k, v) for k, v in data.items()}


def create_error_response(error_code: str, error_message: str, 
                         status_code: int = 500) -> Dict[str, Any]:
    """
    创建标准错误响应
    
    Args:
        error_code: 错误代码
        error_message: 错误消息
        status_code: HTTP状态码
        
    Returns:
        Dict[str, Any]: 错误响应
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({
            "error": {
                "code": error_code,
                "message": error_message,
                "timestamp": int(time.time())
            }
        }, ensure_ascii=False)
    }


def create_success_response(data: Any = None, status_code: int = 200) -> Dict[str, Any]:
    """
    创建标准成功响应
    
    Args:
        data: 响应数据
        status_code: HTTP状态码
        
    Returns:
        Dict[str, Any]: 成功响应
    """
    response_body = {
        "success": True,
        "timestamp": int(time.time())
    }
    
    if data is not None:
        response_body["data"] = data
    
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(response_body, ensure_ascii=False)
    }


def extract_headers_from_event(event: Dict[str, Any]) -> Dict[str, str]:
    """
    从API Gateway事件中提取HTTP头
    
    Args:
        event: API Gateway事件对象
        
    Returns:
        Dict[str, str]: HTTP头字典
    """
    headers = {}
    
    # API Gateway v1.0 format
    if 'headers' in event:
        headers.update(event['headers'] or {})
    
    # API Gateway v2.0 format
    if 'multiValueHeaders' in event:
        for key, values in (event['multiValueHeaders'] or {}).items():
            if values:
                headers[key] = values[0]  # 取第一个值
    
    # 标准化头部名称（转换为小写）
    normalized_headers = {}
    for key, value in headers.items():
        if key and value:
            normalized_headers[key.lower()] = str(value)
    
    return normalized_headers


def is_valid_json(json_str: str) -> bool:
    """
    检查字符串是否为有效的JSON
    
    Args:
        json_str: JSON字符串
        
    Returns:
        bool: 是否为有效JSON
    """
    try:
        json.loads(json_str)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """
    带指数退避的重试装饰器
    
    Args:
        func: 要重试的函数
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        
    Returns:
        装饰器函数
    """
    def decorator(*args, **kwargs):
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # 指数退避
                    time.sleep(delay)
                else:
                    break
        
        # 如果所有重试都失败，抛出最后一个异常
        raise last_exception
    
    return decorator