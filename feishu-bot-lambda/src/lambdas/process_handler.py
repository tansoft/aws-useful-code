"""
消息处理Lambda函数
处理SQS队列中的飞书消息并发送回复
"""

import json
import logging
import os
import time
from typing import Dict, Any, List

from src.shared.models import FeishuMessage, BotConfig
from src.shared.feishu_client import FeishuClient
from src.shared.utils import sanitize_log_data, retry_with_backoff
from src.shared.monitoring import (
    get_structured_logger,
    get_performance_monitor,
    get_metrics_collector,
    monitor_function_performance,
    flush_all_metrics
)

# 配置结构化日志和监控
logger = get_structured_logger('process_handler')
performance_monitor = get_performance_monitor()
metrics = get_metrics_collector()

# 全局变量缓存客户端
_feishu_client = None


@monitor_function_performance('process_handler')
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda入口函数
    处理SQS队列中的消息
    
    Args:
        event: SQS事件对象
        context: Lambda上下文对象
        
    Returns:
        dict: 处理结果
    """
    start_time = time.time()
    request_id = context.aws_request_id if context else 'unknown'
    
    try:
        # 记录处理开始
        records = event.get('Records', [])
        logger.info("Processing SQS batch", 
                   request_id=request_id,
                   function_name='process_handler',
                   metadata={'batch_size': len(records)})
        
        # 记录批处理指标
        metrics.increment_counter('sqs.batch_received', 1.0, {'handler': 'process'})
        metrics.record_histogram('sqs.batch_size', len(records), {'handler': 'process'})
        
        # 获取飞书客户端
        client = _get_feishu_client()
        
        # 处理SQS记录
        results = []
        
        for record in records:
            record_start_time = time.time()
            try:
                result = _process_sqs_record(record, client)
                results.append(result)
                
                # 记录单条消息处理时间
                record_duration = (time.time() - record_start_time) * 1000
                performance_monitor.record_message_processing_metrics(
                    message_type=result.get('message_type', 'unknown'),
                    processing_time_ms=record_duration,
                    success=result.get('status') == 'success'
                )
                
            except Exception as e:
                record_duration = (time.time() - record_start_time) * 1000
                logger.error("Failed to process SQS record", 
                           request_id=request_id,
                           duration_ms=record_duration,
                           error_type=type(e).__name__,
                           metadata={'record_id': record.get('messageId', 'unknown'),
                                   'error': str(e)})
                
                # 记录失败指标
                performance_monitor.record_message_processing_metrics(
                    message_type='unknown',
                    processing_time_ms=record_duration,
                    success=False
                )
                
                # 继续处理其他记录
                results.append({
                    'messageId': record.get('messageId', 'unknown'),
                    'status': 'failed',
                    'error': str(e)
                })
        
        # 统计结果
        successful_count = sum(1 for r in results if r.get('status') == 'success')
        failed_count = len(results) - successful_count
        total_duration = (time.time() - start_time) * 1000
        
        # 记录批处理结果
        logger.info("SQS batch processing completed", 
                   request_id=request_id,
                   duration_ms=total_duration,
                   function_name='process_handler',
                   metadata={
                       'processed': len(results),
                       'successful': successful_count,
                       'failed': failed_count
                   })
        
        # 记录批处理指标
        metrics.increment_counter('sqs.messages_processed', successful_count, 
                                {'handler': 'process', 'status': 'success'})
        metrics.increment_counter('sqs.messages_processed', failed_count, 
                                {'handler': 'process', 'status': 'failed'})
        
        return {
            'statusCode': 200,
            'body': {
                'processed': len(results),
                'successful': successful_count,
                'failed': failed_count,
                'results': results
            }
        }
        
    except Exception as e:
        total_duration = (time.time() - start_time) * 1000
        logger.error("Unexpected error in lambda_handler", 
                    request_id=request_id,
                    duration_ms=total_duration,
                    error_type=type(e).__name__,
                    function_name='process_handler',
                    metadata={'error': str(e)})
        
        metrics.increment_counter('sqs.batch_errors', 1.0, {'handler': 'process'})
        
        return {
            'statusCode': 500,
            'body': {
                'error': 'Internal server error',
                'message': str(e)
            }
        }
    
    finally:
        # 刷新指标缓冲区
        flush_all_metrics()


def _get_feishu_client() -> FeishuClient:
    """
    获取飞书客户端（使用缓存）
    
    Returns:
        FeishuClient: 飞书客户端实例
    """
    global _feishu_client
    
    if _feishu_client is None:
        try:
            # 加载配置
            config = _load_bot_config()
            _feishu_client = FeishuClient(config)
            logger.info("Feishu client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Feishu client: {str(e)}")
            raise
    
    return _feishu_client


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


def _process_sqs_record(record: Dict[str, Any], client: FeishuClient) -> Dict[str, Any]:
    """
    处理单个SQS记录
    
    Args:
        record: SQS记录
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        message_id = record.get('messageId', 'unknown')
        logger.info(f"Processing SQS record: {message_id}")
        
        # 解析消息体
        body = record.get('body', '')
        if not body:
            raise ValueError("Empty message body")
        
        # 解析飞书消息
        feishu_message = FeishuMessage.from_json(body)
        
        # 记录消息信息（清理敏感数据）
        message_dict = feishu_message.to_dict()
        sanitized_message = sanitize_log_data(message_dict)
        logger.info(f"Processing Feishu message: {json.dumps(sanitized_message, ensure_ascii=False)}")
        
        # 处理消息
        response = _handle_feishu_message(feishu_message, client)
        
        return {
            'messageId': message_id,
            'status': 'success',
            'feishuMessageId': feishu_message.message_id,
            'response': response
        }
        
    except Exception as e:
        logger.error(f"Error processing SQS record: {str(e)}")
        raise


