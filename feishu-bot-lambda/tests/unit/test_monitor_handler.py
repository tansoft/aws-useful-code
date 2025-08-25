"""
Unit tests for monitor_handler Lambda function
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.lambdas.monitor_handler import (
    lambda_handler,
    _get_feishu_client,
    _load_bot_config,
    _handle_sns_sqs_event,
    _process_sns_sqs_record,
    _handle_cloudwatch_event,
    _handle_direct_alarm_event,
    _handle_custom_monitor_event,
    _send_alert_to_feishu,
    _get_alert_target_chats,
    _map_cloudwatch_state_to_type,
    _map_cloudwatch_state_to_severity,
    _should_send_alert,
    _format_alert_summary
)
from src.shared.models import MonitorAlert


class TestLambdaHandler:
    """Test cases for lambda_handler function"""
    
    @patch('src.lambdas.monitor_handler._get_feishu_client')
    @patch('src.lambdas.monitor_handler._handle_sns_sqs_event')
    def test_lambda_handler_sns_sqs_event(self, mock_handle_sns, mock_get_client):
        """Test lambda handler with SNS/SQS event"""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_handle_sns.return_value = {
            'statusCode': 200,
            'body': {'processed': 1, 'successful': 1, 'failed': 0}
        }
        
        # Create test event
        event = {
            'Records': [
                {
                    'messageId': 'test_msg_id',
                    'body': json.dumps({
                        'alert_id': 'test_alert',
                        'service_name': 'test_service',
                        'alert_type': 'error',
                        'message': 'Test alert',
                        'timestamp': 1640995200,
                        'severity': 'high',
                        'metadata': {}
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
        
        mock_get_client.assert_called_once()
        mock_handle_sns.assert_called_once_with(event, mock_client)
    
    @patch('src.lambdas.monitor_handler._get_feishu_client')
    @patch('src.lambdas.monitor_handler._handle_cloudwatch_event')
    def test_lambda_handler_cloudwatch_event(self, mock_handle_cw, mock_get_client):
        """Test lambda handler with CloudWatch event"""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_handle_cw.return_value = {
            'statusCode': 200,
            'body': {'alertId': 'cw_test_alarm'}
        }
        
        # Create test event
        event = {
            'source': 'aws.cloudwatch',
            'detail': {
                'alarmName': 'test-alarm',
                'state': {
                    'value': 'ALARM',
                    'reason': 'Threshold crossed'
                }
            }
        }
        
        context = Mock()
        
        # Execute
        result = lambda_handler(event, context)
        
        # Verify
        assert result['statusCode'] == 200
        assert 'cw_test_alarm' in result['body']['alertId']
        
        mock_handle_cw.assert_called_once_with(event, mock_client)
    
    @patch('src.lambdas.monitor_handler._get_feishu_client')
    @patch('src.lambdas.monitor_handler._handle_direct_alarm_event')
    def test_lambda_handler_direct_alarm_event(self, mock_handle_direct, mock_get_client):
        """Test lambda handler with direct alarm event"""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_handle_direct.return_value = {
            'statusCode': 200,
            'body': {'alertId': 'direct_alarm'}
        }
        
        # Create test event
        event = {
            'AlarmName': 'test-direct-alarm',
            'NewStateValue': 'ALARM',
            'NewStateReason': 'Direct alarm test'
        }
        
        context = Mock()
        
        # Execute
        result = lambda_handler(event, context)
        
        # Verify
        assert result['statusCode'] == 200
        
        mock_handle_direct.assert_called_once_with(event, mock_client)
    
    @patch('src.lambdas.monitor_handler._get_feishu_client')
    @patch('src.lambdas.monitor_handler._handle_custom_monitor_event')
    def test_lambda_handler_custom_event(self, mock_handle_custom, mock_get_client):
        """Test lambda handler with custom monitor event"""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_handle_custom.return_value = {
            'statusCode': 200,
            'body': {'alertId': 'custom_alert'}
        }
        
        # Create test event
        event = {
            'alert_id': 'custom_test',
            'service_name': 'custom_service',
            'message': 'Custom alert message'
        }
        
        context = Mock()
        
        # Execute
        result = lambda_handler(event, context)
        
        # Verify
        assert result['statusCode'] == 200
        
        mock_handle_custom.assert_called_once_with(event, mock_client)
    
    @patch('src.lambdas.monitor_handler._get_feishu_client')
    def test_lambda_handler_client_error(self, mock_get_client):
        """Test lambda handler with client initialization error"""
        mock_get_client.side_effect = Exception("Client initialization failed")
        
        event = {'test': 'data'}
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        assert 'error' in result['body']


class TestGetFeishuClient:
    """Test cases for _get_feishu_client function"""
    
    def setup_method(self):
        """Reset global client cache before each test"""
        import src.lambdas.monitor_handler
        src.lambdas.monitor_handler._feishu_client = None
    
    @patch('src.lambdas.monitor_handler._load_bot_config')
    @patch('src.lambdas.monitor_handler.FeishuClient')
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
    
    @patch('src.lambdas.monitor_handler._load_bot_config')
    def test_get_feishu_client_config_error(self, mock_load_config):
        """Test client initialization with config error"""
        mock_load_config.side_effect = Exception("Config load failed")
        
        with pytest.raises(Exception, match="Config load failed"):
            _get_feishu_client()


class TestHandleSnsEvent:
    """Test cases for _handle_sns_sqs_event function"""
    
    @patch('src.lambdas.monitor_handler._process_sns_sqs_record')
    def test_handle_sns_sqs_event_success(self, mock_process_record):
        """Test successful SNS/SQS event handling"""
        # Setup mock
        mock_process_record.return_value = {
            'recordId': 'test_record',
            'status': 'success',
            'alertId': 'test_alert'
        }
        
        # Create test event
        event = {
            'Records': [
                {
                    'messageId': 'test_record',
                    'body': json.dumps({'alert_id': 'test_alert'})
                }
            ]
        }
        
        mock_client = Mock()
        
        # Execute
        result = _handle_sns_sqs_event(event, mock_client)
        
        # Verify
        assert result['statusCode'] == 200
        assert result['body']['processed'] == 1
        assert result['body']['successful'] == 1
        assert result['body']['failed'] == 0
        
        mock_process_record.assert_called_once()
    
    @patch('src.lambdas.monitor_handler._process_sns_sqs_record')
    def test_handle_sns_sqs_event_partial_failure(self, mock_process_record):
        """Test SNS/SQS event handling with partial failures"""
        # Setup mock - first succeeds, second fails
        mock_process_record.side_effect = [
            {'recordId': 'record1', 'status': 'success'},
            Exception("Processing failed")
        ]
        
        # Create test event
        event = {
            'Records': [
                {'messageId': 'record1', 'body': '{"test": "data1"}'},
                {'messageId': 'record2', 'body': '{"test": "data2"}'}
            ]
        }
        
        mock_client = Mock()
        
        # Execute
        result = _handle_sns_sqs_event(event, mock_client)
        
        # Verify
        assert result['statusCode'] == 200
        assert result['body']['processed'] == 2
        assert result['body']['successful'] == 1
        assert result['body']['failed'] == 1


class TestProcessSnsRecord:
    """Test cases for _process_sns_sqs_record function"""
    
    @patch('src.lambdas.monitor_handler._send_alert_to_feishu')
    def test_process_sns_sqs_record_sns_message(self, mock_send_alert):
        """Test processing SNS record"""
        # Setup mock
        mock_send_alert.return_value = {'status': 'sent'}
        
        # Create test record
        record = {
            'messageId': 'test_msg_id',
            'Sns': {
                'Message': json.dumps({
                    'alert_id': 'test_alert',
                    'service_name': 'test_service',
                    'alert_type': 'error',
                    'message': 'Test alert',
                    'timestamp': 1640995200,
                    'severity': 'high',
                    'metadata': {}
                })
            }
        }
        
        mock_client = Mock()
        
        # Execute
        result = _process_sns_sqs_record(record, mock_client)
        
        # Verify
        assert result['recordId'] == 'test_msg_id'
        assert result['status'] == 'success'
        assert result['alertId'] == 'test_alert'
        
        mock_send_alert.assert_called_once()
    
    @patch('src.lambdas.monitor_handler._send_alert_to_feishu')
    def test_process_sns_sqs_record_sqs_message(self, mock_send_alert):
        """Test processing SQS record"""
        # Setup mock
        mock_send_alert.return_value = {'status': 'sent'}
        
        # Create test record
        record = {
            'messageId': 'test_msg_id',
            'body': json.dumps({
                'alert_id': 'test_alert',
                'service_name': 'test_service',
                'alert_type': 'warning',
                'message': 'Test warning',
                'timestamp': 1640995200,
                'severity': 'medium',
                'metadata': {}
            })
        }
        
        mock_client = Mock()
        
        # Execute
        result = _process_sns_sqs_record(record, mock_client)
        
        # Verify
        assert result['recordId'] == 'test_msg_id'
        assert result['status'] == 'success'
        assert result['alertId'] == 'test_alert'
    
    @patch('src.lambdas.monitor_handler._send_alert_to_feishu')
    def test_process_sns_sqs_record_plain_text(self, mock_send_alert):
        """Test processing record with plain text message"""
        # Setup mock
        mock_send_alert.return_value = {'status': 'sent'}
        
        # Create test record
        record = {
            'messageId': 'test_msg_id',
            'body': 'Plain text alert message'
        }
        
        mock_client = Mock()
        
        # Execute
        result = _process_sns_sqs_record(record, mock_client)
        
        # Verify
        assert result['recordId'] == 'test_msg_id'
        assert result['status'] == 'success'
        
        # Should have created alert from plain text
        mock_send_alert.assert_called_once()
        alert_arg = mock_send_alert.call_args[0][0]
        assert alert_arg.message == 'Plain text alert message'
        assert alert_arg.service_name == 'Unknown Service'
    
    def test_process_sns_sqs_record_empty_body(self):
        """Test processing record with empty body"""
        record = {
            'messageId': 'test_msg_id',
            'body': ''
        }
        
        mock_client = Mock()
        
        with pytest.raises(ValueError, match="Empty message body"):
            _process_sns_sqs_record(record, mock_client)


class TestHandleCloudwatchEvent:
    """Test cases for _handle_cloudwatch_event function"""
    
    @patch('src.lambdas.monitor_handler._send_alert_to_feishu')
    def test_handle_cloudwatch_event_success(self, mock_send_alert):
        """Test successful CloudWatch event handling"""
        # Setup mock
        mock_send_alert.return_value = {'status': 'sent'}
        
        # Create test event
        event = {
            'region': 'us-east-1',
            'detail': {
                'alarmName': 'test-cloudwatch-alarm',
                'state': {
                    'value': 'ALARM',
                    'reason': 'Threshold crossed: 1 out of the last 1 datapoints'
                }
            }
        }
        
        mock_client = Mock()
        
        # Execute
        result = _handle_cloudwatch_event(event, mock_client)
        
        # Verify
        assert result['statusCode'] == 200
        assert 'test-cloudwatch-alarm' in result['body']['alarmName']
        assert result['body']['state'] == 'ALARM'
        
        # Verify alert was created correctly
        mock_send_alert.assert_called_once()
        alert_arg = mock_send_alert.call_args[0][0]
        assert alert_arg.service_name == 'test-cloudwatch-alarm'
        assert alert_arg.alert_type == 'error'  # ALARM maps to error
        assert alert_arg.severity == 'high'  # ALARM maps to high
    
    @patch('src.lambdas.monitor_handler._send_alert_to_feishu')
    def test_handle_cloudwatch_event_ok_state(self, mock_send_alert):
        """Test CloudWatch event with OK state"""
        # Setup mock
        mock_send_alert.return_value = {'status': 'sent'}
        
        # Create test event
        event = {
            'detail': {
                'alarmName': 'test-alarm',
                'state': {
                    'value': 'OK',
                    'reason': 'Threshold not crossed'
                }
            }
        }
        
        mock_client = Mock()
        
        # Execute
        result = _handle_cloudwatch_event(event, mock_client)
        
        # Verify
        assert result['statusCode'] == 200
        assert result['body']['state'] == 'OK'
        
        # Verify alert mapping
        alert_arg = mock_send_alert.call_args[0][0]
        assert alert_arg.alert_type == 'info'  # OK maps to info
        assert alert_arg.severity == 'low'  # OK maps to low


class TestSendAlertToFeishu:
    """Test cases for _send_alert_to_feishu function"""
    
    @patch('src.lambdas.monitor_handler._get_alert_target_chats')
    def test_send_alert_to_feishu_success(self, mock_get_targets):
        """Test successful alert sending to Feishu"""
        # Setup mocks
        mock_get_targets.return_value = ['chat1', 'chat2']
        mock_client = Mock()
        mock_client.send_card_message.return_value = {'code': 0, 'msg': 'success'}
        
        # Create test alert
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='test_service',
            alert_type='error',
            message='Test alert message',
            timestamp=1640995200,
            severity='high',
            metadata={}
        )
        
        # Execute
        result = _send_alert_to_feishu(alert, mock_client)
        
        # Verify
        assert result['status'] == 'completed'
        assert result['alert_id'] == 'test_alert'
        assert result['targets'] == 2
        assert result['successful'] == 2
        assert result['failed'] == 0
        
        # Verify client calls
        assert mock_client.send_card_message.call_count == 2
        mock_get_targets.assert_called_once_with(alert)
    
    @patch('src.lambdas.monitor_handler._get_alert_target_chats')
    def test_send_alert_to_feishu_no_targets(self, mock_get_targets):
        """Test alert sending with no target chats"""
        # Setup mock
        mock_get_targets.return_value = []
        mock_client = Mock()
        
        # Create test alert
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='test_service',
            alert_type='info',
            message='Test message',
            timestamp=1640995200,
            severity='low',
            metadata={}
        )
        
        # Execute
        result = _send_alert_to_feishu(alert, mock_client)
        
        # Verify
        assert result['status'] == 'skipped'
        assert result['reason'] == 'no_target_chats'
        
        # Should not call send_card_message
        mock_client.send_card_message.assert_not_called()
    
    @patch('src.lambdas.monitor_handler._get_alert_target_chats')
    def test_send_alert_to_feishu_partial_failure(self, mock_get_targets):
        """Test alert sending with partial failures"""
        # Setup mocks
        mock_get_targets.return_value = ['chat1', 'chat2']
        mock_client = Mock()
        # First call succeeds, second fails
        mock_client.send_card_message.side_effect = [
            {'code': 0, 'msg': 'success'},
            Exception("Send failed")
        ]
        
        # Create test alert
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='test_service',
            alert_type='warning',
            message='Test warning',
            timestamp=1640995200,
            severity='medium',
            metadata={}
        )
        
        # Execute
        result = _send_alert_to_feishu(alert, mock_client)
        
        # Verify
        assert result['status'] == 'completed'
        assert result['successful'] == 1
        assert result['failed'] == 1
        assert len(result['results']) == 2


class TestGetAlertTargetChats:
    """Test cases for _get_alert_target_chats function"""
    
    @patch.dict('os.environ', {
        'FEISHU_ALERT_CHAT_IDS': 'chat1,chat2,chat3'
    })
    def test_get_alert_target_chats_default(self):
        """Test getting default alert target chats"""
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='test_service',
            alert_type='info',
            message='Test message',
            timestamp=1640995200,
            severity='low',
            metadata={}
        )
        
        result = _get_alert_target_chats(alert)
        
        assert set(result) == {'chat1', 'chat2', 'chat3'}
    
    @patch.dict('os.environ', {
        'FEISHU_ALERT_CHAT_IDS': 'chat1,chat2',
        'FEISHU_CRITICAL_ALERT_CHAT_IDS': 'critical_chat1,critical_chat2'
    })
    def test_get_alert_target_chats_critical(self):
        """Test getting target chats for critical alert"""
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='test_service',
            alert_type='error',
            message='Critical error',
            timestamp=1640995200,
            severity='critical',
            metadata={}
        )
        
        result = _get_alert_target_chats(alert)
        
        # Should include both default and critical chats
        expected = {'chat1', 'chat2', 'critical_chat1', 'critical_chat2'}
        assert set(result) == expected
    
    @patch.dict('os.environ', {
        'FEISHU_ALERT_CHAT_IDS': 'chat1',
        'FEISHU_ALERT_CHAT_USER_SERVICE': 'user_chat1,user_chat2'
    })
    def test_get_alert_target_chats_service_specific(self):
        """Test getting target chats for specific service"""
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='user-service',  # Will be converted to USER_SERVICE
            alert_type='warning',
            message='Service warning',
            timestamp=1640995200,
            severity='medium',
            metadata={}
        )
        
        result = _get_alert_target_chats(alert)
        
        # Should include both default and service-specific chats
        expected = {'chat1', 'user_chat1', 'user_chat2'}
        assert set(result) == expected
    
    @patch.dict('os.environ', {}, clear=True)
    def test_get_alert_target_chats_no_config(self):
        """Test getting target chats with no configuration"""
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='test_service',
            alert_type='info',
            message='Test message',
            timestamp=1640995200,
            severity='low',
            metadata={}
        )
        
        result = _get_alert_target_chats(alert)
        
        assert result == []


class TestMappingFunctions:
    """Test cases for state/severity mapping functions"""
    
    def test_map_cloudwatch_state_to_type(self):
        """Test CloudWatch state to type mapping"""
        assert _map_cloudwatch_state_to_type('ALARM') == 'error'
        assert _map_cloudwatch_state_to_type('OK') == 'info'
        assert _map_cloudwatch_state_to_type('INSUFFICIENT_DATA') == 'warning'
        assert _map_cloudwatch_state_to_type('UNKNOWN') == 'info'  # Default
    
    def test_map_cloudwatch_state_to_severity(self):
        """Test CloudWatch state to severity mapping"""
        assert _map_cloudwatch_state_to_severity('ALARM') == 'high'
        assert _map_cloudwatch_state_to_severity('OK') == 'low'
        assert _map_cloudwatch_state_to_severity('INSUFFICIENT_DATA') == 'medium'
        assert _map_cloudwatch_state_to_severity('UNKNOWN') == 'medium'  # Default


class TestShouldSendAlert:
    """Test cases for _should_send_alert function"""
    
    @patch.dict('os.environ', {'FEISHU_MIN_ALERT_SEVERITY': 'medium'})
    def test_should_send_alert_above_threshold(self):
        """Test alert sending for severity above threshold"""
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='test_service',
            alert_type='error',
            message='High severity alert',
            timestamp=1640995200,
            severity='high',
            metadata={}
        )
        
        result = _should_send_alert(alert)
        assert result is True
    
    @patch.dict('os.environ', {'FEISHU_MIN_ALERT_SEVERITY': 'high'})
    def test_should_send_alert_below_threshold(self):
        """Test alert sending for severity below threshold"""
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='test_service',
            alert_type='warning',
            message='Medium severity alert',
            timestamp=1640995200,
            severity='medium',
            metadata={}
        )
        
        result = _should_send_alert(alert)
        assert result is False
    
    @patch.dict('os.environ', {'FEISHU_EXCLUDED_SERVICES': 'test-service,another-service'})
    def test_should_send_alert_excluded_service(self):
        """Test alert sending for excluded service"""
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='test-service',
            alert_type='error',
            message='Alert from excluded service',
            timestamp=1640995200,
            severity='critical',
            metadata={}
        )
        
        result = _should_send_alert(alert)
        assert result is False


class TestFormatAlertSummary:
    """Test cases for _format_alert_summary function"""
    
    def test_format_alert_summary_critical_error(self):
        """Test formatting critical error alert summary"""
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='critical_service',
            alert_type='error',
            message='Critical error occurred',
            timestamp=1640995200,
            severity='critical',
            metadata={}
        )
        
        result = _format_alert_summary(alert)
        
        assert '🔴' in result  # Critical severity emoji
        assert '❌' in result  # Error type emoji
        assert 'critical_service' in result
        assert 'ERROR' in result
    
    def test_format_alert_summary_medium_warning(self):
        """Test formatting medium warning alert summary"""
        alert = MonitorAlert(
            alert_id='test_alert',
            service_name='warning_service',
            alert_type='warning',
            message='Warning message',
            timestamp=1640995200,
            severity='medium',
            metadata={}
        )
        
        result = _format_alert_summary(alert)
        
        assert '🟡' in result  # Medium severity emoji
        assert '⚠️' in result  # Warning type emoji
        assert 'warning_service' in result
        assert 'WARNING' in result