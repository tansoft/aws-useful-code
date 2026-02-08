import logging
import boto3
import json
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from strands_tools import calculator, current_time
from mcp import stdio_client, StdioServerParameters
from strands.models import BedrockModel
import csv
from io import StringIO

#model_id = "us.amazon.nova-2-lite-v1:0"
#model_id = "us.anthropic.claude-opus-4-5-20251101-v1:0"
model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

ce_client = boto3.client('ce', region_name='us-east-1')
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("strands")
logger.setLevel(logging.INFO)

@tool
def get_cost_and_usage(start_date:str, end_date:str, granularity:str='DAILY', group_by:str='SERVICE'):
    """
    获取成本和使用情况数据。
    Args:
        start_date: 查询开始的时间，如：2026-01-15
        end_date: 查询结束的时间，如：2026-01-20
        granularity: 统计的维度，可用：DAILY, MONTHLY, HOURLY
    Returns:
        str: 返回csv格式的成本和使用情况数据
    """
    try:
        logger.info(f"Tool - get_cost_and_usage: date: {start_date} - {end_date} granularity: {granularity} group by: {group_by}")
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity=granularity,  # DAILY, MONTHLY, HOURLY
            Metrics=['BlendedCost', 'UsageQuantity'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': group_by
                }
            ]
        )
        # Convert JSON response to CSV format
        csv_output = StringIO()
        csv_writer = csv.writer(csv_output)
        # Write CSV header
        csv_writer.writerow(['TimePeriod_Start', 'TimePeriod_End', 'Service', 'BlendedCost_Amount', 'BlendedCost_Unit', 'UsageQuantity_Amount', 'UsageQuantity_Unit'])
        # Write data rows
        for result in response.get('ResultsByTime', []):
            time_period_start = result.get('TimePeriod', {}).get('Start', '')
            time_period_end = result.get('TimePeriod', {}).get('End', '')
            
            for group in result.get('Groups', []):
                service = group.get('Keys', [''])[0]
                blended_cost = group.get('Metrics', {}).get('BlendedCost', {})
                usage_quantity = group.get('Metrics', {}).get('UsageQuantity', {})
                csv_writer.writerow([
                    time_period_start,
                    time_period_end,
                    service,
                    blended_cost.get('Amount', '0'),
                    blended_cost.get('Unit', 'USD'),
                    usage_quantity.get('Amount', '0'),
                    usage_quantity.get('Unit', '')
                ])
        csv_data = csv_output.getvalue()
        csv_output.close()
        logger.info(f"Response: length: {len(csv_data)}")
        #logger.info(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)}")
        return csv_data
    except Exception as e:
        print(f"Error getting cost data: {e}")
        return None

@tool
def analyze_top_services(cost_data:str, top_n:int=10):
    """
    获取成本和使用情况数据。
    Args:
        cost_data: 通过 get_cost_and_usage 工具查询到的csv数据
        top_n: 统计前n的排名，如果没有指定排名数量，默认是前10名
    Returns:
        str: 返回csv格式的服务排名数据
    """
    try:
        logger.info(f"Tool - analyze_top_services: csv length:{len(cost_data)} top_n: {top_n}")
        # Parse CSV data
        csv_reader = csv.reader(StringIO(cost_data))
        header = next(csv_reader)  # Skip header row
        # Aggregate costs by service
        service_costs = {}
        for row in csv_reader:
            if len(row) >= 4:
                service = row[2]  # Service column
                cost = float(row[3]) if row[3] else 0.0  # BlendedCost_Amount column
                
                if service in service_costs:
                    service_costs[service] += cost
                else:
                    service_costs[service] = cost
        
        # Sort services by cost (descending) and get top N
        sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)[:top_n]
        # Create CSV output
        csv_output = StringIO()
        csv_writer = csv.writer(csv_output)
        csv_writer.writerow(['Rank', 'Service', 'Total_Cost', 'Unit'])
        for rank, (service, cost) in enumerate(sorted_services, 1):
            csv_writer.writerow([rank, service, f"{cost:.2f}", 'USD'])
        result_csv = csv_output.getvalue()
        csv_output.close()
        logger.info(f"Response: length: {len(result_csv)}")
        return result_csv        
    except Exception as e:
        logger.error(f"Error analyzing top services: {e}")
        return None

