"""
火山云（字节跳动）账单查询模块
API文档: https://www.volcengine.com/docs/6261/104955
"""
import volcenginesdkcore
import volcenginesdkbilling
from volcenginesdkcore.rest import ApiException
from config.config import Config

# --------------------------配置--------------------------
ACCESS_KEY_ID = Config.volcano_ACCESS_KEY_ID  # 火山云 AccessKeyId
SECRET_ACCESS_KEY = Config.volcano_SECRET_ACCESS_KEY  # 火山云 SecretAccessKey
LIMIT = 100  # 每页查询数量

# 默认标签筛选配置
DEFAULT_TAG_KEY = ""
DEFAULT_TAG_VALUE = ""
# ---------------------------------------------------------


def get_resource_bill(month: str, tag_key: str = "", tag_value: str = ""):
    """
    获取火山云资源账单（使用费用分析API）
    :param month: 账单月份 yyyy-MM
    :param tag_key: 标签键，留空表示不按标签筛选
    :param tag_value: 标签值，留空表示不按标签筛选
    :return: 账单列表
    """
    # 配置火山云客户端
    configuration = volcenginesdkcore.Configuration()
    configuration.ak = ACCESS_KEY_ID
    configuration.sk = SECRET_ACCESS_KEY
    configuration.region = "cn-beijing"
    volcenginesdkcore.Configuration.set_default(configuration)

    # 创建API实例
    api_instance = volcenginesdkbilling.BILLINGApi()

    offset = 0
    all_items = []

    while True:
        # 构建请求 - 使用费用分析API
        request = volcenginesdkbilling.ListCostAnalysisOpenApiRequest(
            begin_time_str=f"{month}-01",  # 格式: YYYY-MM-01
            end_time_str=f"{month}-01",     # 查询单月数据
            time_granularity=0,  # 0:账期
            cost_type=2,  # 2:应付金额
            classify_dimension=3,  # 3:按产品分类
            limit=LIMIT,
            offset=offset
        )

        # 添加标签筛选
        if tag_key and tag_value:
            request.classify_dimension = 10  # 10:标签维度
            request.classify_dimension_value = tag_key

        try:
            # 调用API
            response = api_instance.list_cost_analysis_open_api(request)

            # 检查响应
            if not response or not hasattr(response, 'cost_data'):
                break

            cost_data = response.cost_data if response.cost_data else []

            if not cost_data:
                break

            # 将响应对象转换为字典
            for item in cost_data:
                costs_list = []
                total_amount = 0

                # 处理 costs 数组
                if hasattr(item, 'costs') and item.costs:
                    for c in item.costs:
                        amount = float(c.amount) if hasattr(c, 'amount') else 0
                        total_amount += amount
                        costs_list.append({
                            'TimeStr': c.time_str if hasattr(c, 'time_str') else '',
                            'Amount': amount
                        })

                all_items.append({
                    'ClassifyItem': item.classify_item if hasattr(item, 'classify_item') else '未知',
                    'TotalAmount': total_amount,  # 手动计算总额
                    'Costs': costs_list
                })

            # 检查是否还有更多数据
            total = response.total if hasattr(response, 'total') else 0
            offset += LIMIT
            if offset >= total:
                break

        except ApiException as e:
            raise Exception(f"火山云API异常：{e}")
        except Exception as e:
            raise Exception(f"火山云账单查询失败：{str(e)}")

    return all_items


