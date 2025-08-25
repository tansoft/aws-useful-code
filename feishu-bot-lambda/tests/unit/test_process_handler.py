"""
Unit tests for process_handler Lambda function
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.lambdas.process_handler import (
    lambda_handler,
    _get_feishu_client,
    _load_bot_config,
    _process_sqs_record,
    _handle_feishu_message,
    _handle_text_message,
    _handle_image_message,
    _handle_file_message,
    _send_unsupported_message_reply,
    _generate_text_reply,
    _extract_mentions,
    _is_bot_mentioned
)
from src.shared.models import FeishuMessage


class TestLambdaHandler:
    """Test cases for lambda_handler function"""
    
    @patch('src.lambdas.process_handler._get_feishu_client')
    @patch('src.lambdas.process_handler._process_sqs_record')
    def test_lambda_handler_success(self, mock_process_record, mock_get_client):
        """Test successful lambda handler execution"""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_process_record.return_value = {
            'messageId': 'test_msg_id',
            'status': 'success',
            'feishuMessageId': 'feishu_msg_id'
        }
        
        # Create test event
        event = {
            'Records': [
                {
                    'messageId': 'test_msg_id',
                    'body': json.dumps({
                        'message_id': 'feishu_msg_id',
                        'user_id': 'test_user',
                        'chat_id': 'test_chat',
                        'message_type': 'text',
                        'content': 'Hello',
                        'timestamp': 1640995200,
                        'app_id': 'test_app'
                    })
                }
            ]
        }
        
        context = Mock()
        
        # Execute
        result = lambda_handler(event, context)
        
        # Verify
        assert result['statusCode'] == 200
        assert result['body']['processed'] == 1
        assert result['body']['successful'] == 1
        assert result['body']['failed'] == 0
        
        mock_get_client.assert_called_once()
        mock_process_record.assert_called_once()
    
    @patch('src.lambdas.process_handler._get_feishu_client')
    @patch('src.lambdas.process_handler._process_sqs_record')
    def test_lambda_handler_partial_failure(self, mock_process_record, mock_get_client):
        """Test lambda handler with partial failures"""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # First record succeeds, second fails
        mock_process_record.side_effect = [
            {'messageId': 'msg1', 'status': 'success'},
            Exception("Processing failed")
        ]
        
        # Create test event with two records
        event = {
            'Records': [
                {'messageId': 'msg1', 'body': '{"test": "data1"}'},
                {'messageId': 'msg2', 'body': '{"test": "data2"}'}
            ]
        }
        
        context = Mock()
        
        # Execute
        result = lambda_handler(event, context)
        
        # Verify
        assert result['statusCode'] == 200
        assert result['body']['processed'] == 2
        assert result['body']['successful'] == 1
        assert result['body']['failed'] == 1
    
    @patch('src.lambdas.process_handler._get_feishu_client')
    def test_lambda_handler_client_initialization_error(self, mock_get_client):
        """Test lambda handler with client initialization error"""
        mock_get_client.side_effect = Exception("Client initialization failed")
        
        event = {'Records': [{'messageId': 'test', 'body': '{}'}]}
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        assert 'error' in result['body']
    
    def test_lambda_handler_empty_records(self):
        """Test lambda handler with empty records"""
        event = {'Records': []}
        context = Mock()
        
        with patch('src.lambdas.process_handler._get_feishu_client') as mock_get_client:
            mock_get_client.return_value = Mock()
            
            result = lambda_handler(event, context)
            
            assert result['statusCode'] == 200
            assert result['body']['processed'] == 0
            assert result['body']['successful'] == 0
            assert result['body']['failed'] == 0


class TestGetFeishuClient:
    """Test cases for _get_feishu_client function"""
    
    def setup_method(self):
        """Reset global client cache before each test"""
        import src.lambdas.process_handler
        src.lambdas.process_handler._feishu_client = None
    
    @patch('src.lambdas.process_handler._load_bot_config')
    @patch('src.lambdas.process_handler.FeishuClient')
    def test_get_feishu_client_success(self, mock_client_class, mock_load_config):
        """Test successful client initialization"""
        # Setup mocks
        mock_config = Mock()
        mock_load_config.return_value = mock_config
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Execute
        result = _get_feishu_client()
        
        # Verify
        assert result == mock_client
        mock_load_config.assert_called_once()
        mock_client_class.assert_called_once_with(mock_config)
    
    @patch('src.lambdas.process_handler._load_bot_config')
    @patch('src.lambdas.process_handler.FeishuClient')
    def test_get_feishu_client_caching(self, mock_client_class, mock_load_config):
        """Test client caching behavior"""
        # Setup mocks
        mock_config = Mock()
        mock_load_config.return_value = mock_config
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # First call should initialize client
        result1 = _get_feishu_client()
        assert result1 == mock_client
        assert mock_load_config.call_count == 1
        assert mock_client_class.call_count == 1
        
        # Second call should use cached client
        result2 = _get_feishu_client()
        assert result2 == mock_client
        assert mock_load_config.call_count == 1  # No additional calls
        assert mock_client_class.call_count == 1  # No additional calls
    
    @patch('src.lambdas.process_handler._load_bot_config')
    def test_get_feishu_client_config_error(self, mock_load_config):
        """Test client initialization with config error"""
        mock_load_config.side_effect = Exception("Config load failed")
        
        with pytest.raises(Exception, match="Config load failed"):
            _get_feishu_client()


class TestLoadBotConfig:
    """Test cases for _load_bot_config function"""
    
    @patch('src.lambdas.process_handler.BotConfig')
    def test_load_bot_config_from_env_success(self, mock_config_class):
        """Test successful config loading from environment"""
        mock_config = Mock()
        mock_config_class.from_env.return_value = mock_config
        
        result = _load_bot_config()
        
        assert result == mock_config
        mock_config_class.from_env.assert_called_once()
    
    @patch('src.lambdas.process_handler.BotConfig')
    @patch.dict('os.environ', {
        'PARAMETER_STORE_PREFIX': '/test-bot',
        'AWS_REGION': 'us-west-2'
    })
    def test_load_bot_config_from_parameter_store(self, mock_config_class):
        """Test config loading from Parameter Store when env fails"""
        # Env loading fails, Parameter Store succeeds
        mock_config_class.from_env.side_effect = ValueError("Env config incomplete")
        mock_config = Mock()
        mock_config_class.from_parameter_store.return_value = mock_config
        
        result = _load_bot_config()
        
        assert result == mock_config
        mock_config_class.from_env.assert_called_once()
        mock_config_class.from_parameter_store.assert_called_once_with('/test-bot', 'us-west-2')
    
    @patch('src.lambdas.process_handler.BotConfig')
    def test_load_bot_config_both_fail(self, mock_config_class):
        """Test config loading when both methods fail"""
        mock_config_class.from_env.side_effect = ValueError("Env config incomplete")
        mock_config_class.from_parameter_store.side_effect = Exception("Parameter Store failed")
        
        with pytest.raises(Exception):
            _load_bot_config()


class TestProcessSqsRecord:
    """Test cases for _process_sqs_record function"""
    
    @patch('src.lambdas.process_handler._handle_feishu_message')
    def test_process_sqs_record_success(self, mock_handle_message):
        """Test successful SQS record processing"""
        # Setup mock
        mock_handle_message.return_value = {'type': 'text_reply', 'reply_text': 'Hello'}
        
        # Create test record
        message = FeishuMessage(
            message_id='feishu_msg_id',
            user_id='test_user',
            chat_id='test_chat',
            message_type='text',
            content='Hello',
            timestamp=1640995200,
            app_id='test_app'
        )
        
        record = {
            'messageId': 'sqs_msg_id',
            'body': message.to_json()
        }
        
        mock_client = Mock()
        
        # Execute
        result = _process_sqs_record(record, mock_client)
        
        # Verify
        assert result['messageId'] == 'sqs_msg_id'
        assert result['status'] == 'success'
        assert result['feishuMessageId'] == 'feishu_msg_id'
        assert result['response']['type'] == 'text_reply'
        
        mock_handle_message.assert_called_once()
    
    def test_process_sqs_record_empty_body(self):
        """Test SQS record processing with empty body"""
        record = {
            'messageId': 'sqs_msg_id',
            'body': ''
        }
        
        mock_client = Mock()
        
        with pytest.raises(ValueError, match="Empty message body"):
            _process_sqs_record(record, mock_client)
    
    def test_process_sqs_record_invalid_json(self):
        """Test SQS record processing with invalid JSON"""
        record = {
            'messageId': 'sqs_msg_id',
            'body': 'invalid json {'
        }
        
        mock_client = Mock()
        
        with pytest.raises(Exception):
            _process_sqs_record(record, mock_client)


class TestHandleFeishuMessage:
    """Test cases for _handle_feishu_message function"""
    
    @patch('src.lambdas.process_handler._handle_text_message')
    def test_handle_feishu_message_text(self, mock_handle_text):
        """Test handling text message"""
        mock_handle_text.return_value = {'type': 'text_reply'}
        
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='text',
            content='Hello',
            timestamp=1640995200,
            app_id='app_id'
        )
        
        mock_client = Mock()
        
        result = _handle_feishu_message(message, mock_client)
        
        assert result['type'] == 'text_reply'
        mock_handle_text.assert_called_once_with(message, mock_client)
    
    @patch('src.lambdas.process_handler._handle_image_message')
    def test_handle_feishu_message_image(self, mock_handle_image):
        """Test handling image message"""
        mock_handle_image.return_value = {'type': 'image_reply'}
        
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='image',
            content='image_key_123',
            timestamp=1640995200,
            app_id='app_id'
        )
        
        mock_client = Mock()
        
        result = _handle_feishu_message(message, mock_client)
        
        assert result['type'] == 'image_reply'
        mock_handle_image.assert_called_once_with(message, mock_client)
    
    @patch('src.lambdas.process_handler._send_unsupported_message_reply')
    def test_handle_feishu_message_unsupported(self, mock_unsupported):
        """Test handling unsupported message type"""
        mock_unsupported.return_value = {'type': 'unsupported_reply'}
        
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='unknown_type',
            content='content',
            timestamp=1640995200,
            app_id='app_id'
        )
        
        mock_client = Mock()
        
        result = _handle_feishu_message(message, mock_client)
        
        assert result['type'] == 'unsupported_reply'
        mock_unsupported.assert_called_once_with(message, mock_client)


class TestHandleTextMessage:
    """Test cases for _handle_text_message function"""
    
    @patch('src.lambdas.process_handler._generate_text_reply')
    def test_handle_text_message_success(self, mock_generate_reply):
        """Test successful text message handling"""
        # Setup mocks
        mock_generate_reply.return_value = "Generated reply"
        mock_client = Mock()
        mock_client.send_text_message.return_value = {'code': 0, 'msg': 'success'}
        
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='text',
            content='Hello bot',
            timestamp=1640995200,
            app_id='app_id'
        )
        
        # Execute
        result = _handle_text_message(message, mock_client)
        
        # Verify
        assert result['type'] == 'text_reply'
        assert result['reply_text'] == 'Generated reply'
        assert result['feishu_response']['code'] == 0
        
        mock_generate_reply.assert_called_once_with('Hello bot', message)
        mock_client.send_text_message.assert_called_once_with('chat_id', 'Generated reply')
    
    def test_handle_text_message_client_error(self):
        """Test text message handling with client error"""
        mock_client = Mock()
        mock_client.send_text_message.side_effect = Exception("Send failed")
        
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='text',
            content='Hello',
            timestamp=1640995200,
            app_id='app_id'
        )
        
        with pytest.raises(Exception):
            _handle_text_message(message, mock_client)


class TestGenerateTextReply:
    """Test cases for _generate_text_reply function"""
    
    def test_generate_text_reply_greeting(self):
        """Test reply generation for greeting"""
        message = Mock()
        
        result = _generate_text_reply("你好", message)
        
        assert "你好" in result
        assert "😊" in result
    
    def test_generate_text_reply_help(self):
        """Test reply generation for help request"""
        message = Mock()
        
        result = _generate_text_reply("帮助", message)
        
        assert "飞书机器人" in result
        assert "帮助" in result
    
    def test_generate_text_reply_time(self):
        """Test reply generation for time request"""
        message = Mock()
        
        result = _generate_text_reply("现在几点", message)
        
        assert "时间" in result
        assert ":" in result  # Time format should contain colon
    
    def test_generate_text_reply_thanks(self):
        """Test reply generation for thanks"""
        message = Mock()
        
        result = _generate_text_reply("谢谢", message)
        
        assert "不客气" in result
        assert "😊" in result
    
    def test_generate_text_reply_goodbye(self):
        """Test reply generation for goodbye"""
        message = Mock()
        
        result = _generate_text_reply("再见", message)
        
        assert "再见" in result
        assert "👋" in result
    
    def test_generate_text_reply_default(self):
        """Test reply generation for unknown text"""
        message = Mock()
        
        result = _generate_text_reply("random text", message)
        
        assert "random text" in result
        assert "帮助" in result
    
    def test_generate_text_reply_exception(self):
        """Test reply generation with exception"""
        message = Mock()
        
        # This should not raise an exception
        result = _generate_text_reply(None, message)
        
        assert "抱歉" in result


class TestExtractMentions:
    """Test cases for _extract_mentions function"""
    
    def test_extract_mentions_with_mentions(self):
        """Test extracting mentions when they exist"""
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='text',
            content='Hello @user1 @user2',
            timestamp=1640995200,
            app_id='app_id',
            mentions=['user1', 'user2']
        )
        
        result = _extract_mentions(message)
        
        assert result == ['user1', 'user2']
    
    def test_extract_mentions_no_mentions(self):
        """Test extracting mentions when none exist"""
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='text',
            content='Hello world',
            timestamp=1640995200,
            app_id='app_id',
            mentions=None
        )
        
        result = _extract_mentions(message)
        
        assert result == []


class TestIsBotMentioned:
    """Test cases for _is_bot_mentioned function"""
    
    def test_is_bot_mentioned_with_bot_id(self):
        """Test bot mention detection with specific bot ID"""
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='text',
            content='Hello @bot',
            timestamp=1640995200,
            app_id='app_id',
            mentions=['user1', 'bot_id', 'user2']
        )
        
        result = _is_bot_mentioned(message, 'bot_id')
        
        assert result is True
    
    def test_is_bot_mentioned_without_bot_id(self):
        """Test bot mention detection without specific bot ID"""
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='text',
            content='Hello @someone',
            timestamp=1640995200,
            app_id='app_id',
            mentions=['user1']
        )
        
        result = _is_bot_mentioned(message)
        
        assert result is True  # Any mention counts when no bot ID provided
    
    def test_is_bot_mentioned_no_mentions(self):
        """Test bot mention detection with no mentions"""
        message = FeishuMessage(
            message_id='msg_id',
            user_id='user_id',
            chat_id='chat_id',
            message_type='text',
            content='Hello world',
            timestamp=1640995200,
            app_id='app_id',
            mentions=None
        )
        
        result = _is_bot_mentioned(message, 'bot_id')
        
        assert result is False