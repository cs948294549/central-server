"""
VPC 网段同步到 IPAM 定时任务

功能：拉取腾讯云、火山云账号下所有地域的 VPC 网段，与 IPAM 网段表(ipam_net)比对
- 已存在且 role = vpc：按最新 VPC 信息刷新 location / label / comment 字段
- 已存在且 role != vpc：网段已被占用（如已登记为其它用途），产生告警，不覆盖原记录
- 不存在：写入 ipam_net，role 记为 vpc

说明：
- 网段以「网络地址 + 前缀长度」为主键（ipam_net 的主键是 ip+mask），比对时先归一化
  成网络地址，避免 10.18.0.5/18 与 10.18.0.0/18 被当成两个网段
- IPv4 默认同步；IPv6 由于 IPAM 树形展示依赖 IPv4 整型换算，默认不同步，而是把
  IPv6 网段追加到所属网段的 comment 中，如 "IPv6:240d:c000:2022:4e00::/56"
- 腾讯云、火山云都是 VPC 网段（父）与子网网段（子）一起入库，两者都标注 role=vpc，
  通过 label（如 "VPC-火山/Subnet-mpl-A"）和 comment 区分层级；
  子网网段仅在 TASK_CONFIG["sync_subnet"] 为 True 时同步
- 跳过名单 SKIP_CIDRS 中的网段不写入 IPAM、也不参与冲突比对，用于排除账号内
  未实际使用的网段（如火山云默认 VPC 172.31.0.0/16）；跳过的是某个 VPC 网段时，
  其子网网段一并跳过
- 更新时只刷新 location / label / comment，status / manage_user / gateway 等人工维护字段不动

使用方式：
1. 作为定时任务：在 config/task_config.yaml 中配置 cron
2. 单独运行：python3 tasks/sync_vpc_to_ipam.py [--dry-run]
"""
import argparse
import ipaddress
import logging
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from function_clouds.tencent_vpc import analyze_tencent_vpc
from function_clouds.volcano_vpc import analyze_volcano_vpc
from function_queue.message_queue import sendDataToSyslog
from tables.IpamDB import IpamDB
from utils.utils import unwaf

logger = logging.getLogger(__name__)


# 任务配置
TASK_CONFIG = {
    "enabled": True,           # 是否启用任务
    "tencent_enabled": True,   # 是否同步腾讯云 VPC 网段
    "volcano_enabled": True,   # 是否同步火山云 VPC 网段
    "include_default": True,   # 是否包含默认 VPC（默认 VPC 是否真正使用由跳过名单决定）
    "sync_ipv6": False,        # 是否同步 IPv6 网段
    "sync_assistant": True,    # 是否同步辅助 CIDR（腾讯云助理 CIDR / 火山云辅助网段）
    "sync_subnet": True,       # 子网网段是否一起入库（腾讯云、火山云均适用，父子网段）
    "vpc_role": "vpc",         # 云上 VPC/子网网段在 IPAM 中标记的 role
}

# 跳过名单：按网段跳过，网段被名单网段包含即跳过（含其子网网段）
SKIP_CIDRS = [
    "172.31.0.0/16",  # 火山云默认 VPC 网段，账号内未实际使用
    "172.21.0.0/20",  # 腾讯云默认 VPC 网段，账号内未实际使用
]

# 告警配置（推送到 syslog 队列，由 SyslogService 做黑名单过滤、聚合后入库）
ALARM_TYPE = "ipam"
ALARM_KEYWORD = "vpc-conflict"

# 云平台中文名，用于拼接 label / comment / 告警文案
CLOUD_DESC = {
    "tencent": "腾讯云",
    "volcano": "火山云",
}


def _parse_skip_cidrs(cidrs: list) -> list:
    """把跳过名单解析成网段对象，解析失败的条目忽略"""
    networks = []
    for cidr in cidrs:
        try:
            networks.append(ipaddress.ip_network(cidr.strip(), strict=False))
        except ValueError:
            logger.warning(f"跳过名单中的网段无法解析，已忽略: {cidr}")
    return networks


_SKIP_NETWORKS = _parse_skip_cidrs(SKIP_CIDRS)


def is_skipped(cidr: str) -> bool:
    """
    判断网段是否命中跳过名单
    :param cidr: 待判断网段，如 172.31.0.0/16
    :return: True 表示跳过
    """
    try:
        net = ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        return False
    return any(net.version == skip.version and net.subnet_of(skip) for skip in _SKIP_NETWORKS)


