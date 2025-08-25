"""
统一错误处理和重试机制
提供系统级别的错误处理、重试策略和错误监控
"""

import time
import logging
import functools
from typing import Dict, Any, Optional, Callable, Type, Union, List
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""
    NETWORK_ERROR = "network_error"
    API_ERROR = "api_error"
    VALIDATION_ERROR = "validation_error"
    CONFIGURATION_ERROR = "configuration_error"
    BUSINESS_ERROR = "business_error"
    SYSTEM_ERROR = "system_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"


class ErrorSeverity(Enum):
    """错误严重程度枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FeishuBotError(Exception):
    """飞书机器人系统基础异常类"""
    
    def __init__(self, message: str, error_type: ErrorType = ErrorType.SYSTEM_ERROR,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM, 
                 details: Optional[Dict[str, Any]] = None,
                 original_exception: Optional[Exception] = None):
        """
        初始化异常
        
        Args:
            message: 错误消息
            error_type: 错误类型
            severity: 错误严重程度
            details: 错误详细信息
            original_exception: 原始异常
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.severity = severity
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = int(time.time())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'message': self.message,
            'error_type': self.error_type.value,
            'severity': self.severity.value,
            'details': self.details,
            'timestamp': self.timestamp,
            'original_exception': str(self.original_exception) if self.original_exception else None
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class NetworkError(FeishuBotError):
    """网络错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorType.NETWORK_ERROR, **kwargs)


class APIError(FeishuBotError):
    """API错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorType.API_ERROR, **kwargs)


class ValidationError(FeishuBotError):
    """验证错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorType.VALIDATION_ERROR, **kwargs)


class ConfigurationError(FeishuBotError):
    """配置错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorType.CONFIGURATION_ERROR, ErrorSeverity.HIGH, **kwargs)


class BusinessError(FeishuBotError):
    """业务逻辑错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorType.BUSINESS_ERROR, **kwargs)


class TimeoutError(FeishuBotError):
    """超时错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorType.TIMEOUT_ERROR, **kwargs)


