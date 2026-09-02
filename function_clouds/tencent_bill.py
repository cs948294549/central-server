from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.billing.v20180709 import billing_client, models
from config.config import Config

# --------------------------配置--------------------------
SECRET_ID = Config.tencent_SECRET_ID
SECRET_KEY = Config.tencent_SECRET_KEY
LIMIT = 100

# 默认标签筛选配置
DEFAULT_TAG_KEY = "24H 网络带宽"
DEFAULT_TAG_VALUE = "24H 网络带宽"
# ---------------------------------------------------------


def get_resource_bill(month: str, tag_key: str = "", tag_value: str = ""):
    """
    获取资源账单
    :param month: 账单月份 yyyy-MM
    :param tag_key: 标签键，留空表示不按标签筛选
    :param tag_value: 标签值，留空表示不按标签筛选
    :return: 账单列表
    """
    cred = credential.Credential(SECRET_ID, SECRET_KEY)
    client = billing_client.BillingClient(cred, "")

    offset = 0
    all_items = []
    while True:
        req = models.DescribeBillResourceSummaryRequest()
        params = {
            "Month": month,
            "Offset": offset,
            "Limit": LIMIT,
            "NeedRecordNum": 1
        }

        # 添加标签筛选
        if tag_key and tag_value:
            params["TagKey"] = tag_key
            params["TagValue"] = tag_value

        req._deserialize(params)
        try:
            resp = client.DescribeBillResourceSummary(req)
        except TencentCloudSDKException as e:
            raise Exception(f"腾讯云API异常：{e}")

        data = resp.ResourceSummarySet
        if not data:
            break
        all_items.extend(data)
        total = resp.Total
        offset += LIMIT
        if offset >= total:
            break
    return all_items


def analyze_tencent_bill(month: str, tag_key: str = "", tag_value: str = "", include_details: bool = False):
    """
    分析腾讯云账单
    :param month: 账单月份 yyyy-MM
    :param tag_key: 标签键，留空表示不按标签筛选
    :param tag_value: 标签值，留空表示不按标签筛选
    :param include_details: 是否包含明细账单列表
    :return: 账单分析结果字典
    """
    # 获取账单数据
    bill_list = get_resource_bill(month, tag_key, tag_value)

    if not bill_list:
        return {
            "success": False,
            "message": "未查询到账单数据",
            "month": month,
            "filter": {"tag_key": tag_key, "tag_value": tag_value} if tag_key else None
        }

    # 统计总计
    real_total_cost = sum(float(item.RealTotalCost) for item in bill_list)
    cash_total = sum(float(item.CashPayAmount) for item in bill_list)
    voucher_total = sum(float(item.VoucherPayAmount) for item in bill_list)
    incentive_total = sum(float(item.IncentivePayAmount) for item in bill_list)
    transfer_total = sum(float(item.TransferPayAmount) for item in bill_list)

    # 按产品分类汇总
    product_summary = {}
    for item in bill_list:
        product_name = item.BusinessCodeName
        cost = float(item.RealTotalCost)
        if product_name not in product_summary:
            product_summary[product_name] = {
                'cost': 0,
                'count': 0,
                'cash': 0,
                'voucher': 0
            }
        product_summary[product_name]['cost'] += cost
        product_summary[product_name]['count'] += 1
        product_summary[product_name]['cash'] += float(item.CashPayAmount)
        product_summary[product_name]['voucher'] += float(item.VoucherPayAmount)

    # 计算共享带宽包和其他产品费用
    bandwidth_cost = product_summary.get('共享带宽包', {}).get('cost', 0)
    other_cost = sum(v['cost'] for k, v in product_summary.items() if k != '共享带宽包')

    # 构建返回结果
    result = {
        "success": True,
        "month": month,
        "filter": {"tag_key": tag_key, "tag_value": tag_value} if tag_key else None,
        "total_records": len(bill_list),
        "summary": {
            "total_cost": round(real_total_cost, 2),
            "bandwidth_cost": round(bandwidth_cost, 2),
            "other_cost": round(other_cost, 2),
            "payment": {
                "cash": round(cash_total, 2),
                "transfer": round(transfer_total, 2),
                "incentive": round(incentive_total, 2),
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
                "product": item.BusinessCodeName,
                "sub_product": item.ProductCodeName,
                "resource_id": item.ResourceId,
                "resource_name": item.ResourceName or "-",
                "region": item.RegionName,
                "tags": [{"key": tag.TagKey, "value": tag.TagValue} for tag in item.Tags] if item.Tags else [],
                "real_cost": round(float(item.RealTotalCost), 2),
                "cash": round(float(item.CashPayAmount), 2),
                "voucher": round(float(item.VoucherPayAmount), 2)
            }
            for item in bill_list
        ]

    return result


def format_tencent_report(result: dict) -> str:
    """
    格式化账单报告为可读文本
    :param result: analyze_tencent_bill 返回的结果字典
    :return: 格式化的文本报告
    """
    if not result.get("success"):
        return f"❌ {result.get('message', '查询失败')}"

    lines = []
    lines.append("=" * 100)
    lines.append(f"📅 腾讯云账单分析 - {result['month']}")
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
    if summary['bandwidth_cost'] > 0:
        lines.append("💰 费用汇总:")
        lines.append(f"   其他产品(CCN+CLB等): {summary['other_cost']:,.2f} 元")
        lines.append(f"   共享带宽包:           {summary['bandwidth_cost']:,.2f} 元")
        lines.append(f"   {'─' * 50}")
        lines.append(f"   总计:                 {summary['total_cost']:,.2f} 元")
    else:
        lines.append(f"💰 总费用: {summary['total_cost']:,.2f} 元")

    # 支付方式
    payment = summary['payment']
    lines.append(f"\n💳 支付方式:")
    lines.append(f"   现金支付:   {payment['cash']:,.2f} 元")
    lines.append(f"   分成金支付: {payment['transfer']:,.2f} 元")
    lines.append(f"   赠送金支付: {payment['incentive']:,.2f} 元")
    lines.append(f"   优惠券支付: {payment['voucher']:,.2f} 元")
    lines.append(f"   {'─' * 50}")
    total_payment = payment['cash'] + payment['transfer'] + payment['incentive'] + payment['voucher']
    lines.append(f"   合计验证:   {total_payment:,.2f} 元")

    # 明细（如果有）
    if "details" in result:
        lines.append("\n" + "=" * 100)
        lines.append(f"📋 明细账单 (共 {len(result['details'])} 条):")
        lines.append("=" * 100)
        for item in result['details']:
            lines.append(f"产品:{item['product']:15s} "
                        f"子产品:{item['sub_product']:20s} "
                        f"资源ID:{item['resource_id']:25s} "
                        f"地域:{item['region']:15s} "
                        f"实付:{item['real_cost']:10,.2f}")

    lines.append("=" * 100)
    return "\n".join(lines)


if __name__ == "__main__":
    # 示例：命令行调用
    import sys

    # 默认参数
    query_month = "2026-09"
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
    result = analyze_tencent_bill(query_month, tag_key, tag_value, show_details)

    # 打印报告
    print(format_tencent_report(result))