def parse_cidr(cidr: str):
    """
    解析 CIDR，归一化为网络地址 + 前缀长度
    :param cidr: 如 10.18.0.0/18、2402:4e00:1203:f200::/56
    :return: (ip, mask, is_ipv6)，解析失败返回 None
    """
    try:
        net = ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        logger.warning(f"无法解析网段: {cidr}")
        return None
    return str(net.network_address), str(net.prefixlen), net.version == 6


def _fold_ipv6(cidr: str) -> list:
    """
    不同步 IPv6 时，把 IPv6 网段折叠进所属网段的 comment；需要单独同步时返回空
    :param cidr: IPv6 网段，如 240d:c000:2022:4e00::/56，无 IPv6 时传 "-"
    :return: ["网络地址/前缀长度", ...]
    """
    if TASK_CONFIG["sync_ipv6"] or not cidr or cidr == "-":
        return []
    parsed = parse_cidr(cidr)
    return [f"{parsed[0]}/{parsed[1]}"] if parsed else []


def _build_cidr_item(raw: str, vpc: dict, record_type: str, cloud: str,
                     ipv6_cidrs: list = None, **extra):
    """
    把单个网段打包成待同步项（统一腾讯云 / 火山云的字段口径）
    :param raw: 原始网段，如 10.18.0.0/18
    :param vpc: 所属 VPC 的标准化数据
    :param record_type: "vpc" 表示 VPC 网段，"subnet" 表示子网网段
    :param cloud: 云平台标识，tencent / volcano
    :param ipv6_cidrs: 需要折叠进 comment 的 IPv6 网段
    :param extra: 子网相关的附加字段（subnet_id / subnet_name / zone_id）
    :return: 网段项 dict，无需同步时返回 None
    """
    if not raw or raw == "-":
        return None

    parsed = parse_cidr(raw)
    if not parsed:
        return None

    ip, mask, is_ipv6 = parsed
    if is_ipv6 and not TASK_CONFIG["sync_ipv6"]:
        return None

    item = {
        "cidr": f"{ip}/{mask}",
        "ip": ip,
        "mask": mask,
        "is_ipv6": is_ipv6,
        "ipv6_cidrs": ipv6_cidrs or [],
        "cloud": cloud,
        "record_type": record_type,
        "vpc_id": vpc["vpc_id"],
        "vpc_name": vpc["vpc_name"],
        "region": vpc["region"],
        "region_name": vpc["region_name"],
    }
    item.update(extra)
    return item


def collect_cloud_cidrs(vpc_result: dict, cloud: str, assistant_key: str):
    """
    从云平台 VPC 查询结果中提取待同步的网段（父：VPC 网段；子：子网网段）
    :param vpc_result: analyze_tencent_vpc / analyze_volcano_vpc 返回的结果字典
    :param cloud: 云平台标识，tencent / volcano
    :param assistant_key: 辅助网段字段名（腾讯云 assistant_cidrs / 火山云 secondary_cidrs）
    :return: 网段列表，VPC 网段 record_type=vpc，子网网段 record_type=subnet
    """
    cloud_desc = CLOUD_DESC.get(cloud, cloud)
    cidr_list = []
    seen = set()

    def add(raw, vpc, record_type, ipv6_cidrs, **extra):
        if is_skipped(raw):
            logger.info(f"跳过名单命中，忽略网段 {raw}（{cloud_desc} / {vpc['vpc_name']} / {record_type}）")
            return

        item = _build_cidr_item(raw, vpc, record_type, cloud,
                                ipv6_cidrs=ipv6_cidrs, **extra)
        if not item:
            return

        key = (item["ip"], item["mask"])
        if key in seen:
            return
        seen.add(key)
        cidr_list.append(item)

    for vpc in vpc_result.get("vpcs", []):
        if vpc["is_default"] and not TASK_CONFIG["include_default"]:
            continue

        # 父：VPC 主网段 + 辅助网段
        # IPv6 网段不单独入库时，折叠进对应 IPv4 主网段的 comment
        vpc_ipv6 = _fold_ipv6(vpc["ipv6_cidr_block"])
        add(vpc["cidr_block"], vpc, "vpc", vpc_ipv6)
        if TASK_CONFIG["sync_assistant"]:
            for raw in vpc.get(assistant_key) or []:
                add(raw, vpc, "vpc", [])
        if TASK_CONFIG["sync_ipv6"]:
            add(vpc["ipv6_cidr_block"], vpc, "vpc", [])

        # 子：子网网段
        if not TASK_CONFIG["sync_subnet"]:
            continue
        for subnet in vpc.get("subnets") or []:
            subnet_extra = {
                "subnet_id": subnet["subnet_id"],
                "subnet_name": subnet["subnet_name"],
                "zone_id": subnet["zone_id"],
                "zone_name": subnet.get("zone_name") or subnet["zone_id"],
            }
            add(subnet["cidr_block"], vpc, "subnet", _fold_ipv6(subnet["ipv6_cidr_block"]),
                **subnet_extra)
            if TASK_CONFIG["sync_ipv6"]:
                add(subnet["ipv6_cidr_block"], vpc, "subnet", [], **subnet_extra)

    return cidr_list


