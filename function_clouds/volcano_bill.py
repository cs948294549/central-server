"""
火山云（字节跳动）账单查询模块
API文档: https://www.volcengine.com/docs/6261/104955
"""
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
    获取火山云资源账单
    :param month: 账单月份 yyyy-MM
    :param tag_key: 标签键，留空表示不按标签筛选
    :param tag_value: 标签值，留空表示不按标签筛选
    :return: 账单列表
    """
    # TODO: 实现火山云 API 调用
    # 需要安装火山云 SDK: pip install volcengine
    raise NotImplementedError("火山云账单查询功能待实现，需要 AK/SK 认证")


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

    # 统计信息
    real_total_cost = sum(float(item.get('RealCost', 0)) for item in bill_list)
    cash_total = sum(float(item.get('CashAmount', 0)) for item in bill_list)
    voucher_total = sum(float(item.get('VoucherAmount', 0)) for item in bill_list)

    # 按产品分类汇总
    product_summary = {}
    for item in bill_list:
        product_name = item.get('ProductName', '未知产品')
        cost = float(item.get('RealCost', 0))
        if product_name not in product_summary:
            product_summary[product_name] = {
                'cost': 0,
                'count': 0,
                'cash': 0,
                'voucher': 0
            }
        product_summary[product_name]['cost'] += cost
        product_summary[product_name]['count'] += 1
        product_summary[product_name]['cash'] += float(item.get('CashAmount', 0))
        product_summary[product_name]['voucher'] += float(item.get('VoucherAmount', 0))

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
        result["details"] = [
            {
                "product": item.get('ProductName', '-'),
                "resource_id": item.get('ResourceID', '-'),
                "region": item.get('Region', '-'),
                "real_cost": round(float(item.get('RealCost', 0)), 2),
                "cash": round(float(item.get('CashAmount', 0)), 2),
                "voucher": round(float(item.get('VoucherAmount', 0)), 2)
            }
            for item in bill_list
        ]

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
            lines.append(f"产品:{item['product']:20s} "
                        f"资源ID:{item['resource_id']:30s} "
                        f"地域:{item['region']:15s} "
                        f"实付:{item['real_cost']:10,.2f}")

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
