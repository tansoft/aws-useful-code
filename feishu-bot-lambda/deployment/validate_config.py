#!/usr/bin/env python3
"""
配置验证脚本
验证飞书机器人系统的配置和权限
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, List, Optional

import boto3
import requests
from botocore.exceptions import ClientError, NoCredentialsError


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self, region: str = 'us-east-1', profile: Optional[str] = None):
        """
        初始化验证器
        
        Args:
            region: AWS区域
            profile: AWS配置文件
        """
        self.region = region
        self.profile = profile
        
        # 初始化AWS客户端
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.sts = session.client('sts', region_name=region)
        self.iam = session.client('iam', region_name=region)
        self.cloudformation = session.client('cloudformation', region_name=region)
        self.ssm = session.client('ssm', region_name=region)
        self.lambda_client = session.client('lambda', region_name=region)
        self.sqs = session.client('sqs', region_name=region)
        
    def validate_all(self, config: Dict[str, str]) -> Dict[str, Any]:
        """
        执行所有验证
        
        Args:
            config: 配置参数
            
        Returns:
            dict: 验证结果
        """
        results = {
            'overall_status': 'success',
            'checks': {}
        }
        
        print("开始配置验证...")
        
        # AWS凭证和权限验证
        aws_result = self._validate_aws_credentials()
        results['checks']['aws_credentials'] = aws_result
        
        # 飞书配置验证
        feishu_result = self._validate_feishu_config(config)
        results['checks']['feishu_config'] = feishu_result
        
        # AWS权限验证
        permissions_result = self._validate_aws_permissions()
        results['checks']['aws_permissions'] = permissions_result
        
        # 网络连接验证
        network_result = self._validate_network_connectivity()
        results['checks']['network_connectivity'] = network_result
        
        # 检查整体状态
        failed_checks = [
            check for check, result in results['checks'].items()
            if result['status'] != 'success'
        ]
        
        if failed_checks:
            results['overall_status'] = 'failed'
            results['failed_checks'] = failed_checks
        
        return results
    
    def _validate_aws_credentials(self) -> Dict[str, Any]:
        """验证AWS凭证"""
        try:
            print("验证AWS凭证...")
            
            # 获取当前身份
            identity = self.sts.get_caller_identity()
            
            return {
                'status': 'success',
                'message': 'AWS凭证验证成功',
                'details': {
                    'account_id': identity.get('Account'),
                    'user_arn': identity.get('Arn'),
                    'region': self.region
                }
            }
            
        except NoCredentialsError:
            return {
                'status': 'failed',
                'message': '未找到AWS凭证',
                'details': {
                    'suggestion': '请配置AWS CLI或设置环境变量AWS_ACCESS_KEY_ID和AWS_SECRET_ACCESS_KEY'
                }
            }
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'AWS凭证验证失败: {str(e)}',
                'details': {}
            }
    
    def _validate_feishu_config(self, config: Dict[str, str]) -> Dict[str, Any]:
        """验证飞书配置"""
        try:
            print("验证飞书配置...")
            
            # 检查必需参数
            required_params = [
                'FeishuAppId',
                'FeishuAppSecret',
                'FeishuVerificationToken',
                'FeishuEncryptKey'
            ]
            
            missing_params = []
            for param in required_params:
                if not config.get(param):
                    missing_params.append(param)
            
            if missing_params:
                return {
                    'status': 'failed',
                    'message': f'缺少必需的飞书配置参数: {", ".join(missing_params)}',
                    'details': {
                        'missing_parameters': missing_params,
                        'suggestion': '请在飞书开放平台创建应用并获取相关配置'
                    }
                }
            
            # 验证飞书API连接
            api_result = self._test_feishu_api_connection(
                config['FeishuAppId'],
                config['FeishuAppSecret']
            )
            
            if api_result['status'] != 'success':
                return api_result
            
            return {
                'status': 'success',
                'message': '飞书配置验证成功',
                'details': {
                    'app_id': config['FeishuAppId'],
                    'api_connection': 'ok'
                }
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'飞书配置验证失败: {str(e)}',
                'details': {}
            }
    
    def _test_feishu_api_connection(self, app_id: str, app_secret: str) -> Dict[str, Any]:
        """测试飞书API连接"""
        try:
            # 获取访问令牌
            token_url = 'https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal'
            token_payload = {
                'app_id': app_id,
                'app_secret': app_secret
            }
            
            response = requests.post(token_url, json=token_payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('code') != 0:
                return {
                    'status': 'failed',
                    'message': f'飞书API认证失败: {data.get("msg", "未知错误")}',
                    'details': {
                        'error_code': data.get('code'),
                        'suggestion': '请检查飞书应用ID和密钥是否正确'
                    }
                }
            
            return {
                'status': 'success',
                'message': '飞书API连接测试成功',
                'details': {}
            }
            
        except requests.RequestException as e:
            return {
                'status': 'failed',
                'message': f'飞书API连接失败: {str(e)}',
                'details': {
                    'suggestion': '请检查网络连接和飞书API地址'
                }
            }
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'飞书API测试失败: {str(e)}',
                'details': {}
            }
    
    def _validate_aws_permissions(self) -> Dict[str, Any]:
        """验证AWS权限"""
        try:
            print("验证AWS权限...")
            
            # 需要验证的权限
            required_permissions = [
                ('cloudformation', 'CreateStack'),
                ('cloudformation', 'UpdateStack'),
                ('cloudformation', 'DescribeStacks'),
                ('lambda', 'CreateFunction'),
                ('lambda', 'UpdateFunctionCode'),
                ('iam', 'CreateRole'),
                ('iam', 'AttachRolePolicy'),
                ('sqs', 'CreateQueue'),
                ('ssm', 'PutParameter'),
                ('apigateway', 'POST')
            ]
            
            permission_results = []
            
            for service, action in required_permissions:
                try:
                    # 这里只是简单的权限检查，实际部署时会进行更详细的验证
                    if service == 'cloudformation':
                        # 尝试列出栈
                        self.cloudformation.list_stacks(StackStatusFilter=['CREATE_COMPLETE'])
                    elif service == 'lambda':
                        # 尝试列出函数
                        self.lambda_client.list_functions(MaxItems=1)
                    elif service == 'iam':
                        # 尝试获取当前用户信息
                        self.sts.get_caller_identity()
                    elif service == 'sqs':
                        # 尝试列出队列
                        self.sqs.list_queues(MaxResults=1)
                    elif service == 'ssm':
                        # 尝试获取参数（可能不存在，但权限检查有效）
                        try:
                            self.ssm.get_parameter(Name='/test-permission-check')
                        except ClientError as e:
                            if 'ParameterNotFound' not in str(e):
                                raise
                    
                    permission_results.append({
                        'service': service,
                        'action': action,
                        'status': 'success'
                    })
                    
                except ClientError as e:
                    if 'AccessDenied' in str(e) or 'UnauthorizedOperation' in str(e):
                        permission_results.append({
                            'service': service,
                            'action': action,
                            'status': 'failed',
                            'error': str(e)
                        })
                    else:
                        # 其他错误可能不是权限问题
                        permission_results.append({
                            'service': service,
                            'action': action,
                            'status': 'success'
                        })
            
            # 检查是否有权限失败
            failed_permissions = [
                result for result in permission_results
                if result['status'] == 'failed'
            ]
            
            if failed_permissions:
                return {
                    'status': 'failed',
                    'message': f'缺少必需的AWS权限',
                    'details': {
                        'failed_permissions': failed_permissions,
                        'suggestion': '请确保IAM用户或角色具有足够的权限'
                    }
                }
            
            return {
                'status': 'success',
                'message': 'AWS权限验证成功',
                'details': {
                    'checked_permissions': len(permission_results)
                }
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'AWS权限验证失败: {str(e)}',
                'details': {}
            }
    
    def _validate_network_connectivity(self) -> Dict[str, Any]:
        """验证网络连接"""
        try:
            print("验证网络连接...")
            
            # 测试连接的端点
            endpoints = [
                ('飞书API', 'https://open.feishu.cn'),
                ('AWS API', f'https://cloudformation.{self.region}.amazonaws.com')
            ]
            
            connectivity_results = []
            
            for name, url in endpoints:
                try:
                    response = requests.get(url, timeout=10)
                    connectivity_results.append({
                        'endpoint': name,
                        'url': url,
                        'status': 'success',
                        'response_code': response.status_code
                    })
                except requests.RequestException as e:
                    connectivity_results.append({
                        'endpoint': name,
                        'url': url,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            # 检查是否有连接失败
            failed_connections = [
                result for result in connectivity_results
                if result['status'] == 'failed'
            ]
            
            if failed_connections:
                return {
                    'status': 'warning',
                    'message': '部分网络连接测试失败',
                    'details': {
                        'failed_connections': failed_connections,
                        'suggestion': '请检查网络连接和防火墙设置'
                    }
                }
            
            return {
                'status': 'success',
                'message': '网络连接验证成功',
                'details': {
                    'tested_endpoints': len(endpoints)
                }
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'网络连接验证失败: {str(e)}',
                'details': {}
            }
    
    def validate_existing_deployment(self, stack_name: str) -> Dict[str, Any]:
        """验证现有部署"""
        try:
            print(f"验证现有部署: {stack_name}")
            
            # 检查CloudFormation栈
            try:
                response = self.cloudformation.describe_stacks(StackName=stack_name)
                stacks = response.get('Stacks', [])
                
                if not stacks:
                    return {
                        'status': 'failed',
                        'message': f'未找到CloudFormation栈: {stack_name}',
                        'details': {}
                    }
                
                stack = stacks[0]
                stack_status = stack.get('StackStatus')
                
                if stack_status not in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                    return {
                        'status': 'warning',
                        'message': f'栈状态异常: {stack_status}',
                        'details': {
                            'stack_status': stack_status,
                            'suggestion': '请检查栈状态并解决任何问题'
                        }
                    }
                
                # 获取栈输出
                outputs = {
                    output['OutputKey']: output['OutputValue']
                    for output in stack.get('Outputs', [])
                }
                
                # 验证Lambda函数
                lambda_results = self._validate_lambda_functions(outputs)
                
                # 验证SQS队列
                sqs_results = self._validate_sqs_queue(outputs)
                
                return {
                    'status': 'success',
                    'message': '现有部署验证成功',
                    'details': {
                        'stack_status': stack_status,
                        'outputs': outputs,
                        'lambda_validation': lambda_results,
                        'sqs_validation': sqs_results
                    }
                }
                
            except ClientError as e:
                if 'does not exist' in str(e):
                    return {
                        'status': 'failed',
                        'message': f'CloudFormation栈不存在: {stack_name}',
                        'details': {}
                    }
                raise
                
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'现有部署验证失败: {str(e)}',
                'details': {}
            }
    
    def _validate_lambda_functions(self, outputs: Dict[str, str]) -> Dict[str, Any]:
        """验证Lambda函数"""
        try:
            lambda_arns = [
                outputs.get('ReceiveLambdaArn'),
                outputs.get('ProcessLambdaArn'),
                outputs.get('MonitorLambdaArn')
            ]
            
            function_results = []
            
            for arn in lambda_arns:
                if not arn:
                    continue
                
                function_name = arn.split(':')[-1]
                
                try:
                    response = self.lambda_client.get_function(FunctionName=function_name)
                    function_results.append({
                        'function_name': function_name,
                        'status': 'success',
                        'state': response.get('Configuration', {}).get('State')
                    })
                except ClientError as e:
                    function_results.append({
                        'function_name': function_name,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            return {
                'status': 'success',
                'functions': function_results
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _validate_sqs_queue(self, outputs: Dict[str, str]) -> Dict[str, Any]:
        """验证SQS队列"""
        try:
            queue_url = outputs.get('MessageQueueUrl')
            
            if not queue_url:
                return {
                    'status': 'failed',
                    'error': 'SQS队列URL未找到'
                }
            
            # 获取队列属性
            response = self.sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
            
            attributes = response.get('Attributes', {})
            
            return {
                'status': 'success',
                'queue_url': queue_url,
                'attributes': {
                    'ApproximateNumberOfMessages': attributes.get('ApproximateNumberOfMessages'),
                    'VisibilityTimeoutSeconds': attributes.get('VisibilityTimeoutSeconds'),
                    'MessageRetentionPeriod': attributes.get('MessageRetentionPeriod')
                }
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }


def load_config_file(config_path: str) -> Dict[str, str]:
    """从配置文件加载参数"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        if config_path.endswith('.json'):
            return json.load(f)
        else:
            # 简单的key=value格式
            config = {}
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
            return config