def analyze_volcano_bill(month: str, tag_key: str = "", tag_value: str = "", include_details: bool = False):
    """
    分析火山云账单
    :param month: 账单月份 yyyy-MM
    :param tag_key: 标签键，留空表示不按标签筛选
    :param tag_value: 标签值，留空表示不按标签筛选
    :param include_details: 是否包含明细账单列表
    :return: 账单分析结果字典
    """
    try:
        bill_list = get_resource_bill(month, tag_key, tag_value)
    except NotImplementedError as e:
        return {
            "success": False,
            "message": str(e),
            "month": month
        }

    if not bill_list:
        return {
            "success": False,
            "message": "未查询到账单数据",
            "month": month,
            "filter": {"tag_key": tag_key, "tag_value": tag_value} if tag_key else None
        }

    # 统计信息（火山云费用分析API返回格式）
    # CostData 包含 ClassifyItem（产品名）和 Costs（费用明细）
    # 注意：第一条记录通常是"总费用"，其他是各产品明细
    real_total_cost = 0
    cash_total = 0
    voucher_total = 0

    # 按产品分类汇总
    product_summary = {}
    for item in bill_list:
        product_name = item.get('ClassifyItem', '未知产品')
        # Costs 是一个数组，包含每个时间段的费用
        costs = item.get('Costs', [])
        total_amount = float(item.get('TotalAmount', 0))

        # 如果是"总费用"记录，提取真实总额
        if product_name == '总费用':
            real_total_cost = total_amount
            cash_total = total_amount
            continue  # 跳过"总费用"，不加入产品汇总

        if product_name not in product_summary:
            product_summary[product_name] = {
                'cost': 0,
                'count': len(costs),
                'cash': 0,
                'voucher': 0
            }
        product_summary[product_name]['cost'] += total_amount
        product_summary[product_name]['cash'] += total_amount  # 应付金额全部记为现金

    cash_total = real_total_cost  # 费用分析API返回应付金额

    # 如果没有找到"总费用"记录，则手动计算
    if real_total_cost == 0:
        real_total_cost = sum(v['cost'] for v in product_summary.values())
        cash_total = real_total_cost

    # 构建返回结果
    result = {
        "success": True,
        "month": month,
        "filter": {"tag_key": tag_key, "tag_value": tag_value} if tag_key else None,
        "total_records": len(bill_list),
        "summary": {
            "total_cost": round(real_total_cost, 2),
            "payment": {
                "cash": round(cash_total, 2),
                "voucher": round(voucher_total, 2)
            }
        },
        "products": {
            k: {
                "cost": round(v["cost"], 2),
                "count": v["count"],
                "cash": round(v["cash"], 2),
                "voucher": round(v["voucher"], 2)
            }
            for k, v in sorted(product_summary.items(), key=lambda x: x[1]['cost'], reverse=True)
        }
    }

    # 仅在需要时添加明细
    if include_details:
        details = []
        for item in bill_list:
            product = item.get('ClassifyItem', '-')
            costs = item.get('Costs', [])
            total_amount = float(item.get('TotalAmount', 0))

            # 为每个产品添加一条汇总记录
            details.append({
                "product": product,
                "time_periods": len(costs),
                "cost_breakdown": [
                    {
                        "time": c.get('TimeStr', '-'),
                        "amount": round(float(c.get('Amount', 0)), 2)
                    }
                    for c in costs
                ],
                "real_cost": round(total_amount, 2),
                "cash": round(total_amount, 2),
                "voucher": 0
            })
        result["details"] = details

    return result


def format_volcano_report(result: dict) -> str:
    """
    格式化火山云账单报告为可读文本
    :param result: analyze_volcano_bill 返回的结果字典
    :return: 格式化的文本报告
    """
    if not result.get("success"):
        return f"❌ {result.get('message', '查询失败')}"

    lines = []
    lines.append("=" * 100)
    lines.append(f"📅 火山云账单分析 - {result['month']}")
    if result.get("filter"):
        lines.append(f"📌 标签筛选: {result['filter']['tag_key']}={result['filter']['tag_value']}")
    lines.append(f"📊 共 {result['total_records']} 条记录")
    lines.append("=" * 100)

    # 产品汇总
    lines.append("\n📦 产品费用汇总:")
    for product, data in result['products'].items():
        lines.append(f"  {product:20s}: {data['cost']:12,.2f} 元  "
                    f"(现金: {data['cash']:10,.2f}, 优惠券: {data['voucher']:10,.2f})  "
                    f"共 {data['count']} 条")

    # 总费用
    summary = result['summary']
    lines.append("\n" + "=" * 100)
    lines.append(f"💰 总费用: {summary['total_cost']:,.2f} 元")

    # 支付方式
    payment = summary['payment']
    lines.append(f"\n💳 支付方式:")
    lines.append(f"   现金支付:   {payment['cash']:,.2f} 元")
    lines.append(f"   优惠券支付: {payment['voucher']:,.2f} 元")
    lines.append(f"   {'─' * 50}")
    total_payment = payment['cash'] + payment['voucher']
    lines.append(f"   合计验证:   {total_payment:,.2f} 元")

    # 明细（如果有）
    if "details" in result:
        lines.append("\n" + "=" * 100)
        lines.append(f"📋 明细账单 (共 {len(result['details'])} 条):")
        lines.append("=" * 100)
        for item in result['details']:
            lines.append(f"产品:{item['product']:25s} "
                        f"时间段数:{item['time_periods']:3d} "
                        f"实付:{item['real_cost']:12,.2f} 元")
            # 显示各时间段的费用明细
            if item.get('cost_breakdown'):
                for breakdown in item['cost_breakdown']:
                    lines.append(f"    └─ {breakdown['time']:10s}: {breakdown['amount']:12,.2f} 元")

    lines.append("=" * 100)
    return "\n".join(lines)


if __name__ == "__main__":
    # 示例：命令行调用
    import sys

    # 默认参数
    query_month = "2026-08"
    tag_key = DEFAULT_TAG_KEY
    tag_value = DEFAULT_TAG_VALUE
    show_details = False

    # 简单的参数解析
    if len(sys.argv) > 1:
        query_month = sys.argv[1]
    if "--no-tag" in sys.argv:
        tag_key = ""
        tag_value = ""
    if "--details" in sys.argv:
        show_details = True

    # 调用函数
    result = analyze_volcano_bill(query_month, tag_key, tag_value, show_details)

    # 打印报告
    print(format_volcano_report(result))
