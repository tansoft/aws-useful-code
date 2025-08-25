#!/usr/bin/env python3
"""
系统验收测试运行脚本

此脚本协调运行所有验收测试，包括部署验证、功能测试、性能测试和安全测试。
"""

import os
import sys
import json
import time
import subprocess
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TestSuite:
    """测试套件"""
    name: str
    script: str
    required: bool
    timeout: int
    args: List[str]

@dataclass
class TestResult:
    """测试结果"""
    suite_name: str
    success: bool
    duration_seconds: float
    exit_code: int
    output: str
    error: str
    report_file: Optional[str] = None

class AcceptanceTestRunner:
    """验收测试运行器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results: List[TestResult] = []
        
        # 定义测试套件
        self.test_suites = [
            TestSuite(
                name="部署验证",
                script="scripts/deployment_verification.py",
                required=True,
                timeout=300,  # 5分钟
                args=[
                    "--stack-name", config.get('stack_name', 'feishu-bot-dev'),
                    "--region", config.get('region', 'us-east-1'),
                    "--output", "reports/deployment_verification.json"
                ]
            ),
            TestSuite(
                name="系统功能测试",
                script="scripts/system_acceptance_test.py",
                required=True,
                timeout=1800,  # 30分钟
                args=[
                    "--stack-name", config.get('stack_name', 'feishu-bot-dev'),
                    "--environment", config.get('environment', 'dev'),
                    "--region", config.get('region', 'us-east-1'),
                    "--webhook-url", config.get('webhook_url', ''),
                    "--app-id", config.get('app_id', ''),
                    "--app-secret", config.get('app_secret', ''),
                    "--verification-token", config.get('verification_token', ''),
                    "--encrypt-key", config.get('encrypt_key', ''),
                    "--output", "reports/system_acceptance_test.json"
                ]
            ),
            TestSuite(
                name="性能基准测试",
                script="scripts/performance_benchmark.py",
                required=False,
                timeout=3600,  # 1小时
                args=[
                    "--webhook-url", config.get('webhook_url', ''),
                    "--encrypt-key", config.get('encrypt_key', ''),
                    "--verification-token", config.get('verification_token', ''),
                    "--output", "reports/performance_benchmark.json"
                ]
            ),
            TestSuite(
                name="安全扫描",
                script="scripts/security_scan.py",
                required=False,
                timeout=1800,  # 30分钟
                args=[
                    "--webhook-url", config.get('webhook_url', ''),
                    "--encrypt-key", config.get('encrypt_key', ''),
                    "--verification-token", config.get('verification_token', ''),
                    "--output", "reports/security_scan_report.json"
                ]
            )
        ]
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有验收测试"""
        logger.info("开始系统验收测试...")
        start_time = time.time()
        
        # 创建报告目录
        os.makedirs("reports", exist_ok=True)
        
        # 运行每个测试套件
        for suite in self.test_suites:
            logger.info(f"运行测试套件: {suite.name}")
            
            result = self.run_test_suite(suite)
            self.results.append(result)
            
            if result.success:
                logger.info(f"✅ {suite.name} 通过")
            else:
                logger.error(f"❌ {suite.name} 失败")
                
                # 如果是必需的测试失败，考虑是否继续
                if suite.required:
                    logger.warning(f"必需测试 {suite.name} 失败，但继续运行其他测试")
        
        total_duration = time.time() - start_time
        return self.generate_final_report(total_duration)
    
    def run_test_suite(self, suite: TestSuite) -> TestResult:
        """运行单个测试套件"""
        start_time = time.time()
        
        try:
            # 构建命令
            cmd = [sys.executable, suite.script] + suite.args
            
            logger.debug(f"执行命令: {' '.join(cmd)}")
            
            # 运行测试
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.getcwd()
            )
            
            try:
                stdout, stderr = process.communicate(timeout=suite.timeout)
                exit_code = process.returncode
                
                duration = time.time() - start_time
                
                # 确定报告文件
                report_file = None
                for arg in suite.args:
                    if arg.startswith("reports/") and arg.endswith(".json"):
                        if os.path.exists(arg):
                            report_file = arg
                        break
                
                return TestResult(
                    suite_name=suite.name,
                    success=exit_code == 0,
                    duration_seconds=duration,
                    exit_code=exit_code,
                    output=stdout,
                    error=stderr,
                    report_file=report_file
                )
                
            except subprocess.TimeoutExpired:
                process.kill()
                duration = time.time() - start_time
                
                return TestResult(
                    suite_name=suite.name,
                    success=False,
                    duration_seconds=duration,
                    exit_code=-1,
                    output="",
                    error=f"测试超时 ({suite.timeout}秒)",
                    report_file=None
                )
                
        except Exception as e:
            duration = time.time() - start_time
            
            return TestResult(
                suite_name=suite.name,
                success=False,
                duration_seconds=duration,
                exit_code=-1,
                output="",
                error=f"执行异常: {e}",
                report_file=None
            )
    
    def generate_final_report(self, total_duration: float) -> Dict[str, Any]:
        """生成最终报告"""
        total_suites = len(self.results)
        passed_suites = sum(1 for r in self.results if r.success)
        failed_suites = total_suites - passed_suites
        
        required_suites = [s for s in self.test_suites if s.required]
        required_results = [r for r in self.results if any(s.name == r.suite_name and s.required for s in self.test_suites)]
        required_passed = sum(1 for r in required_results if r.success)
        
        # 整体通过条件：所有必需测试通过
        overall_success = required_passed == len(required_suites)
        
        # 收集各个测试的详细报告
        detailed_reports = {}
        for result in self.results:
            if result.report_file and os.path.exists(result.report_file):
                try:
                    with open(result.report_file, 'r', encoding='utf-8') as f:
                        detailed_reports[result.suite_name] = json.load(f)
                except Exception as e:
                    logger.warning(f"无法读取报告文件 {result.report_file}: {e}")
        
        report = {
            'acceptance_test_summary': {
                'test_time': datetime.utcnow().isoformat(),
                'total_duration_seconds': total_duration,
                'overall_success': overall_success,
                'total_test_suites': total_suites,
                'passed_test_suites': passed_suites,
                'failed_test_suites': failed_suites,
                'required_test_suites': len(required_suites),
                'required_passed': required_passed,
                'system_config': {
                    'stack_name': self.config.get('stack_name'),
                    'environment': self.config.get('environment'),
                    'region': self.config.get('region')
                }
            },
            'test_suite_results': [
                {
                    'suite_name': result.suite_name,
                    'success': result.success,
                    'duration_seconds': result.duration_seconds,
                    'exit_code': result.exit_code,
                    'required': any(s.name == result.suite_name and s.required for s in self.test_suites),
                    'output_summary': result.output[:500] if result.output else "",
                    'error_summary': result.error[:500] if result.error else "",
                    'report_file': result.report_file
                }
                for result in self.results
            ],
            'detailed_reports': detailed_reports,
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """生成建议"""
        recommendations = []
        
        failed_results = [r for r in self.results if not r.success]
        
        if not failed_results:
            recommendations.append("🎉 所有测试通过！系统已准备好投入生产使用")
        else:
            recommendations.append("⚠️ 部分测试失败，需要解决以下问题：")
            
            for result in failed_results:
                suite = next((s for s in self.test_suites if s.name == result.suite_name), None)
                if suite and suite.required:
                    recommendations.append(f"  🚨 必需测试失败: {result.suite_name}")
                else:
                    recommendations.append(f"  📋 可选测试失败: {result.suite_name}")
        
        # 基于测试结果的具体建议
        deployment_result = next((r for r in self.results if r.suite_name == "部署验证"), None)
        if deployment_result and not deployment_result.success:
            recommendations.append("  - 检查AWS资源部署状态和配置")
            recommendations.append("  - 验证IAM权限和网络连接")
        
        function_result = next((r for r in self.results if r.suite_name == "系统功能测试"), None)
        if function_result and not function_result.success:
            recommendations.append("  - 检查Lambda函数代码和配置")
            recommendations.append("  - 验证飞书应用配置和权限")
        
        performance_result = next((r for r in self.results if r.suite_name == "性能基准测试"), None)
        if performance_result and not performance_result.success:
            recommendations.append("  - 优化Lambda函数内存和超时配置")
            recommendations.append("  - 考虑实施缓存和连接池")
        
        security_result = next((r for r in self.results if r.suite_name == "安全扫描"), None)
        if security_result and not security_result.success:
            recommendations.append("  - 修复发现的安全漏洞")
            recommendations.append("  - 加强输入验证和错误处理")
        
        # 通用建议
        recommendations.extend([
            "",
            "📋 后续建议:",
            "  - 建立持续集成/持续部署(CI/CD)流程",
            "  - 设置生产环境监控和告警",
            "  - 定期进行安全扫描和性能测试",
            "  - 建立灾难恢复和备份策略",
            "  - 制定运维文档和应急响应计划"
        ])
        
        return recommendations

def load_config_from_file(config_file: str) -> Dict[str, Any]:
    """从配置文件加载配置"""
    config = {}
    
    if os.path.exists(config_file):
        if config_file.endswith('.json'):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        elif config_file.endswith('.env'):
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
    
    return config

def load_config_from_env() -> Dict[str, Any]:
    """从环境变量加载配置"""
    return {
        'stack_name': os.getenv('STACK_NAME', 'feishu-bot-dev'),
        'environment': os.getenv('ENVIRONMENT', 'dev'),
        'region': os.getenv('AWS_REGION', 'us-east-1'),
        'webhook_url': os.getenv('WEBHOOK_URL', ''),
        'app_id': os.getenv('FEISHU_APP_ID', ''),
        'app_secret': os.getenv('FEISHU_APP_SECRET', ''),
        'verification_token': os.getenv('FEISHU_VERIFICATION_TOKEN', ''),
        'encrypt_key': os.getenv('FEISHU_ENCRYPT_KEY', '')
    }

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='飞书机器人系统验收测试')
    parser.add_argument('--config-file', help='配置文件路径 (.env 或 .json)')
    parser.add_argument('--stack-name', help='CloudFormation栈名称')
    parser.add_argument('--environment', help='部署环境')
    parser.add_argument('--region', help='AWS区域')
    parser.add_argument('--webhook-url', help='Webhook URL')
    parser.add_argument('--app-id', help='飞书应用ID')
    parser.add_argument('--app-secret', help='飞书应用密钥')
    parser.add_argument('--verification-token', help='飞书验证Token')
    parser.add_argument('--encrypt-key', help='飞书加密密钥')
    parser.add_argument('--skip-optional', action='store_true', help='跳过可选测试')
    parser.add_argument('--output', default='reports/acceptance_test_report.json', help='最终报告输出文件')
    
    args = parser.parse_args()
    
    # 加载配置
    config = {}
    
    # 1. 从配置文件加载
    if args.config_file:
        config.update(load_config_from_file(args.config_file))
    
    # 2. 从环境变量加载
    config.update(load_config_from_env())
    
    # 3. 从命令行参数覆盖
    for key in ['stack_name', 'environment', 'region', 'webhook_url', 
                'app_id', 'app_secret', 'verification_token', 'encrypt_key']:
        value = getattr(args, key)
        if value:
            config[key] = value
    
    # 验证必需配置
    required_configs = ['stack_name', 'webhook_url', 'app_id', 'app_secret', 
                       'verification_token', 'encrypt_key']
    
    missing_configs = [key for key in required_configs if not config.get(key)]
    if missing_configs:
        logger.error(f"缺少必需配置: {missing_configs}")
        sys.exit(1)
    
    # 如果跳过可选测试，修改测试套件
    runner = AcceptanceTestRunner(config)
    
    if args.skip_optional:
        runner.test_suites = [s for s in runner.test_suites if s.required]
        logger.info("跳过可选测试，仅运行必需测试")
    
    # 运行测试
    report = runner.run_all_tests()
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # 输出最终报告
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 打印摘要
    summary = report['acceptance_test_summary']
    print(f"\n{'='*80}")
    print(f"飞书机器人系统验收测试报告")
    print(f"{'='*80}")
    print(f"测试时间: {summary['test_time']}")
    print(f"总耗时: {summary['total_duration_seconds']:.2f}秒")
    print(f"整体结果: {'✅ 通过' if summary['overall_success'] else '❌ 失败'}")
    print(f"测试套件: {summary['passed_test_suites']}/{summary['total_test_suites']} 通过")
    print(f"必需测试: {summary['required_passed']}/{summary['required_test_suites']} 通过")
    print(f"系统配置: {summary['system_config']['stack_name']} ({summary['system_config']['environment']})")
    print(f"最终报告: {args.output}")
    
    # 打印各测试套件结果
    print(f"\n测试套件详情:")
    for result in report['test_suite_results']:
        status = "✅ 通过" if result['success'] else "❌ 失败"
        required = "必需" if result['required'] else "可选"
        duration = f"{result['duration_seconds']:.1f}s"
        print(f"  {status} {result['suite_name']} ({required}) - {duration}")
        
        if not result['success'] and result['error_summary']:
            print(f"    错误: {result['error_summary'][:100]}...")
    
    # 打印建议
    if 'recommendations' in report:
        print(f"\n建议:")
        for rec in report['recommendations']:
            print(f"{rec}")
    
    # 根据整体结果决定退出码
    if summary['overall_success']:
        print(f"\n🎉 系统验收测试通过！系统已准备好投入使用。")
        sys.exit(0)
    else:
        print(f"\n❌ 系统验收测试失败，需要解决问题后重新测试。")
        sys.exit(1)

if __name__ == '__main__':
    main()