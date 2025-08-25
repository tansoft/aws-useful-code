"""
监控和可观测性模块
提供指标收集、日志记录和性能监控功能
"""

import json
import time
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import boto3
from botocore.exceptions import ClientError


class MetricType(Enum):
    """指标类型枚举"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class Metric:
    """指标数据模型"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: float
    dimensions: Dict[str, str]
    unit: str = "Count"
    
    def to_cloudwatch_format(self) -> Dict[str, Any]:
        """转换为CloudWatch指标格式"""
        return {
            'MetricName': self.name,
            'Value': self.value,
            'Unit': self.unit,
            'Timestamp': datetime.fromtimestamp(self.timestamp),
            'Dimensions': [
                {'Name': key, 'Value': value}
                for key, value in self.dimensions.items()
            ]
        }


@dataclass
class LogEntry:
    """日志条目数据模型"""
    timestamp: float
    level: LogLevel
    message: str
    logger_name: str
    function_name: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    error_type: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_structured_log(self) -> Dict[str, Any]:
        """转换为结构化日志格式"""
        log_data = {
            'timestamp': datetime.fromtimestamp(self.timestamp).isoformat(),
            'level': self.level.value,
            'message': self.message,
            'logger': self.logger_name
        }
        
        # 添加可选字段
        if self.function_name:
            log_data['function'] = self.function_name
        if self.request_id:
            log_data['request_id'] = self.request_id
        if self.user_id:
            log_data['user_id'] = self.user_id
        if self.chat_id:
            log_data['chat_id'] = self.chat_id
        if self.error_type:
            log_data['error_type'] = self.error_type
        if self.duration_ms is not None:
            log_data['duration_ms'] = self.duration_ms
        if self.metadata:
            log_data['metadata'] = self.metadata
        
        return log_data


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, namespace: str = "FeishuBot", region: str = "us-east-1"):
        """
        初始化指标收集器
        
        Args:
            namespace: CloudWatch命名空间
            region: AWS区域
        """
        self.namespace = namespace
        self.region = region
        self.metrics_buffer: List[Metric] = []
        self.cloudwatch = None
        
        # 初始化CloudWatch客户端（延迟初始化）
        self._init_cloudwatch()
    
    def _init_cloudwatch(self):
        """初始化CloudWatch客户端"""
        try:
            self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        except Exception as e:
            logging.warning(f"Failed to initialize CloudWatch client: {e}")
    
    def increment_counter(self, name: str, value: float = 1.0, 
                         dimensions: Optional[Dict[str, str]] = None):
        """增加计数器指标"""
        self._add_metric(name, value, MetricType.COUNTER, dimensions or {})
    
    def set_gauge(self, name: str, value: float, 
                  dimensions: Optional[Dict[str, str]] = None):
        """设置仪表盘指标"""
        self._add_metric(name, value, MetricType.GAUGE, dimensions or {})
    
    def record_timer(self, name: str, duration_ms: float,
                    dimensions: Optional[Dict[str, str]] = None):
        """记录计时器指标"""
        self._add_metric(name, duration_ms, MetricType.TIMER, 
                        dimensions or {}, unit="Milliseconds")
    
    def record_histogram(self, name: str, value: float,
                        dimensions: Optional[Dict[str, str]] = None):
        """记录直方图指标"""
        self._add_metric(name, value, MetricType.HISTOGRAM, dimensions or {})
    
    def _add_metric(self, name: str, value: float, metric_type: MetricType,
                   dimensions: Dict[str, str], unit: str = "Count"):
        """添加指标到缓冲区"""
        metric = Metric(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=time.time(),
            dimensions=dimensions,
            unit=unit
        )
        self.metrics_buffer.append(metric)
        
        # 如果缓冲区满了，自动发送
        if len(self.metrics_buffer) >= 20:  # CloudWatch批量限制
            self.flush_metrics()
    
    def flush_metrics(self):
        """发送缓冲区中的所有指标"""
        if not self.metrics_buffer or not self.cloudwatch:
            return
        
        try:
            # 转换为CloudWatch格式
            metric_data = [metric.to_cloudwatch_format() for metric in self.metrics_buffer]
            
            # 分批发送（CloudWatch限制每次20个指标）
            batch_size = 20
            for i in range(0, len(metric_data), batch_size):
                batch = metric_data[i:i + batch_size]
                
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
            
            logging.info(f"Sent {len(self.metrics_buffer)} metrics to CloudWatch")
            self.metrics_buffer.clear()
            
        except Exception as e:
            logging.error(f"Failed to send metrics to CloudWatch: {e}")
    
    def get_buffered_metrics_count(self) -> int:
        """获取缓冲区中的指标数量"""
        return len(self.metrics_buffer)


