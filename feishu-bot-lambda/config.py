"""
飞书机器人系统配置文件
"""
import os

# 飞书应用配置
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')
FEISHU_VERIFICATION_TOKEN = os.environ.get('FEISHU_VERIFICATION_TOKEN', '')
FEISHU_ENCRYPT_KEY = os.environ.get('FEISHU_ENCRYPT_KEY', '')

# AWS配置
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')
PARAMETER_STORE_PREFIX = os.environ.get('PARAMETER_STORE_PREFIX', '/feishu-bot')

# 系统配置
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
MAX_RETRY_ATTEMPTS = int(os.environ.get('MAX_RETRY_ATTEMPTS', '3'))
RETRY_DELAY_BASE = int(os.environ.get('RETRY_DELAY_BASE', '1'))

# 飞书API配置
FEISHU_API_BASE_URL = 'https://open.feishu.cn/open-apis'
FEISHU_WEBHOOK_TIMEOUT = 30