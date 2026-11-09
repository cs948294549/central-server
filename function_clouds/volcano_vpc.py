"""
火山云（字节跳动）私有网络（VPC）网段采集模块

数据源说明：
- 地域列表走 ECS 的 DescribeRegions（VPC 模块本身未提供 DescribeRegions 接口），
  SDK 返回的 RegionForDescribeRegionsOutput 只有 region_id，中文名由本地 REGION_NAME_MAP 补齐。
- 逐地域调用 VPC 的 DescribeVpcs / DescribeSubnets 翻页拉全量，单地域失败只记入
  failed_regions，不影响其它地域。
- 网段口径：VPC 主网段 cidr_block + 辅助网段 secondary_cidr_blocks + IPv6 网段，
  子网网段来自 DescribeSubnets（含可用 IP 数，便于评估网段使用率）。

API文档:
- DescribeVpcs: https://www.volcengine.com/docs/6401/70495
- DescribeSubnets: https://www.volcengine.com/docs/6401/70519
"""
import volcenginesdkcore
import volcenginesdkecs
import volcenginesdkvpc
from volcenginesdkcore.rest import ApiException
from config.config import Config

# --------------------------配置--------------------------
ACCESS_KEY_ID = Config.volcano_ACCESS_KEY_ID  # 火山云 AccessKeyId
SECRET_ACCESS_KEY = Config.volcano_SECRET_ACCESS_KEY  # 火山云 SecretAccessKey
PAGE_SIZE = 100  # 每页查询数量，DescribeVpcs/DescribeSubnets 单次上限 100
DEFAULT_REGION = "cn-beijing"  # 查询地域列表时使用的地域

# 地域中文名（火山云 DescribeRegions 不返回中文名，本地维护）
REGION_NAME_MAP = {
    "cn-beijing": "华北2(北京)",
    "cn-shanghai": "华东2(上海)",
    "cn-guangzhou": "华南1(广州)",
    "cn-hongkong": "中国香港",
    "ap-southeast-1": "亚太东南(柔佛)",
    "ap-southeast-3": "亚太东南(雅加达)",
}
# ---------------------------------------------------------


def _make_api(region: str, api_cls):
    """按地域创建 API 实例（每个地域独立 ApiClient，避免全局 region 串用）"""
    configuration = volcenginesdkcore.Configuration()
    configuration.ak = ACCESS_KEY_ID
    configuration.sk = SECRET_ACCESS_KEY
    configuration.region = region
    return api_cls(volcenginesdkcore.ApiClient(configuration))


def get_regions():
    """
    获取账号下的地域列表
    :return: [{"region": "cn-beijing", "region_name": "华北2(北京)"}, ...]
    """
    api_instance = _make_api(DEFAULT_REGION, volcenginesdkecs.ECSApi)
    request = volcenginesdkecs.DescribeRegionsRequest(max_results=PAGE_SIZE)

    try:
        response = api_instance.describe_regions(request)
    except ApiException as e:
        raise Exception(f"火山云API异常（获取地域列表）：{e}")
    except Exception as e:
        raise Exception(f"火山云地域列表查询失败：{str(e)}")

    return [
        {
            "region": item.region_id,
            "region_name": REGION_NAME_MAP.get(item.region_id, item.region_id),
        }
        for item in (response.regions or [])
    ]


def get_vpcs_by_region(region: str):
    """
    获取单个地域下的所有 VPC
    :param region: 地域标识，如 cn-beijing
    :return: VPC 对象列表
    """
    api_instance = _make_api(region, volcenginesdkvpc.VPCApi)
    all_items = []
    page_number = 1

    while True:
        request = volcenginesdkvpc.DescribeVpcsRequest(
            page_number=page_number,
            page_size=PAGE_SIZE
        )

        try:
            response = api_instance.describe_vpcs(request)
        except ApiException as e:
            raise Exception(f"火山云API异常（{region}）：{e}")
        except Exception as e:
            raise Exception(f"火山云VPC查询失败（{region}）：{str(e)}")

        data = response.vpcs or []
        if not data:
            break
        all_items.extend(data)

        if len(all_items) >= (response.total_count or 0):
            break
        page_number += 1

    return all_items


def get_subnets_by_region(region: str):
    """
    获取单个地域下的所有子网
    :param region: 地域标识，如 cn-beijing
    :return: 子网对象列表
    """
    api_instance = _make_api(region, volcenginesdkvpc.VPCApi)
    all_items = []
    page_number = 1

    while True:
        request = volcenginesdkvpc.DescribeSubnetsRequest(
            page_number=page_number,
            page_size=PAGE_SIZE
        )

        try:
            response = api_instance.describe_subnets(request)
        except ApiException as e:
            raise Exception(f"火山云API异常（{region} 子网）：{e}")
        except Exception as e:
            raise Exception(f"火山云子网查询失败（{region}）：{str(e)}")

        data = response.subnets or []
        if not data:
            break
        all_items.extend(data)

        if len(all_items) >= (response.total_count or 0):
            break
        page_number += 1

    return all_items