class RateLimitError(FeishuBotError):
    """速率限制错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorType.RATE_LIMIT_ERROR, **kwargs)


class RetryConfig:
    """重试配置"""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, exponential_base: float = 2.0,
                 jitter: bool = True):
        """
        初始化重试配置
        
        Args:
            max_attempts: 最大重试次数
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
            exponential_base: 指数退避基数
            jitter: 是否添加随机抖动
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """
        计算延迟时间
        
        Args:
            attempt: 当前重试次数（从0开始）
            
        Returns:
            float: 延迟时间（秒）
        """
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            import random
            # 添加±25%的随机抖动
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)  # 确保延迟时间不为负
        
        return delay


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        """初始化错误处理器"""
        self.error_stats = {
            'total_errors': 0,
            'errors_by_type': {},
            'errors_by_severity': {}
        }
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> FeishuBotError:
        """
        处理错误
        
        Args:
            error: 原始异常
            context: 错误上下文信息
            
        Returns:
            FeishuBotError: 标准化的错误对象
        """
        context = context or {}
        
        # 如果已经是FeishuBotError，直接返回
        if isinstance(error, FeishuBotError):
            standardized_error = error
        else:
            # 标准化错误
            standardized_error = self._standardize_error(error, context)
        
        # 记录错误统计
        self._record_error_stats(standardized_error)
        
        # 记录错误日志
        self._log_error(standardized_error, context)
        
        # 发送错误监控（如果配置了）
        self._send_error_monitoring(standardized_error, context)
        
        return standardized_error
    
    def _standardize_error(self, error: Exception, context: Dict[str, Any]) -> FeishuBotError:
        """标准化错误"""
        error_message = str(error)
        error_type = ErrorType.SYSTEM_ERROR
        severity = ErrorSeverity.MEDIUM
        
        # 根据异常类型确定错误类型和严重程度
        if isinstance(error, (ConnectionError, OSError)):
            error_type = ErrorType.NETWORK_ERROR
            severity = ErrorSeverity.HIGH
        elif isinstance(error, TimeoutError):
            error_type = ErrorType.TIMEOUT_ERROR
            severity = ErrorSeverity.MEDIUM
        elif isinstance(error, ValueError):
            error_type = ErrorType.VALIDATION_ERROR
            severity = ErrorSeverity.LOW
        elif 'rate limit' in error_message.lower():
            error_type = ErrorType.RATE_LIMIT_ERROR
            severity = ErrorSeverity.MEDIUM
        elif 'api' in error_message.lower():
            error_type = ErrorType.API_ERROR
            severity = ErrorSeverity.MEDIUM
        
        return FeishuBotError(
            message=error_message,
            error_type=error_type,
            severity=severity,
            details=context,
            original_exception=error
        )
    
    def _record_error_stats(self, error: FeishuBotError) -> None:
        """记录错误统计"""
        self.error_stats['total_errors'] += 1
        
        error_type = error.error_type.value
        if error_type not in self.error_stats['errors_by_type']:
            self.error_stats['errors_by_type'][error_type] = 0
        self.error_stats['errors_by_type'][error_type] += 1
        
        severity = error.severity.value
        if severity not in self.error_stats['errors_by_severity']:
            self.error_stats['errors_by_severity'][severity] = 0
        self.error_stats['errors_by_severity'][severity] += 1
    
    def _log_error(self, error: FeishuBotError, context: Dict[str, Any]) -> None:
        """记录错误日志"""
        log_level = self._get_log_level(error.severity)
        
        log_data = {
            'error_type': error.error_type.value,
            'severity': error.severity.value,
            'message': error.message,
            'context': context,
            'timestamp': error.timestamp
        }
        
        # 清理敏感信息
        from src.shared.utils import sanitize_log_data
        sanitized_data = sanitize_log_data(log_data)
        
        logger.log(log_level, f"Error occurred: {json.dumps(sanitized_data, ensure_ascii=False)}")
    
    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """获取日志级别"""
        level_mapping = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }
        return level_mapping.get(severity, logging.ERROR)
    
    def _send_error_monitoring(self, error: FeishuBotError, context: Dict[str, Any]) -> None:
        """发送错误监控（可扩展）"""
        # 这里可以集成外部监控系统，如CloudWatch、Sentry等
        # 目前只记录到日志
        if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            logger.critical(f"Critical error detected: {error.message}")
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return self.error_stats.copy()
    
    def reset_error_stats(self) -> None:
        """重置错误统计"""
        self.error_stats = {
            'total_errors': 0,
            'errors_by_type': {},
            'errors_by_severity': {}
        }


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        初始化重试处理器
        
        Args:
            config: 重试配置
        """
        self.config = config or RetryConfig()
        self.error_handler = ErrorHandler()
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        判断是否应该重试
        
        Args:
            error: 异常对象
            attempt: 当前重试次数
            
        Returns:
            bool: 是否应该重试
        """
        if attempt >= self.config.max_attempts:
            return False
        
        # 根据错误类型判断是否可重试
        if isinstance(error, FeishuBotError):
            return self._is_retryable_error_type(error.error_type)
        
        # 对于标准异常，判断是否为可重试类型
        retryable_exceptions = (
            ConnectionError,
            TimeoutError,
            OSError
        )
        
        return isinstance(error, retryable_exceptions)
    
    def _is_retryable_error_type(self, error_type: ErrorType) -> bool:
        """判断错误类型是否可重试"""
        retryable_types = {
            ErrorType.NETWORK_ERROR,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.RATE_LIMIT_ERROR,
            ErrorType.API_ERROR  # API错误通常可以重试
        }
        
        non_retryable_types = {
            ErrorType.VALIDATION_ERROR,
            ErrorType.CONFIGURATION_ERROR,
            ErrorType.BUSINESS_ERROR
        }
        
        if error_type in non_retryable_types:
            return False
        
        return error_type in retryable_types
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行函数并在失败时重试
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            Any: 函数执行结果
            
        Raises:
            FeishuBotError: 重试失败后的标准化错误
        """
        last_error = None
        
        for attempt in range(self.config.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                # 处理错误
                function_name = getattr(func, '__name__', 'unknown_function')
                standardized_error = self.error_handler.handle_error(
                    e, 
                    context={'attempt': attempt, 'function': function_name}
                )
                
                # 判断是否应该重试
                if not self.should_retry(standardized_error, attempt):
                    logger.info(f"Error not retryable or max attempts reached: {standardized_error.message}")
                    raise standardized_error
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < self.config.max_attempts:
                    delay = self.config.calculate_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{self.config.max_attempts})")
                    time.sleep(delay)
        
        # 如果所有重试都失败，抛出最后一个错误
        if last_error:
            function_name = getattr(func, '__name__', 'unknown_function')
            final_error = self.error_handler.handle_error(
                last_error,
                context={'final_attempt': True, 'total_attempts': self.config.max_attempts + 1, 'function': function_name}
            )
            raise final_error


def retry_with_config(config: Optional[RetryConfig] = None):
    """
    重试装饰器
    
    Args:
        config: 重试配置
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retry_handler = RetryHandler(config)
            return retry_handler.execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator


