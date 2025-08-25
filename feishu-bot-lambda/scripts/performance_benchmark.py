#!/usr/bin/env python3
"""
性能基准测试脚本

此脚本用于测试飞书机器人系统的性能指标，包括响应时间、吞吐量、并发处理能力等。
"""

import json
import time
import asyncio
import aiohttp
import hashlib
import statistics
import logging
import argparse
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """性能指标"""
    metric_name: str
    value: float
    unit: str
    description: str
    threshold: Optional[float] = None
    passed: Optional[bool] = None

@dataclass
class BenchmarkResult:
    """基准测试结果"""
    test_name: str
    duration_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    metrics: List[PerformanceMetric]
    details: Optional[Dict[str, Any]] = None

class PerformanceBenchmark:
    """性能基准测试类"""
    
    def __init__(self, webhook_url: str, encrypt_key: str, verification_token: str):
        self.webhook_url = webhook_url
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token
        self.results: List[BenchmarkResult] = []
    
    async def run_all_benchmarks(self) -> Dict[str, Any]:
        """运行所有性能基准测试"""
        logger.info("开始性能基准测试...")
        start_time = time.time()
        
        benchmark_tests = [
            ("响应时间基准测试", self.benchmark_response_time),
            ("并发处理基准测试", self.benchmark_concurrent_processing),
            ("吞吐量基准测试", self.benchmark_throughput),
            ("负载测试", self.benchmark_load_test),
            ("压力测试", self.benchmark_stress_test)
        ]
        
        for test_name, test_func in benchmark_tests:
            logger.info(f"执行基准测试: {test_name}")
            try:
                await test_func()
                logger.info(f"✅ {test_name} 完成")
            except Exception as e:
                logger.error(f"❌ {test_name} 失败: {e}")
                # 添加失败结果
                self.results.append(BenchmarkResult(
                    test_name=test_name,
                    duration_seconds=0,
                    total_requests=0,
                    successful_requests=0,
                    failed_requests=1,
                    metrics=[],
                    details={'error': str(e)}
                ))
        
        total_duration = time.time() - start_time
        return self.generate_benchmark_report(total_duration)
    
    async def benchmark_response_time(self):
        """响应时间基准测试"""
        logger.info("开始响应时间基准测试...")
        
        # 测试不同类型的请求
        test_cases = [
            ("URL验证请求", self.create_url_verification_payload),
            ("简单消息请求", self.create_simple_message_payload),
            ("复杂消息请求", self.create_complex_message_payload)
        ]
        
        all_response_times = []
        test_details = {}
        
        for case_name, payload_func in test_cases:
            response_times = []
            
            # 每种情况测试10次
            for i in range(10):
                payload = payload_func()
                start_time = time.time()
                
                try:
                    async with aiohttp.ClientSession() as session:
                        headers = self.create_signed_headers(payload)
                        async with session.post(
                            self.webhook_url,
                            json=payload,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            await response.text()
                            response_time = (time.time() - start_time) * 1000
                            response_times.append(response_time)
                            all_response_times.append(response_time)
                            
                except Exception as e:
                    logger.warning(f"请求失败: {e}")
                    continue
            
            if response_times:
                test_details[case_name] = {
                    'avg_response_time': statistics.mean(response_times),
                    'min_response_time': min(response_times),
                    'max_response_time': max(response_times),
                    'p95_response_time': statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times)
                }
        
        if all_response_times:
            metrics = [
                PerformanceMetric(
                    metric_name="平均响应时间",
                    value=statistics.mean(all_response_times),
                    unit="ms",
                    description="所有请求的平均响应时间",
                    threshold=1000.0,
                    passed=statistics.mean(all_response_times) < 1000.0
                ),
                PerformanceMetric(
                    metric_name="P95响应时间",
                    value=statistics.quantiles(all_response_times, n=20)[18] if len(all_response_times) >= 20 else max(all_response_times),
                    unit="ms",
                    description="95%请求的响应时间",
                    threshold=2000.0,
                    passed=(statistics.quantiles(all_response_times, n=20)[18] if len(all_response_times) >= 20 else max(all_response_times)) < 2000.0
                ),
                PerformanceMetric(
                    metric_name="最大响应时间",
                    value=max(all_response_times),
                    unit="ms",
                    description="最慢请求的响应时间",
                    threshold=5000.0,
                    passed=max(all_response_times) < 5000.0
                )
            ]
            
            self.results.append(BenchmarkResult(
                test_name="响应时间基准测试",
                duration_seconds=0,
                total_requests=len(all_response_times),
                successful_requests=len(all_response_times),
                failed_requests=0,
                metrics=metrics,
                details=test_details
            ))
    
    async def benchmark_concurrent_processing(self):
        """并发处理基准测试"""
        logger.info("开始并发处理基准测试...")
        
        # 测试不同并发级别
        concurrency_levels = [5, 10, 20, 50]
        
        for concurrency in concurrency_levels:
            logger.info(f"测试并发级别: {concurrency}")
            
            start_time = time.time()
            successful_requests = 0
            failed_requests = 0
            response_times = []
            
            async with aiohttp.ClientSession() as session:
                tasks = []
                
                for i in range(concurrency):
                    payload = self.create_simple_message_payload()
                    task = self.send_request_async(session, payload)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        failed_requests += 1
                    else:
                        successful_requests += 1
                        response_times.append(result)
            
            duration = time.time() - start_time
            
            if response_times:
                metrics = [
                    PerformanceMetric(
                        metric_name=f"并发{concurrency}-成功率",
                        value=(successful_requests / (successful_requests + failed_requests)) * 100,
                        unit="%",
                        description=f"并发{concurrency}的成功率",
                        threshold=95.0,
                        passed=(successful_requests / (successful_requests + failed_requests)) * 100 >= 95.0
                    ),
                    PerformanceMetric(
                        metric_name=f"并发{concurrency}-平均响应时间",
                        value=statistics.mean(response_times),
                        unit="ms",
                        description=f"并发{concurrency}的平均响应时间",
                        threshold=2000.0,
                        passed=statistics.mean(response_times) < 2000.0
                    ),
                    PerformanceMetric(
                        metric_name=f"并发{concurrency}-吞吐量",
                        value=successful_requests / duration,
                        unit="req/s",
                        description=f"并发{concurrency}的吞吐量",
                        threshold=10.0,
                        passed=(successful_requests / duration) >= 10.0
                    )
                ]
                
                self.results.append(BenchmarkResult(
                    test_name=f"并发处理基准测试-{concurrency}",
                    duration_seconds=duration,
                    total_requests=concurrency,
                    successful_requests=successful_requests,
                    failed_requests=failed_requests,
                    metrics=metrics,
                    details={
                        'concurrency_level': concurrency,
                        'avg_response_time': statistics.mean(response_times),
                        'throughput': successful_requests / duration
                    }
                ))
    
    async def benchmark_throughput(self):
        """吞吐量基准测试"""
        logger.info("开始吞吐量基准测试...")
        
        # 持续发送请求60秒
        test_duration = 60
        start_time = time.time()
        end_time = start_time + test_duration
        
        successful_requests = 0
        failed_requests = 0
        response_times = []
        
        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                payload = self.create_simple_message_payload()
                
                try:
                    request_start = time.time()
                    headers = self.create_signed_headers(payload)
                    async with session.post(
                        self.webhook_url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        await response.text()
                        response_time = (time.time() - request_start) * 1000
                        response_times.append(response_time)
                        successful_requests += 1
                        
                except Exception as e:
                    failed_requests += 1
                    continue
                
                # 短暂延迟避免过度压力
                await asyncio.sleep(0.1)
        
        actual_duration = time.time() - start_time
        
        if successful_requests > 0:
            metrics = [
                PerformanceMetric(
                    metric_name="平均吞吐量",
                    value=successful_requests / actual_duration,
                    unit="req/s",
                    description="每秒处理的请求数",
                    threshold=5.0,
                    passed=(successful_requests / actual_duration) >= 5.0
                ),
                PerformanceMetric(
                    metric_name="成功率",
                    value=(successful_requests / (successful_requests + failed_requests)) * 100,
                    unit="%",
                    description="请求成功率",
                    threshold=95.0,
                    passed=(successful_requests / (successful_requests + failed_requests)) * 100 >= 95.0
                ),
                PerformanceMetric(
                    metric_name="平均响应时间",
                    value=statistics.mean(response_times),
                    unit="ms",
                    description="平均响应时间",
                    threshold=1000.0,
                    passed=statistics.mean(response_times) < 1000.0
                )
            ]
            
            self.results.append(BenchmarkResult(
                test_name="吞吐量基准测试",
                duration_seconds=actual_duration,
                total_requests=successful_requests + failed_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                metrics=metrics,
                details={
                    'test_duration': test_duration,
                    'actual_duration': actual_duration,
                    'throughput': successful_requests / actual_duration
                }
            ))
    
    async def benchmark_load_test(self):
        """负载测试"""
        logger.info("开始负载测试...")
        
        # 模拟正常负载：每秒10个请求，持续5分钟
        test_duration = 300  # 5分钟
        target_rps = 10  # 每秒10个请求
        
        start_time = time.time()
        successful_requests = 0
        failed_requests = 0
        response_times = []
        
        async with aiohttp.ClientSession() as session:
            for second in range(test_duration):
                second_start = time.time()
                
                # 在这一秒内发送target_rps个请求
                tasks = []
                for i in range(target_rps):
                    payload = self.create_simple_message_payload()
                    task = self.send_request_async(session, payload)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        failed_requests += 1
                    else:
                        successful_requests += 1
                        response_times.append(result)
                
                # 等待到下一秒
                elapsed = time.time() - second_start
                if elapsed < 1.0:
                    await asyncio.sleep(1.0 - elapsed)
                
                if (second + 1) % 60 == 0:  # 每分钟报告一次进度
                    logger.info(f"负载测试进度: {second + 1}/{test_duration}秒")
        
        actual_duration = time.time() - start_time
        
        if successful_requests > 0:
            metrics = [
                PerformanceMetric(
                    metric_name="负载测试-平均吞吐量",
                    value=successful_requests / actual_duration,
                    unit="req/s",
                    description="负载测试期间的平均吞吐量",
                    threshold=8.0,
                    passed=(successful_requests / actual_duration) >= 8.0
                ),
                PerformanceMetric(
                    metric_name="负载测试-成功率",
                    value=(successful_requests / (successful_requests + failed_requests)) * 100,
                    unit="%",
                    description="负载测试期间的成功率",
                    threshold=99.0,
                    passed=(successful_requests / (successful_requests + failed_requests)) * 100 >= 99.0
                ),
                PerformanceMetric(
                    metric_name="负载测试-P95响应时间",
                    value=statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times),
                    unit="ms",
                    description="负载测试期间95%请求的响应时间",
                    threshold=2000.0,
                    passed=(statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times)) < 2000.0
                )
            ]
            
            self.results.append(BenchmarkResult(
                test_name="负载测试",
                duration_seconds=actual_duration,
                total_requests=successful_requests + failed_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                metrics=metrics,
                details={
                    'target_rps': target_rps,
                    'test_duration': test_duration,
                    'actual_throughput': successful_requests / actual_duration
                }
            ))
    
    async def benchmark_stress_test(self):
        """压力测试"""
        logger.info("开始压力测试...")
        
        # 逐步增加负载直到系统开始出现错误
        max_concurrency = 100
        step_size = 10
        step_duration = 30  # 每个级别持续30秒
        
        for concurrency in range(step_size, max_concurrency + 1, step_size):
            logger.info(f"压力测试 - 并发级别: {concurrency}")
            
            start_time = time.time()
            successful_requests = 0
            failed_requests = 0
            response_times = []
            
            async with aiohttp.ClientSession() as session:
                # 在step_duration时间内保持concurrency级别的并发
                end_time = start_time + step_duration
                
                while time.time() < end_time:
                    tasks = []
                    for i in range(concurrency):
                        payload = self.create_simple_message_payload()
                        task = self.send_request_async(session, payload)
                        tasks.append(task)
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for result in results:
                        if isinstance(result, Exception):
                            failed_requests += 1
                        else:
                            successful_requests += 1
                            response_times.append(result)
                    
                    # 短暂延迟
                    await asyncio.sleep(1)
            
            actual_duration = time.time() - start_time
            error_rate = (failed_requests / (successful_requests + failed_requests)) * 100 if (successful_requests + failed_requests) > 0 else 100
            
            metrics = [
                PerformanceMetric(
                    metric_name=f"压力测试-{concurrency}-错误率",
                    value=error_rate,
                    unit="%",
                    description=f"并发{concurrency}时的错误率",
                    threshold=10.0,
                    passed=error_rate < 10.0
                )
            ]
            
            if response_times:
                metrics.append(PerformanceMetric(
                    metric_name=f"压力测试-{concurrency}-平均响应时间",
                    value=statistics.mean(response_times),
                    unit="ms",
                    description=f"并发{concurrency}时的平均响应时间",
                    threshold=5000.0,
                    passed=statistics.mean(response_times) < 5000.0
                ))
            
            self.results.append(BenchmarkResult(
                test_name=f"压力测试-{concurrency}",
                duration_seconds=actual_duration,
                total_requests=successful_requests + failed_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                metrics=metrics,
                details={
                    'concurrency_level': concurrency,
                    'error_rate': error_rate,
                    'avg_response_time': statistics.mean(response_times) if response_times else 0
                }
            ))
            
            # 如果错误率超过50%，停止压力测试
            if error_rate > 50:
                logger.warning(f"错误率过高({error_rate:.2f}%)，停止压力测试")
                break
    
    async def send_request_async(self, session: aiohttp.ClientSession, payload: dict) -> float:
        """异步发送请求并返回响应时间"""
        start_time = time.time()
        
        headers = self.create_signed_headers(payload)
        async with session.post(
            self.webhook_url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            await response.text()
            return (time.time() - start_time) * 1000
    
    def create_url_verification_payload(self) -> dict:
        """创建URL验证载荷"""
        return {
            "header": {
                "event_type": "url_verification"
            },
            "challenge": f"test_challenge_{int(time.time())}",
            "token": self.verification_token,
            "type": "url_verification"
        }
    
    def create_simple_message_payload(self) -> dict:
        """创建简单消息载荷"""
        return {
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli_test_app"
            },
            "event": {
                "sender": {
                    "sender_type": "user",
                    "sender_id": {"user_id": f"test_user_{int(time.time())}"}
                },
                "message": {
                    "message_id": f"test_message_{int(time.time())}",
                    "chat_id": f"test_chat_{int(time.time())}",
                    "message_type": "text",
                    "content": json.dumps({"text": "测试消息"})
                }
            }
        }
    
    def create_complex_message_payload(self) -> dict:
        """创建复杂消息载荷"""
        return {
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli_test_app"
            },
            "event": {
                "sender": {
                    "sender_type": "user",
                    "sender_id": {"user_id": f"test_user_{int(time.time())}"}
                },
                "message": {
                    "message_id": f"test_message_{int(time.time())}",
                    "chat_id": f"test_chat_{int(time.time())}",
                    "message_type": "text",
                    "content": json.dumps({
                        "text": "这是一个复杂的测试消息，包含更多内容和数据，用于测试系统处理复杂消息的性能。" * 10
                    }),
                    "mentions": [
                        {
                            "key": "@_user_1",
                            "id": {"user_id": "user_123"},
                            "name": "Test User"
                        }
                    ]
                }
            }
        }
    
    def create_signed_headers(self, payload: dict) -> dict:
        """创建带签名的请求头"""
        timestamp = str(int(time.time()))
        nonce = f"test_nonce_{int(time.time() * 1000)}"
        body = json.dumps(payload)
        
        string_to_sign = f"{timestamp}{nonce}{self.encrypt_key}{body}"
        signature = hashlib.sha256(string_to_sign.encode()).hexdigest()
        
        return {
            'Content-Type': 'application/json',
            'X-Lark-Request-Timestamp': timestamp,
            'X-Lark-Request-Nonce': nonce,
            'X-Lark-Signature': signature
        }
    
    def generate_benchmark_report(self, total_duration: float) -> Dict[str, Any]:
        """生成基准测试报告"""
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results 
                          if all(metric.passed for metric in result.metrics if metric.passed is not None))
        
        total_requests = sum(result.total_requests for result in self.results)
        total_successful = sum(result.successful_requests for result in self.results)
        total_failed = sum(result.failed_requests for result in self.results)
        
        overall_success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0
        
        report = {
            'benchmark_summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': total_tests - passed_tests,
                'total_duration_seconds': total_duration,
                'total_requests': total_requests,
                'successful_requests': total_successful,
                'failed_requests': total_failed,
                'overall_success_rate': f"{overall_success_rate:.2f}%",
                'timestamp': datetime.utcnow().isoformat()
            },
            'test_results': [
                {
                    'test_name': result.test_name,
                    'duration_seconds': result.duration_seconds,
                    'total_requests': result.total_requests,
                    'successful_requests': result.successful_requests,
                    'failed_requests': result.failed_requests,
                    'metrics': [
                        {
                            'metric_name': metric.metric_name,
                            'value': metric.value,
                            'unit': metric.unit,
                            'description': metric.description,
                            'threshold': metric.threshold,
                            'passed': metric.passed
                        }
                        for metric in result.metrics
                    ],
                    'details': result.details
                }
                for result in self.results
            ],
            'performance_summary': self._generate_performance_summary()
        }
        
        return report
    
    def _generate_performance_summary(self) -> Dict[str, Any]:
        """生成性能摘要"""
        all_metrics = []
        for result in self.results:
            all_metrics.extend(result.metrics)
        
        # 按指标类型分组
        response_time_metrics = [m for m in all_metrics if '响应时间' in m.metric_name]
        throughput_metrics = [m for m in all_metrics if '吞吐量' in m.metric_name]
        success_rate_metrics = [m for m in all_metrics if '成功率' in m.metric_name]
        
        summary = {}
        
        if response_time_metrics:
            summary['response_time'] = {
                'avg_response_time': statistics.mean([m.value for m in response_time_metrics]),
                'min_response_time': min([m.value for m in response_time_metrics]),
                'max_response_time': max([m.value for m in response_time_metrics])
            }
        
        if throughput_metrics:
            summary['throughput'] = {
                'avg_throughput': statistics.mean([m.value for m in throughput_metrics]),
                'max_throughput': max([m.value for m in throughput_metrics])
            }
        
        if success_rate_metrics:
            summary['reliability'] = {
                'avg_success_rate': statistics.mean([m.value for m in success_rate_metrics]),
                'min_success_rate': min([m.value for m in success_rate_metrics])
            }
        
        return summary

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='飞书机器人系统性能基准测试')
    parser.add_argument('--webhook-url', required=True, help='Webhook URL')
    parser.add_argument('--encrypt-key', required=True, help='飞书加密密钥')
    parser.add_argument('--verification-token', required=True, help='飞书验证Token')
    parser.add_argument('--output', default='performance_benchmark.json', help='基准测试报告输出文件')
    
    args = parser.parse_args()
    
    async def run_benchmark():
        benchmark = PerformanceBenchmark(
            webhook_url=args.webhook_url,
            encrypt_key=args.encrypt_key,
            verification_token=args.verification_token
        )
        
        return await benchmark.run_all_benchmarks()
    
    # 运行基准测试
    report = asyncio.run(run_benchmark())
    
    # 输出报告
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 打印摘要
    summary = report['benchmark_summary']
    print(f"\n{'='*60}")
    print(f"性能基准测试报告")
    print(f"{'='*60}")
    print(f"总测试数: {summary['total_tests']}")
    print(f"通过测试: {summary['passed_tests']}")
    print(f"失败测试: {summary['failed_tests']}")
    print(f"总请求数: {summary['total_requests']}")
    print(f"成功请求: {summary['successful_requests']}")
    print(f"失败请求: {summary['failed_requests']}")
    print(f"整体成功率: {summary['overall_success_rate']}")
    print(f"总耗时: {summary['total_duration_seconds']:.2f}秒")
    print(f"报告文件: {args.output}")
    
    # 打印性能摘要
    if 'performance_summary' in report:
        perf_summary = report['performance_summary']
        print(f"\n性能摘要:")
        
        if 'response_time' in perf_summary:
            rt = perf_summary['response_time']
            print(f"  响应时间: 平均{rt['avg_response_time']:.2f}ms, 最小{rt['min_response_time']:.2f}ms, 最大{rt['max_response_time']:.2f}ms")
        
        if 'throughput' in perf_summary:
            tp = perf_summary['throughput']
            print(f"  吞吐量: 平均{tp['avg_throughput']:.2f}req/s, 最大{tp['max_throughput']:.2f}req/s")
        
        if 'reliability' in perf_summary:
            rel = perf_summary['reliability']
            print(f"  可靠性: 平均成功率{rel['avg_success_rate']:.2f}%, 最低成功率{rel['min_success_rate']:.2f}%")
    
    if summary['failed_tests'] > 0:
        print(f"\n⚠️  有 {summary['failed_tests']} 个测试未通过基准要求")
        exit(1)
    else:
        print(f"\n🎉 所有性能基准测试通过!")
        exit(0)

if __name__ == '__main__':
    main()