#!/bin/bash
"""
飞书机器人系统部署脚本
简化的Shell脚本版本，用于快速部署
"""

set -e

# 默认配置
STACK_NAME="feishu-bot-dev"
ENVIRONMENT="dev"
REGION="us-east-1"
CONFIG_FILE=""

# 显示帮助信息
show_help() {
    cat << EOF
飞书机器人系统部署脚本

用法: $0 [选项]

选项:
    -s, --stack-name NAME       CloudFormation栈名称 (默认: feishu-bot-dev)
    -e, --environment ENV       部署环境 (默认: dev)
    -r, --region REGION         AWS区域 (默认: us-east-1)
    -c, --config-file FILE      配置文件路径
    -d, --delete               删除栈
    -h, --help                 显示此帮助信息

示例:
    $0 --stack-name feishu-bot-prod --environment prod --config-file config.json
    $0 --delete --stack-name feishu-bot-dev
EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -c|--config-file)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -d|--delete)
            DELETE_STACK=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查AWS CLI
if ! command -v aws &> /dev/null; then
    echo "错误: 未找到AWS CLI，请先安装AWS CLI"
    exit 1
fi

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python 3，请先安装Python 3"
    exit 1
fi

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "项目根目录: $PROJECT_ROOT"
echo "部署脚本目录: $SCRIPT_DIR"

# 删除栈
if [[ "$DELETE_STACK" == "true" ]]; then
    echo "删除CloudFormation栈: $STACK_NAME"
    
    aws cloudformation delete-stack \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    echo "等待栈删除完成..."
    aws cloudformation wait stack-delete-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    echo "栈删除完成!"
    exit 0
fi

# 验证配置文件
if [[ -n "$CONFIG_FILE" && ! -f "$CONFIG_FILE" ]]; then
    echo "错误: 配置文件不存在: $CONFIG_FILE"
    exit 1
fi

# 创建Lambda部署包
echo "创建Lambda部署包..."
cd "$PROJECT_ROOT"

if [[ -f "$SCRIPT_DIR/package_lambda.py" ]]; then
    python3 "$SCRIPT_DIR/package_lambda.py" --output deployment-package.zip
else
    echo "警告: 未找到打包脚本，使用简单打包方式"
    
    # 简单的ZIP打包
    if [[ -f "deployment-package.zip" ]]; then
        rm deployment-package.zip
    fi
    
    zip -r deployment-package.zip src/ config.py -x "**/__pycache__/*" "**/*.pyc"
fi

# 检查部署包是否创建成功
if [[ ! -f "deployment-package.zip" ]]; then
    echo "错误: 部署包创建失败"
    exit 1
fi

echo "部署包创建完成: deployment-package.zip"

# 使用Python部署脚本
if [[ -f "$SCRIPT_DIR/deploy.py" ]]; then
    echo "使用Python部署脚本..."
    
    DEPLOY_CMD="python3 $SCRIPT_DIR/deploy.py --stack-name $STACK_NAME --environment $ENVIRONMENT --region $REGION"
    
    if [[ -n "$CONFIG_FILE" ]]; then
        DEPLOY_CMD="$DEPLOY_CMD --config-file $CONFIG_FILE"
    fi
    
    eval "$DEPLOY_CMD"
else
    echo "错误: 未找到Python部署脚本"
    exit 1
fi

echo "部署完成!"