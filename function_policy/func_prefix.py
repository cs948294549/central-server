"""
地址前缀列表管理中间方法
提供指纹计算、配置对比、统计分析等功能
"""
from lib_config.models import PrefixListConfig
from lib_config.fingerprint import calculate_fingerprint
from tables.PrefixListDB import PrefixListDB
import logging

logger = logging.getLogger(__name__)


def calculate_prefix_list_fingerprint(entries):
    """
    计算地址前缀列表配置指纹
    :param entries: 条目列表 [{"seq": 1000, "action": "permit", "prefix": "172.17.0.0/16", "ge": None, "le": None}, ...]
    :return: SHA256 指纹字符串
    """
    try:
        # 使用 lib_config 中的 PrefixListConfig 和 calculate_fingerprint
        config = PrefixListConfig(
            name="temp",  # 名称不影响指纹
            entries=entries,
            description=None
        )
        fingerprint = calculate_fingerprint(config)
        return fingerprint
    except Exception as err:
        logger.error(f"计算指纹失败: {err}")
        return None


def get_device_statistics_for_standard(standard_id, standard_name, standard_fingerprint):
    """
    获取标准规则的设备应用统计
    :param standard_id: 标准规则ID
    :param standard_name: 标准规则名称（用于查询 records 表的 pl_name）
    :param standard_fingerprint: 标准指纹
    :return: {total, matched, drifted, rate}
    """
    try:
        # 查询该前缀列表名称的所有设备记录
        db = PrefixListDB()
        records = db.getRecordsList({"pl_name": standard_name})

        if records == "failed":
            return {"total": 0, "matched": 0, "drifted": 0, "rate": 0}

        total = len(records)
        matched = 0
        drifted = 0

        for record in records:
            if record["fingerprint"] == standard_fingerprint:
                matched += 1
            else:
                drifted += 1

        rate = round((matched / total * 100) if total > 0 else 0, 1)

        return {
            "total": total,
            "matched": matched,
            "drifted": drifted,
            "rate": rate
        }

    except Exception as err:
        logger.error(f"获取设备统计失败: {err}")
        return {"total": 0, "matched": 0, "drifted": 0, "rate": 0}


def get_device_list_for_standard(standard_name, standard_fingerprint, filter_type='all'):
    """
    获取标准规则关联的设备列表
    :param standard_name: 标准规则名称
    :param standard_fingerprint: 标准指纹
    :param filter_type: 过滤类型 'all' | 'matched' | 'drifted'
    :return: 设备列表
    """
    try:
        db = PrefixListDB()
        records = db.getRecordsList({"pl_name": standard_name})

        if records == "failed":
            return []

        device_list = []
        for record in records:
            match_status = "matched" if record["fingerprint"] == standard_fingerprint else "drifted"

            # 根据过滤类型筛选
            if filter_type == 'all' or filter_type == match_status:
                device_list.append({
                    "device_ip": record["device_ip"],
                    "device_name": record["device_name"],
                    "vendor": record["vendor"],
                    "fingerprint": record["fingerprint"],
                    "match_status": match_status,
                    "collected_at": record["collected_at"]
                })

        return device_list

    except Exception as err:
        logger.error(f"获取设备列表失败: {err}")
        return []


def compare_configurations(standard_entries, device_entries):
    """
    对比标准配置和设备配置
    :param standard_entries: 标准配置条目列表
    :param device_entries: 设备配置条目列表
    :return: {
        "is_matched": bool,
        "added": [],    # 标准中有但设备中没有的
        "removed": [],  # 设备中有但标准中没有的
        "modified": []  # 序号相同但内容不同的
    }
    """
    try:
        # 转换为以 seq 为 key 的字典便于比较
        standard_dict = {entry["seq"]: entry for entry in standard_entries}
        device_dict = {entry["seq"]: entry for entry in device_entries}

        added = []
        removed = []
        modified = []

        # 检查标准中有但设备中没有的
        for seq, entry in standard_dict.items():
            if seq not in device_dict:
                added.append(entry)
            else:
                # 检查内容是否一致
                device_entry = device_dict[seq]
                if (entry["action"] != device_entry["action"] or
                    entry["prefix"] != device_entry["prefix"] or
                    entry.get("ge") != device_entry.get("ge") or
                    entry.get("le") != device_entry.get("le")):
                    modified.append({
                        "standard": entry,
                        "device": device_entry
                    })

        # 检查设备中有但标准中没有的
        for seq, entry in device_dict.items():
            if seq not in standard_dict:
                removed.append(entry)

        is_matched = len(added) == 0 and len(removed) == 0 and len(modified) == 0

        return {
            "is_matched": is_matched,
            "added": added,
            "removed": removed,
            "modified": modified
        }

    except Exception as err:
        logger.error(f"配置对比失败: {err}")
        return {
            "is_matched": False,
            "added": [],
            "removed": [],
            "modified": []
        }


def group_records_by_fingerprint(records):
    """
    按指纹分组设备记录
    :param records: 设备记录列表
    :return: {fingerprint: [device_records]}
    """
    try:
        grouped = {}
        for record in records:
            fingerprint = record["fingerprint"]
            if fingerprint not in grouped:
                grouped[fingerprint] = []
            grouped[fingerprint].append(record)

        return grouped

    except Exception as err:
        logger.error(f"分组失败: {err}")
        return {}


def batch_create_issue_records(standard_id, standard_name, standard_entries, device_list, created_by):
    """
    批量创建问题处理记录
    :param standard_id: 标准规则ID
    :param standard_name: 标准规则名称
    :param standard_entries: 标准配置条目
    :param device_list: 设备列表 [{device_ip, device_name, vendor, fingerprint, device_entries}]
    :param created_by: 创建人
    :return: {success: [], failed: []}
    """
    try:
        success = []
        failed = []

        for device in device_list:
            try:
                # 判断问题类型
                if not device.get("device_entries") or len(device["device_entries"]) == 0:
                    issue_type = "missing"
                else:
                    issue_type = "drifted"

                db = PrefixListDB()
                result = db.createIssueRecord({
                    "standard_id": standard_id,
                    "standard_name": standard_name,
                    "device_ip": device["device_ip"],
                    "device_name": device["device_name"],
                    "device_vendor": device["vendor"],
                    "issue_type": issue_type,
                    "standard_entries": standard_entries,
                    "device_entries": device.get("device_entries", []),
                    "created_by": created_by,
                    "remark": device.get("remark", "")
                })

                if result != "failed":
                    success.append({
                        "device_ip": device["device_ip"],
                        "record_id": result
                    })
                else:
                    failed.append({
                        "device_ip": device["device_ip"],
                        "reason": "数据库操作失败"
                    })

            except Exception as err:
                failed.append({
                    "device_ip": device.get("device_ip", "unknown"),
                    "reason": str(err)
                })

        return {
            "success": success,
            "failed": failed
        }

    except Exception as err:
        logger.error(f"批量创建问题记录失败: {err}")
        return {
            "success": [],
            "failed": []
        }
