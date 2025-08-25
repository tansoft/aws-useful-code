"""
pytest配置文件
提供测试夹具和配置
"""

import os
import pytest
import boto3
from moto import mock_aws
from unittest.mock import patch, Mock


@pytest.fixture
def aws_credentials():
    """Mock AWS凭证"""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def feishu_config():
    """飞书配置夹具"""
    config = {
        'FEISHU_APP_ID': 'cli_test_app_id',
        'FEISHU_APP_SECRET': 'test_app_secret',
        'FEISHU_VERIFICATION_TOKEN': 'test_verification_token',
        'FEISHU_ENCRYPT_KEY': 'test_encrypt_key',
        'FEISHU_BOT_NAME': 'TestBot',
        'FEISHU_ALERT_CHAT_IDS': 'chat1,chat2'
    }
    
    with patch.dict(os.environ, config):
        yield config


@pytest.fixture
def sqs_queue():
    """SQS队列夹具"""
    with mock_aws():
        sqs = boto3.resource('sqs', region_name='us-east-1')
        queue = sqs.create_queue(QueueName='test-queue')
        
        # 设置环境变量
        queue_url = f"https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        with patch.dict(os.environ, {'SQS_QUEUE_URL': queue_url}):
            yield queue


@pytest.fixture
def lambda_context():
    """Lambda上下文夹具"""
    context = Mock()
    context.function_name = 'test-function'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = 'test-request-id'
    context.log_group_name = '/aws/lambda/test-function'
    context.log_stream_name = '2023/01/01/[$LATEST]test-stream'
    
    return context


@pytest.fixture
def mock_feishu_client():
    """Mock飞书客户端"""
    with patch('src.shared.feishu_client.FeishuClient') as mock_client_class:
        mock_client = Mock()
        mock_client.send_text_message.return_value = {'code': 0, 'msg': 'success'}
        mock_client.send_card_message.return_value = {'code': 0, 'msg': 'success'}
        mock_client.get_access_token.return_value = 'mock_access_token'
        mock_client_class.return_value = mock_client
        
        yield mock_client


@pytest.fixture
def sample_webhook_event():
    """示例webhook事件"""
    import json
    import time
    
    return {
        'httpMethod': 'POST',
        'headers': {
            'Content-Type': 'application/json',
            'x-lark-request-timestamp': str(int(time.time())),
            'x-lark-request-nonce': 'test_nonce',
            'x-lark-signature': 'test_signature'
        },
        'body': json.dumps({
            'header': {
                'event_type': 'im.message.receive_v1',
                'app_id': 'cli_test_app_id'
            },
            'event': {
                'sender': {
                    'sender_type': 'user',
                    'sender_id': {
                        'user_id': 'test_user_id'
                    }
                },
                'message': {
                    'message_id': 'test_message_id',
                    'chat_id': 'test_chat_id',
                    'message_type': 'text',
                    'content': '{"text": "Hello bot"}',
                    'mentions': []
                },
                'msg_timestamp': str(int(time.time() * 1000))
            }
        })
    }


@pytest.fixture
def sample_sqs_event():
    """示例SQS事件"""
    import json
    import time
    
    return {
        'Records': [
            {
                'messageId': 'test_sqs_message_id',
                'body': json.dumps({
                    'message_id': 'test_message_id',
                    'user_id': 'test_user_id',
                    'chat_id': 'test_chat_id',
                    'message_type': 'text',
                    'content': 'Hello bot',
                    'timestamp': int(time.time()),
                    'app_id': 'cli_test_app_id',
                    'mentions': []
                })
            }
        ]
    }


@pytest.fixture
def sample_monitor_event():
    """示例监控事件"""
    import time
    
    return {
        'alert_id': 'test_alert_123',
        'service_name': 'test_service',
        'alert_type': 'error',
        'message': 'Service is experiencing issues',
        'timestamp': int(time.time()),
        'severity': 'high',
        'metadata': {
            'region': 'us-east-1',
            'instance': 'i-123456'
        }
    }


# 测试标记
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试项目收集"""
    # 为集成测试添加标记
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        if "performance" in item.name.lower():
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        
        if "security" in item.name.lower():
            item.add_marker(pytest.mark.security)