def collect_cidrs(vpc_result: dict):
    """从腾讯云 VPC 查询结果中提取待同步的网段"""
    return collect_cloud_cidrs(vpc_result, "tencent", "assistant_cidrs")


def collect_volcano_cidrs(vpc_result: dict):
    """从火山云 VPC 查询结果中提取待同步的网段"""
    return collect_cloud_cidrs(vpc_result, "volcano", "secondary_cidrs")


def collect_all_cidrs():
    """
    汇总各云平台待同步的网段，按 (ip, mask) 去重
    :return: (网段列表, 各平台统计 {"腾讯云": {"vpcs": n, "cidrs": n} / {"error": "..."}})
    """
    sources = []
    if TASK_CONFIG["tencent_enabled"]:
        sources.append((
            "腾讯云",
            lambda: analyze_tencent_vpc(include_default=True,
                                        include_subnets=TASK_CONFIG["sync_subnet"],
                                        include_details=True),
            collect_cidrs,
        ))
    if TASK_CONFIG["volcano_enabled"]:
        sources.append((
            "火山云",
            lambda: analyze_volcano_vpc(include_default=True,
                                        include_subnets=TASK_CONFIG["sync_subnet"],
                                        include_details=True),
            collect_volcano_cidrs,
        ))

    cidr_list = []
    seen = {}
    stats = {}

    for cloud_desc, analyzer, collector in sources:
        try:
            result = analyzer()
        except Exception as e:
            logger.error(f"获取{cloud_desc} VPC 列表异常: {e}")
            stats[cloud_desc] = {"error": str(e)}
            continue

        if not result.get("success"):
            logger.error(f"获取{cloud_desc} VPC 列表失败: {result.get('message')}")
            stats[cloud_desc] = {"error": result.get("message")}
            continue

        for item in result.get("failed_regions") or []:
            logger.warning(f"{cloud_desc}地域 {item['region']}({item['region_name']}) "
                           f"查询失败: {item['error']}")

        items = collector(result)
        total_vpcs = result.get("total_vpcs", 0)
        stats[cloud_desc] = {"vpcs": total_vpcs, "cidrs": len(items)}
        logger.info(f"{cloud_desc}: 共 {total_vpcs} 个 VPC，整理出 {len(items)} 个待处理网段")

        for item in items:
            key = (item["ip"], item["mask"])
            if key in seen:
                logger.warning(f"网段 {item['cidr']} 同时出现在{seen[key]}和{cloud_desc}"
                               f"（{item['vpc_id']} / {item['vpc_name']}），保留先采集的一条")
                continue
            seen[key] = cloud_desc
            cidr_list.append(item)

    return cidr_list, stats


def check_network_exists(cidr_item: dict):
    """
    查询 IPAM 中是否已存在该网段
    :param cidr_item: collect_cidrs / collect_volcano_cidrs 返回的网段项
    :return: 已存在的记录 dict，不存在返回 None，查询失败返回 "failed"
    """
    db = IpamDB()
    result = db.get_network_list({"ip": cidr_item["ip"], "mask": cidr_item["mask"]})

    if result == "failed":
        return "failed"
    if result:
        return result[0]
    return None


