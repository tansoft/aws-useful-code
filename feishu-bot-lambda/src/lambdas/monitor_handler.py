"""
监控告警Lambda函数
处理监控系统的告警事件并推送到飞书
"""

import json
import logging
import os
import time
from typing import Dict, Any, List

from src.shared.models import MonitorAlert, BotConfig
from src.shared.feishu_client import FeishuClient
from src.shared.utils import sanitize_log_data, retry_with_backoff

# 配置日志
logger = logging.getLogger()
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# 全局变量缓存客户端
_feishu_client = None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda入口函数
    处理监控告警事件
    
    Args:
        event: 监控事件对象
        context: Lambda上下文对象
        
    Returns:
        dict: 处理结果
    """
    try:
        # 记录事件信息（清理敏感数据）
        sanitized_event = sanitize_log_data(event)
        logger.info(f"Processing monitor event: {json.dumps(sanitized_event, ensure_ascii=False)}")
        
        # 获取飞书客户端
        client = _get_feishu_client()
        
        # 处理不同类型的事件源
        if 'Records' in event:
            # SNS/SQS事件
            return _handle_sns_sqs_event(event, client)
        elif 'source' in event and event['source'] == 'aws.cloudwatch':
            # CloudWatch告警事件
            return _handle_cloudwatch_event(event, client)
        elif 'AlarmName' in event:
            # 直接的CloudWatch告警
            return _handle_direct_alarm_event(event, client)
        else:
            # 自定义监控事件
            return _handle_custom_monitor_event(event, client)
            
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': {
                'error': 'Internal server error',
                'message': str(e)
            }
        }


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


def _handle_sns_sqs_event(event: Dict[str, Any], client: FeishuClient) -> Dict[str, Any]:
    """
    处理SNS/SQS事件
    
    Args:
        event: SNS/SQS事件
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        records = event.get('Records', [])
        results = []
        
        for record in records:
            try:
                result = _process_sns_sqs_record(record, client)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process SNS/SQS record: {str(e)}", exc_info=True)
                results.append({
                    'recordId': record.get('messageId', 'unknown'),
                    'status': 'failed',
                    'error': str(e)
                })
        
        successful_count = sum(1 for r in results if r.get('status') == 'success')
        failed_count = len(results) - successful_count
        
        logger.info(f"Processed {len(results)} SNS/SQS records: {successful_count} successful, {failed_count} failed")
        
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
        logger.error(f"Error handling SNS/SQS event: {str(e)}")
        raise


def _process_sns_sqs_record(record: Dict[str, Any], client: FeishuClient) -> Dict[str, Any]:
    """
    处理单个SNS/SQS记录
    
    Args:
        record: SNS/SQS记录
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        record_id = record.get('messageId', 'unknown')
        logger.info(f"Processing SNS/SQS record: {record_id}")
        
        # 解析消息体
        if 'Sns' in record:
            # SNS消息
            message_body = record['Sns']['Message']
        else:
            # SQS消息
            message_body = record.get('body', '')
        
        if not message_body:
            raise ValueError("Empty message body")
        
        # 尝试解析为JSON
        try:
            alert_data = json.loads(message_body)
        except json.JSONDecodeError:
            # 如果不是JSON，创建简单的告警
            alert_data = {
                'alert_id': f"alert_{int(time.time())}",
                'service_name': 'Unknown Service',
                'alert_type': 'info',
                'message': message_body,
                'timestamp': int(time.time()),
                'severity': 'medium',
                'metadata': {}
            }
        
        # 创建监控告警对象
        alert = MonitorAlert.from_dict(alert_data)
        
        # 发送告警到飞书
        response = _send_alert_to_feishu(alert, client)
        
        return {
            'recordId': record_id,
            'status': 'success',
            'alertId': alert.alert_id,
            'response': response
        }
        
    except Exception as e:
        logger.error(f"Error processing SNS/SQS record: {str(e)}")
        raise


def _handle_cloudwatch_event(event: Dict[str, Any], client: FeishuClient) -> Dict[str, Any]:
    """
    处理CloudWatch事件
    
    Args:
        event: CloudWatch事件
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        logger.info("Processing CloudWatch event")
        
        # 解析CloudWatch事件
        detail = event.get('detail', {})
        alarm_name = detail.get('alarmName', 'Unknown Alarm')
        state = detail.get('state', {})
        new_state = state.get('value', 'UNKNOWN')
        reason = state.get('reason', 'No reason provided')
        
        # 创建告警对象
        alert = MonitorAlert(
            alert_id=f"cw_{alarm_name}_{int(time.time())}",
            service_name=alarm_name,
            alert_type=_map_cloudwatch_state_to_type(new_state),
            message=f"CloudWatch告警: {alarm_name}\n状态: {new_state}\n原因: {reason}",
            timestamp=int(time.time()),
            severity=_map_cloudwatch_state_to_severity(new_state),
            metadata={
                'source': 'cloudwatch',
                'alarm_name': alarm_name,
                'state': new_state,
                'reason': reason,
                'region': event.get('region', 'unknown')
            }
        )
        
        # 发送告警到飞书
        response = _send_alert_to_feishu(alert, client)
        
        return {
            'statusCode': 200,
            'body': {
                'alertId': alert.alert_id,
                'alarmName': alarm_name,
                'state': new_state,
                'response': response
            }
        }
        
    except Exception as e:
        logger.error(f"Error handling CloudWatch event: {str(e)}")
        raise


