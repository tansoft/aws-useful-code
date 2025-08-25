#!/usr/bin/env python3
"""
飞书机器人系统部署脚本
使用CloudFormation部署AWS资源
"""

import os
import sys
import json
import zipfile
import argparse
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class FeishuBotDeployer:
    """飞书机器人部署器"""
    
    def __init__(self, region: str = 'us-east-1', profile: Optional[str] = None):
        """
        初始化部署器
        
        Args:
            region: AWS区域
            profile: AWS配置文件
        """
        self.region = region
        self.profile = profile
        
        # 初始化AWS客户端
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.cloudformation = session.client('cloudformation', region_name=region)
        self.lambda_client = session.client('lambda', region_name=region)
        self.s3_client = session.client('s3', region_name=region)
        
        # 项目路径
        self.project_root = Path(__file__).parent.parent
        self.deployment_dir = self.project_root / 'deployment'
        self.src_dir = self.project_root / 'src'
        
    def deploy(self, stack_name: str, environment: str, parameters: Dict[str, str],
               update_code: bool = True) -> Dict[str, Any]:
        """
        部署飞书机器人系统
        
        Args:
            stack_name: CloudFormation栈名称
            environment: 部署环境
            parameters: 部署参数
            update_code: 是否更新Lambda代码
            
        Returns:
            dict: 部署结果
        """
        try:
            print(f"开始部署飞书机器人系统...")
            print(f"栈名称: {stack_name}")
            print(f"环境: {environment}")
            print(f"区域: {self.region}")
            
            # 验证参数
            self._validate_parameters(parameters)
            
            # 检查栈是否存在
            stack_exists = self._stack_exists(stack_name)
            
            if stack_exists:
                print(f"更新现有栈: {stack_name}")
                result = self._update_stack(stack_name, parameters)
            else:
                print(f"创建新栈: {stack_name}")
                result = self._create_stack(stack_name, parameters)
            
            # 等待栈操作完成
            print("等待栈操作完成...")
            self._wait_for_stack_operation(stack_name, 'CREATE' if not stack_exists else 'UPDATE')
            
            # 获取栈输出
            outputs = self._get_stack_outputs(stack_name)
            
            if update_code:
                # 更新Lambda函数代码
                print("更新Lambda函数代码...")
                self._update_lambda_functions(stack_name, environment)
            
            print("部署完成!")
            return {
                'status': 'success',
                'stack_name': stack_name,
                'outputs': outputs
            }
            
        except Exception as e:
            print(f"部署失败: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _validate_parameters(self, parameters: Dict[str, str]) -> None:
        """验证部署参数"""
        required_params = [
            'FeishuAppId',
            'FeishuAppSecret', 
            'FeishuVerificationToken',
            'FeishuEncryptKey'
        ]
        
        missing_params = [param for param in required_params if not parameters.get(param)]
        if missing_params:
            raise ValueError(f"缺少必需参数: {', '.join(missing_params)}")
    
    def _stack_exists(self, stack_name: str) -> bool:
        """检查CloudFormation栈是否存在"""
        try:
            self.cloudformation.describe_stacks(StackName=stack_name)
            return True
        except ClientError as e:
            if 'does not exist' in str(e):
                return False
            raise
    
    def _create_stack(self, stack_name: str, parameters: Dict[str, str]) -> Dict[str, Any]:
        """创建CloudFormation栈"""
        template_path = self.deployment_dir / 'cloudformation-template.yaml'
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_body = f.read()
        
        # 转换参数格式
        cf_parameters = [
            {'ParameterKey': key, 'ParameterValue': value}
            for key, value in parameters.items()
        ]
        
        response = self.cloudformation.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=cf_parameters,
            Capabilities=['CAPABILITY_NAMED_IAM'],
            Tags=[
                {'Key': 'Project', 'Value': 'feishu-bot'},
                {'Key': 'Environment', 'Value': parameters.get('Environment', 'dev')},
                {'Key': 'ManagedBy', 'Value': 'CloudFormation'}
            ]
        )
        
        return response
    
    def _update_stack(self, stack_name: str, parameters: Dict[str, str]) -> Dict[str, Any]:
        """更新CloudFormation栈"""
        template_path = self.deployment_dir / 'cloudformation-template.yaml'
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_body = f.read()
        
        # 转换参数格式
        cf_parameters = [
            {'ParameterKey': key, 'ParameterValue': value}
            for key, value in parameters.items()
        ]
        
        try:
            response = self.cloudformation.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=cf_parameters,
                Capabilities=['CAPABILITY_NAMED_IAM']
            )
            return response
        except ClientError as e:
            if 'No updates are to be performed' in str(e):
                print("栈无需更新")
                return {'StackId': stack_name}
            raise
    
    def _wait_for_stack_operation(self, stack_name: str, operation: str) -> None:
        """等待栈操作完成"""
        waiter_name = f"stack_{operation.lower()}_complete"
        
        try:
            waiter = self.cloudformation.get_waiter(waiter_name)
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 60
                }
            )
        except Exception as e:
            # 获取栈事件以了解失败原因
            events = self._get_stack_events(stack_name)
            failed_events = [
                event for event in events
                if event.get('ResourceStatus', '').endswith('_FAILED')
            ]
            
            if failed_events:
                print("栈操作失败事件:")
                for event in failed_events[:5]:  # 显示最近5个失败事件
                    print(f"  - {event.get('LogicalResourceId')}: {event.get('ResourceStatusReason')}")
            
            raise Exception(f"栈操作失败: {str(e)}")
    
    def _get_stack_events(self, stack_name: str) -> list:
        """获取栈事件"""
        try:
            response = self.cloudformation.describe_stack_events(StackName=stack_name)
            return response.get('StackEvents', [])
        except Exception:
            return []
    
    def _get_stack_outputs(self, stack_name: str) -> Dict[str, str]:
        """获取栈输出"""
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            stacks = response.get('Stacks', [])
            
            if not stacks:
                return {}
            
            outputs = stacks[0].get('Outputs', [])
            return {
                output['OutputKey']: output['OutputValue']
                for output in outputs
            }
        except Exception as e:
            print(f"获取栈输出失败: {str(e)}")
            return {}
    
    def _update_lambda_functions(self, stack_name: str, environment: str) -> None:
        """更新Lambda函数代码"""
        # 创建部署包
        zip_path = self._create_deployment_package()
        
        try:
            # 获取Lambda函数名称
            function_names = [
                f"feishu-bot-{environment}-receive",
                f"feishu-bot-{environment}-process", 
                f"feishu-bot-{environment}-monitor"
            ]
            
            # 读取ZIP文件
            with open(zip_path, 'rb') as f:
                zip_content = f.read()
            
            # 更新每个Lambda函数
            for function_name in function_names:
                try:
                    print(f"更新Lambda函数: {function_name}")
                    self.lambda_client.update_function_code(
                        FunctionName=function_name,
                        ZipFile=zip_content
                    )
                    print(f"✓ {function_name} 更新成功")
                except ClientError as e:
                    if 'ResourceNotFoundException' in str(e):
                        print(f"⚠ Lambda函数 {function_name} 不存在，跳过")
                    else:
                        print(f"✗ 更新 {function_name} 失败: {str(e)}")
                        
        finally:
            # 清理临时文件
            if os.path.exists(zip_path):
                os.remove(zip_path)
    
    def _create_deployment_package(self) -> str:
        """创建Lambda部署包"""
        print("创建Lambda部署包...")
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 复制源代码
            src_dest = temp_path / 'src'
            shutil.copytree(self.src_dir, src_dest)
            
            # 安装依赖
            requirements_file = self.project_root / 'requirements.txt'
            if requirements_file.exists():
                print("安装Python依赖...")
                os.system(f"pip install -r {requirements_file} -t {temp_path}")
            
            # 创建ZIP文件
            zip_path = temp_path.parent / 'deployment-package.zip'
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_path):
                    for file in files:
                        file_path = Path(root) / file
                        arc_name = file_path.relative_to(temp_path)
                        zipf.write(file_path, arc_name)
            
            # 移动到项目目录
            final_zip_path = self.project_root / 'deployment-package.zip'
            shutil.move(zip_path, final_zip_path)
            
            print(f"部署包创建完成: {final_zip_path}")
            return str(final_zip_path)
    
    def delete_stack(self, stack_name: str) -> Dict[str, Any]:
        """删除CloudFormation栈"""
        try:
            print(f"删除栈: {stack_name}")
            
            self.cloudformation.delete_stack(StackName=stack_name)
            
            # 等待删除完成
            print("等待栈删除完成...")
            waiter = self.cloudformation.get_waiter('stack_delete_complete')
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 60
                }
            )
            
            print("栈删除完成!")
            return {'status': 'success'}
            
        except Exception as e:
            print(f"删除栈失败: {str(e)}")
            return {'status': 'failed', 'error': str(e)}


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
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
            return config


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='飞书机器人系统部署工具')
    parser.add_argument('--stack-name', required=True, help='CloudFormation栈名称')
    parser.add_argument('--environment', default='dev', help='部署环境')
    parser.add_argument('--region', default='us-east-1', help='AWS区域')
    parser.add_argument('--profile', help='AWS配置文件')
    parser.add_argument('--config-file', help='配置文件路径')
    parser.add_argument('--delete', action='store_true', help='删除栈')
    parser.add_argument('--no-code-update', action='store_true', help='不更新Lambda代码')
    
    # 飞书配置参数
    parser.add_argument('--feishu-app-id', help='飞书应用ID')
    parser.add_argument('--feishu-app-secret', help='飞书应用密钥')
    parser.add_argument('--feishu-verification-token', help='飞书验证Token')
    parser.add_argument('--feishu-encrypt-key', help='飞书加密密钥')
    parser.add_argument('--feishu-bot-name', default='FeishuBot', help='机器人名称')
    parser.add_argument('--feishu-alert-chat-ids', default='', help='告警群聊ID')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    
    args = parser.parse_args()
    
    try:
        # 初始化部署器
        deployer = FeishuBotDeployer(region=args.region, profile=args.profile)
        
        if args.delete:
            # 删除栈
            result = deployer.delete_stack(args.stack_name)
        else:
            # 准备部署参数
            parameters = {
                'Environment': args.environment,
                'LogLevel': args.log_level,
                'FeishuBotName': args.feishu_bot_name,
                'FeishuAlertChatIds': args.feishu_alert_chat_ids
            }
            
            # 从配置文件加载参数
            if args.config_file:
                config_params = load_config_file(args.config_file)
                parameters.update(config_params)
            
            # 从命令行参数覆盖
            if args.feishu_app_id:
                parameters['FeishuAppId'] = args.feishu_app_id
            if args.feishu_app_secret:
                parameters['FeishuAppSecret'] = args.feishu_app_secret
            if args.feishu_verification_token:
                parameters['FeishuVerificationToken'] = args.feishu_verification_token
            if args.feishu_encrypt_key:
                parameters['FeishuEncryptKey'] = args.feishu_encrypt_key
            
            # 部署栈
            result = deployer.deploy(
                stack_name=args.stack_name,
                environment=args.environment,
                parameters=parameters,
                update_code=not args.no_code_update
            )
        
        # 输出结果
        if result['status'] == 'success':
            print("\n=== 部署结果 ===")
            if 'outputs' in result:
                for key, value in result['outputs'].items():
                    print(f"{key}: {value}")
            sys.exit(0)
        else:
            print(f"\n部署失败: {result.get('error', '未知错误')}")
            sys.exit(1)
            
    except NoCredentialsError:
        print("错误: 未找到AWS凭证。请配置AWS CLI或设置环境变量。")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()