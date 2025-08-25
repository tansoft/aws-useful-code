#!/usr/bin/env python3
"""
监控工具脚本
提供系统监控、指标查询和健康检查功能
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import boto3
from botocore.exceptions import ClientError


class MonitoringTools:
    """监控工具类"""
    
    def __init__(self, region: str = 'us-east-1', profile: Optional[str] = None):
        """
        初始化监控工具
        
        Args:
            region: AWS区域
            profile: AWS配置文件
        """
        self.region = region
        self.profile = profile
        
        # 初始化AWS客户端
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.cloudwatch = session.client('cloudwatch', region_name=region)
        self.logs = session.client('logs', region_name=region)
        self.lambda_client = session.client('lambda', region_name=region)
        self.sqs = session.client('sqs', region_name=region)
    
    def get_system_health(self, project_name: str = 'feishu-bot', 
                         environment: str = 'dev') -> Dict[str, Any]:
        """
        获取系统整体健康状态
        
        Args:
            project_name: 项目名称
            environment: 环境名称
            
        Returns:
            dict: 系统健康状态
        """
        print(f"Checking system health for {project_name}-{environment}...")
        
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'project': project_name,
            'environment': environment,
            'overall_status': 'healthy',
            'components': {}
        }
        
        # 检查Lambda函数
        lambda_health = self._check_lambda_functions(project_name, environment)
        health_status['components']['lambda'] = lambda_health
        
        # 检查SQS队列
        sqs_health = self._check_sqs_queues(project_name, environment)
        health_status['components']['sqs'] = sqs_health
        
        # 检查CloudWatch告警
        alarms_health = self._check_cloudwatch_alarms(project_name, environment)
        health_status['components']['alarms'] = alarms_health
        
        # 检查自定义指标
        metrics_health = self._check_custom_metrics()
        health_status['components']['metrics'] = metrics_health
        
        # 确定整体健康状态
        unhealthy_components = [
            name for name, status in health_status['components'].items()
            if status.get('status') != 'healthy'
        ]
        
        if unhealthy_components:
            health_status['overall_status'] = 'unhealthy'
            health_status['unhealthy_components'] = unhealthy_components
        
        return health_status
    
    def _check_lambda_functions(self, project_name: str, environment: str) -> Dict[str, Any]:
        """检查Lambda函数状态"""
        function_names = [
            f'{project_name}-{environment}-receive',
            f'{project_name}-{environment}-process',
            f'{project_name}-{environment}-monitor'
        ]
        
        function_status = {
            'status': 'healthy',
            'functions': {}
        }
        
        for function_name in function_names:
            try:
                response = self.lambda_client.get_function(FunctionName=function_name)
                config = response['Configuration']
                
                function_info = {
                    'status': 'healthy',
                    'state': config.get('State'),
                    'last_modified': config.get('LastModified'),
                    'runtime': config.get('Runtime'),
                    'memory_size': config.get('MemorySize'),
                    'timeout': config.get('Timeout')
                }
                
                # 检查函数状态
                if config.get('State') != 'Active':
                    function_info['status'] = 'unhealthy'
                    function_status['status'] = 'unhealthy'
                
                function_status['functions'][function_name] = function_info
                
            except ClientError as e:
                function_status['functions'][function_name] = {
                    'status': 'error',
                    'error': str(e)
                }
                function_status['status'] = 'unhealthy'
        
        return function_status
    
    def _check_sqs_queues(self, project_name: str, environment: str) -> Dict[str, Any]:
        """检查SQS队列状态"""
        queue_names = [
            f'{project_name}-{environment}-messages',
            f'{project_name}-{environment}-messages-dlq'
        ]
        
        queue_status = {
            'status': 'healthy',
            'queues': {}
        }
        
        for queue_name in queue_names:
            try:
                # 构造队列URL
                account_id = boto3.client('sts').get_caller_identity()['Account']
                queue_url = f'https://sqs.{self.region}.amazonaws.com/{account_id}/{queue_name}'
                
                # 获取队列属性
                response = self.sqs.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=['All']
                )
                
                attributes = response['Attributes']
                visible_messages = int(attributes.get('ApproximateNumberOfMessages', 0))
                
                queue_info = {
                    'status': 'healthy',
                    'visible_messages': visible_messages,
                    'in_flight_messages': int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0)),
                    'delayed_messages': int(attributes.get('ApproximateNumberOfMessagesDelayed', 0))
                }
                
                # 检查队列深度
                if 'dlq' in queue_name and visible_messages > 0:
                    queue_info['status'] = 'warning'
                    queue_info['warning'] = 'Messages in dead letter queue'
                elif visible_messages > 100:
                    queue_info['status'] = 'warning'
                    queue_info['warning'] = 'High queue depth'
                
                if queue_info['status'] != 'healthy':
                    queue_status['status'] = 'warning'
                
                queue_status['queues'][queue_name] = queue_info
                
            except ClientError as e:
                queue_status['queues'][queue_name] = {
                    'status': 'error',
                    'error': str(e)
                }
                queue_status['status'] = 'unhealthy'
        
        return queue_status
    
    def _check_cloudwatch_alarms(self, project_name: str, environment: str) -> Dict[str, Any]:
        """检查CloudWatch告警状态"""
        try:
            # 获取项目相关的告警
            response = self.cloudwatch.describe_alarms(
                AlarmNamePrefix=f'{project_name}-{environment}'
            )
            
            alarms = response['MetricAlarms']
            alarm_status = {
                'status': 'healthy',
                'total_alarms': len(alarms),
                'alarm_states': {},
                'active_alarms': []
            }
            
            for alarm in alarms:
                state = alarm['StateValue']
                alarm_status['alarm_states'][state] = alarm_status['alarm_states'].get(state, 0) + 1
                
                if state == 'ALARM':
                    alarm_status['active_alarms'].append({
                        'name': alarm['AlarmName'],
                        'reason': alarm.get('StateReason', ''),
                        'timestamp': alarm.get('StateUpdatedTimestamp', '').isoformat() if alarm.get('StateUpdatedTimestamp') else ''
                    })
            
            # 如果有活跃告警，标记为不健康
            if alarm_status['alarm_states'].get('ALARM', 0) > 0:
                alarm_status['status'] = 'unhealthy'
            
            return alarm_status
            
        except ClientError as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _check_custom_metrics(self) -> Dict[str, Any]:
        """检查自定义指标状态"""
        try:
            # 获取最近的自定义指标
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=15)
            
            response = self.cloudwatch.list_metrics(
                Namespace='FeishuBot',
                RecentlyActive='PT3H'  # 最近3小时
            )
            
            metrics_status = {
                'status': 'healthy',
                'total_metrics': len(response['Metrics']),
                'recent_metrics': len(response['Metrics'])
            }
            
            # 如果没有最近的指标，可能表示系统有问题
            if len(response['Metrics']) == 0:
                metrics_status['status'] = 'warning'
                metrics_status['warning'] = 'No recent custom metrics found'
            
            return metrics_status
            
        except ClientError as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_performance_metrics(self, project_name: str = 'feishu-bot', 
                              environment: str = 'dev',
                              hours: int = 24) -> Dict[str, Any]:
        """
        获取性能指标
        
        Args:
            project_name: 项目名称
            environment: 环境名称
            hours: 查询时间范围（小时）
            
        Returns:
            dict: 性能指标数据
        """
        print(f"Fetching performance metrics for last {hours} hours...")
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        metrics_data = {
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': hours
            },
            'lambda_metrics': {},
            'custom_metrics': {},
            'sqs_metrics': {}
        }
        
        # 获取Lambda指标
        lambda_functions = [
            f'{project_name}-{environment}-receive',
            f'{project_name}-{environment}-process',
            f'{project_name}-{environment}-monitor'
        ]
        
        for function_name in lambda_functions:
            metrics_data['lambda_metrics'][function_name] = self._get_lambda_metrics(
                function_name, start_time, end_time
            )
        
        # 获取自定义指标
        custom_metric_names = [
            'function.calls',
            'function.duration',
            'function.errors',
            'message.processed',
            'api.requests',
            'system.health'
        ]
        
        for metric_name in custom_metric_names:
            metrics_data['custom_metrics'][metric_name] = self._get_custom_metric_data(
                metric_name, start_time, end_time
            )
        
        # 获取SQS指标
        queue_names = [
            f'{project_name}-{environment}-messages',
            f'{project_name}-{environment}-messages-dlq'
        ]
        
        for queue_name in queue_names:
            metrics_data['sqs_metrics'][queue_name] = self._get_sqs_metrics(
                queue_name, start_time, end_time
            )
        
        return metrics_data
    
    def _get_lambda_metrics(self, function_name: str, start_time: datetime, 
                           end_time: datetime) -> Dict[str, Any]:
        """获取Lambda函数指标"""
        try:
            metrics = ['Invocations', 'Duration', 'Errors', 'Throttles']
            metric_data = {}
            
            for metric_name in metrics:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'FunctionName',
                            'Value': function_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,  # 5分钟
                    Statistics=['Sum', 'Average', 'Maximum']
                )
                
                datapoints = response['Datapoints']
                if datapoints:
                    # 计算汇总统计
                    metric_data[metric_name] = {
                        'total': sum(dp.get('Sum', 0) for dp in datapoints),
                        'average': sum(dp.get('Average', 0) for dp in datapoints) / len(datapoints),
                        'maximum': max(dp.get('Maximum', 0) for dp in datapoints),
                        'datapoints': len(datapoints)
                    }
                else:
                    metric_data[metric_name] = {
                        'total': 0,
                        'average': 0,
                        'maximum': 0,
                        'datapoints': 0
                    }
            
            return {
                'status': 'success',
                'metrics': metric_data
            }
            
        except ClientError as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _get_custom_metric_data(self, metric_name: str, start_time: datetime, 
                               end_time: datetime) -> Dict[str, Any]:
        """获取自定义指标数据"""
        try:
            response = self.cloudwatch.get_metric_statistics(
                Namespace='FeishuBot',
                MetricName=metric_name,
                StartTime=start_time,
                EndTime=end_time,
                Period=300,  # 5分钟
                Statistics=['Sum', 'Average', 'Maximum']
            )
            
            datapoints = response['Datapoints']
            if datapoints:
                return {
                    'status': 'success',
                    'total': sum(dp.get('Sum', 0) for dp in datapoints),
                    'average': sum(dp.get('Average', 0) for dp in datapoints) / len(datapoints),
                    'maximum': max(dp.get('Maximum', 0) for dp in datapoints),
                    'datapoints': len(datapoints)
                }
            else:
                return {
                    'status': 'success',
                    'total': 0,
                    'average': 0,
                    'maximum': 0,
                    'datapoints': 0
                }
                
        except ClientError as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _get_sqs_metrics(self, queue_name: str, start_time: datetime, 
                        end_time: datetime) -> Dict[str, Any]:
        """获取SQS队列指标"""
        try:
            metrics = [
                'NumberOfMessagesSent',
                'NumberOfMessagesReceived',
                'ApproximateNumberOfVisibleMessages'
            ]
            
            metric_data = {}
            
            for metric_name in metrics:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/SQS',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'QueueName',
                            'Value': queue_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,  # 5分钟
                    Statistics=['Sum', 'Average', 'Maximum']
                )
                
                datapoints = response['Datapoints']
                if datapoints:
                    metric_data[metric_name] = {
                        'total': sum(dp.get('Sum', 0) for dp in datapoints),
                        'average': sum(dp.get('Average', 0) for dp in datapoints) / len(datapoints),
                        'maximum': max(dp.get('Maximum', 0) for dp in datapoints),
                        'datapoints': len(datapoints)
                    }
                else:
                    metric_data[metric_name] = {
                        'total': 0,
                        'average': 0,
                        'maximum': 0,
                        'datapoints': 0
                    }
            
            return {
                'status': 'success',
                'metrics': metric_data
            }
            
        except ClientError as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_recent_logs(self, project_name: str = 'feishu-bot', 
                       environment: str = 'dev',
                       hours: int = 1,
                       log_level: str = 'ERROR') -> Dict[str, Any]:
        """
        获取最近的日志
        
        Args:
            project_name: 项目名称
            environment: 环境名称
            hours: 查询时间范围（小时）
            log_level: 日志级别
            
        Returns:
            dict: 日志数据
        """
        print(f"Fetching recent {log_level} logs for last {hours} hours...")
        
        log_groups = [
            f'/aws/lambda/{project_name}-{environment}-receive',
            f'/aws/lambda/{project_name}-{environment}-process',
            f'/aws/lambda/{project_name}-{environment}-monitor'
        ]
        
        end_time = int(time.time() * 1000)
        start_time = end_time - (hours * 60 * 60 * 1000)
        
        logs_data = {
            'time_range': {
                'start': datetime.fromtimestamp(start_time / 1000).isoformat(),
                'end': datetime.fromtimestamp(end_time / 1000).isoformat(),
                'hours': hours
            },
            'log_level': log_level,
            'log_groups': {}
        }
        
        for log_group in log_groups:
            try:
                # 构造查询
                query = f'fields @timestamp, level, message, function, error_type, duration_ms | filter level = "{log_level}" | sort @timestamp desc | limit 50'
                
                # 启动查询
                response = self.logs.start_query(
                    logGroupName=log_group,
                    startTime=start_time,
                    endTime=end_time,
                    queryString=query
                )
                
                query_id = response['queryId']
                
                # 等待查询完成
                max_wait = 30  # 最多等待30秒
                wait_time = 0
                
                while wait_time < max_wait:
                    result = self.logs.get_query_results(queryId=query_id)
                    
                    if result['status'] == 'Complete':
                        logs_data['log_groups'][log_group] = {
                            'status': 'success',
                            'total_logs': len(result['results']),
                            'logs': result['results']
                        }
                        break
                    elif result['status'] == 'Failed':
                        logs_data['log_groups'][log_group] = {
                            'status': 'error',
                            'error': 'Query failed'
                        }
                        break
                    
                    time.sleep(1)
                    wait_time += 1
                
                if wait_time >= max_wait:
                    logs_data['log_groups'][log_group] = {
                        'status': 'timeout',
                        'error': 'Query timeout'
                    }
                    
            except ClientError as e:
                logs_data['log_groups'][log_group] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return logs_data
    
    def create_dashboard(self, project_name: str = 'feishu-bot', 
                        environment: str = 'dev') -> Dict[str, Any]:
        """
        创建CloudWatch仪表板
        
        Args:
            project_name: 项目名称
            environment: 环境名称
            
        Returns:
            dict: 创建结果
        """
        dashboard_name = f'{project_name}-{environment}-dashboard'
        
        # 读取仪表板配置
        dashboard_config_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'deployment', 
            'cloudwatch-dashboard.json'
        )
        
        try:
            with open(dashboard_config_path, 'r') as f:
                dashboard_body = f.read()
            
            # 替换项目和环境变量
            dashboard_body = dashboard_body.replace('feishu-bot-dev', f'{project_name}-{environment}')
            
            # 创建仪表板
            response = self.cloudwatch.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=dashboard_body
            )
            
            return {
                'status': 'success',
                'dashboard_name': dashboard_name,
                'dashboard_url': f'https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={dashboard_name}'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='飞书机器人系统监控工具')
    parser.add_argument('--region', default='us-east-1', help='AWS区域')
    parser.add_argument('--profile', help='AWS配置文件')
    parser.add_argument('--project', default='feishu-bot', help='项目名称')
    parser.add_argument('--environment', default='dev', help='环境名称')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 健康检查命令
    health_parser = subparsers.add_parser('health', help='检查系统健康状态')
    
    # 性能指标命令
    metrics_parser = subparsers.add_parser('metrics', help='获取性能指标')
    metrics_parser.add_argument('--hours', type=int, default=24, help='查询时间范围（小时）')
    
    # 日志查询命令
    logs_parser = subparsers.add_parser('logs', help='获取最近日志')
    logs_parser.add_argument('--hours', type=int, default=1, help='查询时间范围（小时）')
    logs_parser.add_argument('--level', default='ERROR', help='日志级别')
    
    # 创建仪表板命令
    dashboard_parser = subparsers.add_parser('dashboard', help='创建CloudWatch仪表板')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 初始化监控工具
    tools = MonitoringTools(region=args.region, profile=args.profile)
    
    try:
        if args.command == 'health':
            result = tools.get_system_health(args.project, args.environment)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        elif args.command == 'metrics':
            result = tools.get_performance_metrics(args.project, args.environment, args.hours)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        elif args.command == 'logs':
            result = tools.get_recent_logs(args.project, args.environment, args.hours, args.level)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        elif args.command == 'dashboard':
            result = tools.create_dashboard(args.project, args.environment)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()