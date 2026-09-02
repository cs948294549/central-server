from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.billing.v20180709 import billing_client, models
from config.config import Config

# --------------------------配置--------------------------
SECRET_ID = Config.tencent_SECRET_ID
SECRET_KEY = Config.tencent_SECRET_KEY
QUERY_MONTH = "2026-08"  # 查询月份 yyyy-MM
LIMIT = 100

# 标签筛选配置（留空表示不筛选）
# 示例: 筛选 "24H 网络带宽" 标签
FILTER_TAG_KEY = "24H 网络带宽"      # 标签键
FILTER_TAG_VALUE = "24H 网络带宽"    # 标签值

# 其他标签示例：
# FILTER_TAG_KEY = "env"
# FILTER_TAG_VALUE = "production"
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
            print(f"API异常：{e}")
            raise

        data = resp.ResourceSummarySet
        if not data:
            break
        all_items.extend(data)
        total = resp.Total
        offset += LIMIT
        if offset >= total:
            break
    return all_items


if __name__ == "__main__":
    # 根据配置获取账单
    if FILTER_TAG_KEY and FILTER_TAG_VALUE:
        print(f"📌 按标签筛选: {FILTER_TAG_KEY}={FILTER_TAG_VALUE}\n")
        bill_list = get_resource_bill(QUERY_MONTH, FILTER_TAG_KEY, FILTER_TAG_VALUE)
    else:
        print("📋 获取全部账单（未筛选标签）\n")
        bill_list = get_resource_bill(QUERY_MONTH)

    print(f"一共 {len(bill_list)} 条资源账单记录\n")

    # 统计信息 - 使用 RealTotalCost
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

    # 打印产品汇总
    print("=" * 100)
    print("📊 产品费用汇总")
    print("=" * 100)

    # 特殊处理：共享带宽包单独列出
    bandwidth_cost = product_summary.get('共享带宽包', {}).get('cost', 0)
    other_cost = sum(v['cost'] for k, v in product_summary.items() if k != '共享带宽包')

    for product, data in sorted(product_summary.items(), key=lambda x: x[1]['cost'], reverse=True):
        print(f"{product:15s}: {data['cost']:12,.2f} 元  "
              f"(现金: {data['cash']:10,.2f}, 优惠券: {data['voucher']:10,.2f})  "
              f"共 {data['count']} 条")

    print("=" * 100)
    if bandwidth_cost > 0:
        print(f"\n💰 腾讯云费用汇总:")
        print(f"   其他产品(CCN+CLB等): {other_cost:,.2f} 元")
        print(f"   共享带宽包:           {bandwidth_cost:,.2f} 元")
        print(f"   {'─' * 50}")
        print(f"   总计:                 {real_total_cost:,.2f} 元")
    else:
        print(f"\n💰 总费用: {real_total_cost:,.2f} 元")

    print(f"\n💳 支付方式明细:")
    print(f"   现金支付:   {cash_total:,.2f} 元")
    print(f"   分成金支付: {transfer_total:,.2f} 元")
    print(f"   赠送金支付: {incentive_total:,.2f} 元")
    print(f"   优惠券支付: {voucher_total:,.2f} 元")
    print(f"   {'─' * 50}")
    print(f"   合计验证:   {cash_total + transfer_total + incentive_total + voucher_total:,.2f} 元")
    print("\n" + "=" * 100)
    print("📋 详细账单列表")
    print("=" * 100)

    for item in bill_list:
        # 格式化标签
        tags_str = ", ".join([f"{tag.TagKey}={tag.TagValue}" for tag in item.Tags]) if item.Tags else "-"

        print(f"产品:{item.BusinessCodeName:15s} "
              f"子产品:{item.ProductCodeName:20s} "
              f"资源ID:{item.ResourceId:25s} "
              f"地域:{item.RegionName:15s} "
              f"实付:{float(item.RealTotalCost):10,.2f}")
