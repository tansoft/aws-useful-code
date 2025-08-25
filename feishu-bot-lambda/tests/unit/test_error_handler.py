"""
Unit tests for error handling and retry mechanisms
"""

import time
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.shared.error_handler import (
    ErrorType,
    ErrorSeverity,
    FeishuBotError,
    NetworkError,
    APIError,
    ValidationError,
    ConfigurationError,
    BusinessError,
    TimeoutError,
    RateLimitError,
    RetryConfig,
    ErrorHandler,
    RetryHandler,
    retry_with_config,
    handle_errors,
    create_circuit_breaker
)


class TestFeishuBotError:
    """Test cases for FeishuBotError class"""
    
    def test_feishu_bot_error_creation(self):
        """Test basic FeishuBotError creation"""
        error = FeishuBotError(
            message="Test error",
            error_type=ErrorType.API_ERROR,
            severity=ErrorSeverity.HIGH,
            details={"key": "value"}
        )
        
        assert error.message == "Test error"
        assert error.error_type == ErrorType.API_ERROR
        assert error.severity == ErrorSeverity.HIGH
        assert error.details == {"key": "value"}
        assert error.original_exception is None
        assert isinstance(error.timestamp, int)
    
    def test_feishu_bot_error_with_original_exception(self):
        """Test FeishuBotError with original exception"""
        original = ValueError("Original error")
        error = FeishuBotError(
            message="Wrapped error",
            original_exception=original
        )
        
        assert error.original_exception == original
        assert error.error_type == ErrorType.SYSTEM_ERROR  # Default
        assert error.severity == ErrorSeverity.MEDIUM  # Default
    
    def test_feishu_bot_error_to_dict(self):
        """Test conversion to dictionary"""
        error = FeishuBotError(
            message="Test error",
            error_type=ErrorType.NETWORK_ERROR,
            severity=ErrorSeverity.CRITICAL,
            details={"context": "test"}
        )
        
        result = error.to_dict()
        
        assert result['message'] == "Test error"
        assert result['error_type'] == "network_error"
        assert result['severity'] == "critical"
        assert result['details'] == {"context": "test"}
        assert 'timestamp' in result
        assert result['original_exception'] is None
    
    def test_feishu_bot_error_to_json(self):
        """Test conversion to JSON"""
        error = FeishuBotError("Test error")
        json_str = error.to_json()
        
        assert isinstance(json_str, str)
        assert "Test error" in json_str
        assert "system_error" in json_str  # Default error type


class TestSpecificErrors:
    """Test cases for specific error types"""
    
    def test_network_error(self):
        """Test NetworkError"""
        error = NetworkError("Connection failed")
        
        assert error.error_type == ErrorType.NETWORK_ERROR
        assert error.message == "Connection failed"
    
    def test_api_error(self):
        """Test APIError"""
        error = APIError("API call failed")
        
        assert error.error_type == ErrorType.API_ERROR
        assert error.message == "API call failed"
    
    def test_validation_error(self):
        """Test ValidationError"""
        error = ValidationError("Invalid input")
        
        assert error.error_type == ErrorType.VALIDATION_ERROR
        assert error.message == "Invalid input"
    
    def test_configuration_error(self):
        """Test ConfigurationError"""
        error = ConfigurationError("Missing config")
        
        assert error.error_type == ErrorType.CONFIGURATION_ERROR
        assert error.severity == ErrorSeverity.HIGH  # Default for config errors
        assert error.message == "Missing config"
    
    def test_business_error(self):
        """Test BusinessError"""
        error = BusinessError("Business rule violation")
        
        assert error.error_type == ErrorType.BUSINESS_ERROR
        assert error.message == "Business rule violation"
    
    def test_timeout_error(self):
        """Test TimeoutError"""
        error = TimeoutError("Operation timed out")
        
        assert error.error_type == ErrorType.TIMEOUT_ERROR
        assert error.message == "Operation timed out"
    
    def test_rate_limit_error(self):
        """Test RateLimitError"""
        error = RateLimitError("Rate limit exceeded")
        
        assert error.error_type == ErrorType.RATE_LIMIT_ERROR
        assert error.message == "Rate limit exceeded"