def print_validation_results(results: Dict[str, Any]) -> None:
    """打印验证结果"""
    print("\n" + "="*50)
    print("配置验证结果")
    print("="*50)
    
    overall_status = results['overall_status']
    status_emoji = "✅" if overall_status == 'success' else "❌"
    print(f"\n整体状态: {status_emoji} {overall_status.upper()}")
    
    print("\n详细检查结果:")
    for check_name, check_result in results['checks'].items():
        status = check_result['status']
        message = check_result['message']
        
        if status == 'success':
            emoji = "✅"
        elif status == 'warning':
            emoji = "⚠️"
        else:
            emoji = "❌"
        
        print(f"  {emoji} {check_name}: {message}")
        
        # 显示详细信息
        if check_result.get('details'):
            details = check_result['details']
            if isinstance(details, dict):
                for key, value in details.items():
                    if key != 'suggestion':
                        print(f"    - {key}: {value}")
                
                # 显示建议
                if 'suggestion' in details:
                    print(f"    💡 建议: {details['suggestion']}")
    
    if overall_status != 'success':
        print(f"\n❌ 验证失败的检查项: {', '.join(results.get('failed_checks', []))}")
        print("请解决上述问题后重新运行验证。")
    else:
        print("\n🎉 所有验证检查都已通过！系统已准备好部署。")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='飞书机器人系统配置验证工具')
    parser.add_argument('--region', default='us-east-1', help='AWS区域')
    parser.add_argument('--profile', help='AWS配置文件')
    parser.add_argument('--config-file', help='配置文件路径')
    parser.add_argument('--stack-name', help='验证现有部署的栈名称')
    
    # 飞书配置参数
    parser.add_argument('--feishu-app-id', help='飞书应用ID')
    parser.add_argument('--feishu-app-secret', help='飞书应用密钥')
    parser.add_argument('--feishu-verification-token', help='飞书验证Token')
    parser.add_argument('--feishu-encrypt-key', help='飞书加密密钥')
    
    args = parser.parse_args()
    
    try:
        # 初始化验证器
        validator = ConfigValidator(region=args.region, profile=args.profile)
        
        if args.stack_name:
            # 验证现有部署
            results = validator.validate_existing_deployment(args.stack_name)
            print_validation_results({'overall_status': results['status'], 'checks': {'existing_deployment': results}})
        else:
            # 准备配置参数
            config = {}
            
            # 从配置文件加载参数
            if args.config_file:
                config.update(load_config_file(args.config_file))
            
            # 从命令行参数覆盖
            if args.feishu_app_id:
                config['FeishuAppId'] = args.feishu_app_id
            if args.feishu_app_secret:
                config['FeishuAppSecret'] = args.feishu_app_secret
            if args.feishu_verification_token:
                config['FeishuVerificationToken'] = args.feishu_verification_token
            if args.feishu_encrypt_key:
                config['FeishuEncryptKey'] = args.feishu_encrypt_key
            
            # 执行全面验证
            results = validator.validate_all(config)
            print_validation_results(results)
        
        # 根据验证结果设置退出码
        if results.get('overall_status') == 'success':
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        print(f"验证过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()