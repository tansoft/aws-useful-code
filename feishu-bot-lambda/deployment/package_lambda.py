#!/usr/bin/env python3
"""
Lambda函数打包脚本
创建Lambda部署包，包含源代码和依赖
"""

import os
import sys
import zipfile
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional


class LambdaPackager:
    """Lambda函数打包器"""
    
    def __init__(self, project_root: Optional[str] = None):
        """
        初始化打包器
        
        Args:
            project_root: 项目根目录路径
        """
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.src_dir = self.project_root / 'src'
        self.requirements_file = self.project_root / 'requirements.txt'
        
    def create_deployment_package(self, output_path: Optional[str] = None) -> str:
        """
        创建Lambda部署包
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            str: 部署包文件路径
        """
        if not output_path:
            output_path = self.project_root / 'deployment-package.zip'
        
        print(f"创建Lambda部署包: {output_path}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 复制源代码
            print("复制源代码...")
            self._copy_source_code(temp_path)
            
            # 安装依赖
            if self.requirements_file.exists():
                print("安装Python依赖...")
                self._install_dependencies(temp_path)
            
            # 创建ZIP文件
            print("创建ZIP文件...")
            self._create_zip_file(temp_path, output_path)
        
        print(f"部署包创建完成: {output_path}")
        return str(output_path)
    
    def _copy_source_code(self, temp_path: Path) -> None:
        """复制源代码到临时目录"""
        src_dest = temp_path / 'src'
        shutil.copytree(self.src_dir, src_dest)
        
        # 复制配置文件
        config_file = self.project_root / 'config.py'
        if config_file.exists():
            shutil.copy2(config_file, temp_path / 'config.py')
    
    def _install_dependencies(self, temp_path: Path) -> None:
        """安装Python依赖到临时目录"""
        try:
            # 使用pip安装依赖到临时目录
            cmd = [
                sys.executable, '-m', 'pip', 'install',
                '-r', str(self.requirements_file),
                '-t', str(temp_path),
                '--no-deps'  # 不安装依赖的依赖，避免冲突
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"警告: 依赖安装失败: {result.stderr}")
                # 尝试不使用--no-deps选项
                cmd_without_no_deps = [
                    sys.executable, '-m', 'pip', 'install',
                    '-r', str(self.requirements_file),
                    '-t', str(temp_path)
                ]
                
                result = subprocess.run(cmd_without_no_deps, capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"依赖安装失败: {result.stderr}")
            
            # 清理不需要的文件
            self._cleanup_dependencies(temp_path)
            
        except Exception as e:
            print(f"警告: 无法安装依赖: {str(e)}")
            print("将创建不包含依赖的部署包")
    
    def _cleanup_dependencies(self, temp_path: Path) -> None:
        """清理不需要的依赖文件"""
        # 删除不需要的文件和目录
        cleanup_patterns = [
            '*.dist-info',
            '*.egg-info',
            '__pycache__',
            '*.pyc',
            '*.pyo',
            'tests',
            'test',
            'docs',
            'examples',
            '*.so',  # 编译的扩展模块可能不兼容Lambda
        ]
        
        for pattern in cleanup_patterns:
            for item in temp_path.glob(f'**/{pattern}'):
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
    
    def _create_zip_file(self, temp_path: Path, output_path: str) -> None:
        """创建ZIP文件"""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_path):
                for file in files:
                    file_path = Path(root) / file
                    arc_name = file_path.relative_to(temp_path)
                    zipf.write(file_path, arc_name)
    
    def create_function_specific_package(self, function_name: str, 
                                       output_path: Optional[str] = None) -> str:
        """
        为特定Lambda函数创建部署包
        
        Args:
            function_name: Lambda函数名称 (receive, process, monitor)
            output_path: 输出文件路径
            
        Returns:
            str: 部署包文件路径
        """
        if not output_path:
            output_path = self.project_root / f'{function_name}-deployment-package.zip'
        
        print(f"为{function_name}函数创建部署包: {output_path}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 复制共享代码
            shared_dest = temp_path / 'src' / 'shared'
            shared_dest.parent.mkdir(parents=True)
            shutil.copytree(self.src_dir / 'shared', shared_dest)
            
            # 复制特定Lambda函数代码
            lambda_src = self.src_dir / 'lambdas' / f'{function_name}_handler.py'
            if lambda_src.exists():
                lambda_dest = temp_path / 'src' / 'lambdas'
                lambda_dest.mkdir(parents=True)
                shutil.copy2(lambda_src, lambda_dest / f'{function_name}_handler.py')
                
                # 创建__init__.py文件
                (temp_path / 'src' / '__init__.py').touch()
                (lambda_dest / '__init__.py').touch()
            
            # 复制配置文件
            config_file = self.project_root / 'config.py'
            if config_file.exists():
                shutil.copy2(config_file, temp_path / 'config.py')
            
            # 安装依赖
            if self.requirements_file.exists():
                print("安装Python依赖...")
                self._install_dependencies(temp_path)
            
            # 创建ZIP文件
            print("创建ZIP文件...")
            self._create_zip_file(temp_path, output_path)
        
        print(f"函数{function_name}的部署包创建完成: {output_path}")
        return str(output_path)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Lambda函数打包工具')
    parser.add_argument('--function', choices=['receive', 'process', 'monitor', 'all'],
                       default='all', help='要打包的函数')
    parser.add_argument('--output', help='输出文件路径')
    parser.add_argument('--project-root', help='项目根目录路径')
    
    args = parser.parse_args()
    
    try:
        packager = LambdaPackager(args.project_root)
        
        if args.function == 'all':
            # 创建通用部署包
            output_path = args.output or 'deployment-package.zip'
            packager.create_deployment_package(output_path)
        else:
            # 创建特定函数的部署包
            output_path = args.output or f'{args.function}-deployment-package.zip'
            packager.create_function_specific_package(args.function, output_path)
        
        print("打包完成!")
        
    except Exception as e:
        print(f"打包失败: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()