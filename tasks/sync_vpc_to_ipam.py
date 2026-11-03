"""
VPC 网段同步到 IPAM 定时任务

功能：拉取腾讯云账号下所有地域的 VPC 网段，与 IPAM 网段表(ipam_net)比对
- 已存在且 role = vpc：按最新 VPC 信息刷新 location / label / comment 字段
- 已存在且 role != vpc：网段已被占用（如已登记为其它用途），产生告警，不覆盖原记录
- 不存在：写入 ipam_net，role 记为 vpc

说明：
- 网段以「网络地址 + 前缀长度」为主键（ipam_net 的主键是 ip+mask），比对时先归一化
  成网络地址，避免 10.18.0.5/18 与 10.18.0.0/18 被当成两个网段
- IPv4 默认同步；IPv6 由于 IPAM 树形展示依赖 IPv4 整型换算，默认不同步，而是把 VPC 的
  IPv6 网段追加到主网段(VPC CidrBlock)的 comment 中，如 "IPv6:240d:c000:2022:4e00::/56"
- 默认 VPC（172.x）也同步，如不需要可置 INCLUDE_DEFAULT = False
- 更新时只刷新 location / label / comment，status / manage_user / gateway 等人工维护字段不动

使用方式：
1. 作为定时任务：在 config/task_config.yaml 中配置 cron
2. 单独运行：python3 tasks/sync_vpc_to_ipam.py [--dry-run]
"""
import argparse
import hashlib
import ipaddress
import logging
import sys
import time
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from function_clouds.tencent_vpc import analyze_tencent_vpc
from tables.AlarmDB import AlarmDB
from tables.IpamDB import IpamDB
from utils.utils import unwaf

logger = logging.getLogger(__name__)


# 任务配置
TASK_CONFIG = {
    "enabled": True,           # 是否启用任务
    "include_default": True,   # 是否同步默认 VPC
    "sync_ipv6": False,        # 是否同步 IPv6 网段
    "sync_assistant": True,    # 是否同步辅助 CIDR
    "vpc_role": "vpc",         # VPC 网段在 IPAM 中标记的 role
}

# 告警配置
ALARM_TYPE = "ipam"
ALARM_GROUP_NAME = "VPC网段冲突"
ALARM_KEYWORD = "vpc-conflict"


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


def collect_cidrs(vpc_result: dict):
    """
    从 VPC 查询结果中提取待同步的网段
    :param vpc_result: analyze_tencent_vpc 返回的结果字典
    :return: 网段列表 [{"cidr", "ip", "mask", "is_ipv6", "vpc_id", "vpc_name", "region", "region_name"}]
    """
    cidr_list = []
    seen = set()

    for vpc in vpc_result.get("vpcs", []):
        if vpc["is_default"] and not TASK_CONFIG["include_default"]:
            continue

        raw_cidrs = [vpc["cidr_block"]]
        if TASK_CONFIG["sync_ipv6"] and vpc["ipv6_cidr_block"] != "-":
            raw_cidrs.append(vpc["ipv6_cidr_block"])
        if TASK_CONFIG["sync_assistant"]:
            raw_cidrs.extend(vpc["assistant_cidrs"])

        for raw in raw_cidrs:
            if not raw or raw == "-":
                continue
            parsed = parse_cidr(raw)
            if not parsed:
                continue

            ip, mask, is_ipv6 = parsed
            if is_ipv6 and not TASK_CONFIG["sync_ipv6"]:
                continue

            key = (ip, mask)
            if key in seen:
                continue
            seen.add(key)

            # IPv6 网段不单独入库，直接写进对应 IPv4 网段的 comment
            ipv6_cidrs = []
            if not is_ipv6 and vpc["ipv6_cidr_block"] != "-" and not TASK_CONFIG["sync_ipv6"]:
                v6_parsed = parse_cidr(vpc["ipv6_cidr_block"])
                if v6_parsed:
                    ipv6_cidrs.append(f"{v6_parsed[0]}/{v6_parsed[1]}")

            cidr_list.append({
                "cidr": f"{ip}/{mask}",
                "ip": ip,
                "mask": mask,
                "is_ipv6": is_ipv6,
                "ipv6_cidrs": ipv6_cidrs,
                "vpc_id": vpc["vpc_id"],
                "vpc_name": vpc["vpc_name"],
                "region": vpc["region"],
                "region_name": vpc["region_name"],
            })

    return cidr_list


