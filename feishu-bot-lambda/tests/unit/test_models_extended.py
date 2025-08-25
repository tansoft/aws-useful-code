"""
Extended unit tests for data models - edge cases and error conditions
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.shared.models import FeishuMessage, MonitorAlert, BotConfig


class TestFeishuMessageEdgeCases:
    """Test edge cases and error conditions for FeishuMessage"""
    
    def test_from_webhook_missing_fields(self):
        """Test creating FeishuMessage from webhook with missing fields"""
        webhook_data = {
            "header": {},  # Missing app_id
            "event": {
                # Missing required fields
            }
        }
        
        message = FeishuMessage.from_webhook(webhook_data)
        
        # Should handle missing fields gracefully
        assert message.message_id == ""
        assert message.user_id == ""
        assert message.chat_id == ""
        assert message.app_id == ""
        assert message.timestamp == 0
    
    def test_from_webhook_malformed_content(self):
        """Test creating FeishuMessage from webhook with malformed content"""
        webhook_data = {
            "header": {"app_id": "test_app"},
            "event": {
                "msg_timestamp": "1640995200000",
                "sender": {"sender_id": {"user_id": "user_123"}},
                "message": {
                    "message_id": "msg_123",
                    "chat_id": "chat_123",
                    "message_type": "text",
                    "content": "not_a_json_object"  # Should be JSON
                }
            }
        }
        
        message = FeishuMessage.from_webhook(webhook_data)
        
        # Should handle malformed content
        assert message.content == "not_a_json_object"
    
    def test_from_webhook_unknown_message_type(self):
        """Test creating FeishuMessage from webhook with unknown message type"""
        webhook_data = {
            "header": {"app_id": "test_app"},
            "event": {
                "msg_timestamp": "1640995200000",
                "sender": {"sender_id": {"user_id": "user_123"}},
                "message": {
                    "message_id": "msg_123",
                    "chat_id": "chat_123",
                    "message_type": "unknown_type",
                    "content": {"unknown_field": "unknown_value"}
                }
            }
        }
        
        message = FeishuMessage.from_webhook(webhook_data)
        
        # Should handle unknown message type
        assert message.message_type == "unknown_type"
        assert message.content == '{"unknown_field": "unknown_value"}'
    
    def test_from_webhook_empty_mentions(self):
        """Test creating FeishuMessage from webhook with empty mentions"""
        webhook_data = {
            "header": {"app_id": "test_app"},
            "event": {
                "msg_timestamp": "1640995200000",
                "sender": {"sender_id": {"user_id": "user_123"}},
                "message": {
                    "message_id": "msg_123",
                    "chat_id": "chat_123",
                    "message_type": "text",
                    "content": {"text": "Hello"},
                    "mentions": []  # Empty mentions
                }
            }
        }
        
        message = FeishuMessage.from_webhook(webhook_data)
        
        # Should handle empty mentions as None
        assert message.mentions is None
    
    def test_from_webhook_malformed_mentions(self):
        """Test creating FeishuMessage from webhook with malformed mentions"""
        webhook_data = {
            "header": {"app_id": "test_app"},
            "event": {
                "msg_timestamp": "1640995200000",
                "sender": {"sender_id": {"user_id": "user_123"}},
                "message": {
                    "message_id": "msg_123",
                    "chat_id": "chat_123",
                    "message_type": "text",
                    "content": {"text": "Hello"},
                    "mentions": [
                        {"id": {}},  # Missing user_id
                        {"invalid": "structure"},  # Invalid structure
                        {"id": {"user_id": "valid_user"}}  # Valid mention
                    ]
                }
            }
        }
        
        message = FeishuMessage.from_webhook(webhook_data)
        
        # Should extract only valid mentions
        assert message.mentions == ["", "", "valid_user"]
    
    def test_from_json_invalid_json(self):
        """Test creating FeishuMessage from invalid JSON"""
        invalid_json = '{"message_id": "test", "invalid": }'
        
        with pytest.raises(json.JSONDecodeError):
            FeishuMessage.from_json(invalid_json)
    
    def test_to_json_with_unicode(self):
        """Test JSON serialization with Unicode characters"""
        message = FeishuMessage(
            message_id="msg_123",
            user_id="user_456",
            chat_id="chat_789",
            message_type="text",
            content="Hello 世界 🌍",  # Unicode and emoji
            timestamp=1640995200,
            app_id="app_abc"
        )
        
        json_str = message.to_json()
        parsed = json.loads(json_str)
        
        assert parsed['content'] == "Hello 世界 🌍"
    
    def test_message_with_very_long_content(self):
        """Test FeishuMessage with very long content"""
        long_content = "x" * 10000  # 10KB content
        
        message = FeishuMessage(
            message_id="msg_123",
            user_id="user_456",
            chat_id="chat_789",
            message_type="text",
            content=long_content,
            timestamp=1640995200,
            app_id="app_abc"
        )
        
        assert len(message.content) == 10000
        assert message.to_json()  # Should not fail


class TestMonitorAlertEdgeCases:
    """Test edge cases and error conditions for MonitorAlert"""
    
    def test_to_feishu_card_with_empty_metadata(self):
        """Test Feishu card generation with empty metadata"""
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="test_service",
            alert_type="info",
            message="Test alert",
            timestamp=1640995200,
            severity="low",
            metadata={}  # Empty metadata
        )
        
        card = alert.to_feishu_card()
        
        # Should not include metadata section
        elements_text = json.dumps(card["elements"])
        assert "附加信息" not in elements_text
    
    def test_to_feishu_card_with_none_metadata(self):
        """Test Feishu card generation with None metadata"""
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="test_service",
            alert_type="info",
            message="Test alert",
            timestamp=1640995200,
            severity="low",
            metadata=None  # None metadata
        )
        
        # Should handle None metadata gracefully
        card = alert.to_feishu_card()
        assert "elements" in card
    
    def test_to_feishu_card_unknown_severity(self):
        """Test Feishu card generation with unknown severity"""
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="test_service",
            alert_type="error",
            message="Test alert",
            timestamp=1640995200,
            severity="unknown_severity",  # Unknown severity
            metadata={}
        )
        
        card = alert.to_feishu_card()
        
        # Should use default color for unknown severity
        assert card["header"]["template"] == "blue"
    
    def test_to_feishu_card_unknown_alert_type(self):
        """Test Feishu card generation with unknown alert type"""
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="test_service",
            alert_type="unknown_type",  # Unknown alert type
            message="Test alert",
            timestamp=1640995200,
            severity="medium",
            metadata={}
        )
        
        card = alert.to_feishu_card()
        
        # Should use default icon for unknown type
        elements_text = json.dumps(card["elements"])
        assert "🔔" in elements_text
    
    def test_to_feishu_card_with_complex_metadata(self):
        """Test Feishu card generation with complex metadata"""
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="test_service",
            alert_type="error",
            message="Complex alert",
            timestamp=1640995200,
            severity="high",
            metadata={
                "nested_object": {"key": "value"},
                "list_data": [1, 2, 3],
                "unicode_text": "测试数据 🚀",
                "boolean_flag": True,
                "null_value": None
            }
        )
        
        card = alert.to_feishu_card()
        
        # Should handle complex metadata
        elements_text = json.dumps(card["elements"])
        assert "nested_object" in elements_text
        assert "unicode_text" in elements_text
    
    def test_from_json_with_missing_fields(self):
        """Test creating MonitorAlert from JSON with missing fields"""
        incomplete_json = json.dumps({
            "alert_id": "alert_123",
            "service_name": "test_service"
            # Missing required fields
        })
        
        with pytest.raises(TypeError):  # Missing required arguments
            MonitorAlert.from_json(incomplete_json)
    
    def test_alert_with_future_timestamp(self):
        """Test MonitorAlert with future timestamp"""
        future_timestamp = int(datetime.now().timestamp()) + 86400  # 1 day in future
        
        alert = MonitorAlert(
            alert_id="alert_123",
            service_name="test_service",
            alert_type="warning",
            message="Future alert",
            timestamp=future_timestamp,
            severity="medium",
            metadata={}
        )
        
        card = alert.to_feishu_card()
        
        # Should handle future timestamp gracefully
        assert "elements" in card


class TestBotConfigEdgeCases:
    """Test edge cases and error conditions for BotConfig"""
    
    @patch('boto3.client')
    def test_from_parameter_store_partial_parameters(self, mock_boto_client):
        """Test loading from Parameter Store with partial parameters"""
        mock_ssm = MagicMock()
        mock_boto_client.return_value = mock_ssm
        
        # Return only some parameters
        mock_ssm.get_parameters.return_value = {
            'Parameters': [
                {'Name': '/feishu-bot/app_id', 'Value': 'app_123'},
                {'Name': '/feishu-bot/app_secret', 'Value': 'secret_456'},
                # Missing other required parameters
            ]
        }
        
        with pytest.raises(RuntimeError) as exc_info:
            BotConfig.from_parameter_store()
        
        assert "Missing required parameters" in str(exc_info.value)
    
    @patch('boto3.client')
    def test_from_parameter_store_empty_response(self, mock_boto_client):
        """Test loading from Parameter Store with empty response"""
        mock_ssm = MagicMock()
        mock_boto_client.return_value = mock_ssm
        
        # Return empty parameters
        mock_ssm.get_parameters.return_value = {'Parameters': []}
        
        with pytest.raises(RuntimeError) as exc_info:
            BotConfig.from_parameter_store()
        
        assert "Missing required parameters" in str(exc_info.value)
    
    @patch('boto3.client')
    def test_from_parameter_store_network_error(self, mock_boto_client):
        """Test loading from Parameter Store with network error"""
        mock_boto_client.side_effect = Exception("Network connection failed")
        
        with pytest.raises(RuntimeError) as exc_info:
            BotConfig.from_parameter_store()
        
        assert "Failed to load configuration from Parameter Store" in str(exc_info.value)
    
    @patch.dict('os.environ', {
        'FEISHU_APP_ID': '',  # Empty value
        'FEISHU_APP_SECRET': 'secret_456',
        'FEISHU_VERIFICATION_TOKEN': 'token_789',
        'FEISHU_ENCRYPT_KEY': 'key_abc',
        'FEISHU_BOT_NAME': 'TestBot',
        'FEISHU_WEBHOOK_URL': 'https://example.com/webhook'
    })
    def test_from_env_empty_values(self):
        """Test loading from environment with empty values"""
        with pytest.raises(ValueError) as exc_info:
            BotConfig.from_env()
        
        # Empty values should be treated as missing
        assert "Missing required environment variables" in str(exc_info.value)
    
    def test_validate_with_whitespace_only_fields(self):
        """Test validation with whitespace-only fields"""
        config = BotConfig(
            app_id="   ",  # Whitespace only
            app_secret="secret_456",
            verification_token="token_789",
            encrypt_key="key_abc",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        
        assert config.validate() is False
    
    def test_validate_with_non_string_fields(self):
        """Test validation with non-string fields"""
        config = BotConfig(
            app_id=123,  # Non-string value
            app_secret="secret_456",
            verification_token="token_789",
            encrypt_key="key_abc",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        
        assert config.validate() is False
    
    def test_to_dict_with_sensitive_data(self):
        """Test dictionary conversion includes sensitive data"""
        config = BotConfig(
            app_id="app_123",
            app_secret="secret_456",
            verification_token="token_789",
            encrypt_key="key_abc",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        
        result = config.to_dict()
        
        # Should include all fields (including sensitive ones)
        assert result['app_secret'] == "secret_456"
        assert result['encrypt_key'] == "key_abc"
        assert result['verification_token'] == "token_789"
    
    @patch('boto3.client')
    def test_from_parameter_store_custom_region(self, mock_boto_client):
        """Test loading from Parameter Store with custom region"""
        mock_ssm = MagicMock()
        mock_boto_client.return_value = mock_ssm
        
        mock_ssm.get_parameters.return_value = {
            'Parameters': [
                {'Name': '/custom-bot/app_id', 'Value': 'app_123'},
                {'Name': '/custom-bot/app_secret', 'Value': 'secret_456'},
                {'Name': '/custom-bot/verification_token', 'Value': 'token_789'},
                {'Name': '/custom-bot/encrypt_key', 'Value': 'key_abc'},
                {'Name': '/custom-bot/bot_name', 'Value': 'CustomBot'},
                {'Name': '/custom-bot/webhook_url', 'Value': 'https://example.com/webhook'}
            ]
        }
        
        config = BotConfig.from_parameter_store('/custom-bot', 'eu-west-1')
        
        assert config.app_id == "app_123"
        assert config.bot_name == "CustomBot"
        
        # Verify correct region was used
        mock_boto_client.assert_called_once_with('ssm', region_name='eu-west-1')