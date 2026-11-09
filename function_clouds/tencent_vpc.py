"""
腾讯云私有网络（VPC）查询模块

数据源说明：
- 地域列表走 CVM 的 DescribeRegions（VPC 模块本身未提供 DescribeRegions 接口）。
- 子网的 Zone 只有 zone_id（如 ap-beijing-7），中文可用区名（如 北京七区）另走 CVM 的
  DescribeZones 按地域查一次并缓存给该地域所有子网。
- 逐地域调用 VPC 的 DescribeVpcs / DescribeSubnets 翻页拉全量，单地域失败（如该地域无
  VPC 产品）只记入 failed_regions，不影响其它地域。
- 网段口径：VPC 主网段 CidrBlock + 辅助网段 AssistantCidrSet + IPv6 网段，
  子网网段来自 DescribeSubnets（含可用 IP 数，便于评估网段使用率）。

API文档:
- DescribeVpcs: https://cloud.tencent.com/document/api/215/15778
- DescribeSubnets: https://cloud.tencent.com/document/api/215/15784
- DescribeZones: https://cloud.tencent.com/document/api/213/15707
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


def get_zones_by_region(region: str):
    """
    获取单个地域下的可用区列表
    :param region: 地域标识，如 ap-beijing
    :return: {可用区ID: 可用区中文名}，如 {"ap-beijing-7": "北京七区"}
    """
    cred = credential.Credential(SECRET_ID, SECRET_KEY)
    client = cvm_client.CvmClient(cred, region)

    req = cvm_models.DescribeZonesRequest()
    try:
        resp = client.DescribeZones(req)
    except TencentCloudSDKException as e:
        raise Exception(f"腾讯云API异常（{region} 可用区）：{e}")

    return {z.Zone: (z.ZoneName or z.Zone) for z in (resp.ZoneSet or [])}


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


def get_subnets_by_region(region: str):
    """
    获取单个地域下的所有子网
    :param region: 地域标识，如 ap-guangzhou
    :return: 子网列表
    """
    cred = credential.Credential(SECRET_ID, SECRET_KEY)
    client = vpc_client.VpcClient(cred, region)

    offset = 0
    all_items = []
    while True:
        req = vpc_models.DescribeSubnetsRequest()
        params = {
            "Offset": str(offset),
            "Limit": str(LIMIT)
        }
        req._deserialize(params)

        try:
            resp = client.DescribeSubnets(req)
        except TencentCloudSDKException as e:
            raise Exception(f"腾讯云API异常（{region} 子网）：{e}")

        data = resp.SubnetSet
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
        "subnets": [],  # 由 analyze 阶段按 vpc_id 回填
        "tags": [{"key": tag.Key, "value": tag.Value} for tag in (vpc.TagSet or [])],
    }


def _normalize_subnet(subnet, region: str, region_name: str, zone_names: dict = None) -> dict:
    """把子网对象统一成内部结构"""
    zone_names = zone_names or {}
    zone_id = subnet.Zone or "-"
    return {
        "region": region,
        "region_name": region_name,
        "vpc_id": subnet.VpcId,
        "subnet_id": subnet.SubnetId,
        "subnet_name": subnet.SubnetName or "-",
        "cidr_block": subnet.CidrBlock or "-",
        "ipv6_cidr_block": subnet.Ipv6CidrBlock or "-",
        "zone_id": zone_id,
        "zone_name": zone_names.get(zone_id) or zone_id,
        "available_ips": subnet.AvailableIpAddressCount or 0,
        "total_ips": subnet.TotalIpAddressCount or 0,
        "is_default": bool(subnet.IsDefault),
        "route_table_id": subnet.RouteTableId or "-",
        "created_time": subnet.CreatedTime or "-",
        "tags": [{"key": tag.Key, "value": tag.Value} for tag in (subnet.TagSet or [])],
    }


def _vpc_cidrs(vpc: dict) -> list:
    """汇总一个 VPC 的全部网段（主网段 + 辅助网段 + IPv6）"""
    cidrs = []
    if vpc["cidr_block"] != "-":
        cidrs.append(vpc["cidr_block"])
    cidrs.extend(vpc["assistant_cidrs"])
    if vpc["ipv6_cidr_block"] != "-":
        cidrs.append(vpc["ipv6_cidr_block"])
    return cidrs


def analyze_tencent_vpc(regions: list = None, include_default: bool = True,
                        include_subnets: bool = True, include_details: bool = False):
    """
    获取账号下所有地域的私有网络 VPC 及网段信息
    :param regions: 指定地域列表，留空表示查询全部可用地域
    :param include_default: 是否包含默认 VPC
    :param include_subnets: 是否同时采集子网网段
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
    all_subnets = []
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

        # 子网按地域一次拉全，再按 vpc_id 归到各 VPC 下
        if include_subnets:
            # 可用区中文名（如 北京七区），子网只带 zone_id，中文名需单独查
            try:
                zone_names = get_zones_by_region(region)
            except Exception as e:
                failed_regions.append({"region": region, "region_name": region_name,
                                       "error": f"可用区查询失败：{str(e)}"})
                zone_names = {}

            try:
                subnet_list = get_subnets_by_region(region)
            except Exception as e:
                failed_regions.append({"region": region, "region_name": region_name,
                                       "error": f"子网查询失败：{str(e)}"})
                subnet_list = []

            subnets = [_normalize_subnet(s, region, region_name, zone_names) for s in subnet_list]
            vpc_index = {v["vpc_id"]: v for v in vpcs}
            for subnet in subnets:
                owner = vpc_index.get(subnet["vpc_id"])
                if owner is None:
                    continue  # 子网所属 VPC 被过滤掉（如默认 VPC）
                owner["subnets"].append(subnet)
                all_subnets.append(subnet)

        all_items.extend(vpcs)
        region_summary[region] = {
            "region_name": region_name,
            "count": len(vpcs),
            "vpcs": [v["vpc_name"] for v in vpcs],
            "cidrs": [c for v in vpcs for c in _vpc_cidrs(v)],
            "subnet_count": sum(len(v["subnets"]) for v in vpcs),
        }

    result = {
        "success": True,
        "regions_scanned": len(scanned),
        "regions_with_vpc": len(region_summary),
        "failed_regions": failed_regions,
        "total_vpcs": len(all_items),
        "default_vpcs": sum(1 for v in all_items if v["is_default"]),
        "total_subnets": len(all_subnets),
        "total_cidrs": sum(len(_vpc_cidrs(v)) for v in all_items),
        "available_ips": sum(s["available_ips"] for s in all_subnets),
        "total_ips": sum(s["total_ips"] for s in all_subnets),
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
    lines.append("🌐 腾讯云 VPC 网段统计")
    lines.append(f"📊 已查询 {result['regions_scanned']} 个地域，"
                 f"{result['regions_with_vpc']} 个地域有 VPC，"
                 f"共 {result['total_vpcs']} 个 VPC（其中默认 VPC {result['default_vpcs']} 个）、"
                 f"{result['total_cidrs']} 个网段、{result['total_subnets']} 个子网")
    if result["total_ips"]:
        used = result["total_ips"] - result["available_ips"]
        lines.append(f"📈 子网 IP 容量 {result['total_ips']} 个，已用 {used} 个，"
                     f"可用 {result['available_ips']} 个"
                     f"（使用率 {used / result['total_ips'] * 100:.1f}%）")
    lines.append("=" * 100)

    lines.append("\n🗂  地域分布:")
    for region, data in sorted(result["summary"].items(),
                               key=lambda x: x[1]["count"], reverse=True):
        lines.append(f"  {region:18s} {data['region_name']:20s} "
                     f"{data['count']:3d} 个 VPC  {data['subnet_count']:3d} 个子网")
        lines.append(f"    网段: {', '.join(data['cidrs']) or '-'}")

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
            lines.append(f"  {item['vpc_name']:24s} {item['vpc_id']:22s} "
                         f"{item['cidr_block']:20s}{flag}")
            if item["assistant_cidrs"]:
                lines.append(f"    辅助网段: {', '.join(item['assistant_cidrs'])}")
            if item["ipv6_cidr_block"] != "-":
                lines.append(f"    IPv6 网段: {item['ipv6_cidr_block']}")
            for subnet in sorted(item["subnets"], key=lambda x: x["cidr_block"]):
                lines.append(f"    └─ {subnet['cidr_block']:20s} {subnet['subnet_name']:24s} "
                             f"{subnet['zone_name']:10s} {subnet['zone_id']:16s} "
                             f"可用 {subnet['available_ips']:5d}/{subnet['total_ips']:5d}")

    lines.append("=" * 100)
    return "\n".join(lines)


if __name__ == "__main__":
    # 示例：命令行调用
    import sys

    # 默认参数
    query_regions = None
    show_details = True
    show_default = True
    show_subnets = True

    # 简单的参数解析
    for arg in sys.argv[1:]:
        if arg.startswith("--region="):
            query_regions = [r.strip() for r in arg.split("=", 1)[1].split(",") if r.strip()]
        elif arg == "--no-details":
            show_details = False
        elif arg == "--no-default":
            show_default = False
        elif arg == "--no-subnet":
            show_subnets = False

    # 调用函数
    result = analyze_tencent_vpc(query_regions, show_default, show_subnets, show_details)

    # 打印报告
    print(format_tencent_vpc_report(result))
