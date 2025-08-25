"""
Unit tests for utility functions in the Feishu Bot System
"""

import json
import time
import pytest
from unittest.mock import patch

from src.shared.utils import (
    verify_feishu_signature,
    format_timestamp,
    sanitize_log_data,
    create_error_response,
    create_success_response,
    extract_headers_from_event,
    is_valid_json,
    retry_with_backoff
)


class TestVerifyFeishuSignature:
    """Test cases for verify_feishu_signature function"""
    
    def test_valid_signature(self):
        """Test signature verification with valid signature"""
        timestamp = "1640995200"
        nonce = "test_nonce"
        encrypt_key = "test_key"
        body = '{"test": "data"}'
        
        # Calculate expected signature
        import hashlib
        string_to_sign = f"{timestamp}{nonce}{encrypt_key}{body}"
        expected_signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
        
        result = verify_feishu_signature(timestamp, nonce, encrypt_key, body, expected_signature)
        assert result is True
    
    def test_invalid_signature(self):
        """Test signature verification with invalid signature"""
        timestamp = "1640995200"
        nonce = "test_nonce"
        encrypt_key = "test_key"
        body = '{"test": "data"}'
        invalid_signature = "invalid_signature"
        
        result = verify_feishu_signature(timestamp, nonce, encrypt_key, body, invalid_signature)
        assert result is False
    
    def test_empty_signature(self):
        """Test signature verification with empty signature"""
        timestamp = "1640995200"
        nonce = "test_nonce"
        encrypt_key = "test_key"
        body = '{"test": "data"}'
        empty_signature = ""
        
        result = verify_feishu_signature(timestamp, nonce, encrypt_key, body, empty_signature)
        assert result is False


class TestFormatTimestamp:
    """Test cases for format_timestamp function"""
    
    def test_default_format(self):
        """Test timestamp formatting with default format"""
        timestamp = 1640995200  # 2022-01-01 08:00:00 UTC
        result = format_timestamp(timestamp)
        
        # Note: This will depend on local timezone
        assert isinstance(result, str)
        assert len(result) == 19  # YYYY-MM-DD HH:MM:SS format
    
    def test_custom_format(self):
        """Test timestamp formatting with custom format"""
        timestamp = 1640995200
        custom_format = "%Y/%m/%d"
        result = format_timestamp(timestamp, custom_format)
        
        assert isinstance(result, str)
        assert "/" in result
    
    def test_zero_timestamp(self):
        """Test timestamp formatting with zero timestamp"""
        timestamp = 0
        result = format_timestamp(timestamp)
        
        assert isinstance(result, str)
        assert "1970" in result  # Unix epoch


class TestSanitizeLogData:
    """Test cases for sanitize_log_data function"""
    
    def test_sanitize_sensitive_keys(self):
        """Test sanitizing data with sensitive keys"""
        data = {
            "app_id": "test_app",
            "app_secret": "secret_value",
            "user_name": "test_user",
            "password": "user_password",
            "normal_field": "normal_value"
        }
        
        result = sanitize_log_data(data)
        
        assert result["app_id"] == "test_app"
        assert result["app_secret"] == "***REDACTED***"
        assert result["user_name"] == "test_user"
        assert result["password"] == "***REDACTED***"
        assert result["normal_field"] == "normal_value"
    
    def test_sanitize_nested_data(self):
        """Test sanitizing nested data structures"""
        data = {
            "config": {
                "app_secret": "secret_value",
                "database_url": "db_url"
            },
            "users": [
                {"name": "user1", "token": "user_token"},
                {"name": "user2", "api_key": "api_key_value"}
            ]
        }
        
        result = sanitize_log_data(data)
        
        assert result["config"]["app_secret"] == "***REDACTED***"
        assert result["config"]["database_url"] == "db_url"
        assert result["users"][0]["name"] == "user1"
        assert result["users"][0]["token"] == "***REDACTED***"
        assert result["users"][1]["api_key"] == "***REDACTED***"
    
    def test_custom_sensitive_keys(self):
        """Test sanitizing with custom sensitive keys"""
        data = {
            "username": "test_user",
            "custom_secret": "secret_value",
            "normal_field": "normal_value"
        }
        
        custom_keys = ["custom_secret"]
        result = sanitize_log_data(data, custom_keys)
        
        assert result["username"] == "test_user"  # Not in custom keys
        assert result["custom_secret"] == "***REDACTED***"
        assert result["normal_field"] == "normal_value"


class TestCreateErrorResponse:
    """Test cases for create_error_response function"""
    
    def test_default_error_response(self):
        """Test creating error response with default status code"""
        error_code = "INVALID_REQUEST"
        error_message = "Request validation failed"
        
        result = create_error_response(error_code, error_message)
        
        assert result["statusCode"] == 500
        assert "Content-Type" in result["headers"]
        assert result["headers"]["Content-Type"] == "application/json"
        
        body = json.loads(result["body"])
        assert body["error"]["code"] == error_code
        assert body["error"]["message"] == error_message
        assert "timestamp" in body["error"]
    
    def test_custom_status_code(self):
        """Test creating error response with custom status code"""
        error_code = "NOT_FOUND"
        error_message = "Resource not found"
        status_code = 404
        
        result = create_error_response(error_code, error_message, status_code)
        
        assert result["statusCode"] == 404


