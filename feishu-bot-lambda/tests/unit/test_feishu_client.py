"""
Unit tests for FeishuClient and related classes
"""

import json
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from src.shared.feishu_client import FeishuClient, FeishuWebhookValidator
from src.shared.models import BotConfig


class TestFeishuClient:
    """Test cases for FeishuClient class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = BotConfig(
            app_id="test_app_id",
            app_secret="test_app_secret",
            verification_token="test_token",
            encrypt_key="test_encrypt_key",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        self.client = FeishuClient(self.config)
    
    def test_feishu_client_initialization(self):
        """Test FeishuClient initialization"""
        assert self.client.config == self.config
        assert self.client.base_url == "https://open.feishu.cn/open-apis"
        assert self.client._access_token is None
        assert self.client._token_expires_at == 0
    
    def test_feishu_client_invalid_config(self):
        """Test FeishuClient initialization with invalid config"""
        invalid_config = BotConfig(
            app_id="",  # Empty app_id
            app_secret="test_secret",
            verification_token="test_token",
            encrypt_key="test_key",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
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
            "app_access_token": "test_access_token",
            "expire": 7200
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Mock time to control expiration calculation
        with patch('time.time', return_value=1000):
            token = self.client._get_access_token()
        
        assert token == "test_access_token"
        assert self.client._access_token == "test_access_token"
        assert self.client._token_expires_at == 6900  # 1000 + 7200 - 300
        
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
    
    @patch('time.time')
    @patch('requests.post')
    def test_get_access_token_caching(self, mock_post, mock_time):
        """Test access token caching behavior"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "app_access_token": "test_access_token",
            "expire": 7200
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # First call - should fetch token
        mock_time.return_value = 1000
        token1 = self.client._get_access_token()
        
        # Second call within expiration - should use cached token
        mock_time.return_value = 2000  # Still within expiration
        token2 = self.client._get_access_token()
        
        assert token1 == token2 == "test_access_token"
        assert mock_post.call_count == 1  # Only called once
        
        # Third call after expiration - should fetch new token
        mock_time.return_value = 8000  # After expiration
        token3 = self.client._get_access_token()
        
        assert token3 == "test_access_token"
        assert mock_post.call_count == 2  # Called again
    
    def test_verify_webhook_signature_valid(self):
        """Test webhook signature verification with valid signature"""
        timestamp = "1640995200"
        nonce = "test_nonce"
        body = '{"test": "data"}'
        
        # Calculate correct signature
        import hashlib
        string_to_sign = f"{timestamp}{nonce}{self.config.encrypt_key}{body}"
        signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
        
        result = self.client.verify_webhook_signature(timestamp, nonce, body, signature)
        assert result is True
    
    def test_verify_webhook_signature_invalid(self):
        """Test webhook signature verification with invalid signature"""
        timestamp = "1640995200"
        nonce = "test_nonce"
        body = '{"test": "data"}'
        signature = "invalid_signature"
        
        result = self.client.verify_webhook_signature(timestamp, nonce, body, signature)
        assert result is False
    
    def test_verify_webhook_signature_exception(self):
        """Test webhook signature verification with exception"""
        # Pass None values to trigger exception
        result = self.client.verify_webhook_signature(None, None, None, None)
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
        timestamp = str(current_time - 400)  # 400 seconds ago (> 300 default)
        
        result = self.client.is_request_fresh(timestamp)
        assert result is False
    
    def test_is_request_fresh_invalid_timestamp(self):
        """Test request freshness check with invalid timestamp"""
        result = self.client.is_request_fresh("invalid_timestamp")
        assert result is False
    
    @patch('src.shared.feishu_client.FeishuClient._get_access_token')
    @patch('requests.post')
    def test_send_text_message_success(self, mock_post, mock_get_token):
        """Test successful text message sending"""
        # Mock access token
        mock_get_token.return_value = "test_access_token"
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "msg": "success",
            "data": {"message_id": "msg_123"}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        chat_id = "test_chat_id"
        text = "Hello, world!"
        
        result = self.client.send_text_message(chat_id, text)
        
        assert result["code"] == 0
        assert result["msg"] == "success"
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://open.feishu.cn/open-apis/im/v1/messages"
        assert call_args[1]['headers']['Authorization'] == "Bearer test_access_token"
        
        payload = call_args[1]['json']
        assert payload['receive_id'] == chat_id
        assert payload['msg_type'] == "text"
        assert json.loads(payload['content'])['text'] == text
    
    @patch('src.shared.feishu_client.FeishuClient._get_access_token')
    @patch('requests.post')
    def test_send_text_message_api_error(self, mock_post, mock_get_token):
        """Test text message sending with API error"""
        mock_get_token.return_value = "test_access_token"
        
        # Mock error response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 1001,
            "msg": "Invalid chat_id"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception, match="Failed to send message"):
            self.client.send_text_message("invalid_chat", "Hello")
    
    @patch('src.shared.feishu_client.FeishuClient._get_access_token')
    @patch('requests.post')
    def test_send_card_message_success(self, mock_post, mock_get_token):
        """Test successful card message sending"""
        mock_get_token.return_value = "test_access_token"
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "msg": "success"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        chat_id = "test_chat_id"
        card = {
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": "Test card",
                        "tag": "lark_md"
                    }
                }
            ]
        }
        
        result = self.client.send_card_message(chat_id, card)
        
        assert result["code"] == 0
        
        # Verify API call
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['receive_id'] == chat_id
        assert payload['msg_type'] == "interactive"
        assert json.loads(payload['content']) == card
    
    @patch('src.shared.feishu_client.FeishuClient._get_access_token')
    @patch('requests.post')
    def test_reply_to_message_success(self, mock_post, mock_get_token):
        """Test successful message reply"""
        mock_get_token.return_value = "test_access_token"
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "msg": "success"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        message_id = "original_msg_id"
        reply_text = "This is a reply"
        
        result = self.client.reply_to_message(message_id, reply_text)
        
        assert result["code"] == 0
        
        # Verify API call
        call_args = mock_post.call_args
        expected_url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
        assert call_args[0][0] == expected_url
        
        payload = call_args[1]['json']
        assert payload['msg_type'] == "text"
        assert json.loads(payload['content'])['text'] == reply_text
    
    @patch('src.shared.feishu_client.FeishuClient._get_access_token')
    @patch('requests.get')
    def test_get_chat_info_success(self, mock_get, mock_get_token):
        """Test successful chat info retrieval"""
        mock_get_token.return_value = "test_access_token"
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "msg": "success",
            "data": {
                "chat_id": "test_chat_id",
                "name": "Test Chat",
                "description": "Test chat description"
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        chat_id = "test_chat_id"
        result = self.client.get_chat_info(chat_id)
        
        assert result["code"] == 0
        assert result["data"]["chat_id"] == chat_id
        
        # Verify API call
        call_args = mock_get.call_args
        expected_url = f"https://open.feishu.cn/open-apis/im/v1/chats/{chat_id}"
        assert call_args[0][0] == expected_url
    
    def test_process_webhook_event_url_verification(self):
        """Test processing URL verification event"""
        event_data = {
            "header": {
                "event_type": "url_verification"
            },
            "challenge": "test_challenge_string"
        }
        
        result = self.client.process_webhook_event(event_data)
        
        assert result == {"challenge": "test_challenge_string"}
    
    @patch('src.shared.feishu_client.FeishuClient._handle_message_event')
    def test_process_webhook_event_message_receive(self, mock_handle_message):
        """Test processing message receive event"""
        mock_handle_message.return_value = None
        
        event_data = {
            "header": {
                "event_type": "im.message.receive_v1"
            },
            "event": {
                "message": {
                    "chat_id": "test_chat",
                    "content": '{"text": "Hello"}'
                }
            }
        }
        
        result = self.client.process_webhook_event(event_data)
        
        assert result is None
        mock_handle_message.assert_called_once_with(event_data)
    
    def test_process_webhook_event_unknown_type(self):
        """Test processing unknown event type"""
        event_data = {
            "header": {
                "event_type": "unknown.event.type"
            }
        }
        
        result = self.client.process_webhook_event(event_data)
        assert result is None
    
    @patch('src.shared.feishu_client.FeishuClient.send_text_message')
    def test_handle_message_event_text_message(self, mock_send_text):
        """Test handling text message event"""
        mock_send_text.return_value = {"code": 0, "msg": "success"}
        
        event_data = {
            "event": {
                "sender": {
                    "sender_type": "user"
                },
                "message": {
                    "chat_id": "test_chat",
                    "message_type": "text",
                    "content": '{"text": "Hello bot"}'
                }
            }
        }
        
        result = self.client._handle_message_event(event_data)
        
        assert result is None
        mock_send_text.assert_called_once()
        call_args = mock_send_text.call_args
        assert call_args[0][0] == "test_chat"
        assert "Hello bot" in call_args[0][1]
    
    def test_handle_message_event_bot_message(self):
        """Test handling message from bot (should be ignored)"""
        event_data = {
            "event": {
                "sender": {
                    "sender_type": "app"  # Bot message
                },
                "message": {
                    "chat_id": "test_chat",
                    "message_type": "text",
                    "content": '{"text": "Bot message"}'
                }
            }
        }
        
        result = self.client._handle_message_event(event_data)
        assert result is None
    
    def test_handle_message_event_empty_text(self):
        """Test handling message with empty text"""
        event_data = {
            "event": {
                "sender": {
                    "sender_type": "user"
                },
                "message": {
                    "chat_id": "test_chat",
                    "message_type": "text",
                    "content": '{"text": ""}'
                }
            }
        }
        
        # Should not send reply for empty text
        with patch('src.shared.feishu_client.FeishuClient.send_text_message') as mock_send:
            result = self.client._handle_message_event(event_data)
            assert result is None
            mock_send.assert_not_called()


class TestFeishuWebhookValidator:
    """Test cases for FeishuWebhookValidator class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.encrypt_key = "test_encrypt_key"
        self.validator = FeishuWebhookValidator(self.encrypt_key)
    
    def test_validator_initialization(self):
        """Test FeishuWebhookValidator initialization"""
        assert self.validator.encrypt_key == self.encrypt_key
    
    def test_validate_request_success(self):
        """Test successful request validation"""
        timestamp = str(int(time.time()))
        nonce = "test_nonce"
        body = '{"test": "data"}'
        
        # Calculate correct signature
        import hashlib
        string_to_sign = f"{timestamp}{nonce}{self.encrypt_key}{body}"
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
    
    def test_validate_request_invalid_signature(self):
        """Test request validation with invalid signature"""
        headers = {
            "x-lark-request-timestamp": str(int(time.time())),
            "x-lark-request-nonce": "test_nonce",
            "x-lark-signature": "invalid_signature"
        }
        body = '{"test": "data"}'
        
        result = self.validator.validate_request(headers, body)
        assert result is False
    
    def test_validate_request_old_timestamp(self):
        """Test request validation with old timestamp"""
        old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago
        nonce = "test_nonce"
        body = '{"test": "data"}'
        
        # Calculate correct signature for old timestamp
        import hashlib
        string_to_sign = f"{old_timestamp}{nonce}{self.encrypt_key}{body}"
        signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
        
        headers = {
            "x-lark-request-timestamp": old_timestamp,
            "x-lark-request-nonce": nonce,
            "x-lark-signature": signature
        }
        
        result = self.validator.validate_request(headers, body)
        assert result is False  # Should fail due to old timestamp
    
    def test_verify_signature_success(self):
        """Test successful signature verification"""
        timestamp = "1640995200"
        nonce = "test_nonce"
        body = '{"test": "data"}'
        
        # Calculate correct signature
        import hashlib
        string_to_sign = f"{timestamp}{nonce}{self.encrypt_key}{body}"
        signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
        
        result = self.validator._verify_signature(timestamp, nonce, body, signature)
        assert result is True
    
    def test_verify_signature_failure(self):
        """Test signature verification failure"""
        timestamp = "1640995200"
        nonce = "test_nonce"
        body = '{"test": "data"}'
        signature = "invalid_signature"
        
        result = self.validator._verify_signature(timestamp, nonce, body, signature)
        assert result is False
    
    def test_verify_signature_exception(self):
        """Test signature verification with exception"""
        # Pass None values to trigger exception
        result = self.validator._verify_signature(None, None, None, None)
        assert result is False
    
    def test_is_request_fresh_valid(self):
        """Test request freshness check with valid timestamp"""
        current_timestamp = str(int(time.time()))
        result = self.validator._is_request_fresh(current_timestamp)
        assert result is True
    
    def test_is_request_fresh_old(self):
        """Test request freshness check with old timestamp"""
        old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago
        result = self.validator._is_request_fresh(old_timestamp)
        assert result is False
    
    def test_is_request_fresh_invalid_timestamp(self):
        """Test request freshness check with invalid timestamp"""
        result = self.validator._is_request_fresh("invalid_timestamp")
        assert result is False
    
    def test_is_request_fresh_custom_max_age(self):
        """Test request freshness check with custom max age"""
        timestamp = str(int(time.time()) - 100)  # 100 seconds ago
        
        # Should be valid with max_age=200
        result = self.validator._is_request_fresh(timestamp, max_age=200)
        assert result is True
        
        # Should be invalid with max_age=50
        result = self.validator._is_request_fresh(timestamp, max_age=50)
        assert result is False


class TestRetryDecorator:
    """Test cases for retry decorator in FeishuClient"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = BotConfig(
            app_id="test_app_id",
            app_secret="test_app_secret",
            verification_token="test_token",
            encrypt_key="test_encrypt_key",
            bot_name="TestBot",
            webhook_url="https://example.com/webhook"
        )
        self.client = FeishuClient(self.config)
    
    @patch('time.sleep')
    @patch('src.shared.feishu_client.FeishuClient._get_access_token')
    @patch('requests.post')
    def test_retry_on_network_error(self, mock_post, mock_get_token, mock_sleep):
        """Test retry behavior on network error"""
        mock_get_token.return_value = "test_access_token"
        
        # First two calls fail with network error, third succeeds
        mock_post.side_effect = [
            requests.ConnectionError("Network error"),
            requests.ConnectionError("Network error"),
            Mock(json=lambda: {"code": 0, "msg": "success"}, raise_for_status=lambda: None)
        ]
        
        result = self.client.send_text_message("test_chat", "Hello")
        
        assert result["code"] == 0
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2  # Two retries
    
    @patch('time.sleep')
    @patch('src.shared.feishu_client.FeishuClient._get_access_token')
    @patch('requests.post')
    def test_retry_exhausted(self, mock_post, mock_get_token, mock_sleep):
        """Test behavior when all retries are exhausted"""
        mock_get_token.return_value = "test_access_token"
        
        # All calls fail with network error
        mock_post.side_effect = requests.ConnectionError("Persistent network error")
        
        with pytest.raises(requests.ConnectionError):
            self.client.send_text_message("test_chat", "Hello")
        
        # Should have tried 3 times (initial + 2 retries)
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2