def build_alarm_data(cidr_item: dict, exist_item: dict) -> dict:
    """
    构建网段冲突告警消息（推送到 syslog 队列的格式）

    group_label / group_name 不在这里生成，由 SyslogService 的 MergelistManager
    按 ip + 时间窗 + keyword(或聚合规则 group_name) + alarm_object + alarm_type 聚合补全
    """
    exist_desc = exist_item.get("comment") or "-"
    exist_label = exist_item.get("label") or "-"

    cloud_desc = CLOUD_DESC.get(cidr_item.get("cloud", "tencent"), "")
    kind = "子网网段" if cidr_item.get("record_type") == "subnet" else "VPC网段"
    owner = cidr_item["vpc_name"]
    if cidr_item.get("subnet_name"):
        owner = f"{owner}/{cidr_item['subnet_name']}"

    msg = (f"{cloud_desc}{kind}冲突: {cidr_item['cidr']} ({cidr_item['region']} / "
           f"{owner} / {cidr_item['vpc_id']}) "
           f"在IPAM中已存在, role={exist_item.get('role') or '空'}, "
           f"label={exist_label}, comment={exist_desc}")

    return {
        "ip": cidr_item["ip"],
        "message": msg[:500],
        "hostname": owner,
        "alarm_type": ALARM_TYPE,
        "alarm_object": cidr_item["vpc_id"],
        "keyword": ALARM_KEYWORD,
    }


def build_ipam_data(cidr_item: dict) -> dict:
    """构建写入 IPAM 的网段数据（VPC 网段为父，子网网段为子，均标注 role=vpc）"""
    cloud_desc = CLOUD_DESC.get(cidr_item.get("cloud", "tencent"), "")

    if cidr_item.get("record_type") == "subnet":
        label = f"{cidr_item['vpc_name']}/{cidr_item['subnet_name']}"
        zone_name = cidr_item.get("zone_name") or "-"
        zone_id = cidr_item.get("zone_id") or "-"
        zone_desc = zone_name if zone_name == zone_id else f"{zone_name} {zone_id}"
        comment = (f"{cloud_desc}子网 {cidr_item['subnet_id']} "
                   f"({cidr_item['vpc_id']} / {zone_desc})")
    else:
        label = cidr_item["vpc_name"]
        comment = f"{cloud_desc}VPC {cidr_item['vpc_id']} {cidr_item['region']}"

    if cidr_item.get("ipv6_cidrs"):
        comment += " IPv6:" + ",".join(cidr_item["ipv6_cidrs"])

    return {
        "ip": cidr_item["ip"],
        "mask": cidr_item["mask"],
        "status": "1",
        "location": cidr_item["region_name"],
        "isp": "",
        "role": TASK_CONFIG["vpc_role"],
        "label": label,
        "comment": comment,
        "manage_user": "",
    }


# 同步时允许刷新的字段（status/manage_user/gateway 等人工维护字段不动）
SYNC_FIELDS = ["location", "label", "comment"]


def get_changed_fields(exist_item: dict, new_data: dict) -> dict:
    """
    比对已存在记录与最新数据，返回需要更新的字段
    :param exist_item: IPAM 中已存在的记录
    :param new_data: build_ipam_data 构建的最新数据
    :return: 有变化的字段 dict（不含 ip/mask），无变化返回空 dict
    """
    changed = {}
    for key in SYNC_FIELDS:
        old_value = unwaf(exist_item.get(key) or "")
        new_value = new_data[key]
        if old_value != new_value:
            changed[key] = new_value
    return changed


