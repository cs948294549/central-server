"""
腾讯云私有网络（VPC）查询模块

数据源说明：
- 地域列表走 CVM 的 DescribeRegions（VPC 模块本身未提供 DescribeRegions 接口）。
- 逐地域调用 VPC 的 DescribeVpcs 翻页拉全量，单地域失败（如该地域无 VPC 产品）只记入
  failed_regions，不影响其它地域。

API文档:
- DescribeVpcs: https://cloud.tencent.com/document/api/215/15778
"""
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.cvm.v20170312 import cvm_client, models as cvm_models
from tencentcloud.vpc.v20170312 import vpc_client, models as vpc_models
from config.config import Config

# --------------------------配置--------------------------
SECRET_ID = Config.tencent_SECRET_ID
SECRET_KEY = Config.tencent_SECRET_KEY
LIMIT = 100  # 每页查询数量，DescribeVpcs 单次上限 100

# 地域可用状态
REGION_STATE_AVAILABLE = "AVAILABLE"
# ---------------------------------------------------------


def get_regions():
    """
    获取账号下的地域列表
    :return: [{"region": "ap-guangzhou", "region_name": "华南地区(广州)", "state": "AVAILABLE"}, ...]
    """
    cred = credential.Credential(SECRET_ID, SECRET_KEY)
    client = cvm_client.CvmClient(cred, "")

    req = cvm_models.DescribeRegionsRequest()
    try:
        resp = client.DescribeRegions(req)
    except TencentCloudSDKException as e:
        raise Exception(f"腾讯云API异常（获取地域列表）：{e}")

    return [
        {
            "region": item.Region,
            "region_name": item.RegionName,
            "state": item.RegionState,
        }
        for item in (resp.RegionSet or [])
    ]


def get_vpcs_by_region(region: str):
    """
    获取单个地域下的所有 VPC
    :param region: 地域标识，如 ap-guangzhou
    :return: VPC 列表
    """
    cred = credential.Credential(SECRET_ID, SECRET_KEY)
    client = vpc_client.VpcClient(cred, region)

    offset = 0
    all_items = []
    while True:
        req = vpc_models.DescribeVpcsRequest()
        params = {
            "Offset": str(offset),
            "Limit": str(LIMIT)
        }
        req._deserialize(params)

        try:
            resp = client.DescribeVpcs(req)
        except TencentCloudSDKException as e:
            raise Exception(f"腾讯云API异常（{region}）：{e}")

        data = resp.VpcSet
        if not data:
            break
        all_items.extend(data)
        offset += LIMIT
        if offset >= (resp.TotalCount or 0):
            break
    return all_items


def _normalize_vpc(vpc, region: str, region_name: str) -> dict:
    """把 VPC 对象统一成内部结构"""
    return {
        "region": region,
        "region_name": region_name,
        "vpc_id": vpc.VpcId,
        "vpc_name": vpc.VpcName or "-",
        "cidr_block": vpc.CidrBlock or "-",
        "ipv6_cidr_block": vpc.Ipv6CidrBlock or "-",
        "is_default": bool(vpc.IsDefault),
        "created_time": vpc.CreatedTime or "-",
        "assistant_cidrs": [item.CidrBlock for item in (vpc.AssistantCidrSet or [])],
        "dns_servers": vpc.DnsServerSet or [],
        "domain_name": vpc.DomainName or "-",
        "tags": [{"key": tag.Key, "value": tag.Value} for tag in (vpc.TagSet or [])],
    }


def analyze_tencent_vpc(regions: list = None, include_default: bool = True, include_details: bool = False):
    """
    获取账号下所有地域的私有网络 VPC
    :param regions: 指定地域列表，留空表示查询全部可用地域
    :param include_default: 是否包含默认 VPC
    :param include_details: 是否包含明细 VPC 列表
    :return: VPC 查询结果字典
    """
    try:
        region_list = get_regions()
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

    # 只保留可用地域，并按需要过滤
    available = [r for r in region_list if r["state"] == REGION_STATE_AVAILABLE]
    if regions:
        wanted = set(regions)
        scanned = [r for r in available if r["region"] in wanted]
    else:
        scanned = available

    if not scanned:
        return {
            "success": False,
            "message": "未找到可查询的地域",
            "regions": regions
        }

    all_items = []
    failed_regions = []
    region_summary = {}

    for item in scanned:
        region = item["region"]
        region_name = item["region_name"]
        try:
            vpc_list = get_vpcs_by_region(region)
        except Exception as e:
            failed_regions.append({"region": region, "region_name": region_name, "error": str(e)})
            continue

        vpcs = [_normalize_vpc(vpc, region, region_name) for vpc in vpc_list]
        if not include_default:
            vpcs = [v for v in vpcs if not v["is_default"]]
        if not vpcs:
            continue

        all_items.extend(vpcs)
        region_summary[region] = {
            "region_name": region_name,
            "count": len(vpcs),
            "vpcs": [v["vpc_name"] for v in vpcs],
        }

    result = {
        "success": True,
        "regions_scanned": len(scanned),
        "regions_with_vpc": len(region_summary),
        "failed_regions": failed_regions,
        "total_vpcs": len(all_items),
        "default_vpcs": sum(1 for v in all_items if v["is_default"]),
        "summary": region_summary,
    }

    if include_details:
        result["vpcs"] = all_items

    return result


def format_tencent_vpc_report(result: dict) -> str:
    """
    格式化 VPC 报告为可读文本
    :param result: analyze_tencent_vpc 返回的结果字典
    :return: 格式化的文本报告
    """
    if not result.get("success"):
        return f"❌ {result.get('message', '查询失败')}"

    lines = []
    lines.append("=" * 100)
    lines.append("🌐 腾讯云 VPC 资产统计")
    lines.append(f"📊 已查询 {result['regions_scanned']} 个地域，"
                 f"{result['regions_with_vpc']} 个地域有 VPC，"
                 f"共 {result['total_vpcs']} 个 VPC（其中默认 VPC {result['default_vpcs']} 个）")
    lines.append("=" * 100)

    lines.append("\n🗂  地域分布:")
    for region, data in sorted(result["summary"].items(),
                               key=lambda x: x[1]["count"], reverse=True):
        lines.append(f"  {region:18s} {data['region_name']:20s} {data['count']:3d} 个")

    if result.get("failed_regions"):
        lines.append("\n⚠️  查询失败的地域:")
        for item in result["failed_regions"]:
            lines.append(f"  {item['region']:18s} {item['region_name']:20s} {item['error']}")

    if "vpcs" in result:
        lines.append("\n" + "=" * 100)
        lines.append(f"📋 VPC 明细 (共 {len(result['vpcs'])} 个):")
        lines.append("=" * 100)
        current_region = None
        for item in sorted(result["vpcs"], key=lambda x: (x["region"], x["vpc_name"])):
            if item["region"] != current_region:
                current_region = item["region"]
                lines.append(f"\n[{current_region}] {item['region_name']}")
            flag = " (默认)" if item["is_default"] else ""
            cidr = item["cidr_block"]
            if item["ipv6_cidr_block"] != "-":
                cidr = f"{cidr}, {item['ipv6_cidr_block']}"
            lines.append(f"  {item['vpc_name']:28s} {item['vpc_id']:22s} {cidr:32s}{flag}")

    lines.append("=" * 100)
    return "\n".join(lines)


if __name__ == "__main__":
    # 示例：命令行调用
    import sys

    # 默认参数
    query_regions = None
    show_details = True
    show_default = True

    # 简单的参数解析
    for arg in sys.argv[1:]:
        if arg.startswith("--region="):
            query_regions = [r.strip() for r in arg.split("=", 1)[1].split(",") if r.strip()]
        elif arg == "--no-details":
            show_details = False
        elif arg == "--no-default":
            show_default = False

    # 调用函数
    result = analyze_tencent_vpc(query_regions, show_default, show_details)

    # 打印报告
    print(format_tencent_vpc_report(result))