def _handle_feishu_message(message: FeishuMessage, client: FeishuClient) -> Dict[str, Any]:
    """
    处理飞书消息
    
    Args:
        message: 飞书消息对象
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        # 根据消息类型处理
        if message.message_type == "text":
            return _handle_text_message(message, client)
        elif message.message_type == "image":
            return _handle_image_message(message, client)
        elif message.message_type == "file":
            return _handle_file_message(message, client)
        else:
            logger.warning(f"Unsupported message type: {message.message_type}")
            return _send_unsupported_message_reply(message, client)
            
    except Exception as e:
        logger.error(f"Error handling Feishu message: {str(e)}")
        raise


def _handle_text_message(message: FeishuMessage, client: FeishuClient) -> Dict[str, Any]:
    """
    处理文本消息
    
    Args:
        message: 飞书消息对象
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        text_content = message.content.strip()
        logger.info(f"Processing text message: {text_content}")
        
        # 简单的消息处理逻辑
        reply_text = _generate_text_reply(text_content, message)
        
        # 发送回复
        response = client.send_text_message(message.chat_id, reply_text)
        
        logger.info(f"Successfully sent text reply to chat {message.chat_id}")
        return {
            'type': 'text_reply',
            'reply_text': reply_text,
            'feishu_response': response
        }
        
    except Exception as e:
        logger.error(f"Error handling text message: {str(e)}")
        raise


def _handle_image_message(message: FeishuMessage, client: FeishuClient) -> Dict[str, Any]:
    """
    处理图片消息
    
    Args:
        message: 飞书消息对象
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        logger.info(f"Processing image message with key: {message.content}")
        
        # 简单回复图片消息
        reply_text = "我收到了您发送的图片！"
        response = client.send_text_message(message.chat_id, reply_text)
        
        logger.info(f"Successfully sent image reply to chat {message.chat_id}")
        return {
            'type': 'image_reply',
            'image_key': message.content,
            'reply_text': reply_text,
            'feishu_response': response
        }
        
    except Exception as e:
        logger.error(f"Error handling image message: {str(e)}")
        raise


def _handle_file_message(message: FeishuMessage, client: FeishuClient) -> Dict[str, Any]:
    """
    处理文件消息
    
    Args:
        message: 飞书消息对象
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        logger.info(f"Processing file message with key: {message.content}")
        
        # 简单回复文件消息
        reply_text = "我收到了您发送的文件！"
        response = client.send_text_message(message.chat_id, reply_text)
        
        logger.info(f"Successfully sent file reply to chat {message.chat_id}")
        return {
            'type': 'file_reply',
            'file_key': message.content,
            'reply_text': reply_text,
            'feishu_response': response
        }
        
    except Exception as e:
        logger.error(f"Error handling file message: {str(e)}")
        raise