def check_network_exists(cidr_item: dict):
    """
    查询 IPAM 中是否已存在该网段
    :param cidr_item: collect_cidrs 返回的网段项
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
    """构建网段冲突告警数据"""
    exist_desc = exist_item.get("comment") or "-"
    exist_label = exist_item.get("label") or "-"
    msg = (f"VPC网段冲突: {cidr_item['cidr']} ({cidr_item['region']} / "
           f"{cidr_item['vpc_name']} / {cidr_item['vpc_id']}) "
           f"在IPAM中已存在, role={exist_item.get('role') or '空'}, "
           f"label={exist_label}, comment={exist_desc}")

    timestamp = int(time.time())
    # 同一网段 + 同一天聚合成一条告警，避免每天重复堆积
    group_key = f"{ALARM_KEYWORD}.{cidr_item['cidr']}.{timestamp // 86400}"
    group_label = hashlib.md5(group_key.encode("utf-8")).hexdigest()

    return {
        "ip": cidr_item["ip"],
        "hostname": cidr_item["vpc_name"],
        "alarm_type": ALARM_TYPE,
        "group_label": group_label,
        "msg": msg[:500],
        "group_name": ALARM_GROUP_NAME,
        "alarm_object": cidr_item["vpc_id"],
        "keyword": ALARM_KEYWORD,
        "create_time": timestamp
    }


def build_ipam_data(cidr_item: dict) -> dict:
    """构建写入 IPAM 的网段数据"""
    comment = f"腾讯云VPC {cidr_item['vpc_id']} {cidr_item['region']}"
    if cidr_item.get("ipv6_cidrs"):
        comment += " IPv6:" + ",".join(cidr_item["ipv6_cidrs"])

    return {
        "ip": cidr_item["ip"],
        "mask": cidr_item["mask"],
        "status": "1",
        "location": cidr_item["region_name"],
        "isp": "",
        "role": TASK_CONFIG["vpc_role"],
        "label": cidr_item["vpc_name"],
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
    1. 拉取所有地域的 VPC 网段
    2. 逐个查询 IPAM 中是否已存在
    3. 存在且 role=vpc 刷新可变字段；存在且 role 非 vpc 告警；不存在则写入
    """
    if not TASK_CONFIG["enabled"]:
        logger.info("VPC 网段同步任务已禁用")
        return

    logger.info("开始执行 VPC 网段同步任务" + ("（dry-run，不写库）" if dry_run else ""))

    # 1. 拉取 VPC 网段
    vpc_result = analyze_tencent_vpc(include_default=True, include_details=True)
    if not vpc_result.get("success"):
        logger.error(f"获取 VPC 列表失败: {vpc_result.get('message')}")
        return

    if vpc_result.get("failed_regions"):
        for item in vpc_result["failed_regions"]:
            logger.warning(f"地域 {item['region']}({item['region_name']}) 查询失败: {item['error']}")

    cidr_list = collect_cidrs(vpc_result)
    logger.info(f"共获取到 {vpc_result['total_vpcs']} 个 VPC，"
                f"整理出 {len(cidr_list)} 个待处理网段")

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
                        ret = AlarmDB().addAlarmList(build_alarm_data(cidr_item, exist_item))
                        if ret == "failed":
                            logger.error(f"{cidr}: 告警写入失败")
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
    }


def main():
    parser = argparse.ArgumentParser(description="同步腾讯云 VPC 网段到 IPAM")
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
