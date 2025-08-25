#!/usr/bin/env python3
"""
测试运行脚本
运行单元测试、集成测试和生成覆盖率报告
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, cwd=None):
    """运行命令并返回结果"""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


def install_dependencies():
    """安装测试依赖"""
    print("Installing test dependencies...")
    
    # 安装基础依赖
    if not run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]):
        return False
    
    # 安装测试相关依赖
    test_deps = [
        "pytest>=7.4.0",
        "pytest-cov>=4.1.0",
        "pytest-mock>=3.11.0",
        "pytest-xdist>=3.3.0",  # 并行测试
        "coverage>=7.2.0",
        "moto>=4.2.0",
        "psutil>=5.9.0"  # 性能测试需要
    ]
    
    for dep in test_deps:
        if not run_command([sys.executable, "-m", "pip", "install", dep]):
            return False
    
    return True


def run_unit_tests(coverage=True, parallel=False):
    """运行单元测试"""
    print("\n" + "="*50)
    print("Running Unit Tests")
    print("="*50)
    
    cmd = [sys.executable, "-m", "pytest", "tests/unit/"]
    
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml:coverage.xml",
            "--cov-fail-under=85"  # 要求85%以上覆盖率
        ])
    
    if parallel:
        cmd.extend(["-n", "auto"])  # 自动并行
    
    cmd.extend([
        "-v",
        "--tb=short",
        "--strict-markers"
    ])
    
    return run_command(cmd)


def run_integration_tests():
    """运行集成测试"""
    print("\n" + "="*50)
    print("Running Integration Tests")
    print("="*50)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/integration/",
        "-v",
        "--tb=short",
        "-m", "integration"
    ]
    
    return run_command(cmd)


def run_performance_tests():
    """运行性能测试"""
    print("\n" + "="*50)
    print("Running Performance Tests")
    print("="*50)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/performance/",
        "-v",
        "--tb=short",
        "-m", "performance"
    ]
    
    return run_command(cmd)


def run_security_tests():
    """运行安全测试"""
    print("\n" + "="*50)
    print("Running Security Tests")
    print("="*50)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/security/",
        "-v",
        "--tb=short",
        "-m", "security"
    ]
    
    return run_command(cmd)


def run_all_tests(coverage=True, parallel=False):
    """运行所有测试"""
    print("\n" + "="*50)
    print("Running All Tests")
    print("="*50)
    
    cmd = [sys.executable, "-m", "pytest", "tests/"]
    
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml:coverage.xml"
        ])
    
    if parallel:
        cmd.extend(["-n", "auto"])
    
    cmd.extend([
        "-v",
        "--tb=short",
        "--strict-markers"
    ])
    
    return run_command(cmd)


def run_lint_checks():
    """运行代码质量检查"""
    print("\n" + "="*50)
    print("Running Code Quality Checks")
    print("="*50)
    
    # 安装linting工具
    lint_tools = ["flake8", "black", "isort", "mypy"]
    for tool in lint_tools:
        run_command([sys.executable, "-m", "pip", "install", tool])
    
    success = True
    
    # 检查代码格式
    print("\nChecking code formatting with black...")
    if not run_command([sys.executable, "-m", "black", "--check", "src/", "tests/"]):
        print("Code formatting issues found. Run 'black src/ tests/' to fix.")
        success = False
    
    # 检查import排序
    print("\nChecking import sorting with isort...")
    if not run_command([sys.executable, "-m", "isort", "--check-only", "src/", "tests/"]):
        print("Import sorting issues found. Run 'isort src/ tests/' to fix.")
        success = False
    
    # 检查代码风格
    print("\nChecking code style with flake8...")
    if not run_command([sys.executable, "-m", "flake8", "src/", "tests/", "--max-line-length=100"]):
        success = False
    
    return success


def generate_test_report():
    """生成测试报告"""
    print("\n" + "="*50)
    print("Generating Test Report")
    print("="*50)
    
    # 生成HTML覆盖率报告
    if os.path.exists("htmlcov/index.html"):
        print("Coverage report generated: htmlcov/index.html")
    
    # 生成JUnit XML报告（用于CI/CD）
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "--junitxml=test-results.xml",
        "--quiet"
    ]
    
    run_command(cmd)
    
    if os.path.exists("test-results.xml"):
        print("JUnit XML report generated: test-results.xml")


def clean_test_artifacts():
    """清理测试产生的文件"""
    print("\nCleaning test artifacts...")
    
    artifacts = [
        ".coverage",
        "coverage.xml",
        "test-results.xml",
        "htmlcov/",
        ".pytest_cache/",
        "**/__pycache__/",
        "**/*.pyc"
    ]
    
    for pattern in artifacts:
        if "*" in pattern:
            # 使用find命令删除匹配的文件
            if pattern.endswith("__pycache__/"):
                run_command(["find", ".", "-type", "d", "-name", "__pycache__", "-exec", "rm", "-rf", "{}", "+"])
            elif pattern.endswith("*.pyc"):
                run_command(["find", ".", "-name", "*.pyc", "-delete"])
        else:
            path = Path(pattern)
            if path.exists():
                if path.is_dir():
                    import shutil
                    shutil.rmtree(path)
                else:
                    path.unlink()
                print(f"Removed: {pattern}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Run tests for Feishu Bot System")
    parser.add_argument("--type", choices=["unit", "integration", "performance", "security", "all"],
                       default="unit", help="Type of tests to run")
    parser.add_argument("--no-coverage", action="store_true", help="Skip coverage reporting")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--install-deps", action="store_true", help="Install test dependencies")
    parser.add_argument("--lint", action="store_true", help="Run code quality checks")
    parser.add_argument("--clean", action="store_true", help="Clean test artifacts")
    parser.add_argument("--report", action="store_true", help="Generate test report")
    
    args = parser.parse_args()
    
    # 切换到项目根目录
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    success = True
    
    # 清理旧的测试文件
    if args.clean:
        clean_test_artifacts()
        return
    
    # 安装依赖
    if args.install_deps:
        if not install_dependencies():
            print("Failed to install dependencies")
            sys.exit(1)
    
    # 运行代码质量检查
    if args.lint:
        if not run_lint_checks():
            success = False
    
    # 运行测试
    coverage = not args.no_coverage
    
    if args.type == "unit":
        success = run_unit_tests(coverage, args.parallel)
    elif args.type == "integration":
        success = run_integration_tests()
    elif args.type == "performance":
        success = run_performance_tests()
    elif args.type == "security":
        success = run_security_tests()
    elif args.type == "all":
        success = run_all_tests(coverage, args.parallel)
    
    # 生成报告
    if args.report:
        generate_test_report()
    
    # 输出结果
    if success:
        print("\n" + "="*50)
        print("✅ All tests passed!")
        print("="*50)
        
        if coverage and os.path.exists("htmlcov/index.html"):
            print(f"📊 Coverage report: file://{os.path.abspath('htmlcov/index.html')}")
        
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("❌ Some tests failed!")
        print("="*50)
        sys.exit(1)


if __name__ == "__main__":
    main()