class TestRetryConfig:
    """Test cases for RetryConfig class"""
    
    def test_retry_config_defaults(self):
        """Test RetryConfig with default values"""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
    
    def test_retry_config_custom_values(self):
        """Test RetryConfig with custom values"""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False
        )
        
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_base == 3.0
        assert config.jitter is False
    
    def test_calculate_delay_without_jitter(self):
        """Test delay calculation without jitter"""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        
        assert config.calculate_delay(0) == 1.0  # 1.0 * 2^0
        assert config.calculate_delay(1) == 2.0  # 1.0 * 2^1
        assert config.calculate_delay(2) == 4.0  # 1.0 * 2^2
    
    def test_calculate_delay_with_max_delay(self):
        """Test delay calculation with max delay limit"""
        config = RetryConfig(base_delay=10.0, max_delay=15.0, exponential_base=2.0, jitter=False)
        
        assert config.calculate_delay(0) == 10.0  # 10.0 * 2^0
        assert config.calculate_delay(1) == 15.0  # min(20.0, 15.0)
        assert config.calculate_delay(2) == 15.0  # min(40.0, 15.0)
    
    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter"""
        config = RetryConfig(base_delay=4.0, jitter=True)
        
        # With jitter, delay should be within ±25% of base calculation
        delay = config.calculate_delay(0)
        expected_base = 4.0
        assert 3.0 <= delay <= 5.0  # 4.0 ± 25%
        
        # Ensure delay is not negative
        assert delay >= 0


class TestErrorHandler:
    """Test cases for ErrorHandler class"""
    
    def test_error_handler_initialization(self):
        """Test ErrorHandler initialization"""
        handler = ErrorHandler()
        
        assert handler.error_stats['total_errors'] == 0
        assert handler.error_stats['errors_by_type'] == {}
        assert handler.error_stats['errors_by_severity'] == {}
    
    def test_handle_feishu_bot_error(self):
        """Test handling FeishuBotError"""
        handler = ErrorHandler()
        original_error = NetworkError("Network failed")
        
        result = handler.handle_error(original_error)
        
        assert result == original_error
        assert handler.error_stats['total_errors'] == 1
        assert handler.error_stats['errors_by_type']['network_error'] == 1
    
    def test_handle_standard_exception(self):
        """Test handling standard Python exception"""
        handler = ErrorHandler()
        original_error = ConnectionError("Connection failed")
        
        result = handler.handle_error(original_error)
        
        assert isinstance(result, FeishuBotError)
        assert result.error_type == ErrorType.NETWORK_ERROR
        assert result.severity == ErrorSeverity.HIGH
        assert result.original_exception == original_error
        assert handler.error_stats['total_errors'] == 1
    
    def test_handle_error_with_context(self):
        """Test handling error with context"""
        handler = ErrorHandler()
        context = {"function": "test_func", "user_id": "123"}
        
        result = handler.handle_error(ValueError("Invalid value"), context)
        
        assert result.details == context
        assert result.error_type == ErrorType.VALIDATION_ERROR
    
    def test_standardize_different_error_types(self):
        """Test standardization of different error types"""
        handler = ErrorHandler()
        
        # Test timeout error
        timeout_error = handler._standardize_error(TimeoutError("Timeout"), {})
        assert timeout_error.error_type == ErrorType.TIMEOUT_ERROR
        
        # Test value error
        value_error = handler._standardize_error(ValueError("Invalid"), {})
        assert value_error.error_type == ErrorType.VALIDATION_ERROR
        
        # Test rate limit error (by message content)
        rate_limit_error = handler._standardize_error(Exception("Rate limit exceeded"), {})
        assert rate_limit_error.error_type == ErrorType.RATE_LIMIT_ERROR
        
        # Test API error (by message content)
        api_error = handler._standardize_error(Exception("API call failed"), {})
        assert api_error.error_type == ErrorType.API_ERROR
    
    def test_error_stats_tracking(self):
        """Test error statistics tracking"""
        handler = ErrorHandler()
        
        # Handle different types of errors
        handler.handle_error(NetworkError("Network error"))
        handler.handle_error(APIError("API error"))
        handler.handle_error(NetworkError("Another network error"))
        
        stats = handler.get_error_stats()
        
        assert stats['total_errors'] == 3
        assert stats['errors_by_type']['network_error'] == 2
        assert stats['errors_by_type']['api_error'] == 1
        assert stats['errors_by_severity']['medium'] == 3  # All errors use default medium severity
    
    def test_reset_error_stats(self):
        """Test resetting error statistics"""
        handler = ErrorHandler()
        
        # Generate some errors
        handler.handle_error(NetworkError("Error"))
        assert handler.error_stats['total_errors'] == 1
        
        # Reset stats
        handler.reset_error_stats()
        
        assert handler.error_stats['total_errors'] == 0
        assert handler.error_stats['errors_by_type'] == {}
        assert handler.error_stats['errors_by_severity'] == {}


class TestRetryHandler:
    """Test cases for RetryHandler class"""
    
    def test_retry_handler_initialization(self):
        """Test RetryHandler initialization"""
        handler = RetryHandler()
        
        assert isinstance(handler.config, RetryConfig)
        assert isinstance(handler.error_handler, ErrorHandler)
    
    def test_retry_handler_with_custom_config(self):
        """Test RetryHandler with custom config"""
        config = RetryConfig(max_attempts=5)
        handler = RetryHandler(config)
        
        assert handler.config.max_attempts == 5
    
    def test_should_retry_with_retryable_errors(self):
        """Test should_retry with retryable errors"""
        handler = RetryHandler()
        
        # Test retryable FeishuBotError types
        assert handler.should_retry(NetworkError("Network error"), 0) is True
        assert handler.should_retry(TimeoutError("Timeout"), 1) is True
        assert handler.should_retry(RateLimitError("Rate limit"), 2) is True
        
        # Test retryable standard exceptions
        assert handler.should_retry(ConnectionError("Connection failed"), 0) is True
        assert handler.should_retry(OSError("OS error"), 1) is True
    
    def test_should_retry_with_non_retryable_errors(self):
        """Test should_retry with non-retryable errors"""
        handler = RetryHandler()
        
        # Test non-retryable FeishuBotError types
        assert handler.should_retry(ValidationError("Invalid input"), 0) is False
        assert handler.should_retry(ConfigurationError("Config error"), 1) is False
        assert handler.should_retry(BusinessError("Business error"), 2) is False
    
    def test_should_retry_max_attempts_exceeded(self):
        """Test should_retry when max attempts exceeded"""
        config = RetryConfig(max_attempts=2)
        handler = RetryHandler(config)
        
        # Should not retry when max attempts reached
        assert handler.should_retry(NetworkError("Network error"), 2) is False
        assert handler.should_retry(NetworkError("Network error"), 3) is False
    
    @patch('time.sleep')
    def test_execute_with_retry_success_on_first_attempt(self, mock_sleep):
        """Test execute_with_retry succeeding on first attempt"""
        handler = RetryHandler()
        
        mock_func = Mock(return_value="success")
        
        result = handler.execute_with_retry(mock_func, "arg1", kwarg1="value1")
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
        mock_sleep.assert_not_called()
    
    @patch('time.sleep')
    def test_execute_with_retry_success_after_retries(self, mock_sleep):
        """Test execute_with_retry succeeding after retries"""
        handler = RetryHandler()
        
        # Mock function that fails twice then succeeds
        mock_func = Mock(side_effect=[
            ConnectionError("Connection failed"),
            ConnectionError("Connection failed again"),
            "success"
        ])
        
        result = handler.execute_with_retry(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2  # Two retries
    
    @patch('time.sleep')
    def test_execute_with_retry_all_attempts_fail(self, mock_sleep):
        """Test execute_with_retry when all attempts fail"""
        config = RetryConfig(max_attempts=2)
        handler = RetryHandler(config)
        
        mock_func = Mock(side_effect=ConnectionError("Always fails"))
        
        with pytest.raises(FeishuBotError) as exc_info:
            handler.execute_with_retry(mock_func)
        
        assert exc_info.value.error_type == ErrorType.NETWORK_ERROR
        assert mock_func.call_count == 3  # Initial + 2 retries
        assert mock_sleep.call_count == 2
    
    @patch('time.sleep')
    def test_execute_with_retry_non_retryable_error(self, mock_sleep):
        """Test execute_with_retry with non-retryable error"""
        handler = RetryHandler()
        
        mock_func = Mock(side_effect=ValidationError("Invalid input"))
        
        with pytest.raises(FeishuBotError) as exc_info:
            handler.execute_with_retry(mock_func)
        
        assert exc_info.value.error_type == ErrorType.VALIDATION_ERROR
        assert mock_func.call_count == 1  # No retries
        mock_sleep.assert_not_called()


class TestRetryDecorator:
    """Test cases for retry decorator"""
    
    @patch('time.sleep')
    def test_retry_decorator_success(self, mock_sleep):
        """Test retry decorator with successful function"""
        config = RetryConfig(max_attempts=2)
        
        @retry_with_config(config)
        def test_function():
            return "success"
        
        result = test_function()
        
        assert result == "success"
        mock_sleep.assert_not_called()
    
    @patch('time.sleep')
    def test_retry_decorator_with_retries(self, mock_sleep):
        """Test retry decorator with retries"""
        config = RetryConfig(max_attempts=2)
        call_count = 0
        
        @retry_with_config(config)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"
        
        result = test_function()
        
        assert result == "success"
        assert call_count == 3
        assert mock_sleep.call_count == 2
    
    @patch('time.sleep')
    def test_retry_decorator_all_attempts_fail(self, mock_sleep):
        """Test retry decorator when all attempts fail"""
        config = RetryConfig(max_attempts=1)
        
        @retry_with_config(config)
        def test_function():
            raise ConnectionError("Always fails")
        
        with pytest.raises(FeishuBotError):
            test_function()
        
        assert mock_sleep.call_count == 1


class TestErrorHandlerDecorator:
    """Test cases for error handler decorator"""
    
    def test_error_handler_decorator_success(self):
        """Test error handler decorator with successful function"""
        @handle_errors()
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_error_handler_decorator_with_exception(self):
        """Test error handler decorator with exception"""
        @handle_errors()
        def test_function():
            raise ValueError("Test error")
        
        with pytest.raises(FeishuBotError) as exc_info:
            test_function()
        
        assert exc_info.value.error_type == ErrorType.VALIDATION_ERROR
        assert exc_info.value.original_exception.__class__ == ValueError
    
    def test_error_handler_decorator_with_custom_handler(self):
        """Test error handler decorator with custom handler"""
        custom_handler = ErrorHandler()
        
        @handle_errors(custom_handler)
        def test_function():
            raise NetworkError("Network error")
        
        with pytest.raises(FeishuBotError):
            test_function()
        
        # Check that custom handler recorded the error
        assert custom_handler.error_stats['total_errors'] == 1


class TestCircuitBreaker:
    """Test cases for circuit breaker"""
    
    def test_circuit_breaker_normal_operation(self):
        """Test circuit breaker in normal operation"""
        @create_circuit_breaker(failure_threshold=3, recovery_timeout=1)
        def test_function():
            return "success"
        
        # Should work normally
        result = test_function()
        assert result == "success"
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures"""
        call_count = 0
        
        @create_circuit_breaker(failure_threshold=2, recovery_timeout=1)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")
        
        # First two calls should fail normally
        with pytest.raises(ConnectionError):
            test_function()
        
        with pytest.raises(ConnectionError):
            test_function()
        
        # Third call should trigger circuit breaker
        with pytest.raises(FeishuBotError) as exc_info:
            test_function()
        
        assert "Circuit breaker is OPEN" in str(exc_info.value)
        assert call_count == 2  # Third call was blocked
    
    @patch('time.time')
    def test_circuit_breaker_recovery(self, mock_time):
        """Test circuit breaker recovery after timeout"""
        mock_time.side_effect = [0, 1, 2, 65, 66]  # Simulate time progression
        
        call_count = 0
        
        @create_circuit_breaker(failure_threshold=1, recovery_timeout=60)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Fails first time")
            return "success"
        
        # First call fails, opens circuit
        with pytest.raises(ConnectionError):
            test_function()
        
        # Second call blocked by open circuit
        with pytest.raises(FeishuBotError):
            test_function()
        
        # After recovery timeout, should try again and succeed
        result = test_function()
        assert result == "success"
        assert call_count == 2  # First call failed, second call succeeded