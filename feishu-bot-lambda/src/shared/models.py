"""
Data models for Feishu Bot System
Contains core data structures for messages, alerts, and configuration
"""

import json
import boto3
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class FeishuMessage:
    """飞书消息数据模型"""
    message_id: str
    user_id: str
    chat_id: str
    message_type: str  # text, image, file, etc.
    content: str
    timestamp: int
    app_id: str
    mentions: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_webhook(cls, webhook_data: Dict[str, Any]) -> 'FeishuMessage':
        """从webhook数据创建消息对象"""
        # 解析飞书webhook数据结构
        event = webhook_data.get('event', {})
        message = event.get('message', {})
        sender = event.get('sender', {})
        
        # 提取消息内容
        content = ""
        message_type = message.get('message_type', 'text')
        
        if message_type == 'text':
            content = message.get('content', {}).get('text', '')
        elif message_type == 'image':
            content = message.get('content', {}).get('image_key', '')
        elif message_type == 'file':
            content = message.get('content', {}).get('file_key', '')
        else:
            content = str(message.get('content', ''))
        
        # 提取mentions信息
        mentions = []
        if 'mentions' in message:
            mentions = [mention.get('id', {}).get('user_id', '') 
                       for mention in message.get('mentions', [])]
        
        return cls(
            message_id=message.get('message_id', ''),
            user_id=sender.get('sender_id', {}).get('user_id', ''),
            chat_id=message.get('chat_id', ''),
            message_type=message_type,
            content=content,
            timestamp=int(event.get('msg_timestamp', 0)),
            app_id=webhook_data.get('header', {}).get('app_id', ''),
            mentions=mentions if mentions else None
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeishuMessage':
        """从字典创建消息对象"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'FeishuMessage':
        """从JSON字符串创建消息对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class MonitorAlert:
    """监控告警数据模型"""
    alert_id: str
    service_name: str
    alert_type: str  # error, warning, info
    message: str
    timestamp: int
    severity: str  # critical, high, medium, low
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def to_feishu_card(self) -> Dict[str, Any]:
        """转换为飞书卡片消息格式"""
        # 根据告警级别设置颜色
        color_map = {
            'critical': 'red',
            'high': 'orange', 
            'medium': 'yellow',
            'low': 'blue'
        }
        
        # 根据告警类型设置图标
        icon_map = {
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        
        # 格式化时间戳
        alert_time = datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        card = {
            "config": {
                "wide_screen_mode": True
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": f"{icon_map.get(self.alert_type, '🔔')} **{self.service_name}服务告警**",
                        "tag": "lark_md"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "content": f"**告警级别:** {self.severity}",
                                "tag": "lark_md"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "content": f"**告警类型:** {self.alert_type}",
                                "tag": "lark_md"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "content": f"**服务名称:** {self.service_name}",
                                "tag": "lark_md"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "content": f"**告警时间:** {alert_time}",
                                "tag": "lark_md"
                            }
                        }
                    ]
                },
                {
                    "tag": "div",
                    "text": {
                        "content": f"**告警详情:**\n{self.message}",
                        "tag": "lark_md"
                    }
                }
            ],
            "header": {
                "template": color_map.get(self.severity, 'blue'),
                "title": {
                    "content": f"系统监控告警 - {self.alert_id}",
                    "tag": "plain_text"
                }
            }
        }
        
        # 添加元数据信息（如果存在）
        if self.metadata:
            metadata_text = "\n".join([f"- **{k}:** {v}" for k, v in self.metadata.items()])
            card["elements"].append({
                "tag": "div",
                "text": {
                    "content": f"**附加信息:**\n{metadata_text}",
                    "tag": "lark_md"
                }
            })
        
        return card
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MonitorAlert':
        """从字典创建告警对象"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MonitorAlert':
        """从JSON字符串创建告警对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class BotConfig:
    """机器人配置模型"""
    app_id: str
    app_secret: str
    verification_token: str
    encrypt_key: str
    bot_name: str
    webhook_url: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_parameter_store(cls, parameter_prefix: str = '/feishu-bot', 
                           region_name: str = 'us-east-1') -> 'BotConfig':
        """从Parameter Store加载配置"""
        ssm_client = boto3.client('ssm', region_name=region_name)
        
        # 定义需要获取的参数
        parameters = {
            'app_id': f'{parameter_prefix}/app_id',
            'app_secret': f'{parameter_prefix}/app_secret',
            'verification_token': f'{parameter_prefix}/verification_token',
            'encrypt_key': f'{parameter_prefix}/encrypt_key',
            'bot_name': f'{parameter_prefix}/bot_name',
            'webhook_url': f'{parameter_prefix}/webhook_url'
        }
        
        # 批量获取参数
        try:
            response = ssm_client.get_parameters(
                Names=list(parameters.values()),
                WithDecryption=True
            )
            
            # 构建参数映射
            param_values = {}
            for param in response['Parameters']:
                # 找到对应的配置键
                for key, param_name in parameters.items():
                    if param['Name'] == param_name:
                        param_values[key] = param['Value']
                        break
            
            # 检查是否所有参数都获取到了
            missing_params = set(parameters.keys()) - set(param_values.keys())
            if missing_params:
                raise ValueError(f"Missing required parameters: {missing_params}")
            
            return cls(**param_values)
            
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration from Parameter Store: {str(e)}")
    
    @classmethod
    def from_env(cls) -> 'BotConfig':
        """从环境变量加载配置"""
        import os
        
        required_vars = {
            'app_id': 'FEISHU_APP_ID',
            'app_secret': 'FEISHU_APP_SECRET', 
            'verification_token': 'FEISHU_VERIFICATION_TOKEN',
            'encrypt_key': 'FEISHU_ENCRYPT_KEY',
            'bot_name': 'FEISHU_BOT_NAME',
            'webhook_url': 'FEISHU_WEBHOOK_URL'
        }
        
        config_values = {}
        missing_vars = []
        
        for key, env_var in required_vars.items():
            value = os.getenv(env_var)
            if value is None:
                missing_vars.append(env_var)
            else:
                config_values[key] = value
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        return cls(**config_values)
    
    def validate(self) -> bool:
        """验证配置的完整性"""
        required_fields = ['app_id', 'app_secret', 'verification_token', 'encrypt_key']
        
        for field in required_fields:
            value = getattr(self, field, None)
            if not value or not isinstance(value, str) or len(value.strip()) == 0:
                return False
        
        return True