if __name__ == "__main__":
    
    # Initialize Bedrock model
    bedrock_model = BedrockModel(
        model_id=model_id,
        #max_tokens=64000,
        temperature=0.1
    )

    # List our custom tools
    custom_tools = [
        get_cost_and_usage,
        analyze_top_services,
        current_time,
        calculator
    ]

    # Create the agent with both our custom tools and MCP tools
    agent = Agent(
        model=bedrock_model,
        system_prompt="""你是一个AWS账单专家，可以提供AWS服务、实例类型和价格信息。你可以使用以下工具：
1. get_cost_and_usage - 获取成本和使用情况数据
2. analyze_top_services - 通过成本和使用情况数据，总结调用最多的服务

请提供准确的AWS账单使用信息，并解释价格结构、可用区域和服务特性等。
需要使用current_time工具验证相对时间。
优先调用上述工具进行计算，如果没有合适的工具，则需要使用calculator工具进行计算验证。
输出使用表格进行汇总展现，如果没有指定需要的数据，默认使用BlendedCost数据。
注意json作为工具参数是否需要进行编码处理。
""",
        tools = custom_tools
    )

    print("\n👨 AWS价格助手: 询问关于AWS服务、实例类型和价格的问题! 输入'exit'退出。\n如：最近7天使用最多的服务？")
    
    # Run the agent in a loop for interactive conversation
    while True:
        # 最近7天使用最多的服务是哪个？
        user_input = input("\n您 > ")
        if user_input.lower() in ['quit', 'exit']:
            print("感谢使用AWS账单助手！")
            break
        response = agent(user_input + "，请以中文回答，并需要确保信息是准确的。")
        print(f"\nAWS账单助手 > {response}")



