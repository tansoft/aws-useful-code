"""
Unit tests for data models in the Feishu Bot System
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.shared.models import FeishuMessage, MonitorAlert, BotConfig


class TestFeishuMessage:
    """Test cases for FeishuMessage data model"""
    
    def test_feishu_message_creation(self):
        """Test basic FeishuMessage creation"""
        message = FeishuMessage(
            message_id="msg_123",
            user_id="user_456", 
            chat_id="chat_789",
            message_type="text",
            content="Hello, world!",
            timestamp=1640995200,
            app_id="app_abc"
        )
        
        assert message.message_id == "msg_123"
        assert message.user_id == "user_456"
        assert message.chat_id == "chat_789"
        assert message.message_type == "text"
        assert message.content == "Hello, world!"
        assert message.timestamp == 1640995200
        assert message.app_id == "app_abc"
        assert message.mentions is None
    
    def test_feishu_message_with_mentions(self):
        """Test FeishuMessage with mentions"""
        message = FeishuMessage(
            message_id="msg_123",
            user_id="user_456",
            chat_id="chat_789", 
            message_type="text",
            content="Hello @user1 @user2",
            timestamp=1640995200,
            app_id="app_abc",
            mentions=["user1", "user2"]
        )
        
        assert message.mentions == ["user1", "user2"]
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        message = FeishuMessage(
            message_id="msg_123",
            user_id="user_456",
            chat_id="chat_789",
            message_type="text", 
            content="Hello, world!",
            timestamp=1640995200,
            app_id="app_abc"
        )
        
        result = message.to_dict()
        expected = {
            'message_id': 'msg_123',
            'user_id': 'user_456',
            'chat_id': 'chat_789',
            'message_type': 'text',
            'content': 'Hello, world!',
            'timestamp': 1640995200,
            'app_id': 'app_abc',
            'mentions': None
        }
        
        assert result == expected
    
    def test_to_json(self):
        """Test conversion to JSON string"""
        message = FeishuMessage(
            message_id="msg_123",
            user_id="user_456",
            chat_id="chat_789",
            message_type="text",
            content="Hello, world!",
            timestamp=1640995200,
            app_id="app_abc"
        )
        
        json_str = message.to_json()
        parsed = json.loads(json_str)
        
        assert parsed['message_id'] == 'msg_123'
        assert parsed['content'] == 'Hello, world!'
    
    def test_from_webhook_text_message(self):
        """Test creating FeishuMessage from webhook data - text message"""
        webhook_data = {
            "header": {
                "app_id": "app_abc"
            },
            "event": {
                "msg_timestamp": "1640995200000",
                "sender": {
                    "sender_id": {
                        "user_id": "user_456"
                    }
                },
                "message": {
                    "message_id": "msg_123",
                    "chat_id": "chat_789",
                    "message_type": "text",
                    "content": {
                        "text": "Hello, world!"
                    }
                }
            }
        }
        
        message = FeishuMessage.from_webhook(webhook_data)
        
        assert message.message_id == "msg_123"
        assert message.user_id == "user_456"
        assert message.chat_id == "chat_789"
        assert message.message_type == "text"
        assert message.content == "Hello, world!"
        assert message.timestamp == 1640995200000
        assert message.app_id == "app_abc"
    
    def test_from_webhook_image_message(self):
        """Test creating FeishuMessage from webhook data - image message"""
        webhook_data = {
            "header": {
                "app_id": "app_abc"
            },
            "event": {
                "msg_timestamp": "1640995200000",
                "sender": {
                    "sender_id": {
                        "user_id": "user_456"
                    }
                },
                "message": {
                    "message_id": "msg_123",
                    "chat_id": "chat_789",
                    "message_type": "image",
                    "content": {
                        "image_key": "img_key_123"
                    }
                }
            }
        }
        
        message = FeishuMessage.from_webhook(webhook_data)
        
        assert message.message_type == "image"
        assert message.content == "img_key_123"
    
    def test_from_webhook_with_mentions(self):
        """Test creating FeishuMessage from webhook data with mentions"""
        webhook_data = {
            "header": {
                "app_id": "app_abc"
            },
            "event": {
                "msg_timestamp": "1640995200000",
                "sender": {
                    "sender_id": {
                        "user_id": "user_456"
                    }
                },
                "message": {
                    "message_id": "msg_123",
                    "chat_id": "chat_789",
                    "message_type": "text",
                    "content": {
                        "text": "Hello @user1 @user2"
                    },
                    "mentions": [
                        {
                            "id": {
                                "user_id": "user1"
                            }
                        },
                        {
                            "id": {
                                "user_id": "user2"
                            }
                        }
                    ]
                }
            }
        }
        
        message = FeishuMessage.from_webhook(webhook_data)
        
        assert message.mentions == ["user1", "user2"]
    
    def test_from_dict(self):
        """Test creating FeishuMessage from dictionary"""
        data = {
            'message_id': 'msg_123',
            'user_id': 'user_456',
            'chat_id': 'chat_789',
            'message_type': 'text',
            'content': 'Hello, world!',
            'timestamp': 1640995200,
            'app_id': 'app_abc',
            'mentions': None
        }
        
        message = FeishuMessage.from_dict(data)
        
        assert message.message_id == "msg_123"
        assert message.content == "Hello, world!"
    
    def test_from_json(self):
        """Test creating FeishuMessage from JSON string"""
        json_str = json.dumps({
            'message_id': 'msg_123',
            'user_id': 'user_456',
            'chat_id': 'chat_789',
            'message_type': 'text',
            'content': 'Hello, world!',
            'timestamp': 1640995200,
            'app_id': 'app_abc',
            'mentions': None
        })
        
        message = FeishuMessage.from_json(json_str)
        
        assert message.message_id == "msg_123"
        assert message.content == "Hello, world!"


class TestMonitorAlert:
    """Test cases for MonitorAlert data model"""
    
    def test_monitor_alert_creation(self):
        """Test basic MonitorAlert creation"""
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="user-service",
            alert_type="error",
            message="Service is down",
            timestamp=1640995200,
            severity="critical",
            metadata={"region": "us-east-1", "instance": "i-123"}
        )
        
        assert alert.alert_id == "alert_123"
        assert alert.service_name == "user-service"
        assert alert.alert_type == "error"
        assert alert.message == "Service is down"
        assert alert.timestamp == 1640995200
        assert alert.severity == "critical"
        assert alert.metadata == {"region": "us-east-1", "instance": "i-123"}
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="user-service",
            alert_type="error",
            message="Service is down",
            timestamp=1640995200,
            severity="critical",
            metadata={"region": "us-east-1"}
        )
        
        result = alert.to_dict()
        expected = {
            'alert_id': 'alert_123',
            'service_name': 'user-service',
            'alert_type': 'error',
            'message': 'Service is down',
            'timestamp': 1640995200,
            'severity': 'critical',
            'metadata': {'region': 'us-east-1'}
        }
        
        assert result == expected
    
    def test_to_json(self):
        """Test conversion to JSON string"""
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="user-service",
            alert_type="error",
            message="Service is down",
            timestamp=1640995200,
            severity="critical",
            metadata={"region": "us-east-1"}
        )
        
        json_str = alert.to_json()
        parsed = json.loads(json_str)
        
        assert parsed['alert_id'] == 'alert_123'
        assert parsed['service_name'] == 'user-service'
    
    def test_to_feishu_card_critical_error(self):
        """Test conversion to Feishu card format - critical error"""
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="user-service",
            alert_type="error",
            message="Database connection failed",
            timestamp=1640995200,
            severity="critical",
            metadata={"database": "mysql", "host": "db.example.com"}
        )
        
        card = alert.to_feishu_card()
        
        # Check basic structure
        assert "config" in card
        assert "elements" in card
        assert "header" in card
        
        # Check header
        assert card["header"]["template"] == "red"
        assert "alert_123" in card["header"]["title"]["content"]
        
        # Check elements contain expected content
        elements_text = json.dumps(card["elements"])
        assert "user-service" in elements_text
        assert "critical" in elements_text
        assert "error" in elements_text
        assert "Database connection failed" in elements_text
        assert "database" in elements_text
        assert "mysql" in elements_text
    
    def test_to_feishu_card_warning(self):
        """Test conversion to Feishu card format - warning"""
        alert = MonitorAlert(
            alert_id="alert_456",
            service_name="api-gateway",
            alert_type="warning",
            message="High response time detected",
            timestamp=1640995200,
            severity="medium",
            metadata={}
        )
        
        card = alert.to_feishu_card()
        
        # Check warning-specific formatting
        assert card["header"]["template"] == "yellow"
        elements_text = json.dumps(card["elements"], ensure_ascii=False)
        assert "⚠️" in elements_text
        assert "warning" in elements_text
        assert "medium" in elements_text
    
    def test_from_dict(self):
        """Test creating MonitorAlert from dictionary"""
        data = {
            'alert_id': 'alert_123',
            'service_name': 'user-service',
            'alert_type': 'error',
            'message': 'Service is down',
            'timestamp': 1640995200,
            'severity': 'critical',
            'metadata': {'region': 'us-east-1'}
        }
        
        alert = MonitorAlert.from_dict(data)
        
        assert alert.alert_id == "alert_123"
        assert alert.service_name == "user-service"
    
    def test_from_json(self):
        """Test creating MonitorAlert from JSON string"""
        json_str = json.dumps({
            'alert_id': 'alert_123',
            'service_name': 'user-service',
            'alert_type': 'error',
            'message': 'Service is down',
            'timestamp': 1640995200,
            'severity': 'critical',
            'metadata': {'region': 'us-east-1'}
        })
        
        alert = MonitorAlert.from_json(json_str)
        
        assert alert.alert_id == "alert_123"
        assert alert.service_name == "user-service"


class TestBotConfig:
    """Test cases for BotConfig data model"""
    
    def test_bot_config_creation(self):
        """Test basic BotConfig creation"""
        config = BotConfig(
            app_id="app_123",
            app_secret="secret_456",
            verification_token="token_789",
            encrypt_key="key_abc",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        
        assert config.app_id == "app_123"
        assert config.app_secret == "secret_456"
        assert config.verification_token == "token_789"
        assert config.encrypt_key == "key_abc"
        assert config.bot_name == "TestBot"
        assert config.webhook_url == "https://example.com/webhook"
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        config = BotConfig(
            app_id="app_123",
            app_secret="secret_456",
            verification_token="token_789",
            encrypt_key="key_abc",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        
        result = config.to_dict()
        expected = {
            'app_id': 'app_123',
            'app_secret': 'secret_456',
            'verification_token': 'token_789',
            'encrypt_key': 'key_abc',
            'bot_name': 'TestBot',
            'webhook_url': 'https://example.com/webhook'
        }
        
        assert result == expected
    
    @patch('boto3.client')
    def test_from_parameter_store_success(self, mock_boto_client):
        """Test loading configuration from Parameter Store - success case"""
        # Mock SSM client response
        mock_ssm = MagicMock()
        mock_boto_client.return_value = mock_ssm
        
        mock_ssm.get_parameters.return_value = {
            'Parameters': [
                {'Name': '/feishu-bot/app_id', 'Value': 'app_123'},
                {'Name': '/feishu-bot/app_secret', 'Value': 'secret_456'},
                {'Name': '/feishu-bot/verification_token', 'Value': 'token_789'},
                {'Name': '/feishu-bot/encrypt_key', 'Value': 'key_abc'},
                {'Name': '/feishu-bot/bot_name', 'Value': 'TestBot'},
                {'Name': '/feishu-bot/webhook_url', 'Value': 'https://example.com/webhook'}
            ]
        }
        
        config = BotConfig.from_parameter_store()
        
        assert config.app_id == "app_123"
        assert config.app_secret == "secret_456"
        assert config.verification_token == "token_789"
        assert config.encrypt_key == "key_abc"
        assert config.bot_name == "TestBot"
        assert config.webhook_url == "https://example.com/webhook"
        
        # Verify SSM client was called correctly
        mock_boto_client.assert_called_once_with('ssm', region_name='us-east-1')
        mock_ssm.get_parameters.assert_called_once()
    
    @patch('boto3.client')
    def test_from_parameter_store_missing_params(self, mock_boto_client):
        """Test loading configuration from Parameter Store - missing parameters"""
        # Mock SSM client response with missing parameters
        mock_ssm = MagicMock()
        mock_boto_client.return_value = mock_ssm
        
        mock_ssm.get_parameters.return_value = {
            'Parameters': [
                {'Name': '/feishu-bot/app_id', 'Value': 'app_123'},
                {'Name': '/feishu-bot/app_secret', 'Value': 'secret_456'}
                # Missing other required parameters
            ]
        }
        
        with pytest.raises(RuntimeError) as exc_info:
            BotConfig.from_parameter_store()
        
        assert "Failed to load configuration from Parameter Store" in str(exc_info.value)
        assert "Missing required parameters" in str(exc_info.value)
    
    @patch('boto3.client')
    def test_from_parameter_store_boto_error(self, mock_boto_client):
        """Test loading configuration from Parameter Store - boto3 error"""
        # Mock SSM client to raise exception
        mock_ssm = MagicMock()
        mock_boto_client.return_value = mock_ssm
        mock_ssm.get_parameters.side_effect = Exception("AWS Error")
        
        with pytest.raises(RuntimeError) as exc_info:
            BotConfig.from_parameter_store()
        
        assert "Failed to load configuration from Parameter Store" in str(exc_info.value)
    
    @patch.dict('os.environ', {
        'FEISHU_APP_ID': 'app_123',
        'FEISHU_APP_SECRET': 'secret_456',
        'FEISHU_VERIFICATION_TOKEN': 'token_789',
        'FEISHU_ENCRYPT_KEY': 'key_abc',
        'FEISHU_BOT_NAME': 'TestBot',
        'FEISHU_WEBHOOK_URL': 'https://example.com/webhook'
    })
    def test_from_env_success(self):
        """Test loading configuration from environment variables - success case"""
        config = BotConfig.from_env()
        
        assert config.app_id == "app_123"
        assert config.app_secret == "secret_456"
        assert config.verification_token == "token_789"
        assert config.encrypt_key == "key_abc"
        assert config.bot_name == "TestBot"
        assert config.webhook_url == "https://example.com/webhook"
    
    @patch.dict('os.environ', {
        'FEISHU_APP_ID': 'app_123',
        'FEISHU_APP_SECRET': 'secret_456'
        # Missing other required environment variables
    }, clear=True)
    def test_from_env_missing_vars(self):
        """Test loading configuration from environment variables - missing variables"""
        with pytest.raises(ValueError) as exc_info:
            BotConfig.from_env()
        
        assert "Missing required environment variables" in str(exc_info.value)
    
    def test_validate_success(self):
        """Test configuration validation - success case"""
        config = BotConfig(
            app_id="app_123",
            app_secret="secret_456",
            verification_token="token_789",
            encrypt_key="key_abc",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        
        assert config.validate() is True
    
    def test_validate_missing_required_field(self):
        """Test configuration validation - missing required field"""
        config = BotConfig(
            app_id="",  # Empty required field
            app_secret="secret_456",
            verification_token="token_789",
            encrypt_key="key_abc",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        
        assert config.validate() is False
    
    def test_validate_none_field(self):
        """Test configuration validation - None field"""
        config = BotConfig(
            app_id="app_123",
            app_secret=None,  # None required field
            verification_token="token_789",
            encrypt_key="key_abc",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        
        assert config.validate() is False