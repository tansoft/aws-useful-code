"""
接收Lambda函数
处理API Gateway传入的飞书webhook请求
"""

import json
import logging
import os
import time
import boto3
from typing import Dict, Any

from src.shared.models import FeishuMessage, BotConfig
from src.shared.feishu_client import FeishuWebhookValidator
from src.shared.utils import (
    extract_headers_from_event,
    create_success_response,
    create_error_response,
    sanitize_log_data
)
from src.shared.monitoring import (
    get_structured_logger,
    get_performance_monitor,
    get_metrics_collector,
    monitor_function_performance,
    flush_all_metrics
)

# 配置结构化日志
logger = get_structured_logger('receive_handler')
performance_monitor = get_performance_monitor()
metrics = get_metrics_collector()

# 初始化AWS客户端
sqs_client = boto3.client('sqs')


@monitor_function_performance('receive_handler')
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda入口函数
    处理API Gateway传入的飞书webhook请求
    
    Args:
        event: API Gateway事件对象
        context: Lambda上下文对象
        
    Returns:
        dict: HTTP响应对象
    """
    start_time = time.time()
    request_id = context.aws_request_id if context else 'unknown'
    
    try:
        # 记录请求开始
        logger.info("Processing webhook request", 
                   request_id=request_id,
                   function_name='receive_handler')
        
        # 记录请求指标
        metrics.increment_counter('webhook.requests', 1.0, {'handler': 'receive'})
        
        # 提取HTTP头和请求体
        headers = extract_headers_from_event(event)
        body = event.get('body', '')
        
        # 记录请求大小
        request_size = len(body.encode('utf-8')) if body else 0
        metrics.record_histogram('webhook.request_size', request_size, {'handler': 'receive'})
        
        if not body:
            logger.warning("Empty request body", request_id=request_id)
            metrics.increment_counter('webhook.errors', 1.0, 
                                    {'handler': 'receive', 'error_type': 'empty_body'})
            return create_error_response("EMPTY_BODY", "Request body is empty", 400)
        
        # 验证请求签名
        signature_start = time.time()
        signature_valid = _verify_request_signature(headers, body)
        signature_duration = (time.time() - signature_start) * 1000
        
        performance_monitor.record_timer('signature_verification_duration', 
                                       signature_duration, {'handler': 'receive'})
        
        if not signature_valid:
            logger.warning("Request signature verification failed", 
                          request_id=request_id)
            metrics.increment_counter('webhook.errors', 1.0, 
                                    {'handler': 'receive', 'error_type': 'invalid_signature'})
            return create_error_response("INVALID_SIGNATURE", "Invalid request signature", 401)
        
        # 解析请求体
        try:
            webhook_data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse request body as JSON", 
                        request_id=request_id, 
                        error_type='json_decode_error',
                        metadata={'error': str(e)})
            metrics.increment_counter('webhook.errors', 1.0, 
                                    {'handler': 'receive', 'error_type': 'invalid_json'})
            return create_error_response("INVALID_JSON", "Invalid JSON format", 400)
        
        # 处理webhook事件
        event_processing_start = time.time()
        response_data = _process_webhook_event(webhook_data)
        event_processing_duration = (time.time() - event_processing_start) * 1000
        
        performance_monitor.record_timer('event_processing_duration', 
                                       event_processing_duration, {'handler': 'receive'})
        
        # 记录成功指标
        total_duration = (time.time() - start_time) * 1000
        logger.info("Webhook request processed successfully", 
                   request_id=request_id,
                   duration_ms=total_duration,
                   function_name='receive_handler')
        
        metrics.increment_counter('webhook.success', 1.0, {'handler': 'receive'})
        
        if response_data:
            # 如果有响应数据（如URL验证），直接返回
            return create_success_response(response_data)
        else:
            # 普通消息事件，返回成功响应
            return create_success_response({"message": "Event processed successfully"})
            
    except Exception as e:
        total_duration = (time.time() - start_time) * 1000
        logger.error("Unexpected error in lambda_handler", 
                    request_id=request_id,
                    duration_ms=total_duration,
                    error_type=type(e).__name__,
                    function_name='receive_handler',
                    metadata={'error': str(e)})
        
        metrics.increment_counter('webhook.errors', 1.0, 
                                {'handler': 'receive', 'error_type': 'internal_error'})
        
        return create_error_response("INTERNAL_ERROR", "Internal server error", 500)
    
    finally:
        # 刷新指标缓冲区
        flush_all_metrics()


def _verify_request_signature(headers: Dict[str, str], body: str) -> bool:
    """
    验证请求签名
    
    Args:
        headers: HTTP头
        body: 请求体
        
    Returns:
        bool: 验证结果
    """
    try:
        # 获取加密密钥
        encrypt_key = os.getenv('FEISHU_ENCRYPT_KEY')
        if not encrypt_key:
            logger.error("FEISHU_ENCRYPT_KEY environment variable not set")
            return False
        
        # 创建验证器并验证请求
        validator = FeishuWebhookValidator(encrypt_key)
        return validator.validate_request(headers, body)
        
    except Exception as e:
        logger.error(f"Error during signature verification: {str(e)}")
        return False


def _process_webhook_event(webhook_data: Dict[str, Any]) -> Any:
    """
    处理webhook事件
    
    Args:
        webhook_data: webhook事件数据
        
    Returns:
        Any: 处理结果，如果需要响应的话
    """
    try:
        # 获取事件类型
        header = webhook_data.get("header", {})
        event_type = header.get("event_type")
        
        logger.info(f"Processing webhook event type: {event_type}")
        
        if event_type == "url_verification":
            # URL验证事件
            return _handle_url_verification(webhook_data)
        
        elif event_type == "im.message.receive_v1":
            # 消息接收事件
            return _handle_message_receive(webhook_data)
        
        else:
            logger.warning(f"Unhandled event type: {event_type}")
            return None
            
    except Exception as e:
        logger.error(f"Error processing webhook event: {str(e)}")
        raise


def _handle_url_verification(webhook_data: Dict[str, Any]) -> Dict[str, str]:
    """
    处理URL验证事件
    
    Args:
        webhook_data: webhook事件数据
        
    Returns:
        dict: 验证响应
    """
    challenge = webhook_data.get("challenge", "")
    logger.info(f"Handling URL verification with challenge: {challenge}")
    
    return {"challenge": challenge}


def _handle_message_receive(webhook_data: Dict[str, Any]) -> None:
    """
    处理消息接收事件
    
    Args:
        webhook_data: webhook事件数据
    """
    try:
        # 解析消息数据
        message = FeishuMessage.from_webhook(webhook_data)
        
        # 记录消息信息（清理敏感数据）
        message_dict = message.to_dict()
        sanitized_message = sanitize_log_data(message_dict)
        logger.info(f"Parsed message: {json.dumps(sanitized_message, ensure_ascii=False)}")
        
        # 检查是否是机器人自己发送的消息
        event = webhook_data.get("event", {})
        sender = event.get("sender", {})
        sender_type = sender.get("sender_type")
        
        if sender_type == "app":
            logger.info("Ignoring message from app (bot)")
            return
        
        # 发送消息到SQS队列进行异步处理
        _send_message_to_sqs(message)
        
    except Exception as e:
        logger.error(f"Error handling message receive event: {str(e)}")
        raise


def _send_message_to_sqs(message: FeishuMessage) -> None:
    """
    将消息发送到SQS队列
    
    Args:
        message: 飞书消息对象
    """
    try:
        # 获取SQS队列URL
        queue_url = os.getenv('SQS_QUEUE_URL')
        if not queue_url:
            raise ValueError("SQS_QUEUE_URL environment variable not set")
        
        # 准备消息属性
        message_attributes = {
            'MessageType': {
                'StringValue': 'feishu_message',
                'DataType': 'String'
            },
            'ChatId': {
                'StringValue': message.chat_id,
                'DataType': 'String'
            },
            'UserId': {
                'StringValue': message.user_id,
                'DataType': 'String'
            },
            'AppId': {
                'StringValue': message.app_id,
                'DataType': 'String'
            }
        }
        
        # 发送消息到SQS
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message.to_json(),
            MessageAttributes=message_attributes
        )
        
        message_id = response.get('MessageId')
        logger.info(f"Successfully sent message to SQS: {message_id}")
        
    except Exception as e:
        logger.error(f"Failed to send message to SQS: {str(e)}")
        raise


def _load_bot_config() -> BotConfig:
    """
    加载机器人配置
    
    Returns:
        BotConfig: 机器人配置对象
    """
    try:
        # 尝试从环境变量加载配置
        return BotConfig.from_env()
    except ValueError:
        # 如果环境变量不完整，尝试从Parameter Store加载
        try:
            parameter_prefix = os.getenv('PARAMETER_STORE_PREFIX', '/feishu-bot')
            region = os.getenv('AWS_REGION', 'us-east-1')
            return BotConfig.from_parameter_store(parameter_prefix, region)
        except Exception as e:
            logger.error(f"Failed to load bot configuration: {str(e)}")
            raise


def _create_challenge_response(challenge: str) -> Dict[str, Any]:
    """
    创建URL验证挑战响应
    
    Args:
        challenge: 挑战字符串
        
    Returns:
        dict: API Gateway响应格式
    """
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({"challenge": challenge})
    }


def _validate_webhook_data(webhook_data: Dict[str, Any]) -> bool:
    """
    验证webhook数据格式
    
    Args:
        webhook_data: webhook数据
        
    Returns:
        bool: 是否有效
    """
    try:
        # 检查必需的字段
        if "header" not in webhook_data:
            logger.warning("Missing 'header' field in webhook data")
            return False
        
        header = webhook_data["header"]
        if "event_type" not in header:
            logger.warning("Missing 'event_type' field in header")
            return False
        
        # 对于消息事件，检查event字段
        event_type = header["event_type"]
        if event_type == "im.message.receive_v1":
            if "event" not in webhook_data:
                logger.warning("Missing 'event' field for message event")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating webhook data: {str(e)}")
        return False


def _get_request_info(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取请求信息用于日志记录
    
    Args:
        event: API Gateway事件
        
    Returns:
        dict: 请求信息
    """
    return {
        "method": event.get("httpMethod", "UNKNOWN"),
        "path": event.get("path", "UNKNOWN"),
        "source_ip": event.get("requestContext", {}).get("identity", {}).get("sourceIp", "UNKNOWN"),
        "user_agent": event.get("headers", {}).get("User-Agent", "UNKNOWN"),
        "request_id": event.get("requestContext", {}).get("requestId", "UNKNOWN")
    }