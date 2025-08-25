#!/usr/bin/env python3
"""
Lambda函数代码更新脚本
用于更新已部署的Lambda函数代码
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from package_lambda import LambdaPackager


class LambdaUpdater:
    """Lambda函数代码更新器"""
    
    def __init__(self, region: str = 'us-east-1', profile: Optional[str] = None):
        """
        初始化更新器
        
        Args:
            region: AWS区域
            profile: AWS配置文件
        """
        self.region = region
        self.profile = profile
        
        # 初始化AWS客户端
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.lambda_client = session.client('lambda', region_name=region)
        
        # 初始化打包器
        self.packager = LambdaPackager()
    
    def update_function_code(self, function_name: str, 
                           use_function_specific_package: bool = False) -> dict:
        """
        更新Lambda函数代码
        
        Args:
            function_name: Lambda函数名称
            use_function_specific_package: 是否使用函数特定的部署包
            
        Returns:
            dict: 更新结果
        """
        try:
            print(f"更新Lambda函数代码: {function_name}")
            
            # 创建部署包
            if use_function_specific_package:
                # 提取函数类型 (receive, process, monitor)
                function_type = self._extract_function_type(function_name)
                if function_type:
                    package_path = self.packager.create_function_specific_package(function_type)
                else:
                    package_path = self.packager.create_deployment_package()
            else:
                package_path = self.packager.create_deployment_package()
            
            # 读取部署包
            with open(package_path, 'rb') as f:
                zip_content = f.read()
            
            # 更新函数代码
            response = self.lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_content
            )
            
            print(f"✓ {function_name} 更新成功")
            
            # 清理临时文件
            os.remove(package_path)
            
            return {
                'status': 'success',
                'function_name': function_name,
                'version': response.get('Version'),
                'last_modified': response.get('LastModified')
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            if error_code == 'ResourceNotFoundException':
                print(f"✗ Lambda函数 {function_name} 不存在")
                return {
                    'status': 'not_found',
                    'function_name': function_name,
                    'error': f"Function not found: {function_name}"
                }
            else:
                print(f"✗ 更新 {function_name} 失败: {error_message}")
                return {
                    'status': 'failed',
                    'function_name': function_name,
                    'error': f"{error_code}: {error_message}"
                }
        
        except Exception as e:
            print(f"✗ 更新 {function_name} 时发生错误: {str(e)}")
            return {
                'status': 'error',
                'function_name': function_name,
                'error': str(e)
            }
    
    def _extract_function_type(self, function_name: str) -> Optional[str]:
        """
        从函数名称中提取函数类型
        
        Args:
            function_name: Lambda函数名称
            
        Returns:
            str: 函数类型 (receive, process, monitor)
        """
        function_name_lower = function_name.lower()
        
        if 'receive' in function_name_lower:
            return 'receive'
        elif 'process' in function_name_lower:
            return 'process'
        elif 'monitor' in function_name_lower:
            return 'monitor'
        
        return None
    
    def update_multiple_functions(self, function_names: List[str],
                                use_function_specific_package: bool = False) -> List[dict]:
        """
        批量更新多个Lambda函数
        
        Args:
            function_names: Lambda函数名称列表
            use_function_specific_package: 是否使用函数特定的部署包
            
        Returns:
            list: 更新结果列表
        """
        results = []
        
        for function_name in function_names:
            result = self.update_function_code(function_name, use_function_specific_package)
            results.append(result)
        
        return results
    
    def list_functions_by_prefix(self, prefix: str) -> List[str]:
        """
        根据前缀列出Lambda函数
        
        Args:
            prefix: 函数名前缀
            
        Returns:
            list: 匹配的函数名列表
        """
        try:
            response = self.lambda_client.list_functions()
            functions = response.get('Functions', [])
            
            matching_functions = [
                func['FunctionName'] 
                for func in functions 
                if func['FunctionName'].startswith(prefix)
            ]
            
            return matching_functions
            
        except Exception as e:
            print(f"获取函数列表失败: {str(e)}")
            return []
    
    def get_function_info(self, function_name: str) -> Optional[dict]:
        """
        获取Lambda函数信息
        
        Args:
            function_name: Lambda函数名称
            
        Returns:
            dict: 函数信息
        """
        try:
            response = self.lambda_client.get_function(FunctionName=function_name)
            
            config = response.get('Configuration', {})
            return {
                'function_name': config.get('FunctionName'),
                'runtime': config.get('Runtime'),
                'handler': config.get('Handler'),
                'code_size': config.get('CodeSize'),
                'last_modified': config.get('LastModified'),
                'version': config.get('Version'),
                'state': config.get('State')
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return None
            raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Lambda函数代码更新工具')
    parser.add_argument('--function-name', help='要更新的Lambda函数名称')
    parser.add_argument('--stack-prefix', help='栈名称前缀，用于批量更新')
    parser.add_argument('--region', default='us-east-1', help='AWS区域')
    parser.add_argument('--profile', help='AWS配置文件')
    parser.add_argument('--function-specific', action='store_true',
                       help='使用函数特定的部署包')
    parser.add_argument('--list-functions', action='store_true',
                       help='列出匹配的函数')
    parser.add_argument('--info', action='store_true',
                       help='显示函数信息')
    
    args = parser.parse_args()
    
    try:
        updater = LambdaUpdater(region=args.region, profile=args.profile)
        
        if args.function_name:
            if args.list_functions:
                # 列出匹配的函数
                functions = updater.list_functions_by_prefix(args.function_name)
                if functions:
                    print(f"找到 {len(functions)} 个匹配的函数:")
                    for func in functions:
                        print(f"  - {func}")
                else:
                    print("未找到匹配的函数")
                return
            
            if args.info:
                # 显示函数信息
                info = updater.get_function_info(args.function_name)
                if info:
                    print(f"函数信息: {args.function_name}")
                    for key, value in info.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"函数不存在: {args.function_name}")
                return
            
            # 更新单个函数
            result = updater.update_function_code(args.function_name, args.function_specific)
            
            if result['status'] == 'success':
                print(f"函数 {args.function_name} 更新成功!")
            else:
                print(f"函数 {args.function_name} 更新失败: {result.get('error', '未知错误')}")
                sys.exit(1)
        
        elif args.stack_prefix:
            # 批量更新函数
            functions = updater.list_functions_by_prefix(args.stack_prefix)
            
            if not functions:
                print(f"未找到前缀为 '{args.stack_prefix}' 的函数")
                return
            
            print(f"找到 {len(functions)} 个函数，开始批量更新...")
            
            results = updater.update_multiple_functions(functions, args.function_specific)
            
            # 统计结果
            success_count = sum(1 for r in results if r['status'] == 'success')
            failed_count = len(results) - success_count
            
            print(f"\n批量更新完成:")
            print(f"  成功: {success_count}")
            print(f"  失败: {failed_count}")
            
            # 显示失败的函数
            failed_functions = [r for r in results if r['status'] != 'success']
            if failed_functions:
                print("\n失败的函数:")
                for result in failed_functions:
                    print(f"  - {result['function_name']}: {result.get('error', '未知错误')}")
                sys.exit(1)
        
        else:
            print("错误: 请指定 --function-name 或 --stack-prefix")
            parser.print_help()
            sys.exit(1)
    
    except Exception as e:
        print(f"更新过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()