def handle_errors(error_handler: Optional[ErrorHandler] = None):
    """
    错误处理装饰器
    
    Args:
        error_handler: 错误处理器实例
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            handler = error_handler or ErrorHandler()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                function_name = getattr(func, '__name__', 'unknown_function')
                standardized_error = handler.handle_error(
                    e,
                    context={'function': function_name, 'args_count': len(args)}
                )
                raise standardized_error
        return wrapper
    return decorator


# 全局错误处理器实例
global_error_handler = ErrorHandler()
global_retry_handler = RetryHandler()


def create_dead_letter_handler(queue_url: str) -> Callable:
    """
    创建死信队列处理器
    
    Args:
        queue_url: 死信队列URL
        
    Returns:
        处理函数
    """
    def handle_dead_letter_message(message_body: str, error: Exception) -> None:
        """处理死信消息"""
        try:
            import boto3
            sqs = boto3.client('sqs')
            
            # 构造死信消息
            dead_letter_data = {
                'original_message': message_body,
                'error': str(error),
                'timestamp': int(time.time()),
                'error_type': type(error).__name__
            }
            
            # 发送到死信队列
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(dead_letter_data, ensure_ascii=False)
            )
            
            logger.error(f"Message sent to dead letter queue: {dead_letter_data}")
            
        except Exception as dlq_error:
            logger.error(f"Failed to send message to dead letter queue: {str(dlq_error)}")
    
    return handle_dead_letter_message


def create_circuit_breaker(failure_threshold: int = 5, recovery_timeout: int = 60):
    """
    创建断路器装饰器
    
    Args:
        failure_threshold: 失败阈值
        recovery_timeout: 恢复超时时间（秒）
        
    Returns:
        装饰器函数
    """
    class CircuitBreaker:
        def __init__(self):
            self.failure_count = 0
            self.last_failure_time = None
            self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        
        def call(self, func, *args, **kwargs):
            if self.state == 'OPEN':
                if time.time() - self.last_failure_time > recovery_timeout:
                    self.state = 'HALF_OPEN'
                else:
                    raise FeishuBotError(
                        "Circuit breaker is OPEN",
                        ErrorType.SYSTEM_ERROR,
                        ErrorSeverity.HIGH
                    )
            
            try:
                result = func(*args, **kwargs)
                if self.state == 'HALF_OPEN':
                    self.state = 'CLOSED'
                    self.failure_count = 0
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= failure_threshold:
                    self.state = 'OPEN'
                
                raise e
    
    def decorator(func: Callable) -> Callable:
        circuit_breaker = CircuitBreaker()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)
        return wrapper
    
    return decorator