def _normalize_vpc(vpc, region: str, region_name: str) -> dict:
    """把 VPC 对象统一成内部结构"""
    return {
        "region": region,
        "region_name": region_name,
        "vpc_id": vpc.vpc_id,
        "vpc_name": vpc.vpc_name or "-",
        "cidr_block": vpc.cidr_block or "-",
        "secondary_cidrs": list(vpc.secondary_cidr_blocks or []),
        "user_cidrs": list(vpc.user_cidr_blocks or []),
        "ipv6_cidr_block": vpc.ipv6_cidr_block or "-",
        "is_default": bool(vpc.is_default),
        "status": vpc.status or "-",
        "created_time": vpc.creation_time or "-",
        "description": vpc.description or "-",
        "project_name": vpc.project_name or "-",
        "dns_servers": list(vpc.dns_servers or []),
        "subnet_count": len(vpc.subnet_ids or []),
        "subnets": [],  # 由 analyze 阶段按 vpc_id 回填
        "tags": [{"key": tag.key, "value": tag.value} for tag in (vpc.tags or [])],
    }


def _normalize_subnet(subnet, region: str, region_name: str) -> dict:
    """把子网对象统一成内部结构"""
    return {
        "region": region,
        "region_name": region_name,
        "vpc_id": subnet.vpc_id,
        "subnet_id": subnet.subnet_id,
        "subnet_name": subnet.subnet_name or "-",
        "cidr_block": subnet.cidr_block or "-",
        "ipv6_cidr_block": subnet.ipv6_cidr_block or "-",
        "zone_id": subnet.zone_id or "-",
        "available_ips": subnet.available_ip_address_count or 0,
        "total_ips": subnet.total_ipv4_count or 0,
        "is_default": bool(subnet.is_default),
        "status": subnet.status or "-",
        "created_time": subnet.creation_time or "-",
        "description": subnet.description or "-",
        "tags": [{"key": tag.key, "value": tag.value} for tag in (subnet.tags or [])],
    }


def _vpc_cidrs(vpc: dict) -> list:
    """汇总一个 VPC 的全部网段（主网段 + 辅助网段 + IPv6）"""
    cidrs = []
    if vpc["cidr_block"] != "-":
        cidrs.append(vpc["cidr_block"])
    cidrs.extend(vpc["secondary_cidrs"])
    if vpc["ipv6_cidr_block"] != "-":
        cidrs.append(vpc["ipv6_cidr_block"])
    return cidrs


def analyze_volcano_vpc(regions: list = None, include_default: bool = True,
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

    if regions:
        wanted = set(regions)
        scanned = [r for r in region_list if r["region"] in wanted]
    else:
        scanned = region_list

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
            try:
                subnet_list = get_subnets_by_region(region)
            except Exception as e:
                failed_regions.append({"region": region, "region_name": region_name,
                                       "error": f"子网查询失败：{str(e)}"})
                subnet_list = []

            subnets = [_normalize_subnet(s, region, region_name) for s in subnet_list]
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


def format_volcano_vpc_report(result: dict) -> str:
    """
    格式化火山云 VPC 网段报告为可读文本
    :param result: analyze_volcano_vpc 返回的结果字典
    :return: 格式化的文本报告
    """
    if not result.get("success"):
        return f"❌ {result.get('message', '查询失败')}"

    lines = []
    lines.append("=" * 100)
    lines.append("🌐 火山云 VPC 网段统计")
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
            lines.append(f"  {item['vpc_name']:24s} {item['vpc_id']:32s} "
                         f"{item['cidr_block']:20s}{flag}")
            if item["secondary_cidrs"]:
                lines.append(f"    辅助网段: {', '.join(item['secondary_cidrs'])}")
            if item["ipv6_cidr_block"] != "-":
                lines.append(f"    IPv6 网段: {item['ipv6_cidr_block']}")
            for subnet in sorted(item["subnets"], key=lambda x: x["cidr_block"]):
                lines.append(f"    └─ {subnet['cidr_block']:20s} {subnet['subnet_name']:24s} "
                             f"{subnet['zone_id']:16s} "
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
    result = analyze_volcano_vpc(query_regions, show_default, show_subnets, show_details)

    # 打印报告
    print(format_volcano_vpc_report(result))