class TestCreateSuccessResponse:
    """Test cases for create_success_response function"""
    
    def test_success_response_without_data(self):
        """Test creating success response without data"""
        result = create_success_response()
        
        assert result["statusCode"] == 200
        assert "Content-Type" in result["headers"]
        
        body = json.loads(result["body"])
        assert body["success"] is True
        assert "timestamp" in body
        assert "data" not in body
    
    def test_success_response_with_data(self):
        """Test creating success response with data"""
        test_data = {"message": "Operation completed", "count": 5}
        result = create_success_response(test_data)
        
        assert result["statusCode"] == 200
        
        body = json.loads(result["body"])
        assert body["success"] is True
        assert body["data"] == test_data
    
    def test_custom_status_code(self):
        """Test creating success response with custom status code"""
        result = create_success_response(status_code=201)
        
        assert result["statusCode"] == 201


class TestExtractHeadersFromEvent:
    """Test cases for extract_headers_from_event function"""
    
    def test_api_gateway_v1_headers(self):
        """Test extracting headers from API Gateway v1.0 event"""
        event = {
            "headers": {
                "Content-Type": "application/json",
                "X-Feishu-Signature": "test_signature",
                "Authorization": "Bearer token"
            }
        }
        
        result = extract_headers_from_event(event)
        
        assert result["content-type"] == "application/json"
        assert result["x-feishu-signature"] == "test_signature"
        assert result["authorization"] == "Bearer token"
    
    def test_api_gateway_v2_headers(self):
        """Test extracting headers from API Gateway v2.0 event"""
        event = {
            "multiValueHeaders": {
                "Content-Type": ["application/json"],
                "X-Feishu-Signature": ["test_signature"],
                "Custom-Header": ["value1", "value2"]  # Multiple values
            }
        }
        
        result = extract_headers_from_event(event)
        
        assert result["content-type"] == "application/json"
        assert result["x-feishu-signature"] == "test_signature"
        assert result["custom-header"] == "value1"  # Should take first value
    
    def test_empty_headers(self):
        """Test extracting headers from event with no headers"""
        event = {}
        
        result = extract_headers_from_event(event)
        
        assert result == {}
    
    def test_null_headers(self):
        """Test extracting headers from event with null headers"""
        event = {
            "headers": None,
            "multiValueHeaders": None
        }
        
        result = extract_headers_from_event(event)
        
        assert result == {}


class TestIsValidJson:
    """Test cases for is_valid_json function"""
    
    def test_valid_json_object(self):
        """Test with valid JSON object"""
        json_str = '{"key": "value", "number": 123}'
        result = is_valid_json(json_str)
        assert result is True
    
    def test_valid_json_array(self):
        """Test with valid JSON array"""
        json_str = '[1, 2, 3, "test"]'
        result = is_valid_json(json_str)
        assert result is True
    
    def test_valid_json_string(self):
        """Test with valid JSON string"""
        json_str = '"simple string"'
        result = is_valid_json(json_str)
        assert result is True
    
    def test_invalid_json(self):
        """Test with invalid JSON"""
        json_str = '{"key": "value", "invalid": }'
        result = is_valid_json(json_str)
        assert result is False
    
    def test_empty_string(self):
        """Test with empty string"""
        json_str = ''
        result = is_valid_json(json_str)
        assert result is False
    
    def test_none_input(self):
        """Test with None input"""
        result = is_valid_json(None)
        assert result is False


class TestRetryWithBackoff:
    """Test cases for retry_with_backoff decorator"""
    
    def test_successful_function(self):
        """Test retry decorator with function that succeeds"""
        @retry_with_backoff
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    def test_function_succeeds_after_retries(self):
        """Test retry decorator with function that succeeds after retries"""
        call_count = 0
        
        @retry_with_backoff
        def function_with_retries():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = function_with_retries()
        assert result == "success"
        assert call_count == 3
    
    @patch('time.sleep')
    def test_function_fails_all_retries(self, mock_sleep):
        """Test retry decorator with function that always fails"""
        @retry_with_backoff
        def always_failing_function():
            raise ValueError("Permanent error")
        
        with pytest.raises(ValueError) as exc_info:
            always_failing_function()
        
        assert str(exc_info.value) == "Permanent error"
        # Should have called sleep 3 times (for 3 retries)
        assert mock_sleep.call_count == 3
    
    @patch('time.sleep')
    def test_custom_retry_parameters(self, mock_sleep):
        """Test retry decorator with custom parameters"""
        call_count = 0
        
        def custom_retry_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        decorated_function = retry_with_backoff(custom_retry_function, max_retries=2, base_delay=0.5)
        
        with pytest.raises(ValueError):
            decorated_function()
        
        assert call_count == 3  # 1 initial + 2 retries
        assert mock_sleep.call_count == 2
        
        # Check exponential backoff delays
        expected_delays = [0.5, 1.0]  # base_delay * 2^attempt
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays