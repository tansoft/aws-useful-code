#!/usr/bin/env python3
"""
部署验证脚本

此脚本用于验证飞书机器人系统的部署状态，确保所有组件正常工作。
"""

import json
import time
import boto3
import logging
import argparse
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class DeploymentStatus:
    """部署状态"""
    component: str
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None

class DeploymentVerifier:
    """部署验证器"""
    
    def __init__(self, stack_name: str, region: str):
        self.stack_name = stack_name
        self.region = region
        
        # 初始化AWS客户端
        self.cloudformation = boto3.client('cloudformation', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.sqs_client = boto3.client('sqs', region_name=region)
        self.apigateway = boto3.client('apigateway', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.logs_client = boto3.client('logs', region_name=region)
        self.ssm_client = boto3.client('ssm', region_name=region)
        
        self.statuses: List[DeploymentStatus] = []
    
    def verify_deployment(self) -> Dict[str, Any]:
        """验证完整部署"""
        logger.info(f"开始验证部署: {self.stack_name}")
        
        verification_steps = [
            ("CloudFormation栈", self._verify_cloudformation_stack),
            ("Lambda函数", self._verify_lambda_functions),
            ("SQS队列", self._verify_sqs_queues),
            ("API Gateway", self._verify_api_gateway),
            ("IAM角色和权限", self._verify_iam_roles),
            ("Parameter Store", self._verify_parameter_store),
            ("CloudWatch监控", self._verify_cloudwatch_monitoring),
            ("日志配置", self._verify_logging_configuration)
        ]
        
        for step_name, verify_func in verification_steps:
            logger.info(f"验证: {step_name}")
            try:
                verify_func()
                logger.info(f"✅ {step_name} 验证通过")
            except Exception as e:
                logger.error(f"❌ {step_name} 验证失败: {e}")
                self.statuses.append(DeploymentStatus(
                    component=step_name,
                    status="FAILED",
                    message=str(e)
                ))
        
        return self._generate_verification_report()
    
    def _verify_cloudformation_stack(self):
        """验证CloudFormation栈"""
        try:
            response = self.cloudformation.describe_stacks(
                StackName=self.stack_name
            )
            
            stack = response['Stacks'][0]
            stack_status = stack['StackStatus']
            
            if stack_status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                self.statuses.append(DeploymentStatus(
                    component="CloudFormation栈",
                    status="HEALTHY",
                    message=f"栈状态: {stack_status}",
                    details={
                        'stack_id': stack['StackId'],
                        'creation_time': stack['CreationTime'].isoformat(),
                        'stack_status': stack_status
                    }
                ))
                
                # 获取栈输出
                outputs = {output['OutputKey']: output['OutputValue'] 
                          for output in stack.get('Outputs', [])}
                
                if outputs:
                    logger.info("栈输出:")
                    for key, value in outputs.items():
                        logger.info(f"  {key}: {value}")
                
            else:
                raise Exception(f"栈状态异常: {stack_status}")
                
        except self.cloudformation.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                raise Exception(f"栈不存在: {self.stack_name}")
            else:
                raise Exception(f"获取栈信息失败: {e}")
    
    def _verify_lambda_functions(self):
        """验证Lambda函数"""
        expected_functions = [
            f"{self.stack_name}-receive",
            f"{self.stack_name}-process",
            f"{self.stack_name}-monitor"
        ]
        
        for func_name in expected_functions:
            try:
                response = self.lambda_client.get_function(
                    FunctionName=func_name
                )
                
                config = response['Configuration']
                state = config['State']
                
                if state == 'Active':
                    self.statuses.append(DeploymentStatus(
                        component=f"Lambda函数-{func_name}",
                        status="HEALTHY",
                        message="函数状态正常",
                        details={
                            'function_name': config['FunctionName'],
                            'runtime': config['Runtime'],
                            'memory_size': config['MemorySize'],
                            'timeout': config['Timeout'],
                            'last_modified': config['LastModified']
                        }
                    ))
                else:
                    raise Exception(f"函数状态异常: {state}")
                    
            except self.lambda_client.exceptions.ResourceNotFoundException:
                raise Exception(f"Lambda函数不存在: {func_name}")
            except Exception as e:
                raise Exception(f"验证Lambda函数失败: {e}")
    
    def _verify_sqs_queues(self):
        """验证SQS队列"""
        expected_queues = [
            f"{self.stack_name}-messages",
            f"{self.stack_name}-messages-dlq"
        ]
        
        for queue_name in expected_queues:
            try:
                response = self.sqs_client.get_queue_url(
                    QueueName=queue_name
                )
                queue_url = response['QueueUrl']
                
                # 获取队列属性
                attributes = self.sqs_client.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=['All']
                )
                
                queue_attrs = attributes['Attributes']
                
                self.statuses.append(DeploymentStatus(
                    component=f"SQS队列-{queue_name}",
                    status="HEALTHY",
                    message="队列配置正常",
                    details={
                        'queue_url': queue_url,
                        'visibility_timeout': queue_attrs.get('VisibilityTimeout'),
                        'message_retention_period': queue_attrs.get('MessageRetentionPeriod'),
                        'max_receive_count': queue_attrs.get('maxReceiveCount')
                    }
                ))
                
            except self.sqs_client.exceptions.QueueDoesNotExist:
                raise Exception(f"SQS队列不存在: {queue_name}")
            except Exception as e:
                raise Exception(f"验证SQS队列失败: {e}")
    
    def _verify_api_gateway(self):
        """验证API Gateway"""
        try:
            # 获取API Gateway信息
            apis = self.apigateway.get_rest_apis()
            
            target_api = None
            for api in apis['items']:
                if self.stack_name in api['name']:
                    target_api = api
                    break
            
            if not target_api:
                raise Exception(f"未找到API Gateway: {self.stack_name}")
            
            api_id = target_api['id']
            
            # 获取部署信息
            deployments = self.apigateway.get_deployments(restApiId=api_id)
            
            if not deployments['items']:
                raise Exception("API Gateway未部署")
            
            # 获取阶段信息
            stages = self.apigateway.get_stages(restApiId=api_id)
            
            self.statuses.append(DeploymentStatus(
                component="API Gateway",
                status="HEALTHY",
                message="API Gateway配置正常",
                details={
                    'api_id': api_id,
                    'api_name': target_api['name'],
                    'created_date': target_api['createdDate'].isoformat(),
                    'stages': [stage['stageName'] for stage in stages['item']],
                    'endpoint_url': f"https://{api_id}.execute-api.{self.region}.amazonaws.com"
                }
            ))
            
        except Exception as e:
            raise Exception(f"验证API Gateway失败: {e}")
    
    def _verify_iam_roles(self):
        """验证IAM角色和权限"""
        try:
            iam_client = boto3.client('iam')
            
            # 检查Lambda执行角色
            role_name = f"{self.stack_name}-lambda-role"
            
            try:
                role = iam_client.get_role(RoleName=role_name)
                
                # 获取附加的策略
                attached_policies = iam_client.list_attached_role_policies(
                    RoleName=role_name
                )
                
                self.statuses.append(DeploymentStatus(
                    component="IAM角色",
                    status="HEALTHY",
                    message="IAM角色配置正常",
                    details={
                        'role_name': role_name,
                        'role_arn': role['Role']['Arn'],
                        'attached_policies': [
                            policy['PolicyName'] 
                            for policy in attached_policies['AttachedPolicies']
                        ]
                    }
                ))
                
            except iam_client.exceptions.NoSuchEntityException:
                raise Exception(f"IAM角色不存在: {role_name}")
                
        except Exception as e:
            raise Exception(f"验证IAM角色失败: {e}")
    
    def _verify_parameter_store(self):
        """验证Parameter Store参数"""
        try:
            # 检查必需的参数
            required_params = [
                f"/feishu-bot/{self.stack_name.split('-')[-1]}/app_id",
                f"/feishu-bot/{self.stack_name.split('-')[-1]}/app_secret",
                f"/feishu-bot/{self.stack_name.split('-')[-1]}/verification_token",
                f"/feishu-bot/{self.stack_name.split('-')[-1]}/encrypt_key"
            ]
            
            existing_params = []
            missing_params = []
            
            for param_name in required_params:
                try:
                    self.ssm_client.get_parameter(Name=param_name)
                    existing_params.append(param_name)
                except self.ssm_client.exceptions.ParameterNotFound:
                    missing_params.append(param_name)
            
            if missing_params:
                raise Exception(f"缺少必需参数: {missing_params}")
            
            self.statuses.append(DeploymentStatus(
                component="Parameter Store",
                status="HEALTHY",
                message="参数配置正常",
                details={
                    'existing_parameters': existing_params,
                    'parameter_count': len(existing_params)
                }
            ))
            
        except Exception as e:
            raise Exception(f"验证Parameter Store失败: {e}")
    
    def _verify_cloudwatch_monitoring(self):
        """验证CloudWatch监控"""
        try:
            # 检查告警
            alarms = self.cloudwatch.describe_alarms(
                AlarmNamePrefix=self.stack_name
            )
            
            alarm_count = len(alarms['MetricAlarms'])
            
            # 检查自定义指标
            metrics = self.cloudwatch.list_metrics(
                Namespace='FeishuBot'
            )
            
            metric_count = len(metrics['Metrics'])
            
            self.statuses.append(DeploymentStatus(
                component="CloudWatch监控",
                status="HEALTHY",
                message="监控配置正常",
                details={
                    'alarm_count': alarm_count,
                    'custom_metric_count': metric_count,
                    'alarms': [alarm['AlarmName'] for alarm in alarms['MetricAlarms']]
                }
            ))
            
        except Exception as e:
            raise Exception(f"验证CloudWatch监控失败: {e}")
    
    def _verify_logging_configuration(self):
        """验证日志配置"""
        try:
            # 检查Lambda函数日志组
            log_groups = []
            paginator = self.logs_client.get_paginator('describe_log_groups')
            
            for page in paginator.paginate(
                logGroupNamePrefix=f'/aws/lambda/{self.stack_name}'
            ):
                log_groups.extend(page['logGroups'])
            
            if len(log_groups) < 3:
                raise Exception(f"日志组数量不足: {len(log_groups)}")
            
            self.statuses.append(DeploymentStatus(
                component="日志配置",
                status="HEALTHY",
                message="日志配置正常",
                details={
                    'log_group_count': len(log_groups),
                    'log_groups': [lg['logGroupName'] for lg in log_groups]
                }
            ))
            
        except Exception as e:
            raise Exception(f"验证日志配置失败: {e}")
    
    def _generate_verification_report(self) -> Dict[str, Any]:
        """生成验证报告"""
        total_components = len(self.statuses)
        healthy_components = sum(1 for status in self.statuses if status.status == "HEALTHY")
        failed_components = total_components - healthy_components
        
        health_score = (healthy_components / total_components * 100) if total_components > 0 else 0
        
        report = {
            'deployment_verification': {
                'stack_name': self.stack_name,
                'region': self.region,
                'verification_time': datetime.utcnow().isoformat(),
                'overall_status': 'HEALTHY' if failed_components == 0 else 'UNHEALTHY',
                'health_score': f"{health_score:.2f}%",
                'total_components': total_components,
                'healthy_components': healthy_components,
                'failed_components': failed_components
            },
            'component_status': [
                {
                    'component': status.component,
                    'status': status.status,
                    'message': status.message,
                    'details': status.details
                }
                for status in self.statuses
            ],
            'failed_components': [
                {
                    'component': status.component,
                    'message': status.message,
                    'details': status.details
                }
                for status in self.statuses if status.status == "FAILED"
            ]
        }
        
        return report

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='飞书机器人系统部署验证')
    parser.add_argument('--stack-name', required=True, help='CloudFormation栈名称')
    parser.add_argument('--region', default='us-east-1', help='AWS区域')
    parser.add_argument('--output', default='deployment_verification.json', help='验证报告输出文件')
    
    args = parser.parse_args()
    
    # 运行验证
    verifier = DeploymentVerifier(args.stack_name, args.region)
    report = verifier.verify_deployment()
    
    # 输出报告
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 打印摘要
    verification = report['deployment_verification']
    print(f"\n{'='*60}")
    print(f"部署验证报告")
    print(f"{'='*60}")
    print(f"栈名称: {verification['stack_name']}")
    print(f"区域: {verification['region']}")
    print(f"整体状态: {verification['overall_status']}")
    print(f"健康评分: {verification['health_score']}")
    print(f"总组件数: {verification['total_components']}")
    print(f"健康组件: {verification['healthy_components']}")
    print(f"失败组件: {verification['failed_components']}")
    print(f"报告文件: {args.output}")
    
    if verification['failed_components'] > 0:
        print(f"\n失败的组件:")
        for failed_component in report['failed_components']:
            print(f"  ❌ {failed_component['component']}: {failed_component['message']}")
        
        exit(1)
    else:
        print(f"\n🎉 所有组件验证通过!")
        exit(0)

if __name__ == '__main__':
    main()