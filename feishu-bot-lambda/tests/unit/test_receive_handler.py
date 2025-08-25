"""
Unit tests for receive_handler Lambda function
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import boto3
from moto import mock_aws

from src.lambdas.receive_handler import (
    lambda_handler,
    _verify_request_signature,
    _process_webhook_event,
    _handle_url_verification,
    _handle_message_receive,
    _send_message_to_sqs,
    _validate_webhook_data
)


class TestLambdaHandler:
    """Test cases for lambda_handler function"""
    
    @patch('src.lambdas.receive_handler._verify_request_signature')
    @patch('src.lambdas.receive_handler._process_webhook_event')
    def test_lambda_handler_success(self, mock_process_event, mock_verify_signature):
        """Test successful lambda handler execution"""
        # Setup mocks
        mock_verify_signature.return_value = True
        mock_process_event.return_value = None
        
        # Create test event
        event = {
            "body": json.dumps({"header": {"event_type": "im.message.receive_v1"}}),
            "headers": {
                "Content-Type": "application/json",
                "X-Lark-Request-Timestamp": "1640995200",
                "X-Lark-Request-Nonce": "test_nonce",
                "X-Lark-Signature": "test_signature"
            }
        }
        
        context = Mock()
        
        # Execute
        result = lambda_handler(event, context)
        
        # Verify
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert "Event processed successfully" in body["data"]["message"]
        
        mock_verify_signature.assert_called_once()
        mock_process_event.assert_called_once()
    
    def test_lambda_handler_empty_body(self):
        """Test lambda handler with empty body"""
        event = {
            "body": "",
            "headers": {}
        }
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"]["code"] == "EMPTY_BODY"
    
    @patch('src.lambdas.receive_handler._verify_request_signature')
    def test_lambda_handler_invalid_signature(self, mock_verify_signature):
        """Test lambda handler with invalid signature"""
        mock_verify_signature.return_value = False
        
        event = {
            "body": json.dumps({"test": "data"}),
            "headers": {"X-Lark-Signature": "invalid"}
        }
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error"]["code"] == "INVALID_SIGNATURE"
    
    @patch('src.lambdas.receive_handler._verify_request_signature')
    def test_lambda_handler_invalid_json(self, mock_verify_signature):
        """Test lambda handler with invalid JSON body"""
        mock_verify_signature.return_value = True
        
        event = {
            "body": "invalid json {",
            "headers": {}
        }
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"]["code"] == "INVALID_JSON"
    
    @patch('src.lambdas.receive_handler._verify_request_signature')
    @patch('src.lambdas.receive_handler._process_webhook_event')
    def test_lambda_handler_url_verification(self, mock_process_event, mock_verify_signature):
        """Test lambda handler with URL verification event"""
        mock_verify_signature.return_value = True
        mock_process_event.return_value = {"challenge": "test_challenge"}
        
        event = {
            "body": json.dumps({
                "header": {"event_type": "url_verification"},
                "challenge": "test_challenge"
            }),
            "headers": {}
        }
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["data"]["challenge"] == "test_challenge"
    
    @patch('src.lambdas.receive_handler._verify_request_signature')
    @patch('src.lambdas.receive_handler._process_webhook_event')
    def test_lambda_handler_exception(self, mock_process_event, mock_verify_signature):
        """Test lambda handler with unexpected exception"""
        mock_verify_signature.return_value = True
        mock_process_event.side_effect = Exception("Unexpected error")
        
        event = {
            "body": json.dumps({"header": {"event_type": "test"}}),
            "headers": {}
        }
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert body["error"]["code"] == "INTERNAL_ERROR"


class TestVerifyRequestSignature:
    """Test cases for _verify_request_signature function"""
    
    @patch.dict('os.environ', {'FEISHU_ENCRYPT_KEY': 'test_encrypt_key'})
    @patch('src.lambdas.receive_handler.FeishuWebhookValidator')
    def test_verify_request_signature_success(self, mock_validator_class):
        """Test successful signature verification"""
        # Setup mock
        mock_validator = Mock()
        mock_validator.validate_request.return_value = True
        mock_validator_class.return_value = mock_validator
        
        headers = {"x-lark-signature": "test_signature"}
        body = '{"test": "data"}'
        
        result = _verify_request_signature(headers, body)
        
        assert result is True
        mock_validator_class.assert_called_once_with('test_encrypt_key')
        mock_validator.validate_request.assert_called_once_with(headers, body)
    
    @patch.dict('os.environ', {}, clear=True)
    def test_verify_request_signature_missing_key(self):
        """Test signature verification with missing encrypt key"""
        headers = {"x-lark-signature": "test_signature"}
        body = '{"test": "data"}'
        
        result = _verify_request_signature(headers, body)
        
        assert result is False
    
    @patch.dict('os.environ', {'FEISHU_ENCRYPT_KEY': 'test_encrypt_key'})
    @patch('src.lambdas.receive_handler.FeishuWebhookValidator')
    def test_verify_request_signature_validation_failed(self, mock_validator_class):
        """Test signature verification failure"""
        # Setup mock
        mock_validator = Mock()
        mock_validator.validate_request.return_value = False
        mock_validator_class.return_value = mock_validator
        
        headers = {"x-lark-signature": "invalid_signature"}
        body = '{"test": "data"}'
        
        result = _verify_request_signature(headers, body)
        
        assert result is False
    
    @patch.dict('os.environ', {'FEISHU_ENCRYPT_KEY': 'test_encrypt_key'})
    @patch('src.lambdas.receive_handler.FeishuWebhookValidator')
    def test_verify_request_signature_exception(self, mock_validator_class):
        """Test signature verification with exception"""
        mock_validator_class.side_effect = Exception("Validator error")
        
        headers = {"x-lark-signature": "test_signature"}
        body = '{"test": "data"}'
        
        result = _verify_request_signature(headers, body)
        
        assert result is False


class TestProcessWebhookEvent:
    """Test cases for _process_webhook_event function"""
    
    @patch('src.lambdas.receive_handler._handle_url_verification')
    def test_process_webhook_event_url_verification(self, mock_handle_url):
        """Test processing URL verification event"""
        mock_handle_url.return_value = {"challenge": "test_challenge"}
        
        webhook_data = {
            "header": {"event_type": "url_verification"},
            "challenge": "test_challenge"
        }
        
        result = _process_webhook_event(webhook_data)
        
        assert result == {"challenge": "test_challenge"}
        mock_handle_url.assert_called_once_with(webhook_data)
    
    @patch('src.lambdas.receive_handler._handle_message_receive')
    def test_process_webhook_event_message_receive(self, mock_handle_message):
        """Test processing message receive event"""
        mock_handle_message.return_value = None
        
        webhook_data = {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {"message": {"chat_id": "test_chat"}}
        }
        
        result = _process_webhook_event(webhook_data)
        
        assert result is None
        mock_handle_message.assert_called_once_with(webhook_data)
    
    def test_process_webhook_event_unknown_type(self):
        """Test processing unknown event type"""
        webhook_data = {
            "header": {"event_type": "unknown.event.type"}
        }
        
        result = _process_webhook_event(webhook_data)
        
        assert result is None
    
    def test_process_webhook_event_exception(self):
        """Test processing webhook event with exception"""
        webhook_data = {
            "header": {}  # Missing event_type
        }
        
        with pytest.raises(Exception):
            _process_webhook_event(webhook_data)


class TestHandleUrlVerification:
    """Test cases for _handle_url_verification function"""
    
    def test_handle_url_verification_success(self):
        """Test successful URL verification handling"""
        webhook_data = {
            "challenge": "test_challenge_string"
        }
        
        result = _handle_url_verification(webhook_data)
        
        assert result == {"challenge": "test_challenge_string"}
    
    def test_handle_url_verification_missing_challenge(self):
        """Test URL verification handling with missing challenge"""
        webhook_data = {}
        
        result = _handle_url_verification(webhook_data)
        
        assert result == {"challenge": ""}


class TestHandleMessageReceive:
    """Test cases for _handle_message_receive function"""
    
    @patch('src.lambdas.receive_handler._send_message_to_sqs')
    @patch('src.lambdas.receive_handler.FeishuMessage')
    def test_handle_message_receive_success(self, mock_message_class, mock_send_sqs):
        """Test successful message receive handling"""
        # Setup mock message
        mock_message = Mock()
        mock_message.to_dict.return_value = {"message_id": "test_msg"}
        mock_message_class.from_webhook.return_value = mock_message
        
        webhook_data = {
            "event": {
                "sender": {"sender_type": "user"},
                "message": {"chat_id": "test_chat"}
            }
        }
        
        _handle_message_receive(webhook_data)
        
        mock_message_class.from_webhook.assert_called_once_with(webhook_data)
        mock_send_sqs.assert_called_once_with(mock_message)
    
    @patch('src.lambdas.receive_handler.FeishuMessage')
    def test_handle_message_receive_bot_message(self, mock_message_class):
        """Test handling message from bot (should be ignored)"""
        webhook_data = {
            "event": {
                "sender": {"sender_type": "app"},  # Bot message
                "message": {"chat_id": "test_chat"}
            }
        }
        
        _handle_message_receive(webhook_data)
        
        # Should not create message or send to SQS
        mock_message_class.from_webhook.assert_called_once()
    
    @patch('src.lambdas.receive_handler.FeishuMessage')
    def test_handle_message_receive_exception(self, mock_message_class):
        """Test message receive handling with exception"""
        mock_message_class.from_webhook.side_effect = Exception("Parse error")
        
        webhook_data = {
            "event": {
                "sender": {"sender_type": "user"},
                "message": {"chat_id": "test_chat"}
            }
        }
        
        with pytest.raises(Exception):
            _handle_message_receive(webhook_data)


class TestSendMessageToSqs:
    """Test cases for _send_message_to_sqs function"""
    
    @mock_aws
    @patch.dict('os.environ', {
        'SQS_QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'AWS_REGION': 'us-east-1'
    })
    def test_send_message_to_sqs_success(self):
        """Test successful message sending to SQS"""
        # Create mock SQS queue
        sqs = boto3.resource('sqs', region_name='us-east-1')
        queue = sqs.create_queue(QueueName='test-queue')
        
        # Create test message
        from src.shared.models import FeishuMessage
        message = FeishuMessage(
            message_id="test_msg_id",
            user_id="test_user_id",
            chat_id="test_chat_id",
            message_type="text",
            content="Test message",
            timestamp=1640995200,
            app_id="test_app_id"
        )
        
        # Execute
        _send_message_to_sqs(message)
        
        # Verify message was sent
        messages = queue.receive_messages()
        assert len(messages) == 1
        
        message_body = json.loads(messages[0].body)
        assert message_body["message_id"] == "test_msg_id"
        assert message_body["content"] == "Test message"
    
    @patch.dict('os.environ', {}, clear=True)
    def test_send_message_to_sqs_missing_queue_url(self):
        """Test sending message to SQS with missing queue URL"""
        from src.shared.models import FeishuMessage
        message = FeishuMessage(
            message_id="test_msg_id",
            user_id="test_user_id",
            chat_id="test_chat_id",
            message_type="text",
            content="Test message",
            timestamp=1640995200,
            app_id="test_app_id"
        )
        
        with pytest.raises(ValueError, match="SQS_QUEUE_URL environment variable not set"):
            _send_message_to_sqs(message)
    
    @patch('boto3.client')
    @patch.dict('os.environ', {'SQS_QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'})
    def test_send_message_to_sqs_boto_error(self, mock_boto_client):
        """Test sending message to SQS with boto3 error"""
        # Setup mock to raise exception
        mock_sqs = Mock()
        mock_sqs.send_message.side_effect = Exception("SQS error")
        mock_boto_client.return_value = mock_sqs
        
        from src.shared.models import FeishuMessage
        message = FeishuMessage(
            message_id="test_msg_id",
            user_id="test_user_id",
            chat_id="test_chat_id",
            message_type="text",
            content="Test message",
            timestamp=1640995200,
            app_id="test_app_id"
        )
        
        with pytest.raises(Exception):
            _send_message_to_sqs(message)


class TestValidateWebhookData:
    """Test cases for _validate_webhook_data function"""
    
    def test_validate_webhook_data_valid(self):
        """Test validation of valid webhook data"""
        webhook_data = {
            "header": {
                "event_type": "im.message.receive_v1"
            },
            "event": {
                "message": {"chat_id": "test_chat"}
            }
        }
        
        result = _validate_webhook_data(webhook_data)
        assert result is True
    
    def test_validate_webhook_data_missing_header(self):
        """Test validation with missing header"""
        webhook_data = {
            "event": {"message": {"chat_id": "test_chat"}}
        }
        
        result = _validate_webhook_data(webhook_data)
        assert result is False
    
    def test_validate_webhook_data_missing_event_type(self):
        """Test validation with missing event_type"""
        webhook_data = {
            "header": {},
            "event": {"message": {"chat_id": "test_chat"}}
        }
        
        result = _validate_webhook_data(webhook_data)
        assert result is False
    
    def test_validate_webhook_data_message_event_missing_event(self):
        """Test validation of message event with missing event field"""
        webhook_data = {
            "header": {
                "event_type": "im.message.receive_v1"
            }
            # Missing event field
        }
        
        result = _validate_webhook_data(webhook_data)
        assert result is False
    
    def test_validate_webhook_data_url_verification(self):
        """Test validation of URL verification event"""
        webhook_data = {
            "header": {
                "event_type": "url_verification"
            },
            "challenge": "test_challenge"
        }
        
        result = _validate_webhook_data(webhook_data)
        assert result is True
    
    def test_validate_webhook_data_exception(self):
        """Test validation with exception"""
        webhook_data = None  # This will cause an exception
        
        result = _validate_webhook_data(webhook_data)
        assert result is False