# 飞书机器人系统

基于AWS无服务器架构的飞书机器人系统，支持消息接收、处理和监控告警推送。

## 项目结构

```
├── src/
│   ├── shared/          # 共享模块
│   │   ├── models.py    # 数据模型
│   │   └── utils.py     # 工具函数
│   └── lambdas/         # Lambda函数
│       ├── receive_handler.py    # 消息接收处理
│       ├── process_handler.py    # 消息处理
│       └── monitor_handler.py    # 监控告警处理
├── tests/
│   ├── unit/            # 单元测试
│   └── integration/     # 集成测试
├── deployment/          # 部署脚本和CloudFormation模板
├── config.py           # 配置管理
├── requirements.txt    # Python依赖
└── .env.template      # 环境变量模板
```

## 快速开始

1. 复制环境变量模板：
   ```bash
   cp .env.template .env
   ```

2. 配置飞书应用信息和AWS资源

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 运行测试：
   ```bash
   python -m pytest tests/
   ```

## 部署

使用CloudFormation进行一键部署：

```bash
python deployment/deploy.py
```

## 功能特性

- 飞书消息接收和回复
- 异步消息处理
- 监控告警推送
- 错误处理和重试机制
- 安全签名验证
- 一键部署和配置