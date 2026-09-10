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
    :return: 账单列表（包含应付金额和现金支付两种维度）
    """
    # 配置火山云客户端
    configuration = volcenginesdkcore.Configuration()
    configuration.ak = ACCESS_KEY_ID
    configuration.sk = SECRET_ACCESS_KEY
    configuration.region = "cn-beijing"
    volcenginesdkcore.Configuration.set_default(configuration)

    # 创建API实例
    api_instance = volcenginesdkbilling.BILLINGApi()

    # 查询两种费用类型
    result = {
        'payable': [],  # 应付金额
        'cash': []      # 现金支付
    }

    for cost_type, key in [(2, 'payable'), (3, 'cash')]:
        offset = 0
        all_items = []

        while True:
            # 构建请求 - 使用费用分析API
            # CostType: 2-应付金额, 3-现金支付
            request = volcenginesdkbilling.ListCostAnalysisOpenApiRequest(
                begin_time_str=f"{month}-01",
                end_time_str=f"{month}-01",
                time_granularity=0,
                cost_type=cost_type,
                classify_dimension=3,  # 3:按产品分类
                limit=LIMIT,
                offset=offset
            )

            # 添加标签筛选
            if tag_key and tag_value:
                request.classify_dimension = 10
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
                        'TotalAmount': total_amount,
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

        result[key] = all_items

    return result


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
        bill_data = get_resource_bill(month, tag_key, tag_value)
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "month": month
        }

    payable_list = bill_data.get('payable', [])
    cash_list = bill_data.get('cash', [])

    if not payable_list and not cash_list:
        return {
            "success": False,
            "message": "未查询到账单数据",
            "month": month,
            "filter": {"tag_key": tag_key, "tag_value": tag_value} if tag_key else None
        }

    # 提取总费用（应付金额和现金支付）
    payable_total = 0
    cash_total = 0

    # 从应付金额列表中提取"总费用"
    for item in payable_list:
        if item.get('ClassifyItem') == '总费用':
            payable_total = float(item.get('TotalAmount', 0))
            break

    # 从现金支付列表中提取"总费用"
    for item in cash_list:
        if item.get('ClassifyItem') == '总费用':
            cash_total = float(item.get('TotalAmount', 0))
            break

    # 如果现金支付为0，说明使用了其他支付方式，设置为应付金额
    if cash_total == 0:
        cash_total = payable_total

    # 计算退款抵扣 = 应付金额 - 现金支付
    # 正数表示有退款，负数表示需要额外支付
    refund_amount = payable_total - cash_total

    # 按产品分类汇总（使用应付金额数据）
    product_summary = {}
    for item in payable_list:
        product_name = item.get('ClassifyItem', '未知产品')

        # 跳过"总费用"
        if product_name == '总费用':
            continue

        costs = item.get('Costs', [])
        total_amount = float(item.get('TotalAmount', 0))

        if product_name not in product_summary:
            product_summary[product_name] = {
                'cost': 0,
                'count': len(costs),
                'cash': 0,
                'voucher': 0
            }
        product_summary[product_name]['cost'] += total_amount
        product_summary[product_name]['cash'] += total_amount

    # 如果没有找到"总费用"记录，则手动计算
    if payable_total == 0:
        payable_total = sum(v['cost'] for v in product_summary.values())
    if cash_total == 0:
        cash_total = payable_total

    # 构建返回结果
    result = {
        "success": True,
        "month": month,
        "filter": {"tag_key": tag_key, "tag_value": tag_value} if tag_key else None,
        "total_records": len(payable_list),
        "summary": {
            "payable_amount": round(payable_total, 2),  # 应付金额
            "cash_payment": round(cash_total, 2),        # 现金支付
            "refund_deduction": round(refund_amount, 2), # 退款抵扣
            "total_cost": round(payable_total, 2),
            "payment": {
                "cash": round(cash_total, 2),
                "refund": round(refund_amount, 2),
                "voucher": 0
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
        for item in payable_list:
            product = item.get('ClassifyItem', '-')

            # 跳过"总费用"
            if product == '总费用':
                continue

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
    lines.append(f"💰 费用汇总:")
    lines.append(f"   应付金额:         {summary['payable_amount']:,.2f} 元")
    lines.append(f"   现金支付:         {summary['cash_payment']:,.2f} 元")
    if summary['refund_deduction'] != 0:
        lines.append(f"   信控额度退款抵扣: {summary['refund_deduction']:,.2f} 元")

    # 支付方式
    payment = summary['payment']
    lines.append(f"\n💳 支付明细:")
    lines.append(f"   现金支付:   {payment['cash']:,.2f} 元")
    if payment['refund'] != 0:
        lines.append(f"   退款抵扣:   {payment['refund']:,.2f} 元")
    lines.append(f"   优惠券支付: {payment['voucher']:,.2f} 元")
    lines.append(f"   {'─' * 50}")
    lines.append(f"   应付总额:   {summary['payable_amount']:,.2f} 元")

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
    query_month = "2026-06"
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
