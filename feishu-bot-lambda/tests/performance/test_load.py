"""
负载和性能测试
测试系统在高负载下的表现
"""

import time
import json
import pytest
import threading
import concurrent.futures
from unittest.mock import Mock, patch
import psutil
import os

from src.lambdas.receive_handler import lambda_handler as receive_handler
from src.lambdas.process_handler import lambda_handler as process_handler
from src.shared.models import FeishuMessage


@pytest.mark.performance
class TestLoadPerformance:
    """负载性能测试"""
    
    def test_high_volume_webhook_processing(self, feishu_config, lambda_context):
        """测试高并发webhook处理"""
        # 准备大量测试事件
        test_events = []
        for i in range(100):
            event = {
                'httpMethod': 'POST',
                'headers': {
                    'Content-Type': 'application/json',
                    'x-lark-request-timestamp': str(int(time.time())),
                    'x-lark-request-nonce': f'nonce_{i}',
                    'x-lark-signature': 'test_signature'
                },
                'body': json.dumps({
                    'header': {
                        'event_type': 'url_verification'
                    },
                    'challenge': f'challenge_{i}'
                })
            }
            test_events.append(event)
        
        # 记录开始时间和内存
        start_time = time.time()
        process = psutil.Process(os.getpid())
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 并发处理事件
        with patch('src.lambdas.receive_handler._verify_request_signature', return_value=True):
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(receive_handler, event, lambda_context)
                    for event in test_events
                ]
                
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 记录结束时间和内存
        end_time = time.time()
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 性能断言
        processing_time = end_time - start_time
        memory_increase = end_memory - start_memory
        
        # 验证所有请求都成功处理
        assert len(results) == 100
        success_count = sum(1 for r in results if r['statusCode'] == 200)
        assert success_count >= 95  # 至少95%成功率
        
        # 性能要求
        assert processing_time < 30.0  # 30秒内完成100个请求
        assert memory_increase < 200  # 内存增长不超过200MB
        
        # 计算吞吐量
        throughput = len(test_events) / processing_time
        print(f"Throughput: {throughput:.2f} requests/second")
        print(f"Average response time: {processing_time/len(test_events)*1000:.2f}ms")
        print(f"Memory increase: {memory_increase:.2f}MB")
        
        assert throughput > 3.0  # 至少3 RPS
    
    def test_batch_message_processing_performance(self, feishu_config, lambda_context, mock_feishu_client):
        """测试批量消息处理性能"""
        # 创建大量测试消息
        batch_size = 50
        test_messages = []
        
        for i in range(batch_size):
            message = FeishuMessage(
                message_id=f'msg_{i}',
                user_id=f'user_{i}',
                chat_id=f'chat_{i % 10}',  # 10个不同的聊天
                message_type='text',
                content=f'Performance test message {i}',
                timestamp=int(time.time()),
                app_id='test_app',
                mentions=[]
            )
            test_messages.append(message)
        
        # 创建SQS事件
        sqs_event = {
            'Records': [
                {
                    'messageId': f'sqs_msg_{i}',
                    'body': msg.to_json()
                }
                for i, msg in enumerate(test_messages)
            ]
        }
        
        # 记录性能指标
        start_time = time.time()
        process = psutil.Process(os.getpid())
        start_memory = process.memory_info().rss / 1024 / 1024
        
        # 处理消息
        response = process_handler(sqs_event, lambda_context)
        
        end_time = time.time()
        end_memory = process.memory_info().rss / 1024 / 1024
        
        # 验证处理结果
        assert response['statusCode'] == 200
        assert response['body']['successful'] == batch_size
        assert response['body']['failed'] == 0
        
        # 性能要求
        processing_time = end_time - start_time
        memory_increase = end_memory - start_memory
        
        assert processing_time < 15.0  # 15秒内处理50条消息
        assert memory_increase < 100  # 内存增长不超过100MB
        
        # 验证飞书API调用次数
        assert mock_feishu_client.send_text_message.call_count == batch_size
        
        # 计算处理速度
        messages_per_second = batch_size / processing_time
        print(f"Message processing rate: {messages_per_second:.2f} messages/second")
        print(f"Average processing time per message: {processing_time/batch_size*1000:.2f}ms")
        
        assert messages_per_second > 3.0  # 至少3条消息/秒
    
    def test_memory_leak_detection(self, feishu_config, lambda_context):
        """测试内存泄漏检测"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        memory_readings = []
        
        # 多次执行相同操作
        for iteration in range(15):  # 增加迭代次数
            # 创建测试事件
            events = []
            for i in range(30):  # 增加每次迭代的事件数量
                event = {
                    'httpMethod': 'POST',
                    'headers': {
                        'x-lark-request-timestamp': str(int(time.time())),
                        'x-lark-request-nonce': f'nonce_{iteration}_{i}',
                        'x-lark-signature': 'test_signature'
                    },
                    'body': json.dumps({
                        'header': {'event_type': 'url_verification'},
                        'challenge': f'challenge_{iteration}_{i}'
                    })
                }
                events.append(event)
            
            # 处理事件
            with patch('src.lambdas.receive_handler._verify_request_signature', return_value=True):
                for event in events:
                    receive_handler(event, lambda_context)
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            # 记录内存使用
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = current_memory - initial_memory
            memory_readings.append(current_memory)
            
            print(f"Iteration {iteration + 1}: Memory usage = {current_memory:.2f}MB, "
                  f"Increase = {memory_increase:.2f}MB")
            
            # 内存增长应该保持在合理范围内
            assert memory_increase < 100  # 不超过100MB增长
        
        # 检查内存增长趋势
        if len(memory_readings) >= 10:
            # 计算后半段的平均内存使用
            recent_avg = sum(memory_readings[-5:]) / 5
            early_avg = sum(memory_readings[:5]) / 5
            
            # 内存增长应该趋于稳定
            growth_rate = (recent_avg - early_avg) / early_avg
            assert growth_rate < 0.5  # 增长率不超过50%
            
            print(f"Memory growth rate: {growth_rate:.2%}")
    
    def test_memory_usage_under_stress(self, feishu_config, lambda_context):
        """测试压力下的内存使用"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # 创建大量并发事件
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def stress_worker(worker_id):
            """压力测试工作线程"""
            for i in range(50):
                event = {
                    'httpMethod': 'POST',
                    'headers': {
                        'x-lark-request-timestamp': str(int(time.time())),
                        'x-lark-request-nonce': f'stress_{worker_id}_{i}',
                        'x-lark-signature': 'test_signature'
                    },
                    'body': json.dumps({
                        'header': {'event_type': 'url_verification'},
                        'challenge': f'stress_challenge_{worker_id}_{i}'
                    })
                }
                
                with patch('src.lambdas.receive_handler._verify_request_signature', return_value=True):
                    try:
                        response = receive_handler(event, lambda_context)
                        results_queue.put(('success', response['statusCode']))
                    except Exception as e:
                        results_queue.put(('error', str(e)))
        
        # 启动多个压力测试线程
        threads = []
        for worker_id in range(10):
            thread = threading.Thread(target=stress_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 检查最终内存使用
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        print(f"Stress test memory increase: {memory_increase:.2f}MB")
        
        # 收集结果
        success_count = 0
        error_count = 0
        
        while not results_queue.empty():
            result_type, result_data = results_queue.get()
            if result_type == 'success':
                success_count += 1
            else:
                error_count += 1
        
        # 验证结果
        total_requests = 10 * 50  # 10个线程，每个50个请求
        assert success_count + error_count == total_requests
        assert success_count >= total_requests * 0.95  # 至少95%成功率
        assert memory_increase < 200  # 内存增长不超过200MB
    
    def test_concurrent_different_operations(self, feishu_config, lambda_context, mock_feishu_client):
        """测试不同操作的并发处理"""
        import queue
        
        results_queue = queue.Queue()
        
        def webhook_worker():
            """Webhook处理工作线程"""
            event = {
                'httpMethod': 'POST',
                'headers': {
                    'x-lark-request-timestamp': str(int(time.time())),
                    'x-lark-request-nonce': 'webhook_nonce',
                    'x-lark-signature': 'test_signature'
                },
                'body': json.dumps({
                    'header': {'event_type': 'url_verification'},
                    'challenge': 'webhook_challenge'
                })
            }
            
            with patch('src.lambdas.receive_handler._verify_request_signature', return_value=True):
                result = receive_handler(event, lambda_context)
                results_queue.put(('webhook', result))
        
        def message_worker():
            """消息处理工作线程"""
            message = FeishuMessage(
                message_id='concurrent_msg',
                user_id='concurrent_user',
                chat_id='concurrent_chat',
                message_type='text',
                content='Concurrent test message',
                timestamp=int(time.time()),
                app_id='test_app',
                mentions=[]
            )
            
            sqs_event = {
                'Records': [
                    {
                        'messageId': 'concurrent_sqs_msg',
                        'body': message.to_json()
                    }
                ]
            }
            
            result = process_handler(sqs_event, lambda_context)
            results_queue.put(('message', result))
        
        # 启动并发工作线程
        threads = []
        
        # 创建多个webhook处理线程
        for _ in range(5):
            thread = threading.Thread(target=webhook_worker)
            threads.append(thread)
        
        # 创建多个消息处理线程
        for _ in range(5):
            thread = threading.Thread(target=message_worker)
            threads.append(thread)
        
        # 启动所有线程
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # 收集结果
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # 验证结果
        assert len(results) == 10  # 5个webhook + 5个消息处理
        
        webhook_results = [r for r in results if r[0] == 'webhook']
        message_results = [r for r in results if r[0] == 'message']
        
        assert len(webhook_results) == 5
        assert len(message_results) == 5
        
        # 验证所有操作都成功
        for _, result in results:
            assert result['statusCode'] == 200
        
        # 性能要求
        total_time = end_time - start_time
        assert total_time < 10.0  # 10秒内完成所有并发操作
        
        print(f"Concurrent operations completed in {total_time:.2f} seconds")


@pytest.mark.performance
class TestScalabilityLimits:
    """可扩展性限制测试"""
    
    def test_maximum_message_size_handling(self, feishu_config, lambda_context):
        """测试最大消息大小处理"""
        # 创建大消息（接近Lambda限制）
        large_content = 'x' * (5 * 1024 * 1024)  # 5MB内容
        
        large_event = {
            'httpMethod': 'POST',
            'headers': {
                'x-lark-request-timestamp': str(int(time.time())),
                'x-lark-request-nonce': 'large_nonce',
                'x-lark-signature': 'test_signature'
            },
            'body': json.dumps({
                'header': {
                    'event_type': 'im.message.receive_v1',
                    'app_id': 'test_app'
                },
                'event': {
                    'message': {
                        'content': f'{{"text": "{large_content}"}}'
                    }
                }
            })
        }
        
        start_time = time.time()
        
        with patch('src.lambdas.receive_handler._verify_request_signature', return_value=True):
            response = receive_handler(large_event, lambda_context)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 应该能够处理大消息（可能返回错误，但不应该崩溃）
        assert response['statusCode'] in [200, 400, 413]  # 200成功, 400错误, 413过大
        assert processing_time < 30.0  # 30秒内完成处理
    
    def test_deep_json_nesting_handling(self, feishu_config, lambda_context):
        """测试深度嵌套JSON处理"""
        # 创建深度嵌套的JSON
        nested_data = {}
        current = nested_data
        
        for i in range(100):  # 100层嵌套
            current['level'] = i
            current['next'] = {}
            current = current['next']
        
        current['final'] = 'deep_value'
        
        deep_event = {
            'httpMethod': 'POST',
            'headers': {
                'x-lark-request-timestamp': str(int(time.time())),
                'x-lark-request-nonce': 'deep_nonce',
                'x-lark-signature': 'test_signature'
            },
            'body': json.dumps({
                'header': {'event_type': 'url_verification'},
                'challenge': 'deep_challenge',
                'nested_data': nested_data
            })
        }
        
        with patch('src.lambdas.receive_handler._verify_request_signature', return_value=True):
            response = receive_handler(deep_event, lambda_context)
        
        # 应该能够处理深度嵌套（可能有限制，但不应该崩溃）
        assert response['statusCode'] in [200, 400]
    
    def test_unicode_and_emoji_handling_performance(self, feishu_config, lambda_context, mock_feishu_client):
        """测试Unicode和表情符号处理性能"""
        # 创建包含大量Unicode字符的消息
        unicode_content = '🎉🚀💻🔥⭐️🎯🌟💡🎊🎈' * 1000  # 大量表情符号
        chinese_content = '这是一个包含中文字符的测试消息，用于验证Unicode处理性能。' * 100
        mixed_content = f'{unicode_content} {chinese_content}'
        
        message = FeishuMessage(
            message_id='unicode_msg',
            user_id='unicode_user',
            chat_id='unicode_chat',
            message_type='text',
            content=mixed_content,
            timestamp=int(time.time()),
            app_id='test_app',
            mentions=[]
        )
        
        sqs_event = {
            'Records': [
                {
                    'messageId': 'unicode_sqs_msg',
                    'body': message.to_json()
                }
            ]
        }
        
        start_time = time.time()
        response = process_handler(sqs_event, lambda_context)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # 验证处理结果
        assert response['statusCode'] == 200
        assert response['body']['successful'] == 1
        
        # Unicode处理不应该显著影响性能
        assert processing_time < 5.0  # 5秒内完成
        
        # 验证飞书API被正确调用
        mock_feishu_client.send_text_message.assert_called_once()
        call_args = mock_feishu_client.send_text_message.call_args
        assert '🎉' in call_args[0][1]  # 确保表情符号被保留
        assert '中文' in call_args[0][1]  # 确保中文字符被保留


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'performance'])
@p
ytest.mark.performance
class TestAdvancedPerformance:
    """高级性能测试"""
    
    def test_cpu_intensive_operations(self, feishu_config, lambda_context, mock_feishu_client):
        """测试CPU密集型操作的性能"""
        import time
        import threading
        
        # 创建CPU密集型的消息处理任务
        cpu_intensive_messages = []
        for i in range(20):
            # 创建包含复杂内容的消息
            complex_content = json.dumps({
                "text": f"Complex message {i} with nested data",
                "metadata": {
                    "numbers": list(range(100)),
                    "nested": {
                        "level1": {
                            "level2": {
                                "data": [{"id": j, "value": f"item_{j}"} for j in range(50)]
                            }
                        }
                    }
                }
            })
            
            message = FeishuMessage(
                message_id=f'cpu_msg_{i}',
                user_id=f'cpu_user_{i}',
                chat_id=f'cpu_chat_{i}',
                message_type='text',
                content=complex_content,
                timestamp=int(time.time()),
                app_id='test_app',
                mentions=[]
            )
            cpu_intensive_messages.append(message)
        
        # 创建SQS事件
        sqs_event = {
            'Records': [
                {
                    'messageId': f'cpu_sqs_msg_{i}',
                    'body': msg.to_json()
                }
                for i, msg in enumerate(cpu_intensive_messages)
            ]
        }
        
        # 测量CPU使用率
        import psutil
        process = psutil.Process(os.getpid())
        
        start_time = time.time()
        start_cpu_percent = process.cpu_percent()
        
        # 处理消息
        response = process_handler(sqs_event, lambda_context)
        
        end_time = time.time()
        end_cpu_percent = process.cpu_percent()
        
        processing_time = end_time - start_time
        
        # 验证处理结果
        assert response['statusCode'] == 200
        assert response['body']['successful'] == 20
        
        # 性能要求
        assert processing_time < 30.0  # 30秒内完成
        
        # CPU使用率应该在合理范围内
        print(f"CPU usage: {end_cpu_percent:.2f}%")
        print(f"Processing time: {processing_time:.2f}s")
        print(f"Messages per second: {20/processing_time:.2f}")
        
        # 验证飞书API调用
        assert mock_feishu_client.send_text_message.call_count == 20
    
    def test_io_intensive_operations(self, feishu_config, lambda_context):
        """测试I/O密集型操作的性能"""
        import concurrent.futures
        import time
        
        # 模拟I/O密集型操作（网络请求）
        def simulate_io_operation(message_id):
            """模拟I/O操作"""
            # 模拟网络延迟
            time.sleep(0.1)  # 100ms延迟
            
            message_data = {
                'message_id': message_id,
                'user_id': f'io_user_{message_id}',
                'chat_id': f'io_chat_{message_id}',
                'message_type': 'text',
                'content': f'IO intensive message {message_id}',
                'timestamp': int(time.time()),
                'app_id': 'test_app',
                'mentions': []
            }
            
            sqs_event = {
                'Records': [
                    {
                        'messageId': f'io_sqs_msg_{message_id}',
                        'body': json.dumps(message_data)
                    }
                ]
            }
            
            # Mock飞书API调用
            with patch('src.shared.feishu_client.FeishuClient.send_text_message') as mock_send:
                mock_send.return_value = {'code': 0, 'msg': 'success'}
                
                start_time = time.time()
                response = process_handler(sqs_event, lambda_context)
                end_time = time.time()
                
                return {
                    'message_id': message_id,
                    'response': response,
                    'processing_time': end_time - start_time
                }
        
        # 并发执行I/O操作
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(simulate_io_operation, f'io_msg_{i}')
                for i in range(50)
            ]
            
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 验证结果
        assert len(results) == 50
        
        successful_results = [r for r in results if r['response']['statusCode'] == 200]
        assert len(successful_results) == 50
        
        # 性能分析
        avg_processing_time = sum(r['processing_time'] for r in results) / len(results)
        throughput = len(results) / total_time
        
        print(f"Total time: {total_time:.2f}s")
        print(f"Average processing time per message: {avg_processing_time:.2f}s")
        print(f"Throughput: {throughput:.2f} messages/second")
        
        # 性能要求
        assert total_time < 15.0  # 并发处理应该显著快于串行
        assert throughput > 3.0   # 至少3 messages/second
    
    def test_memory_efficiency_with_large_batches(self, feishu_config, lambda_context, mock_feishu_client):
        """测试大批量处理的内存效率"""
        import psutil
        import gc
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # 创建大批量消息
        batch_sizes = [10, 50, 100, 200]
        memory_usage_per_batch = []
        
        for batch_size in batch_sizes:
            # 强制垃圾回收
            gc.collect()
            
            # 记录批处理前的内存
            before_memory = process.memory_info().rss / 1024 / 1024
            
            # 创建批量消息
            messages = []
            for i in range(batch_size):
                message = FeishuMessage(
                    message_id=f'batch_msg_{batch_size}_{i}',
                    user_id=f'batch_user_{i}',
                    chat_id=f'batch_chat_{i}',
                    message_type='text',
                    content=f'Batch message {i} in batch of {batch_size}',
                    timestamp=int(time.time()),
                    app_id='test_app',
                    mentions=[]
                )
                messages.append(message)
            
            # 创建SQS事件
            sqs_event = {
                'Records': [
                    {
                        'messageId': f'batch_sqs_{batch_size}_{i}',
                        'body': msg.to_json()
                    }
                    for i, msg in enumerate(messages)
                ]
            }
            
            # 处理批量消息
            start_time = time.time()
            response = process_handler(sqs_event, lambda_context)
            end_time = time.time()
            
            # 记录批处理后的内存
            after_memory = process.memory_info().rss / 1024 / 1024
            memory_used = after_memory - before_memory
            
            # 验证处理结果
            assert response['statusCode'] == 200
            assert response['body']['successful'] == batch_size
            
            # 记录性能指标
            processing_time = end_time - start_time
            memory_per_message = memory_used / batch_size if batch_size > 0 else 0
            
            memory_usage_per_batch.append({
                'batch_size': batch_size,
                'memory_used': memory_used,
                'memory_per_message': memory_per_message,
                'processing_time': processing_time,
                'messages_per_second': batch_size / processing_time
            })
            
            print(f"Batch size {batch_size}: "
                  f"Memory used: {memory_used:.2f}MB, "
                  f"Per message: {memory_per_message:.3f}MB, "
                  f"Time: {processing_time:.2f}s, "
                  f"Rate: {batch_size/processing_time:.2f} msg/s")
            
            # 内存使用应该随批量大小线性增长
            assert memory_used < batch_size * 0.5  # 每条消息不超过0.5MB
        
        # 分析内存效率趋势
        if len(memory_usage_per_batch) >= 2:
            # 检查内存使用是否随批量大小合理增长
            for i in range(1, len(memory_usage_per_batch)):
                current = memory_usage_per_batch[i]
                previous = memory_usage_per_batch[i-1]
                
                # 内存使用应该大致与批量大小成正比
                size_ratio = current['batch_size'] / previous['batch_size']
                memory_ratio = current['memory_used'] / previous['memory_used'] if previous['memory_used'] > 0 else 1
                
                # 允许一定的偏差
                assert 0.5 < memory_ratio / size_ratio < 2.0
    
    def test_error_handling_performance_impact(self, feishu_config, lambda_context):
        """测试错误处理对性能的影响"""
        import time
        
        # 创建混合成功和失败的消息
        mixed_messages = []
        for i in range(100):
            message = FeishuMessage(
                message_id=f'mixed_msg_{i}',
                user_id=f'mixed_user_{i}',
                chat_id=f'mixed_chat_{i}',
                message_type='text',
                content=f'Mixed message {i}',
                timestamp=int(time.time()),
                app_id='test_app',
                mentions=[]
            )
            mixed_messages.append(message)
        
        # 测试1: 全部成功的情况
        sqs_event_success = {
            'Records': [
                {
                    'messageId': f'success_sqs_msg_{i}',
                    'body': msg.to_json()
                }
                for i, msg in enumerate(mixed_messages[:50])
            ]
        }
        
        with patch('src.shared.feishu_client.FeishuClient.send_text_message') as mock_send:
            mock_send.return_value = {'code': 0, 'msg': 'success'}
            
            start_time = time.time()
            response_success = process_handler(sqs_event_success, lambda_context)
            success_time = time.time() - start_time
        
        # 测试2: 部分失败的情况
        sqs_event_mixed = {
            'Records': [
                {
                    'messageId': f'mixed_sqs_msg_{i}',
                    'body': msg.to_json()
                }
                for i, msg in enumerate(mixed_messages[50:])
            ]
        }
        
        with patch('src.shared.feishu_client.FeishuClient.send_text_message') as mock_send:
            # 模拟50%失败率
            mock_send.side_effect = [
                {'code': 0, 'msg': 'success'} if i % 2 == 0 else Exception("API Error")
                for i in range(50)
            ]
            
            # Mock time.sleep to speed up retry tests
            with patch('time.sleep'):
                start_time = time.time()
                response_mixed = process_handler(sqs_event_mixed, lambda_context)
                mixed_time = time.time() - start_time
        
        # 验证结果
        assert response_success['statusCode'] == 200
        assert response_success['body']['successful'] == 50
        
        assert response_mixed['statusCode'] == 200
        # 部分消息应该成功，部分失败
        assert response_mixed['body']['successful'] > 0
        assert response_mixed['body']['failed'] > 0
        
        # 性能分析
        success_rate = 50 / success_time
        mixed_rate = 50 / mixed_time
        
        print(f"Success-only processing rate: {success_rate:.2f} msg/s")
        print(f"Mixed success/failure processing rate: {mixed_rate:.2f} msg/s")
        print(f"Performance impact of errors: {((success_time - mixed_time) / success_time * 100):.1f}%")
        
        # 错误处理不应该显著影响性能（考虑到重试机制）
        # 允许错误情况下性能下降，但不应该超过5倍
        assert mixed_time < success_time * 5
    
    def test_garbage_collection_impact(self, feishu_config, lambda_context, mock_feishu_client):
        """测试垃圾回收对性能的影响"""
        import gc
        import time
        
        # 禁用自动垃圾回收
        gc.disable()
        
        try:
            # 创建大量对象以触发垃圾回收
            large_messages = []
            for i in range(500):
                # 创建包含大量数据的消息
                large_content = {
                    "text": f"Large message {i}",
                    "data": ["item_" + str(j) for j in range(100)],
                    "metadata": {f"key_{k}": f"value_{k}" for k in range(50)}
                }
                
                message = FeishuMessage(
                    message_id=f'gc_msg_{i}',
                    user_id=f'gc_user_{i}',
                    chat_id=f'gc_chat_{i}',
                    message_type='text',
                    content=json.dumps(large_content),
                    timestamp=int(time.time()),
                    app_id='test_app',
                    mentions=[]
                )
                large_messages.append(message)
            
            # 分批处理消息
            batch_size = 50
            processing_times = []
            
            for batch_start in range(0, len(large_messages), batch_size):
                batch_end = min(batch_start + batch_size, len(large_messages))
                batch_messages = large_messages[batch_start:batch_end]
                
                sqs_event = {
                    'Records': [
                        {
                            'messageId': f'gc_sqs_msg_{i}',
                            'body': msg.to_json()
                        }
                        for i, msg in enumerate(batch_messages)
                    ]
                }
                
                # 测量处理时间
                start_time = time.time()
                response = process_handler(sqs_event, lambda_context)
                end_time = time.time()
                
                processing_time = end_time - start_time
                processing_times.append(processing_time)
                
                # 验证处理结果
                assert response['statusCode'] == 200
                assert response['body']['successful'] == len(batch_messages)
                
                # 每隔几批手动触发垃圾回收
                if (batch_start // batch_size) % 3 == 0:
                    gc_start = time.time()
                    gc.collect()
                    gc_time = time.time() - gc_start
                    print(f"Manual GC took {gc_time:.3f}s")
            
            # 分析处理时间的变化
            avg_time = sum(processing_times) / len(processing_times)
            max_time = max(processing_times)
            min_time = min(processing_times)
            
            print(f"Processing times - Avg: {avg_time:.3f}s, Min: {min_time:.3f}s, Max: {max_time:.3f}s")
            print(f"Time variation: {((max_time - min_time) / avg_time * 100):.1f}%")
            
            # 处理时间的变化应该在合理范围内
            assert max_time < avg_time * 3  # 最大时间不超过平均时间的3倍
            
        finally:
            # 重新启用自动垃圾回收
            gc.enable()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'performance'])