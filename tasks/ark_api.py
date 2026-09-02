"""
火山云（字节跳动）账单查询脚本
API文档: https://www.volcengine.com/docs/6261/104955
"""
from config.config import Config

# --------------------------配置--------------------------
ACCESS_KEY_ID = Config.volcano_ACCESS_KEY_ID  # 火山云 AccessKeyId
SECRET_ACCESS_KEY = Config.volcano_SECRET_ACCESS_KEY  # 火山云 SecretAccessKey
QUERY_MONTH = "2026-08"  # 查询月份 yyyy-MM
LIMIT = 100  # 每页查询数量

# 标签筛选配置（留空表示不筛选）
FILTER_TAG_KEY = ""      # 标签键
FILTER_TAG_VALUE = ""    # 标签值
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
    pass


if __name__ == "__main__":
    # 根据配置获取账单
    if FILTER_TAG_KEY and FILTER_TAG_VALUE:
        print(f"📌 按标签筛选: {FILTER_TAG_KEY}={FILTER_TAG_VALUE}\n")
        bill_list = get_resource_bill(QUERY_MONTH, FILTER_TAG_KEY, FILTER_TAG_VALUE)
    else:
        print("📋 获取全部账单（未筛选标签）\n")
        bill_list = get_resource_bill(QUERY_MONTH)

    if not bill_list:
        print("⚠️  未查询到账单数据")
        exit(0)

    print(f"一共 {len(bill_list)} 条资源账单记录\n")

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

    # 打印产品汇总
    print("=" * 100)
    print("📊 产品费用汇总")
    print("=" * 100)

    for product, data in sorted(product_summary.items(), key=lambda x: x[1]['cost'], reverse=True):
        print(f"{product:20s}: {data['cost']:12,.2f} 元  "
              f"(现金: {data['cash']:10,.2f}, 优惠券: {data['voucher']:10,.2f})  "
              f"共 {data['count']} 条")

    print("=" * 100)
    print(f"\n💰 火山云总费用: {real_total_cost:,.2f} 元")
    print(f"\n💳 支付方式明细:")
    print(f"   现金支付:   {cash_total:,.2f} 元")
    print(f"   优惠券支付: {voucher_total:,.2f} 元")
    print(f"   {'─' * 50}")
    print(f"   合计验证:   {cash_total + voucher_total:,.2f} 元")

    print("\n" + "=" * 100)
    print("📋 详细账单列表")
    print("=" * 100)

    for item in bill_list[:20]:  # 只显示前20条
        print(f"产品:{item.get('ProductName', '-'):20s} "
              f"资源ID:{item.get('ResourceID', '-'):30s} "
              f"地域:{item.get('Region', '-'):15s} "
              f"实付:{float(item.get('RealCost', 0)):10,.2f}")