def _handle_direct_alarm_event(event: Dict[str, Any], client: FeishuClient) -> Dict[str, Any]:
    """
    处理直接的告警事件
    
    Args:
        event: 告警事件
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        logger.info("Processing direct alarm event")
        
        # 直接从事件创建告警对象
        alert = MonitorAlert(
            alert_id=event.get('AlarmName', f"alarm_{int(time.time())}"),
            service_name=event.get('AlarmName', 'Unknown Service'),
            alert_type=_map_alarm_state_to_type(event.get('NewStateValue', 'UNKNOWN')),
            message=event.get('NewStateReason', 'No reason provided'),
            timestamp=int(time.time()),
            severity=_map_alarm_state_to_severity(event.get('NewStateValue', 'UNKNOWN')),
            metadata={
                'source': 'direct_alarm',
                'old_state': event.get('OldStateValue', 'unknown'),
                'new_state': event.get('NewStateValue', 'unknown'),
                'region': event.get('Region', 'unknown')
            }
        )
        
        # 发送告警到飞书
        response = _send_alert_to_feishu(alert, client)
        
        return {
            'statusCode': 200,
            'body': {
                'alertId': alert.alert_id,
                'alarmName': event.get('AlarmName'),
                'response': response
            }
        }
        
    except Exception as e:
        logger.error(f"Error handling direct alarm event: {str(e)}")
        raise


def _handle_custom_monitor_event(event: Dict[str, Any], client: FeishuClient) -> Dict[str, Any]:
    """
    处理自定义监控事件
    
    Args:
        event: 自定义监控事件
        client: 飞书客户端
        
    Returns:
        dict: 处理结果
    """
    try:
        logger.info("Processing custom monitor event")
        
        # 尝试从事件中提取告警信息
        alert_data = {
            'alert_id': event.get('alert_id', f"custom_{int(time.time())}"),
            'service_name': event.get('service_name', 'Custom Service'),
            'alert_type': event.get('alert_type', 'info'),
            'message': event.get('message', 'Custom monitoring alert'),
            'timestamp': event.get('timestamp', int(time.time())),
            'severity': event.get('severity', 'medium'),
            'metadata': event.get('metadata', {})
        }
        
        # 创建告警对象
        alert = MonitorAlert.from_dict(alert_data)
        
        # 发送告警到飞书
        response = _send_alert_to_feishu(alert, client)
        
        return {
            'statusCode': 200,
            'body': {
                'alertId': alert.alert_id,
                'serviceName': alert.service_name,
                'response': response
            }
        }
        
    except Exception as e:
        logger.error(f"Error handling custom monitor event: {str(e)}")
        raise


@retry_with_backoff
def _send_alert_to_feishu(alert: MonitorAlert, client: FeishuClient) -> Dict[str, Any]:
    """
    发送告警到飞书
    
    Args:
        alert: 监控告警对象
        client: 飞书客户端
        
    Returns:
        dict: 发送结果
    """
    try:
        # 获取目标聊天ID
        target_chat_ids = _get_alert_target_chats(alert)
        
        if not target_chat_ids:
            logger.warning("No target chat IDs configured for alerts")
            return {'status': 'skipped', 'reason': 'no_target_chats'}
        
        # 生成告警卡片
        card = alert.to_feishu_card()
        
        # 发送到所有目标聊天
        results = []
        for chat_id in target_chat_ids:
            try:
                response = client.send_card_message(chat_id, card)
                results.append({
                    'chat_id': chat_id,
                    'status': 'success',
                    'response': response
                })
                logger.info(f"Successfully sent alert to chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send alert to chat {chat_id}: {str(e)}")
                results.append({
                    'chat_id': chat_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return {
            'status': 'completed',
            'alert_id': alert.alert_id,
            'targets': len(target_chat_ids),
            'successful': sum(1 for r in results if r['status'] == 'success'),
            'failed': sum(1 for r in results if r['status'] == 'failed'),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error sending alert to Feishu: {str(e)}")
        raise


def _get_alert_target_chats(alert: MonitorAlert) -> List[str]:
    """
    获取告警目标聊天ID列表
    
    Args:
        alert: 监控告警对象
        
    Returns:
        list: 聊天ID列表
    """
    try:
        # 从环境变量获取默认目标聊天
        default_chats = os.getenv('FEISHU_ALERT_CHAT_IDS', '')
        if default_chats:
            chat_ids = [chat_id.strip() for chat_id in default_chats.split(',') if chat_id.strip()]
        else:
            chat_ids = []
        
        # 根据告警严重程度添加特定聊天
        if alert.severity == 'critical':
            critical_chats = os.getenv('FEISHU_CRITICAL_ALERT_CHAT_IDS', '')
            if critical_chats:
                critical_chat_ids = [chat_id.strip() for chat_id in critical_chats.split(',') if chat_id.strip()]
                chat_ids.extend(critical_chat_ids)
        
        # 根据服务名称添加特定聊天
        service_chat_env = f"FEISHU_ALERT_CHAT_{alert.service_name.upper().replace('-', '_')}"
        service_chats = os.getenv(service_chat_env, '')
        if service_chats:
            service_chat_ids = [chat_id.strip() for chat_id in service_chats.split(',') if chat_id.strip()]
            chat_ids.extend(service_chat_ids)
        
        # 去重并返回
        return list(set(chat_ids))
        
    except Exception as e:
        logger.error(f"Error getting alert target chats: {str(e)}")
        return []


def _map_cloudwatch_state_to_type(state: str) -> str:
    """
    将CloudWatch状态映射到告警类型
    
    Args:
        state: CloudWatch状态
        
    Returns:
        str: 告警类型
    """
    state_mapping = {
        'ALARM': 'error',
        'OK': 'info',
        'INSUFFICIENT_DATA': 'warning'
    }
    return state_mapping.get(state, 'info')


def _map_cloudwatch_state_to_severity(state: str) -> str:
    """
    将CloudWatch状态映射到严重程度
    
    Args:
        state: CloudWatch状态
        
    Returns:
        str: 严重程度
    """
    severity_mapping = {
        'ALARM': 'high',
        'OK': 'low',
        'INSUFFICIENT_DATA': 'medium'
    }
    return severity_mapping.get(state, 'medium')


def _map_alarm_state_to_type(state: str) -> str:
    """
    将告警状态映射到告警类型
    
    Args:
        state: 告警状态
        
    Returns:
        str: 告警类型
    """
    return _map_cloudwatch_state_to_type(state)


def _map_alarm_state_to_severity(state: str) -> str:
    """
    将告警状态映射到严重程度
    
    Args:
        state: 告警状态
        
    Returns:
        str: 严重程度
    """
    return _map_cloudwatch_state_to_severity(state)


def _should_send_alert(alert: MonitorAlert) -> bool:
    """
    判断是否应该发送告警
    
    Args:
        alert: 监控告警对象
        
    Returns:
        bool: 是否发送
    """
    try:
        # 检查告警级别过滤
        min_severity = os.getenv('FEISHU_MIN_ALERT_SEVERITY', 'low')
        severity_levels = ['low', 'medium', 'high', 'critical']
        
        if alert.severity not in severity_levels:
            return True  # 未知级别默认发送
        
        min_level_index = severity_levels.index(min_severity)
        alert_level_index = severity_levels.index(alert.severity)
        
        if alert_level_index < min_level_index:
            logger.info(f"Alert severity {alert.severity} below minimum {min_severity}, skipping")
            return False
        
        # 检查服务过滤
        excluded_services = os.getenv('FEISHU_EXCLUDED_SERVICES', '')
        if excluded_services:
            excluded_list = [service.strip() for service in excluded_services.split(',')]
            if alert.service_name in excluded_list:
                logger.info(f"Service {alert.service_name} is excluded, skipping alert")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking if alert should be sent: {str(e)}")
        return True  # 出错时默认发送


def _format_alert_summary(alert: MonitorAlert) -> str:
    """
    格式化告警摘要
    
    Args:
        alert: 监控告警对象
        
    Returns:
        str: 告警摘要
    """
    try:
        severity_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        
        type_emoji = {
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        
        emoji = severity_emoji.get(alert.severity, '🔔')
        type_icon = type_emoji.get(alert.alert_type, '📢')
        
        return f"{emoji} {type_icon} {alert.service_name} - {alert.alert_type.upper()}"
        
    except Exception as e:
        logger.error(f"Error formatting alert summary: {str(e)}")
        return f"Alert: {alert.service_name}"