class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        """
        初始化结构化日志记录器
        
        Args:
            name: 日志记录器名称
            level: 日志级别
        """
        self.name = name
        self.level = level
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))
        
        # 配置结构化日志格式
        self._setup_structured_logging()
    
    def _setup_structured_logging(self):
        """设置结构化日志格式"""
        # 移除现有的处理器
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 创建新的处理器
        handler = logging.StreamHandler()
        
        # 使用JSON格式化器
        formatter = StructuredLogFormatter()
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.propagate = False
    
    def debug(self, message: str, **kwargs):
        """记录DEBUG级别日志"""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """记录INFO级别日志"""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """记录WARNING级别日志"""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """记录ERROR级别日志"""
        self._log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """记录CRITICAL级别日志"""
        self._log(LogLevel.CRITICAL, message, **kwargs)
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """内部日志记录方法"""
        if level.value < self.level.value:
            return
        
        # 清理敏感信息
        sanitized_kwargs = self._sanitize_log_data(kwargs)
        
        log_entry = LogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            logger_name=self.name,
            function_name=sanitized_kwargs.get('function_name'),
            request_id=sanitized_kwargs.get('request_id'),
            user_id=sanitized_kwargs.get('user_id'),
            chat_id=sanitized_kwargs.get('chat_id'),
            error_type=sanitized_kwargs.get('error_type'),
            duration_ms=sanitized_kwargs.get('duration_ms'),
            metadata=sanitized_kwargs.get('metadata')
        )
        
        # 使用标准logger输出结构化日志
        log_level = getattr(logging, level.value)
        self.logger.log(log_level, json.dumps(log_entry.to_structured_log(), ensure_ascii=False))
    
    def _sanitize_log_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清理日志数据中的敏感信息"""
        from src.shared.utils import sanitize_log_data
        return sanitize_log_data(data)


class StructuredLogFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def format(self, record):
        """格式化日志记录"""
        # 直接返回消息，因为消息已经是JSON格式
        return record.getMessage()


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, metrics_collector: MetricsCollector, 
                 logger: StructuredLogger):
        """
        初始化性能监控器
        
        Args:
            metrics_collector: 指标收集器
            logger: 结构化日志记录器
        """
        self.metrics = metrics_collector
        self.logger = logger
        self.active_timers: Dict[str, float] = {}
    
    def start_timer(self, timer_name: str):
        """开始计时"""
        self.active_timers[timer_name] = time.time()
    
    def end_timer(self, timer_name: str, dimensions: Optional[Dict[str, str]] = None):
        """结束计时并记录指标"""
        if timer_name not in self.active_timers:
            self.logger.warning(f"Timer {timer_name} was not started")
            return
        
        start_time = self.active_timers.pop(timer_name)
        duration_ms = (time.time() - start_time) * 1000
        
        self.metrics.record_timer(timer_name, duration_ms, dimensions)
        
        return duration_ms
    
    def record_function_performance(self, function_name: str, duration_ms: float,
                                  success: bool, error_type: Optional[str] = None):
        """记录函数性能指标"""
        dimensions = {
            'function': function_name,
            'status': 'success' if success else 'error'
        }
        
        if error_type:
            dimensions['error_type'] = error_type
        
        # 记录执行时间
        self.metrics.record_timer(f'function.duration', duration_ms, dimensions)
        
        # 记录调用次数
        self.metrics.increment_counter(f'function.calls', 1.0, dimensions)
        
        # 记录错误率
        if not success:
            self.metrics.increment_counter(f'function.errors', 1.0, dimensions)
    
    def record_api_performance(self, api_name: str, status_code: int, 
                             duration_ms: float, request_size: Optional[int] = None,
                             response_size: Optional[int] = None):
        """记录API性能指标"""
        dimensions = {
            'api': api_name,
            'status_code': str(status_code),
            'status_class': f'{status_code // 100}xx'
        }
        
        # 记录响应时间
        self.metrics.record_timer('api.response_time', duration_ms, dimensions)
        
        # 记录请求数量
        self.metrics.increment_counter('api.requests', 1.0, dimensions)
        
        # 记录请求和响应大小
        if request_size is not None:
            self.metrics.record_histogram('api.request_size', request_size, dimensions)
        
        if response_size is not None:
            self.metrics.record_histogram('api.response_size', response_size, dimensions)
    
    def record_message_processing_metrics(self, message_type: str, processing_time_ms: float,
                                        success: bool, queue_depth: Optional[int] = None):
        """记录消息处理指标"""
        dimensions = {
            'message_type': message_type,
            'status': 'success' if success else 'error'
        }
        
        # 记录处理时间
        self.metrics.record_timer('message.processing_time', processing_time_ms, dimensions)
        
        # 记录处理数量
        self.metrics.increment_counter('message.processed', 1.0, dimensions)
        
        # 记录队列深度
        if queue_depth is not None:
            self.metrics.set_gauge('message.queue_depth', queue_depth)


class HealthChecker:
    """健康检查器"""
    
    def __init__(self, metrics_collector: MetricsCollector,
                 logger: StructuredLogger):
        """
        初始化健康检查器
        
        Args:
            metrics_collector: 指标收集器
            logger: 结构化日志记录器
        """
        self.metrics = metrics_collector
        self.logger = logger
    
    def check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状态"""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'checks': {}
        }
        
        # 检查内存使用
        memory_check = self._check_memory_usage()
        health_status['checks']['memory'] = memory_check
        
        # 检查AWS服务连接
        aws_check = self._check_aws_connectivity()
        health_status['checks']['aws'] = aws_check
        
        # 检查指标缓冲区
        metrics_check = self._check_metrics_buffer()
        health_status['checks']['metrics'] = metrics_check
        
        # 确定整体健康状态
        failed_checks = [
            check_name for check_name, check_result in health_status['checks'].items()
            if check_result['status'] != 'healthy'
        ]
        
        if failed_checks:
            health_status['status'] = 'unhealthy'
            health_status['failed_checks'] = failed_checks
        
        # 记录健康检查指标
        self.metrics.set_gauge('system.health', 1.0 if health_status['status'] == 'healthy' else 0.0)
        
        return health_status
    
    def _check_memory_usage(self) -> Dict[str, Any]:
        """检查内存使用情况"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # 记录内存使用指标
            self.metrics.set_gauge('system.memory_usage_mb', memory_mb)
            
            # 检查内存使用是否过高
            memory_limit_mb = int(os.environ.get('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', '512'))
            memory_usage_percent = (memory_mb / memory_limit_mb) * 100
            
            status = 'healthy'
            if memory_usage_percent > 90:
                status = 'critical'
            elif memory_usage_percent > 75:
                status = 'warning'
            
            return {
                'status': status,
                'memory_mb': memory_mb,
                'memory_limit_mb': memory_limit_mb,
                'memory_usage_percent': memory_usage_percent
            }
            
        except Exception as e:
            self.logger.error(f"Memory check failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _check_aws_connectivity(self) -> Dict[str, Any]:
        """检查AWS服务连接"""
        try:
            # 测试CloudWatch连接
            if self.metrics.cloudwatch:
                # 尝试列出指标（限制结果数量）
                self.metrics.cloudwatch.list_metrics(
                    Namespace=self.metrics.namespace,
                    MaxRecords=1
                )
            
            return {
                'status': 'healthy',
                'cloudwatch': 'connected'
            }
            
        except Exception as e:
            self.logger.error(f"AWS connectivity check failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _check_metrics_buffer(self) -> Dict[str, Any]:
        """检查指标缓冲区状态"""
        try:
            buffer_size = self.metrics.get_buffered_metrics_count()
            
            status = 'healthy'
            if buffer_size > 50:
                status = 'warning'
            elif buffer_size > 100:
                status = 'critical'
            
            return {
                'status': status,
                'buffer_size': buffer_size,
                'max_buffer_size': 20
            }
            
        except Exception as e:
            self.logger.error(f"Metrics buffer check failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }


# 全局监控实例
_metrics_collector = None
_structured_logger = None
_performance_monitor = None
_health_checker = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器实例"""
    global _metrics_collector
    if _metrics_collector is None:
        namespace = os.environ.get('CUSTOM_METRICS_NAMESPACE', 'FeishuBot')
        region = os.environ.get('AWS_REGION', 'us-east-1')
        _metrics_collector = MetricsCollector(namespace, region)
    return _metrics_collector


def get_structured_logger(name: str) -> StructuredLogger:
    """获取结构化日志记录器实例"""
    log_level_str = os.environ.get('LOG_LEVEL', 'INFO')
    log_level = LogLevel(log_level_str)
    return StructuredLogger(name, log_level)


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        metrics = get_metrics_collector()
        logger = get_structured_logger('performance')
        _performance_monitor = PerformanceMonitor(metrics, logger)
    return _performance_monitor


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器实例"""
    global _health_checker
    if _health_checker is None:
        metrics = get_metrics_collector()
        logger = get_structured_logger('health')
        _health_checker = HealthChecker(metrics, logger)
    return _health_checker


def monitor_function_performance(function_name: str):
    """函数性能监控装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            success = True
            error_type = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                monitor.record_function_performance(
                    function_name, duration_ms, success, error_type
                )
        
        return wrapper
    return decorator


def flush_all_metrics():
    """刷新所有缓冲的指标"""
    global _metrics_collector
    if _metrics_collector:
        _metrics_collector.flush_metrics()