"""
Integration tests for Feishu client
"""

import json
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from src.shared.feishu_client import FeishuClient, FeishuWebhookValidator
from src.shared.models import BotConfig


class TestFeishuClient:
    """Integration tests for FeishuClient"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.config = BotConfig(
            app_id="test_app_id",
            app_secret="test_app_secret",
            verification_token="test_verification_token",
            encrypt_key="test_encrypt_key",
            bot_name="TestBot",
            webhook_url="https://test.example.com/webhook"
        )
        self.client = FeishuClient(self.config)
    
    def test_client_initialization_valid_config(self):
        """Test client initialization with valid config"""
        assert self.client.config == self.config
        assert self.client.base_url == "https://open.feishu.cn/open-apis"
        assert self.client._access_token is None
        assert self.client._token_expires_at == 0
    
    def test_client_initialization_invalid_config(self):
        """Test client initialization with invalid config"""
        invalid_config = BotConfig(
            app_id="",  # Empty app_id
            app_secret="test_app_secret",
            verification_token="test_verification_token",
            encrypt_key="test_encrypt_key",
            bot_name="TestBot",
            webhook_url="https://test.example.com/webhook"
        )
        
        with pytest.raises(ValueError, match="Invalid bot configuration"):
            FeishuClient(invalid_config)
    
    @patch('requests.post')
    def test_get_access_token_success(self, mock_post):
        """Test successful access token retrieval"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "msg": "success",
            "app_access_token": "test_access_token",
            "expire": 7200
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        token = self.client._get_access_token()
        
        assert token == "test_access_token"
        assert self.client._access_token == "test_access_token"
        assert self.client._token_expires_at > int(time.time())
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
        assert call_args[1]['json']['app_id'] == "test_app_id"
        assert call_args[1]['json']['app_secret'] == "test_app_secret"
    
    @patch('requests.post')
    def test_get_access_token_api_error(self, mock_post):
        """Test access token retrieval with API error"""
        # Mock error response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 99991663,
            "msg": "app not found"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception, match="Failed to get access token"):
            self.client._get_access_token()
    
    @patch('requests.post')
    def test_get_access_token_network_error(self, mock_post):
        """Test access token retrieval with network error"""
        mock_post.side_effect = requests.RequestException("Network error")
        
        with pytest.raises(requests.RequestException):
            self.client._get_access_token()
    
    @patch('requests.post')
    def test_get_access_token_caching(self, mock_post):
        """Test access token caching"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "msg": "success",
            "app_access_token": "test_access_token",
            "expire": 7200
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # First call should make API request
        token1 = self.client._get_access_token()
        assert mock_post.call_count == 1
        
        # Second call should use cached token
        token2 = self.client._get_access_token()
        assert mock_post.call_count == 1  # No additional API call
        assert token1 == token2
    
    def test_verify_webhook_signature_valid(self):
        """Test webhook signature verification with valid signature"""
        timestamp = "1640995200"
        nonce = "test_nonce"
        body = '{"test": "data"}'
        
        # Calculate expected signature
        import hashlib
        string_to_sign = f"{timestamp}{nonce}{self.config.encrypt_key}{body}"
        expected_signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
        
        result = self.client.verify_webhook_signature(timestamp, nonce, body, expected_signature)
        assert result is True
    
    def test_verify_webhook_signature_invalid(self):
        """Test webhook signature verification with invalid signature"""
        timestamp = "1640995200"
        nonce = "test_nonce"
        body = '{"test": "data"}'
        invalid_signature = "invalid_signature"
        
        result = self.client.verify_webhook_signature(timestamp, nonce, body, invalid_signature)
        assert result is False
    
    def test_is_request_fresh_valid(self):
        """Test request freshness check with valid timestamp"""
        current_time = int(time.time())
        timestamp = str(current_time - 100)  # 100 seconds ago
        
        result = self.client.is_request_fresh(timestamp)
        assert result is True
    
    def test_is_request_fresh_expired(self):
        """Test request freshness check with expired timestamp"""
        current_time = int(time.time())
        timestamp = str(current_time - 400)  # 400 seconds ago (> 300 default max_age)
        
        result = self.client.is_request_fresh(timestamp)
        assert result is False
    
    def test_is_request_fresh_invalid_timestamp(self):
        """Test request freshness check with invalid timestamp"""
        invalid_timestamp = "invalid_timestamp"
        
        result = self.client.is_request_fresh(invalid_timestamp)
        assert result is False
    
    @patch('requests.post')
    def test_send_text_message_success(self, mock_post):
        """Test successful text message sending"""
        # Mock access token request
        token_response = Mock()
        token_response.json.return_value = {
            "code": 0,
            "app_access_token": "test_token",
            "expire": 7200
        }
        token_response.raise_for_status.return_value = None
        
        # Mock message sending request
        message_response = Mock()
        message_response.json.return_value = {
            "code": 0,
            "msg": "success",
            "data": {"message_id": "test_message_id"}
        }
        message_response.raise_for_status.return_value = None
        
        mock_post.side_effect = [token_response, message_response]
        
        result = self.client.send_text_message("test_chat_id", "Hello, world!")
        
        assert result["code"] == 0
        assert result["data"]["message_id"] == "test_message_id"
        assert mock_post.call_count == 2
        
        # Verify message API call
        message_call = mock_post.call_args_list[1]
        assert "im/v1/messages" in message_call[0][0]
        assert message_call[1]['headers']['Authorization'] == "Bearer test_token"
        assert message_call[1]['json']['msg_type'] == "text"
    
    @patch('requests.post')
    def test_send_card_message_success(self, mock_post):
        """Test successful card message sending"""
        # Mock access token request
        token_response = Mock()
        token_response.json.return_value = {
            "code": 0,
            "app_access_token": "test_token",
            "expire": 7200
        }
        token_response.raise_for_status.return_value = None
        
        # Mock message sending request
        message_response = Mock()
        message_response.json.return_value = {
            "code": 0,
            "msg": "success",
            "data": {"message_id": "test_message_id"}
        }
        message_response.raise_for_status.return_value = None
        
        mock_post.side_effect = [token_response, message_response]
        
        card = {
            "config": {"wide_screen_mode": True},
            "elements": [{"tag": "div", "text": {"tag": "plain_text", "content": "Test card"}}]
        }
        
        result = self.client.send_card_message("test_chat_id", card)
        
        assert result["code"] == 0
        assert mock_post.call_count == 2
        
        # Verify message API call
        message_call = mock_post.call_args_list[1]
        assert message_call[1]['json']['msg_type'] == "interactive"
    
    def test_process_webhook_event_url_verification(self):
        """Test processing URL verification webhook event"""
        event_data = {
            "header": {
                "event_type": "url_verification"
            },
            "challenge": "test_challenge_string"
        }
        
        result = self.client.process_webhook_event(event_data)
        
        assert result is not None
        assert result["challenge"] == "test_challenge_string"
    
    @patch.object(FeishuClient, 'send_text_message')
    def test_process_webhook_event_message_receive(self, mock_send):
        """Test processing message receive webhook event"""
        event_data = {
            "header": {
                "event_type": "im.message.receive_v1"
            },
            "event": {
                "sender": {
                    "sender_type": "user",
                    "sender_id": {"user_id": "test_user"}
                },
                "message": {
                    "chat_id": "test_chat_id",
                    "message_type": "text",
                    "content": '{"text": "Hello bot"}'
                }
            }
        }
        
        mock_send.return_value = {"code": 0}
        
        result = self.client.process_webhook_event(event_data)
        
        # Should send a reply
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == "test_chat_id"
        assert "Hello bot" in call_args[0][1]
    
    def test_process_webhook_event_bot_message(self):
        """Test processing message from bot (should be ignored)"""
        event_data = {
            "header": {
                "event_type": "im.message.receive_v1"
            },
            "event": {
                "sender": {
                    "sender_type": "app"  # Message from bot
                },
                "message": {
                    "chat_id": "test_chat_id",
                    "message_type": "text",
                    "content": '{"text": "Bot message"}'
                }
            }
        }
        
        result = self.client.process_webhook_event(event_data)
        
        # Should return None (ignore bot messages)
        assert result is None
    
    def test_process_webhook_event_unknown_type(self):
        """Test processing unknown webhook event type"""
        event_data = {
            "header": {
                "event_type": "unknown.event.type"
            }
        }
        
        result = self.client.process_webhook_event(event_data)
        
        # Should return None for unknown events
        assert result is None


class TestFeishuWebhookValidator:
    """Tests for FeishuWebhookValidator"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.validator = FeishuWebhookValidator("test_encrypt_key")
    
    def test_validate_request_success(self):
        """Test successful request validation"""
        timestamp = str(int(time.time()))
        nonce = "test_nonce"
        body = '{"test": "data"}'
        
        # Calculate signature
        import hashlib
        string_to_sign = f"{timestamp}{nonce}test_encrypt_key{body}"
        signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
        
        headers = {
            "x-lark-request-timestamp": timestamp,
            "x-lark-request-nonce": nonce,
            "x-lark-signature": signature
        }
        
        result = self.validator.validate_request(headers, body)
        assert result is True
    
    def test_validate_request_missing_headers(self):
        """Test request validation with missing headers"""
        headers = {
            "x-lark-request-timestamp": str(int(time.time())),
            # Missing nonce and signature
        }
        body = '{"test": "data"}'
        
        result = self.validator.validate_request(headers, body)
        assert result is False
    
    def test_validate_request_expired_timestamp(self):
        """Test request validation with expired timestamp"""
        old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago
        nonce = "test_nonce"
        body = '{"test": "data"}'
        
        # Calculate signature (even though timestamp is old)
        import hashlib
        string_to_sign = f"{old_timestamp}{nonce}test_encrypt_key{body}"
        signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
        
        headers = {
            "x-lark-request-timestamp": old_timestamp,
            "x-lark-request-nonce": nonce,
            "x-lark-signature": signature
        }
        
        result = self.validator.validate_request(headers, body)
        assert result is False
    
    def test_validate_request_invalid_signature(self):
        """Test request validation with invalid signature"""
        timestamp = str(int(time.time()))
        nonce = "test_nonce"
        body = '{"test": "data"}'
        
        headers = {
            "x-lark-request-timestamp": timestamp,
            "x-lark-request-nonce": nonce,
            "x-lark-signature": "invalid_signature"
        }
        
        result = self.validator.validate_request(headers, body)
        assert result is False