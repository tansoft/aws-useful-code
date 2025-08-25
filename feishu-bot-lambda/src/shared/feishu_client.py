"""
飞书API客户端
基于飞书官方文档实现的轻量级客户端，减少第三方依赖
"""

import json
import time
import hashlib
import hmac
import logging
from typing import Dict, Any, Optional
import requests
from src.shared.models import BotConfig
from src.shared.utils import sanitize_log_data, retry_with_backoff

logger = logging.getLogger(__name__)


class FeishuClient:
    """飞书API客户端"""
    
    def __init__(self, config: BotConfig):
        """
        初始化飞书客户端
        
        Args:
            config: 机器人配置
        """
        self.config = config
        self.base_url = "https://open.feishu.cn/open-apis"
        self._access_token = None
        self._token_expires_at = 0
        
        # 验证配置
        if not config.validate():
            raise ValueError("Invalid bot configuration")
    
    def _get_access_token(self) -> str:
        """
        获取访问令牌
        
        Returns:
            str: 访问令牌
        """
        # 检查token是否过期
        current_time = int(time.time())
        if self._access_token and current_time < self._token_expires_at:
            return self._access_token
        
        # 获取新的access token
        url = f"{self.base_url}/auth/v3/app_access_token/internal"
        payload = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"Failed to get access token: {data.get('msg')}")
            
            self._access_token = data["app_access_token"]
            # 提前5分钟过期，确保token有效性
            self._token_expires_at = current_time + data["expire"] - 300
            
            logger.info("Successfully obtained access token")
            return self._access_token
            
        except Exception as e:
            logger.error(f"Failed to get access token: {str(e)}")
            raise
    
    def verify_webhook_signature(self, timestamp: str, nonce: str, 
                                body: str, signature: str) -> bool:
        """
        验证webhook签名
        
        Args:
            timestamp: 时间戳
            nonce: 随机数
            body: 请求体
            signature: 签名
            
        Returns:
            bool: 验证结果
        """
        try:
            # 构造签名字符串
            string_to_sign = f"{timestamp}{nonce}{self.config.encrypt_key}{body}"
            
            # 计算SHA256签名
            expected_signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
            
            # 比较签名
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False
    
    def is_request_fresh(self, timestamp: str, max_age: int = 300) -> bool:
        """
        检查请求是否在有效时间内
        
        Args:
            timestamp: 请求时间戳
            max_age: 最大允许时间差（秒）
            
        Returns:
            bool: 是否有效
        """
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            return abs(current_time - request_time) <= max_age
        except (ValueError, TypeError):
            return False
    
    @retry_with_backoff
    def send_text_message(self, chat_id: str, text: str) -> Dict[str, Any]:
        """
        发送文本消息
        
        Args:
            chat_id: 聊天ID
            text: 消息文本
            
        Returns:
            dict: API响应
        """
        url = f"{self.base_url}/im/v1/messages"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False)
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"Failed to send message: {data.get('msg')}")
            
            logger.info(f"Successfully sent text message to chat {chat_id}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to send text message: {str(e)}")
            raise
    
    @retry_with_backoff
    def send_card_message(self, chat_id: str, card: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送卡片消息
        
        Args:
            chat_id: 聊天ID
            card: 卡片内容
            
        Returns:
            dict: API响应
        """
        url = f"{self.base_url}/im/v1/messages"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False)
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"Failed to send card message: {data.get('msg')}")
            
            logger.info(f"Successfully sent card message to chat {chat_id}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to send card message: {str(e)}")
            raise
    
    @retry_with_backoff
    def reply_to_message(self, message_id: str, text: str) -> Dict[str, Any]:
        """
        回复消息
        
        Args:
            message_id: 原消息ID
            text: 回复文本
            
        Returns:
            dict: API响应
        """
        url = f"{self.base_url}/im/v1/messages/{message_id}/reply"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False)
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"Failed to reply to message: {data.get('msg')}")
            
            logger.info(f"Successfully replied to message {message_id}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to reply to message: {str(e)}")
            raise
    
    @retry_with_backoff
    def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """
        获取群聊信息
        
        Args:
            chat_id: 聊天ID
            
        Returns:
            dict: 群聊信息
        """
        url = f"{self.base_url}/im/v1/chats/{chat_id}"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"Failed to get chat info: {data.get('msg')}")
            
            logger.info(f"Successfully retrieved chat info for {chat_id}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get chat info: {str(e)}")
            raise
    
    def process_webhook_event(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理webhook事件
        
        Args:
            event_data: webhook事件数据
            
        Returns:
            dict: 处理结果，如果需要响应的话
        """
        try:
            # 记录事件（清理敏感信息）
            sanitized_event = sanitize_log_data(event_data)
            logger.info(f"Processing webhook event: {json.dumps(sanitized_event, ensure_ascii=False)}")
            
            # 获取事件类型
            event_type = event_data.get("header", {}).get("event_type")
            
            if event_type == "url_verification":
                # URL验证事件
                challenge = event_data.get("challenge", "")
                logger.info("Responding to URL verification challenge")
                return {"challenge": challenge}
            
            elif event_type == "im.message.receive_v1":
                # 消息接收事件
                logger.info("Received message event")
                return self._handle_message_event(event_data)
            
            else:
                logger.warning(f"Unhandled event type: {event_type}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to process webhook event: {str(e)}")
            raise
    
    def _handle_message_event(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理消息事件
        
        Args:
            event_data: 消息事件数据
            
        Returns:
            dict: 处理结果
        """
        try:
            event = event_data.get("event", {})
            message = event.get("message", {})
            
            # 忽略机器人自己发送的消息
            sender = event.get("sender", {})
            sender_type = sender.get("sender_type")
            if sender_type == "app":
                logger.info("Ignoring message from app (bot)")
                return None
            
            # 提取消息信息
            chat_id = message.get("chat_id")
            message_type = message.get("message_type")
            
            if message_type == "text":
                content = json.loads(message.get("content", "{}"))
                text = content.get("text", "")
                
                logger.info(f"Received text message: {text}")
                
                # 简单的回复逻辑（可以在后续任务中扩展）
                if text.strip():
                    reply_text = f"收到您的消息：{text}"
                    self.send_text_message(chat_id, reply_text)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to handle message event: {str(e)}")
            raise


class FeishuWebhookValidator:
    """飞书Webhook验证器"""
    
    def __init__(self, encrypt_key: str):
        """
        初始化验证器
        
        Args:
            encrypt_key: 加密密钥
        """
        self.encrypt_key = encrypt_key
    
    def validate_request(self, headers: Dict[str, str], body: str) -> bool:
        """
        验证webhook请求
        
        Args:
            headers: HTTP头
            body: 请求体
            
        Returns:
            bool: 验证结果
        """
        try:
            # 提取验证所需的头部信息
            timestamp = headers.get("x-lark-request-timestamp", "")
            nonce = headers.get("x-lark-request-nonce", "")
            signature = headers.get("x-lark-signature", "")
            
            if not all([timestamp, nonce, signature]):
                logger.warning("Missing required headers for signature verification")
                return False
            
            # 检查请求时效性
            if not self._is_request_fresh(timestamp):
                logger.warning("Request timestamp is too old")
                return False
            
            # 验证签名
            if not self._verify_signature(timestamp, nonce, body, signature):
                logger.warning("Signature verification failed")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request validation failed: {str(e)}")
            return False
    
    def _verify_signature(self, timestamp: str, nonce: str, 
                         body: str, signature: str) -> bool:
        """
        验证签名
        
        Args:
            timestamp: 时间戳
            nonce: 随机数
            body: 请求体
            signature: 签名
            
        Returns:
            bool: 验证结果
        """
        try:
            # 构造签名字符串
            string_to_sign = f"{timestamp}{nonce}{self.encrypt_key}{body}"
            
            # 计算SHA256签名
            expected_signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
            
            # 比较签名
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Signature verification error: {str(e)}")
            return False
    
    def _is_request_fresh(self, timestamp: str, max_age: int = 300) -> bool:
        """
        检查请求时效性
        
        Args:
            timestamp: 请求时间戳
            max_age: 最大允许时间差（秒）
            
        Returns:
            bool: 是否有效
        """
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            return abs(current_time - request_time) <= max_age
        except (ValueError, TypeError):
            return False