def run(dry_run: bool = False):
    """
    主执行函数 - 同步 VPC 网段到 IPAM

    执行流程：
    1. 拉取各云平台所有地域的 VPC 网段（腾讯云、火山云均含子网网段）
    2. 逐个查询 IPAM 中是否已存在
    3. 存在且 role=vpc 刷新可变字段；存在且 role 非 vpc 告警；不存在则写入
    """
    if not TASK_CONFIG["enabled"]:
        logger.info("VPC 网段同步任务已禁用")
        return

    logger.info("开始执行 VPC 网段同步任务" + ("（dry-run，不写库）" if dry_run else ""))

    # 1. 拉取 VPC 网段
    cidr_list, cloud_stats = collect_all_cidrs()
    logger.info(f"共整理出 {len(cidr_list)} 个待处理网段")

    if not cidr_list:
        logger.error(f"未获取到任何网段，各平台情况: {cloud_stats}")
        return {
            "total": 0,
            "added": 0,
            "updated": 0,
            "ignored": 0,
            "conflicted": 0,
            "failed": 0,
            "failed_items": [],
            "clouds": cloud_stats,
        }

    vpc_role = TASK_CONFIG["vpc_role"]
    added = 0
    updated = 0
    ignored = 0
    conflicted = 0
    failed = 0
    failed_items = []

    for cidr_item in cidr_list:
        cidr = cidr_item["cidr"]
        try:
            exist_item = check_network_exists(cidr_item)

            # 查询失败
            if exist_item == "failed":
                failed += 1
                failed_items.append({"cidr": cidr, "reason": "查询IPAM失败"})
                logger.error(f"{cidr}: 查询IPAM失败")
                continue

            # 2. 已存在
            if exist_item is not None:
                exist_role = (exist_item.get("role") or "").strip()
                if exist_role == vpc_role:
                    # 是历史同步的 VPC 网段，按最新数据刷新可变字段
                    new_data = build_ipam_data(cidr_item)
                    changed = get_changed_fields(exist_item, new_data)

                    if not changed:
                        ignored += 1
                        logger.debug(f"{cidr}: 已存在且内容无变化，跳过")
                        continue

                    if dry_run:
                        logger.info(f"[dry-run] 待更新: {cidr} 字段变更 {changed}")
                        updated += 1
                        continue

                    update_data = {"ip": cidr_item["ip"], "mask": cidr_item["mask"]}
                    update_data.update(changed)
                    ret = IpamDB().update_network_item(update_data)
                    if ret == "success":
                        updated += 1
                        logger.info(f"{cidr}: 更新成功 {changed} ({cidr_item['region']} / {cidr_item['vpc_name']})")
                    else:
                        failed += 1
                        failed_items.append({"cidr": cidr, "reason": "更新IPAM失败"})
                        logger.error(f"{cidr}: 更新失败")
                else:
                    conflicted += 1
                    logger.warning(f"{cidr}: 已存在但 role={exist_role or '空'}（{cidr_item['vpc_name']}），产生告警")
                    if not dry_run:
                        if not sendDataToSyslog(messages=build_alarm_data(cidr_item, exist_item),
                                                key=cidr_item["ip"]):
                            logger.error(f"{cidr}: 告警推送到 syslog 队列失败")
                continue

            # 3. 不存在，写入
            if dry_run:
                logger.info(f"[dry-run] 待写入: {cidr} ({cidr_item['region']} / {cidr_item['vpc_name']})")
                added += 1
                continue

            ret = IpamDB().add_network_item(build_ipam_data(cidr_item))
            if ret == "success":
                added += 1
                logger.info(f"{cidr}: 写入成功 ({cidr_item['region']} / {cidr_item['vpc_name']})")
            else:
                failed += 1
                failed_items.append({"cidr": cidr, "reason": "写入IPAM失败"})
                logger.error(f"{cidr}: 写入失败")

        except Exception as e:
            failed += 1
            failed_items.append({"cidr": cidr, "reason": str(e)})
            logger.error(f"{cidr}: 处理异常 - {e}")

    logger.info("VPC 网段同步任务完成 - "
                f"网段总数: {len(cidr_list)}, 新增: {added}, 更新: {updated}, "
                f"无变化跳过: {ignored}, 冲突告警: {conflicted}, 失败: {failed}")

    if failed_items:
        for item in failed_items:
            logger.error(f"  失败: {item['cidr']} - {item['reason']}")

    return {
        "total": len(cidr_list),
        "added": added,
        "updated": updated,
        "ignored": ignored,
        "conflicted": conflicted,
        "failed": failed,
        "failed_items": failed_items,
        "clouds": cloud_stats,
    }


def main():
    parser = argparse.ArgumentParser(description="同步腾讯云/火山云 VPC 网段到 IPAM")
    parser.add_argument("--dry-run", action="store_true", help="只查询比对，不写入数据库、不产生告警")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/sync_vpc_to_ipam.log')
        ]
    )

    logger.info("=" * 60)
    logger.info("手动触发 VPC 网段同步任务")
    logger.info("=" * 60)

    try:
        run(dry_run=args.dry_run)
        logger.info("=" * 60)
        logger.info("任务执行成功")
        logger.info("=" * 60)
    except KeyboardInterrupt:
        logger.info("\n任务被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        logger.info("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