def _send_unsupported_message_reply(message: FeishuMessage, client: FeishuClient) -> Dict[str, Any]:
    """
    发送不支持消息类型的回复
    
    Args:
        message: 飞书消息对象
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        reply_text = f"抱歉，我暂时不支持处理 {message.message_type} 类型的消息。"
        response = client.send_text_message(message.chat_id, reply_text)
        
        logger.info(f"Successfully sent unsupported message reply to chat {message.chat_id}")
        return {
            'type': 'unsupported_reply',
            'original_type': message.message_type,
            'reply_text': reply_text,
            'feishu_response': response
        }
        
    except Exception as e:
        logger.error(f"Error sending unsupported message reply: {str(e)}")
        raise


def _generate_text_reply(text_content: str, message: FeishuMessage) -> str:
    """
    生成文本回复内容
    
    Args:
        text_content: 原始文本内容
        message: 飞书消息对象
        
    Returns:
        str: 回复文本
    """
    try:
        # 转换为小写以便匹配
        lower_text = text_content.lower()
        
        # 简单的关键词匹配回复
        if any(keyword in lower_text for keyword in ['你好', 'hello', 'hi', '嗨']):
            return f"你好！很高兴见到你！😊"
        
        elif any(keyword in lower_text for keyword in ['帮助', 'help', '功能']):
            return """我是飞书机器人，可以帮助您：
• 回复您的消息
• 处理图片和文件
• 提供简单的对话交互

如有问题，请随时联系！"""
        
        elif any(keyword in lower_text for keyword in ['时间', 'time', '现在几点']):
            current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            return f"现在时间是：{current_time}"
        
        elif any(keyword in lower_text for keyword in ['谢谢', 'thank', '感谢']):
            return "不客气！很高兴能帮助到您！😊"
        
        elif any(keyword in lower_text for keyword in ['再见', 'bye', 'goodbye']):
            return "再见！期待下次与您交流！👋"
        
        else:
            # 默认回复
            return f"我收到了您的消息：「{text_content}」\n\n如需帮助，请发送「帮助」查看功能介绍。"
            
    except Exception as e:
        logger.error(f"Error generating text reply: {str(e)}")
        return "抱歉，处理您的消息时出现了问题，请稍后再试。"


@retry_with_backoff
def _send_reply_with_retry(client: FeishuClient, chat_id: str, content: str, message_type: str = "text") -> Dict[str, Any]:
    """
    带重试的消息发送
    
    Args:
        client: 飞书客户端
        chat_id: 聊天ID
        content: 消息内容
        message_type: 消息类型
        
    Returns:
        dict: 发送结果
    """
    if message_type == "text":
        return client.send_text_message(chat_id, content)
    else:
        raise ValueError(f"Unsupported message type for retry: {message_type}")


def _extract_mentions(message: FeishuMessage) -> List[str]:
    """
    提取消息中的@用户
    
    Args:
        message: 飞书消息对象
        
    Returns:
        list: 被@的用户ID列表
    """
    return message.mentions or []


def _is_bot_mentioned(message: FeishuMessage, bot_user_id: str = None) -> bool:
    """
    检查机器人是否被@
    
    Args:
        message: 飞书消息对象
        bot_user_id: 机器人用户ID
        
    Returns:
        bool: 是否被@
    """
    if not message.mentions:
        return False
    
    # 如果没有提供机器人用户ID，假设任何@都可能是@机器人
    if not bot_user_id:
        return len(message.mentions) > 0
    
    return bot_user_id in message.mentions


def _get_processing_stats() -> Dict[str, Any]:
    """
    获取处理统计信息
    
    Returns:
        dict: 统计信息
    """
    return {
        'timestamp': int(time.time()),
        'lambda_version': os.getenv('AWS_LAMBDA_FUNCTION_VERSION', 'unknown'),
        'memory_limit': os.getenv('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', 'unknown'),
        'remaining_time': 'unknown'  # 需要从context获取
    }