'''

python demo_aws_cur.py 

👨 AWS价格助手: 询问关于AWS服务、实例类型和价格的问题! 输入'exit'退出。
如：最近7天使用最多的服务？

您 > 最近7天使用最多的服务？
INFO | strands.telemetry.metrics | Creating Strands MetricsClient
我来帮您查询最近7天使用最多的服务。首先，我需要获取当前时间，然后查询最近7天的成本数据。
Tool #1: current_time
现在我知道当前时间是2026年2月1日，让我查询最近7天（从1月25日到2月1日）的成本和使用情况数据。
Tool #2: get_cost_and_usage
INFO | strands | Tool - get_cost_and_usage: date: 2026-01-25 - 2026-02-01 granularity: DAILY group by: SERVICE
INFO | strands | Response: length: 23300
现在让我分析这些数据，找出使用最多的服务：
Tool #3: analyze_top_services
INFO | strands | Tool - analyze_top_services: csv length:22981 top_n: 10
INFO | strands | Response: length: 389
完美！现在让我为您整理一份详细的报告。根据数据分析，我将为您展示最近7天（2026年1月25日至2月1日）使用最多的AWS服务。

## 📊 最近7天AWS服务使用情况报告

**查询时间范围：** 2026年1月25日 - 2026年2月1日（共7天）

### 🏆 使用成本排名前10的服务

| 排名 | AWS服务名称 | 总成本（USD） | 占比说明 |
|------|------------|--------------|----------|
| 1 | **Amazon SageMaker** | $331.11 | 机器学习平台服务，成本最高 |
| 2 | **EC2 - Other** | $123.90 | EC2相关其他服务（如数据传输、EBS等） |
| 3 | **Amazon RDS** | $63.82 | 关系型数据库服务 |
| 4 | **Amazon EC2 Compute** | $43.64 | EC2计算实例 |
| 5 | **Amazon CloudWatch** | $33.43 | 监控和日志服务 |
| 6 | **Amazon VPC** | $31.25 | 虚拟私有云网络服务 |
| 7 | **AWS WAF** | $27.32 | Web应用防火墙 |
| 8 | **AWS Firewall Manager** | $20.97 | 防火墙管理服务 |
| 9 | **Amazon S3** | $20.52 | 对象存储服务 |
| 10 | **Amazon QuickSight** | $16.77 | 商业智能分析服务 |

### 📈 关键发现

1. **机器学习占主导地位**：Amazon SageMaker以$331.11的成本遥遥领先，占据了最大的支出份额，说明您的业务在机器学习方面有大量投入。

2. **计算资源消耗显著**：EC2相关服务（EC2 - Other + EC2 Compute）合计约$167.54，是第二大支出类别。

3. **数据库服务稳定**：Amazon RDS保持在第三位，7天总成本$63.82，平均每天约$9.12。

4. **安全服务投入**：AWS WAF和Firewall Manager合计约$48.29，显示出对安全防护的重视。

5. **基础设施服务**：CloudWatch、VPC、S3等基础服务合计约$85.20，支撑着整体架构运行。

### 💡 建议

- **成本优化**：建议重点关注SageMaker的使用情况，检查是否有未使用的训练实例或端点
- **资源监控**：EC2相关成本较高，建议使用AWS Cost Explorer深入分析具体资源使用情况
- **预留实例**：对于RDS和EC2等长期运行的服务，可考虑购买预留实例以降低成本

---

**数据来源：** AWS Cost and Usage Report  
**数据准确性：** ✅ 已通过实时API验证  
**报告生成时间：** 2026年2月1日
AWS账单助手 > 完美！现在让我为您整理一份详细的报告。根据数据分析，我将为您展示最近7天（2026年1月25日至2月1日）使用最多的AWS服务。

## 📊 最近7天AWS服务使用情况报告

**查询时间范围：** 2026年1月25日 - 2026年2月1日（共7天）

### 🏆 使用成本排名前10的服务

| 排名 | AWS服务名称 | 总成本（USD） | 占比说明 |
|------|------------|--------------|----------|
| 1 | **Amazon SageMaker** | $331.11 | 机器学习平台服务，成本最高 |
| 2 | **EC2 - Other** | $123.90 | EC2相关其他服务（如数据传输、EBS等） |
| 3 | **Amazon RDS** | $63.82 | 关系型数据库服务 |
| 4 | **Amazon EC2 Compute** | $43.64 | EC2计算实例 |
| 5 | **Amazon CloudWatch** | $33.43 | 监控和日志服务 |
| 6 | **Amazon VPC** | $31.25 | 虚拟私有云网络服务 |
| 7 | **AWS WAF** | $27.32 | Web应用防火墙 |
| 8 | **AWS Firewall Manager** | $20.97 | 防火墙管理服务 |
| 9 | **Amazon S3** | $20.52 | 对象存储服务 |
| 10 | **Amazon QuickSight** | $16.77 | 商业智能分析服务 |

### 📈 关键发现

1. **机器学习占主导地位**：Amazon SageMaker以$331.11的成本遥遥领先，占据了最大的支出份额，说明您的业务在机器学习方面有大量投入。

2. **计算资源消耗显著**：EC2相关服务（EC2 - Other + EC2 Compute）合计约$167.54，是第二大支出类别。

3. **数据库服务稳定**：Amazon RDS保持在第三位，7天总成本$63.82，平均每天约$9.12。

4. **安全服务投入**：AWS WAF和Firewall Manager合计约$48.29，显示出对安全防护的重视。

5. **基础设施服务**：CloudWatch、VPC、S3等基础服务合计约$85.20，支撑着整体架构运行。

### 💡 建议

- **成本优化**：建议重点关注SageMaker的使用情况，检查是否有未使用的训练实例或端点
- **资源监控**：EC2相关成本较高，建议使用AWS Cost Explorer深入分析具体资源使用情况
- **预留实例**：对于RDS和EC2等长期运行的服务，可考虑购买预留实例以降低成本

---

**数据来源：** AWS Cost and Usage Report  
**数据准确性：** ✅ 已通过实时API验证  
**报告生成时间：** 2026年2月1日


'''