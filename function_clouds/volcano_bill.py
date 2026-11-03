"""
火山云（字节跳动）账单查询模块

数据源说明：
- 默认走「账单总览」ListBillOverviewByProd，与官网账单详情页口径一致（按产品 + 计费模式逐行返回）。
- 指定标签筛选时，账单总览接口不支持标签，退化为「账单明细」ListBillDetail 按标签过滤后按产品聚合。

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

# 默认标签筛选配置（留空表示不按标签筛选）
DEFAULT_TAG_KEY = ""
DEFAULT_TAG_VALUE = ""

# 计费模式编码 -> 名称
BILLING_MODE_MAP = {
    "1": "包年包月",
    "2": "按量计费",
}
# ---------------------------------------------------------


def _f(value) -> float:
    """字符串金额转 float，空值/异常返回 0"""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _get_api():
    """初始化并返回火山云账单 API 实例"""
    configuration = volcenginesdkcore.Configuration()
    configuration.ak = ACCESS_KEY_ID
    configuration.sk = SECRET_ACCESS_KEY
    configuration.region = "cn-beijing"
    volcenginesdkcore.Configuration.set_default(configuration)
    return volcenginesdkbilling.BILLINGApi()


def _normalize(product, billing_mode, bill_category, payable, paid, coupon,
               unpaid, preferential, original, **extra):
    """把账单行统一成内部结构"""
    row = {
        "product": product or "未知",
        "billing_mode": BILLING_MODE_MAP.get(str(billing_mode), billing_mode or "-"),
        "bill_category": bill_category or "-",
        "payable": round(_f(payable), 2),          # 应付金额
        "paid": round(_f(paid), 2),                # 已支付（现金）
        "coupon": round(_f(coupon), 2),            # 优惠券抵扣
        "unpaid": round(_f(unpaid), 2),            # 未支付
        "preferential": round(_f(preferential), 2),  # 优惠金额
        "original": round(_f(original), 2),        # 原价
    }
    row.update(extra)
    return row


def get_bill_overview(month: str):
    """
    获取账单总览（官网账单详情页口径）
    :param month: 账单月份 yyyy-MM
    :return: 账单行列表，按「产品 + 计费模式」逐行
    """
    api_instance = _get_api()
    all_items = []
    offset = 0

    while True:
        request = volcenginesdkbilling.ListBillOverviewByProdRequest(
            bill_period=month,
            ignore_zero=0,       # 保留 0 元行，保证产品条数与官网一致
            limit=LIMIT,
            offset=offset,
            need_record_num=1
        )

        try:
            response = api_instance.list_bill_overview_by_prod(request)
        except ApiException as e:
            raise Exception(f"火山云API异常：{e}")
        except Exception as e:
            raise Exception(f"火山云账单总览查询失败：{str(e)}")

        data = response.list if response and response.list else []
        if not data:
            break

        for item in data:
            all_items.append(_normalize(
                product=item.product_zh or item.product,
                billing_mode=item.billing_mode,
                bill_category=item.bill_category_parent,
                payable=item.payable_amount,
                paid=item.paid_amount,
                coupon=item.coupon_amount,
                unpaid=item.unpaid_amount,
                preferential=item.preferential_bill_amount,
                original=item.original_bill_amount,
            ))

        offset += LIMIT
        if offset >= (response.total or 0):
            break

    return all_items


def get_bill_by_tag(month: str, tag_key: str, tag_value: str):
    """
    按标签查询账单明细并按产品聚合（账单总览接口不支持标签筛选）
    :param month: 账单月份 yyyy-MM
    :param tag_key: 标签键
    :param tag_value: 标签值
    :return: 聚合后的账单行列表，结构同 get_bill_overview
    """
    api_instance = _get_api()
    aggregated = {}
    offset = 0

    while True:
        request = volcenginesdkbilling.ListBillDetailRequest(
            bill_period=month,
            tag_kv=[volcenginesdkbilling.TagKVForListBillDetailInput(
                key=tag_key, value=tag_value)],
            tag_kv_filter_mode=1,
            ignore_zero=0,
            limit=LIMIT,
            offset=offset,
            need_record_num=1
        )

        try:
            response = api_instance.list_bill_detail(request)
        except ApiException as e:
            raise Exception(f"火山云API异常：{e}")
        except Exception as e:
            raise Exception(f"火山云标签账单查询失败：{str(e)}")

        data = response.list if response and response.list else []
        if not data:
            break

        for item in data:
            product = item.product_zh or item.product or "未知"
            mode = str(item.billing_mode or "-")
            key = (product, mode)
            agg = aggregated.setdefault(key, {
                "product": product,
                "billing_mode": BILLING_MODE_MAP.get(mode, mode),
                "bill_category": item.bill_category or "-",
                "payable": 0.0,
                "paid": 0.0,
                "coupon": 0.0,
                "unpaid": 0.0,
                "preferential": 0.0,
                "original": 0.0,
                "detail_count": 0,
            })
            agg["payable"] += _f(item.payable_amount)
            agg["paid"] += _f(item.paid_amount)
            agg["coupon"] += _f(item.coupon_amount)
            agg["preferential"] += _f(item.preferential_bill_amount)
            agg["original"] += _f(item.original_bill_amount)
            agg["detail_count"] += 1

        offset += LIMIT
        if offset >= (response.total or 0):
            break

    rows = []
    for agg in aggregated.values():
        agg["payable"] = round(agg["payable"], 2)
        agg["paid"] = round(agg["paid"], 2)
        agg["coupon"] = round(agg["coupon"], 2)
        agg["preferential"] = round(agg["preferential"], 2)
        agg["original"] = round(agg["original"], 2)
        agg["unpaid"] = round(max(agg["payable"] - agg["paid"] - agg["coupon"], 0), 2)
        rows.append(agg)
    return rows


def get_resource_bill(month: str, tag_key: str = "", tag_value: str = ""):
    """
    获取火山云资源账单
    :param month: 账单月份 yyyy-MM
    :param tag_key: 标签键，留空表示不按标签筛选
    :param tag_value: 标签值，留空表示不按标签筛选
    :return: 账单行列表
    """
    if tag_key and tag_value:
        return get_bill_by_tag(month, tag_key, tag_value)
    return get_bill_overview(month)


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
    except Exception as e:
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

    payable_total = sum(item["payable"] for item in bill_list)
    paid_total = sum(item["paid"] for item in bill_list)
    coupon_total = sum(item["coupon"] for item in bill_list)
    unpaid_total = sum(item["unpaid"] for item in bill_list)
    preferential_total = sum(item["preferential"] for item in bill_list)

    # 按产品汇总
    product_summary = {}
    for item in bill_list:
        name = item["product"]
        if name not in product_summary:
            product_summary[name] = {
                "cost": 0.0,
                "cash": 0.0,
                "voucher": 0.0,
                "unpaid": 0.0,
                "count": 0
            }
        summary = product_summary[name]
        summary["cost"] += item["payable"]
        summary["cash"] += item["paid"]
        summary["voucher"] += item["coupon"]
        summary["unpaid"] += item["unpaid"]
        summary["count"] += 1

    result = {
        "success": True,
        "month": month,
        "filter": {"tag_key": tag_key, "tag_value": tag_value} if tag_key else None,
        "total_records": len(bill_list),
        "summary": {
            "payable_amount": round(payable_total, 2),      # 应付金额
            "cash_payment": round(paid_total, 2),           # 已支付现金
            "voucher_payment": round(coupon_total, 2),      # 优惠券抵扣
            "unpaid_amount": round(unpaid_total, 2),        # 未支付
            "preferential_amount": round(preferential_total, 2),  # 优惠金额
            "total_cost": round(payable_total, 2),
        },
        "products": {
            k: {
                "cost": round(v["cost"], 2),
                "count": v["count"],
                "cash": round(v["cash"], 2),
                "voucher": round(v["voucher"], 2),
                "unpaid": round(v["unpaid"], 2),
            }
            for k, v in sorted(product_summary.items(), key=lambda x: x[1]["cost"], reverse=True)
        }
    }

    if include_details:
        result["details"] = [
            {
                "product": item["product"],
                "billing_mode": item["billing_mode"],
                "bill_category": item["bill_category"],
                "payable": item["payable"],
                "paid": item["paid"],
                "coupon": item["coupon"],
                "unpaid": item["unpaid"],
                "preferential": item["preferential"],
                "detail_count": item.get("detail_count", 1),
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
    for product, data in result["products"].items():
        lines.append(f"  {product:20s}: {data['cost']:12,.2f} 元  "
                     f"(已付: {data['cash']:10,.2f}, 优惠券: {data['voucher']:10,.2f}, "
                     f"未付: {data['unpaid']:10,.2f})  共 {data['count']} 条")

    # 费用汇总
    summary = result["summary"]
    lines.append("\n" + "=" * 100)
    lines.append("💰 费用汇总:")
    lines.append(f"   应付金额:     {summary['payable_amount']:12,.2f} 元")
    lines.append(f"   已支付:       {summary['cash_payment']:12,.2f} 元")
    lines.append(f"   优惠券抵扣:   {summary['voucher_payment']:12,.2f} 元")
    lines.append(f"   优惠金额:     {summary['preferential_amount']:12,.2f} 元")
    lines.append(f"   未支付:       {summary['unpaid_amount']:12,.2f} 元")

    # 明细（如果有）
    if "details" in result:
        lines.append("\n" + "=" * 100)
        lines.append(f"📋 明细账单 (共 {len(result['details'])} 条):")
        lines.append("=" * 100)
        for item in result["details"]:
            lines.append(f"  {item['product']:22s} | {item['billing_mode']:6s} | "
                         f"{item['bill_category']:8s} | "
                         f"应付 {item['payable']:12,.2f} | 已付 {item['paid']:10,.2f} | "
                         f"券 {item['coupon']:10,.2f} | 未付 {item['unpaid']:10,.2f}")

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
