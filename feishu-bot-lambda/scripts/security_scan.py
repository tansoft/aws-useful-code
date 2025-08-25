#!/usr/bin/env python3
"""
安全扫描脚本

此脚本用于对飞书机器人系统进行安全扫描，检测潜在的安全漏洞和配置问题。
"""

import json
import time
import requests
import hashlib
import hmac
import logging
import argparse
import base64
import urllib.parse
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
class SecurityFinding:
    """安全发现"""
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    category: str
    title: str
    description: str
    recommendation: str
    evidence: Optional[Dict[str, Any]] = None

@dataclass
class SecurityTestResult:
    """安全测试结果"""
    test_name: str
    passed: bool
    findings: List[SecurityFinding]
    details: Optional[Dict[str, Any]] = None

class SecurityScanner:
    """安全扫描器"""
    
    def __init__(self, webhook_url: str, encrypt_key: str, verification_token: str):
        self.webhook_url = webhook_url
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token
        self.results: List[SecurityTestResult] = []
    
    def run_security_scan(self) -> Dict[str, Any]:
        """运行完整的安全扫描"""
        logger.info("开始安全扫描...")
        start_time = time.time()
        
        security_tests = [
            ("输入验证测试", self.test_input_validation),
            ("签名验证测试", self.test_signature_verification),
            ("注入攻击测试", self.test_injection_attacks),
            ("认证绕过测试", self.test_authentication_bypass),
            ("信息泄露测试", self.test_information_disclosure),
            ("拒绝服务测试", self.test_denial_of_service),
            ("HTTP安全头测试", self.test_http_security_headers),
            ("SSL/TLS配置测试", self.test_ssl_tls_configuration)
        ]
        
        for test_name, test_func in security_tests:
            logger.info(f"执行安全测试: {test_name}")
            try:
                test_func()
                logger.info(f"✅ {test_name} 完成")
            except Exception as e:
                logger.error(f"❌ {test_name} 失败: {e}")
                self.results.append(SecurityTestResult(
                    test_name=test_name,
                    passed=False,
                    findings=[SecurityFinding(
                        severity="HIGH",
                        category="测试执行",
                        title=f"{test_name}执行失败",
                        description=f"安全测试执行过程中发生错误: {e}",
                        recommendation="检查测试环境和配置"
                    )],
                    details={'error': str(e)}
                ))
        
        total_duration = time.time() - start_time
        return self.generate_security_report(total_duration)
    
    def test_input_validation(self):
        """测试输入验证"""
        findings = []
        
        # 测试用例：无效JSON
        test_cases = [
            {
                'name': '无效JSON格式',
                'payload': 'invalid json',
                'expected_status': 400,
                'content_type': 'application/json'
            },
            {
                'name': '空请求体',
                'payload': '',
                'expected_status': 400,
                'content_type': 'application/json'
            },
            {
                'name': '超大请求体',
                'payload': json.dumps({'data': 'x' * 1000000}),  # 1MB数据
                'expected_status': 413,
                'content_type': 'application/json'
            },
            {
                'name': '恶意字符注入',
                'payload': json.dumps({
                    'header': {'event_type': '<script>alert("xss")</script>'},
                    'event': {'test': '../../etc/passwd'}
                }),
                'expected_status': 400,
                'content_type': 'application/json'
            }
        ]
        
        for test_case in test_cases:
            try:
                response = requests.post(
                    self.webhook_url,
                    data=test_case['payload'],
                    headers={'Content-Type': test_case['content_type']},
                    timeout=10
                )
                
                if response.status_code != test_case['expected_status']:
                    findings.append(SecurityFinding(
                        severity="MEDIUM",
                        category="输入验证",
                        title=f"输入验证不当: {test_case['name']}",
                        description=f"期望状态码{test_case['expected_status']}，实际返回{response.status_code}",
                        recommendation="加强输入验证，正确处理无效输入",
                        evidence={
                            'test_case': test_case['name'],
                            'expected_status': test_case['expected_status'],
                            'actual_status': response.status_code,
                            'response_body': response.text[:500]
                        }
                    ))
                    
            except requests.exceptions.RequestException as e:
                # 网络错误可能是正常的（如超时保护）
                logger.debug(f"请求异常（可能正常）: {e}")
        
        self.results.append(SecurityTestResult(
            test_name="输入验证测试",
            passed=len(findings) == 0,
            findings=findings
        ))
    
    def test_signature_verification(self):
        """测试签名验证"""
        findings = []
        
        # 测试用例
        test_cases = [
            {
                'name': '无签名头',
                'headers': {'Content-Type': 'application/json'},
                'payload': {'test': 'data'},
                'expected_status': 401
            },
            {
                'name': '错误签名',
                'headers': {
                    'Content-Type': 'application/json',
                    'X-Lark-Request-Timestamp': str(int(time.time())),
                    'X-Lark-Request-Nonce': 'test_nonce',
                    'X-Lark-Signature': 'invalid_signature'
                },
                'payload': {'test': 'data'},
                'expected_status': 401
            },
            {
                'name': '过期时间戳',
                'headers': {
                    'Content-Type': 'application/json',
                    'X-Lark-Request-Timestamp': str(int(time.time()) - 3600),  # 1小时前
                    'X-Lark-Request-Nonce': 'test_nonce',
                    'X-Lark-Signature': 'test_signature'
                },
                'payload': {'test': 'data'},
                'expected_status': 401
            },
            {
                'name': '重放攻击',
                'headers': None,  # 将使用相同的nonce发送两次
                'payload': {'test': 'data'},
                'expected_status': 401
            }
        ]
        
        # 测试重放攻击
        timestamp = str(int(time.time()))
        nonce = 'replay_test_nonce'
        payload = json.dumps({'test': 'replay'})
        
        string_to_sign = f"{timestamp}{nonce}{self.encrypt_key}{payload}"
        signature = hashlib.sha256(string_to_sign.encode()).hexdigest()
        
        replay_headers = {
            'Content-Type': 'application/json',
            'X-Lark-Request-Timestamp': timestamp,
            'X-Lark-Request-Nonce': nonce,
            'X-Lark-Signature': signature
        }
        
        # 发送第一次请求
        response1 = requests.post(
            self.webhook_url,
            data=payload,
            headers=replay_headers,
            timeout=10
        )
        
        # 发送第二次相同请求（重放攻击）
        response2 = requests.post(
            self.webhook_url,
            data=payload,
            headers=replay_headers,
            timeout=10
        )
        
        if response2.status_code != 401:
            findings.append(SecurityFinding(
                severity="HIGH",
                category="签名验证",
                title="重放攻击防护不足",
                description="系统未能检测和阻止重放攻击",
                recommendation="实施nonce验证机制，防止重放攻击",
                evidence={
                    'first_response': response1.status_code,
                    'replay_response': response2.status_code
                }
            ))
        
        # 测试其他用例
        for test_case in test_cases[:-1]:  # 排除重放攻击用例
            try:
                response = requests.post(
                    self.webhook_url,
                    json=test_case['payload'],
                    headers=test_case['headers'],
                    timeout=10
                )
                
                if response.status_code != test_case['expected_status']:
                    findings.append(SecurityFinding(
                        severity="HIGH",
                        category="签名验证",
                        title=f"签名验证绕过: {test_case['name']}",
                        description=f"期望状态码{test_case['expected_status']}，实际返回{response.status_code}",
                        recommendation="加强签名验证逻辑，确保所有请求都经过验证",
                        evidence={
                            'test_case': test_case['name'],
                            'expected_status': test_case['expected_status'],
                            'actual_status': response.status_code
                        }
                    ))
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"请求异常: {e}")
        
        self.results.append(SecurityTestResult(
            test_name="签名验证测试",
            passed=len(findings) == 0,
            findings=findings
        ))
    
    def test_injection_attacks(self):
        """测试注入攻击"""
        findings = []
        
        # SQL注入测试载荷
        sql_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "1' UNION SELECT * FROM users --",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --"
        ]
        
        # NoSQL注入测试载荷
        nosql_payloads = [
            {"$ne": None},
            {"$gt": ""},
            {"$where": "function() { return true; }"}
        ]
        
        # 命令注入测试载荷
        command_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& whoami",
            "`id`"
        ]
        
        # LDAP注入测试载荷
        ldap_payloads = [
            "*)(uid=*",
            "*)(|(uid=*))",
            "admin)(&(password=*))"
        ]
        
        all_payloads = {
            'SQL注入': sql_payloads,
            'NoSQL注入': nosql_payloads,
            '命令注入': command_payloads,
            'LDAP注入': ldap_payloads
        }
        
        for injection_type, payloads in all_payloads.items():
            for payload in payloads:
                test_data = {
                    "header": {
                        "event_type": "im.message.receive_v1"
                    },
                    "event": {
                        "message": {
                            "content": json.dumps({"text": str(payload)}),
                            "message_type": "text"
                        }
                    }
                }
                
                try:
                    # 创建有效签名
                    timestamp = str(int(time.time()))
                    nonce = f"injection_test_{int(time.time() * 1000)}"
                    body = json.dumps(test_data)
                    
                    string_to_sign = f"{timestamp}{nonce}{self.encrypt_key}{body}"
                    signature = hashlib.sha256(string_to_sign.encode()).hexdigest()
                    
                    headers = {
                        'Content-Type': 'application/json',
                        'X-Lark-Request-Timestamp': timestamp,
                        'X-Lark-Request-Nonce': nonce,
                        'X-Lark-Signature': signature
                    }
                    
                    response = requests.post(
                        self.webhook_url,
                        data=body,
                        headers=headers,
                        timeout=10
                    )
                    
                    # 检查响应中是否包含敏感信息泄露
                    response_text = response.text.lower()
                    sensitive_patterns = [
                        'error', 'exception', 'stack trace', 'sql',
                        'database', 'mysql', 'postgresql', 'mongodb',
                        'root', 'admin', 'password', '/etc/passwd',
                        'uid=', 'gid=', 'groups='
                    ]
                    
                    for pattern in sensitive_patterns:
                        if pattern in response_text:
                            findings.append(SecurityFinding(
                                severity="HIGH",
                                category="注入攻击",
                                title=f"{injection_type}可能成功",
                                description=f"响应中包含敏感信息，可能存在{injection_type}漏洞",
                                recommendation="实施输入过滤和参数化查询，避免直接拼接用户输入",
                                evidence={
                                    'injection_type': injection_type,
                                    'payload': str(payload),
                                    'response_status': response.status_code,
                                    'sensitive_pattern': pattern,
                                    'response_snippet': response_text[:200]
                                }
                            ))
                            break
                    
                    # 检查异常长的响应时间（可能表示盲注成功）
                    # 这里简化处理，实际应该测量响应时间
                    
                except requests.exceptions.RequestException as e:
                    logger.debug(f"注入测试请求异常: {e}")
        
        self.results.append(SecurityTestResult(
            test_name="注入攻击测试",
            passed=len(findings) == 0,
            findings=findings
        ))
    
    def test_authentication_bypass(self):
        """测试认证绕过"""
        findings = []
        
        # 测试用例
        bypass_attempts = [
            {
                'name': '缺少时间戳头',
                'headers': {
                    'Content-Type': 'application/json',
                    'X-Lark-Request-Nonce': 'test_nonce',
                    'X-Lark-Signature': 'test_signature'
                }
            },
            {
                'name': '缺少nonce头',
                'headers': {
                    'Content-Type': 'application/json',
                    'X-Lark-Request-Timestamp': str(int(time.time())),
                    'X-Lark-Signature': 'test_signature'
                }
            },
            {
                'name': '空签名',
                'headers': {
                    'Content-Type': 'application/json',
                    'X-Lark-Request-Timestamp': str(int(time.time())),
                    'X-Lark-Request-Nonce': 'test_nonce',
                    'X-Lark-Signature': ''
                }
            },
            {
                'name': '修改Content-Type绕过',
                'headers': {
                    'Content-Type': 'text/plain',
                    'X-Lark-Request-Timestamp': str(int(time.time())),
                    'X-Lark-Request-Nonce': 'test_nonce',
                    'X-Lark-Signature': 'test_signature'
                }
            }
        ]
        
        test_payload = {'test': 'bypass_attempt'}
        
        for attempt in bypass_attempts:
            try:
                response = requests.post(
                    self.webhook_url,
                    json=test_payload,
                    headers=attempt['headers'],
                    timeout=10
                )
                
                # 如果返回200，可能存在认证绕过
                if response.status_code == 200:
                    findings.append(SecurityFinding(
                        severity="CRITICAL",
                        category="认证绕过",
                        title=f"认证绕过漏洞: {attempt['name']}",
                        description="系统未能正确验证请求认证信息",
                        recommendation="确保所有请求都经过完整的认证验证",
                        evidence={
                            'bypass_method': attempt['name'],
                            'response_status': response.status_code,
                            'response_body': response.text[:200]
                        }
                    ))
                
            except requests.exceptions.RequestException as e:
                logger.debug(f"认证绕过测试请求异常: {e}")
        
        self.results.append(SecurityTestResult(
            test_name="认证绕过测试",
            passed=len(findings) == 0,
            findings=findings
        ))
    
    def test_information_disclosure(self):
        """测试信息泄露"""
        findings = []
        
        # 测试错误信息泄露
        error_test_cases = [
            {
                'name': '服务器错误信息',
                'payload': {'invalid': 'structure'},
                'headers': {'Content-Type': 'application/json'}
            },
            {
                'name': '异常堆栈信息',
                'payload': 'malformed json',
                'headers': {'Content-Type': 'application/json'}
            }
        ]
        
        for test_case in error_test_cases:
            try:
                response = requests.post(
                    self.webhook_url,
                    data=test_case['payload'] if isinstance(test_case['payload'], str) else json.dumps(test_case['payload']),
                    headers=test_case['headers'],
                    timeout=10
                )
                
                response_text = response.text.lower()
                
                # 检查敏感信息泄露
                sensitive_info = [
                    'traceback', 'stack trace', 'exception',
                    'internal server error', 'debug',
                    'aws', 'lambda', 'function',
                    'database', 'connection',
                    'secret', 'key', 'token',
                    'file not found', 'permission denied',
                    'version', 'server'
                ]
                
                for info in sensitive_info:
                    if info in response_text:
                        findings.append(SecurityFinding(
                            severity="MEDIUM",
                            category="信息泄露",
                            title=f"敏感信息泄露: {info}",
                            description=f"错误响应中包含敏感信息: {info}",
                            recommendation="配置通用错误页面，避免泄露系统内部信息",
                            evidence={
                                'test_case': test_case['name'],
                                'sensitive_info': info,
                                'response_status': response.status_code,
                                'response_snippet': response_text[:300]
                            }
                        ))
                        break
                
            except requests.exceptions.RequestException as e:
                logger.debug(f"信息泄露测试请求异常: {e}")
        
        # 测试HTTP方法信息泄露
        methods = ['GET', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        
        for method in methods:
            try:
                response = requests.request(
                    method,
                    self.webhook_url,
                    timeout=10
                )
                
                # 检查是否返回了不应该支持的方法的响应
                if response.status_code not in [405, 501]:
                    findings.append(SecurityFinding(
                        severity="LOW",
                        category="信息泄露",
                        title=f"HTTP方法{method}意外响应",
                        description=f"HTTP {method}方法返回了意外的状态码: {response.status_code}",
                        recommendation="确保只支持必要的HTTP方法",
                        evidence={
                            'method': method,
                            'status_code': response.status_code,
                            'response_headers': dict(response.headers)
                        }
                    ))
                
            except requests.exceptions.RequestException as e:
                logger.debug(f"HTTP方法测试异常: {e}")
        
        self.results.append(SecurityTestResult(
            test_name="信息泄露测试",
            passed=len(findings) == 0,
            findings=findings
        ))
    
    def test_denial_of_service(self):
        """测试拒绝服务攻击"""
        findings = []
        
        # 测试大量并发请求
        logger.info("测试DoS攻击抵抗能力...")
        
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def send_request():
            try:
                payload = {'test': 'dos_test'}
                timestamp = str(int(time.time()))
                nonce = f"dos_test_{threading.current_thread().ident}"
                body = json.dumps(payload)
                
                string_to_sign = f"{timestamp}{nonce}{self.encrypt_key}{body}"
                signature = hashlib.sha256(string_to_sign.encode()).hexdigest()
                
                headers = {
                    'Content-Type': 'application/json',
                    'X-Lark-Request-Timestamp': timestamp,
                    'X-Lark-Request-Nonce': nonce,
                    'X-Lark-Signature': signature
                }
                
                response = requests.post(
                    self.webhook_url,
                    data=body,
                    headers=headers,
                    timeout=5
                )
                
                results_queue.put({
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds()
                })
                
            except requests.exceptions.RequestException as e:
                results_queue.put({'error': str(e)})
        
        # 发送50个并发请求
        threads = []
        for i in range(50):
            thread = threading.Thread(target=send_request)
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=10)
        
        # 收集结果
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # 分析结果
        successful_requests = [r for r in results if 'status_code' in r]
        error_requests = [r for r in results if 'error' in r]
        
        if len(error_requests) > len(successful_requests):
            findings.append(SecurityFinding(
                severity="MEDIUM",
                category="拒绝服务",
                title="DoS攻击敏感性",
                description=f"在并发测试中，{len(error_requests)}个请求失败，{len(successful_requests)}个成功",
                recommendation="实施速率限制和请求队列管理",
                evidence={
                    'total_requests': len(results),
                    'successful_requests': len(successful_requests),
                    'failed_requests': len(error_requests)
                }
            ))
        
        # 测试慢速攻击
        try:
            # 发送一个非常慢的请求
            slow_payload = json.dumps({'data': 'x' * 10000})  # 较大载荷
            
            start_time = time.time()
            response = requests.post(
                self.webhook_url,
                data=slow_payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response_time = time.time() - start_time
            
            # 如果响应时间过长，可能存在慢速攻击风险
            if response_time > 10:
                findings.append(SecurityFinding(
                    severity="LOW",
                    category="拒绝服务",
                    title="慢速攻击风险",
                    description=f"大载荷请求响应时间过长: {response_time:.2f}秒",
                    recommendation="设置合理的请求超时时间和载荷大小限制",
                    evidence={
                        'response_time': response_time,
                        'payload_size': len(slow_payload)
                    }
                ))
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"慢速攻击测试异常: {e}")
        
        self.results.append(SecurityTestResult(
            test_name="拒绝服务测试",
            passed=len(findings) == 0,
            findings=findings
        ))
    
    def test_http_security_headers(self):
        """测试HTTP安全头"""
        findings = []
        
        try:
            response = requests.get(self.webhook_url, timeout=10)
            headers = response.headers
            
            # 检查安全头
            security_headers = {
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
                'X-XSS-Protection': '1; mode=block',
                'Strict-Transport-Security': None,  # 应该存在
                'Content-Security-Policy': None,  # 应该存在
                'Referrer-Policy': None  # 应该存在
            }
            
            for header, expected_value in security_headers.items():
                if header not in headers:
                    findings.append(SecurityFinding(
                        severity="MEDIUM",
                        category="HTTP安全头",
                        title=f"缺少安全头: {header}",
                        description=f"响应中缺少重要的安全头: {header}",
                        recommendation=f"添加{header}安全头以增强安全性",
                        evidence={'missing_header': header}
                    ))
                elif expected_value and isinstance(expected_value, list):
                    if headers[header] not in expected_value:
                        findings.append(SecurityFinding(
                            severity="LOW",
                            category="HTTP安全头",
                            title=f"安全头配置不当: {header}",
                            description=f"{header}的值不在推荐范围内",
                            recommendation=f"将{header}设置为推荐值: {expected_value}",
                            evidence={
                                'header': header,
                                'current_value': headers[header],
                                'recommended_values': expected_value
                            }
                        ))
                elif expected_value and headers[header] != expected_value:
                    findings.append(SecurityFinding(
                        severity="LOW",
                        category="HTTP安全头",
                        title=f"安全头配置不当: {header}",
                        description=f"{header}的值不是推荐值",
                        recommendation=f"将{header}设置为: {expected_value}",
                        evidence={
                            'header': header,
                            'current_value': headers[header],
                            'recommended_value': expected_value
                        }
                    ))
            
            # 检查信息泄露头
            info_disclosure_headers = [
                'Server', 'X-Powered-By', 'X-AspNet-Version',
                'X-AspNetMvc-Version', 'X-Runtime'
            ]
            
            for header in info_disclosure_headers:
                if header in headers:
                    findings.append(SecurityFinding(
                        severity="LOW",
                        category="HTTP安全头",
                        title=f"信息泄露头: {header}",
                        description=f"响应中包含可能泄露服务器信息的头: {header}",
                        recommendation=f"移除或隐藏{header}头",
                        evidence={
                            'header': header,
                            'value': headers[header]
                        }
                    ))
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"HTTP安全头测试异常: {e}")
        
        self.results.append(SecurityTestResult(
            test_name="HTTP安全头测试",
            passed=len(findings) == 0,
            findings=findings
        ))
    
    def test_ssl_tls_configuration(self):
        """测试SSL/TLS配置"""
        findings = []
        
        if not self.webhook_url.startswith('https://'):
            findings.append(SecurityFinding(
                severity="CRITICAL",
                category="SSL/TLS配置",
                title="未使用HTTPS",
                description="Webhook URL未使用HTTPS协议",
                recommendation="启用HTTPS以保护数据传输安全",
                evidence={'webhook_url': self.webhook_url}
            ))
        else:
            try:
                import ssl
                import socket
                from urllib.parse import urlparse
                
                parsed_url = urlparse(self.webhook_url)
                hostname = parsed_url.hostname
                port = parsed_url.port or 443
                
                # 创建SSL上下文
                context = ssl.create_default_context()
                
                # 连接并获取证书信息
                with socket.create_connection((hostname, port), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                        cert = ssock.getpeercert()
                        cipher = ssock.cipher()
                        version = ssock.version()
                        
                        # 检查SSL/TLS版本
                        if version in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']:
                            findings.append(SecurityFinding(
                                severity="HIGH",
                                category="SSL/TLS配置",
                                title=f"使用不安全的TLS版本: {version}",
                                description="使用了已知存在安全漏洞的TLS版本",
                                recommendation="升级到TLS 1.2或更高版本",
                                evidence={'tls_version': version}
                            ))
                        
                        # 检查加密套件
                        if cipher:
                            cipher_name = cipher[0]
                            # 检查弱加密套件
                            weak_ciphers = ['RC4', 'DES', '3DES', 'MD5']
                            for weak_cipher in weak_ciphers:
                                if weak_cipher in cipher_name:
                                    findings.append(SecurityFinding(
                                        severity="MEDIUM",
                                        category="SSL/TLS配置",
                                        title=f"使用弱加密套件: {cipher_name}",
                                        description="使用了不安全的加密套件",
                                        recommendation="配置强加密套件",
                                        evidence={'cipher': cipher_name}
                                    ))
                                    break
                        
                        # 检查证书有效期
                        if cert:
                            import datetime
                            not_after = datetime.datetime.strptime(
                                cert['notAfter'], '%b %d %H:%M:%S %Y %Z'
                            )
                            days_until_expiry = (not_after - datetime.datetime.now()).days
                            
                            if days_until_expiry < 30:
                                findings.append(SecurityFinding(
                                    severity="MEDIUM",
                                    category="SSL/TLS配置",
                                    title="SSL证书即将过期",
                                    description=f"SSL证书将在{days_until_expiry}天后过期",
                                    recommendation="及时更新SSL证书",
                                    evidence={
                                        'expiry_date': cert['notAfter'],
                                        'days_until_expiry': days_until_expiry
                                    }
                                ))
                
            except Exception as e:
                logger.debug(f"SSL/TLS配置测试异常: {e}")
        
        self.results.append(SecurityTestResult(
            test_name="SSL/TLS配置测试",
            passed=len(findings) == 0,
            findings=findings
        ))
    
    def generate_security_report(self, total_duration: float) -> Dict[str, Any]:
        """生成安全扫描报告"""
        all_findings = []
        for result in self.results:
            all_findings.extend(result.findings)
        
        # 按严重程度分类
        findings_by_severity = {
            'CRITICAL': [f for f in all_findings if f.severity == 'CRITICAL'],
            'HIGH': [f for f in all_findings if f.severity == 'HIGH'],
            'MEDIUM': [f for f in all_findings if f.severity == 'MEDIUM'],
            'LOW': [f for f in all_findings if f.severity == 'LOW'],
            'INFO': [f for f in all_findings if f.severity == 'INFO']
        }
        
        # 计算安全评分
        severity_weights = {'CRITICAL': 10, 'HIGH': 7, 'MEDIUM': 4, 'LOW': 2, 'INFO': 1}
        total_score = sum(
            len(findings) * weight 
            for severity, findings in findings_by_severity.items() 
            for weight in [severity_weights.get(severity, 0)]
        )
        
        # 安全评分（100分制，分数越高越安全）
        max_possible_score = len(self.results) * 10  # 假设每个测试最多10分
        security_score = max(0, 100 - (total_score / max_possible_score * 100)) if max_possible_score > 0 else 100
        
        report = {
            'security_scan_summary': {
                'scan_time': datetime.utcnow().isoformat(),
                'total_duration_seconds': total_duration,
                'total_tests': len(self.results),
                'passed_tests': sum(1 for r in self.results if r.passed),
                'failed_tests': sum(1 for r in self.results if not r.passed),
                'total_findings': len(all_findings),
                'security_score': f"{security_score:.1f}/100",
                'findings_by_severity': {
                    severity: len(findings) 
                    for severity, findings in findings_by_severity.items()
                }
            },
            'test_results': [
                {
                    'test_name': result.test_name,
                    'passed': result.passed,
                    'findings_count': len(result.findings),
                    'findings': [
                        {
                            'severity': finding.severity,
                            'category': finding.category,
                            'title': finding.title,
                            'description': finding.description,
                            'recommendation': finding.recommendation,
                            'evidence': finding.evidence
                        }
                        for finding in result.findings
                    ],
                    'details': result.details
                }
                for result in self.results
            ],
            'security_findings': [
                {
                    'severity': finding.severity,
                    'category': finding.category,
                    'title': finding.title,
                    'description': finding.description,
                    'recommendation': finding.recommendation,
                    'evidence': finding.evidence
                }
                for finding in all_findings
            ],
            'recommendations': self._generate_security_recommendations(findings_by_severity)
        }
        
        return report
    
    def _generate_security_recommendations(self, findings_by_severity: Dict[str, List[SecurityFinding]]) -> List[str]:
        """生成安全建议"""
        recommendations = []
        
        if findings_by_severity['CRITICAL']:
            recommendations.append("🚨 发现严重安全漏洞，需要立即修复")
        
        if findings_by_severity['HIGH']:
            recommendations.append("⚠️ 发现高危安全问题，建议优先处理")
        
        if findings_by_severity['MEDIUM']:
            recommendations.append("📋 发现中等安全问题，建议在下次更新中修复")
        
        if findings_by_severity['LOW']:
            recommendations.append("📝 发现低危安全问题，可在方便时修复")
        
        # 通用建议
        recommendations.extend([
            "定期进行安全扫描和渗透测试",
            "保持系统和依赖库的最新版本",
            "实施安全开发生命周期(SDLC)",
            "建立安全事件响应计划",
            "定期审查和更新安全配置"
        ])
        
        return recommendations

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='飞书机器人系统安全扫描')
    parser.add_argument('--webhook-url', required=True, help='Webhook URL')
    parser.add_argument('--encrypt-key', required=True, help='飞书加密密钥')
    parser.add_argument('--verification-token', required=True, help='飞书验证Token')
    parser.add_argument('--output', default='security_scan_report.json', help='安全扫描报告输出文件')
    
    args = parser.parse_args()
    
    # 运行安全扫描
    scanner = SecurityScanner(
        webhook_url=args.webhook_url,
        encrypt_key=args.encrypt_key,
        verification_token=args.verification_token
    )
    
    report = scanner.run_security_scan()
    
    # 输出报告
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 打印摘要
    summary = report['security_scan_summary']
    print(f"\n{'='*60}")
    print(f"安全扫描报告")
    print(f"{'='*60}")
    print(f"总测试数: {summary['total_tests']}")
    print(f"通过测试: {summary['passed_tests']}")
    print(f"失败测试: {summary['failed_tests']}")
    print(f"安全评分: {summary['security_score']}")
    print(f"总发现数: {summary['total_findings']}")
    print(f"扫描耗时: {summary['total_duration_seconds']:.2f}秒")
    print(f"报告文件: {args.output}")
    
    # 打印发现摘要
    findings_by_severity = summary['findings_by_severity']
    print(f"\n发现摘要:")
    for severity, count in findings_by_severity.items():
        if count > 0:
            emoji = {'CRITICAL': '🚨', 'HIGH': '⚠️', 'MEDIUM': '📋', 'LOW': '📝', 'INFO': 'ℹ️'}
            print(f"  {emoji.get(severity, '•')} {severity}: {count}")
    
    # 打印建议
    if 'recommendations' in report:
        print(f"\n安全建议:")
        for i, rec in enumerate(report['recommendations'][:5], 1):  # 只显示前5条
            print(f"  {i}. {rec}")
    
    # 根据安全评分决定退出码
    score = float(summary['security_score'].split('/')[0])
    if score < 70:
        print(f"\n❌ 安全评分过低，存在重要安全问题")
        exit(1)
    elif score < 85:
        print(f"\n⚠️ 安全评分一般，建议改进安全配置")
        exit(0)
    else:
        print(f"\n✅ 安全评分良好!")
        exit(0)

if __name__ == '__main__':
    main()