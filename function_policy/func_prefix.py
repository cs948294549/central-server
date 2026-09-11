"""
地址前缀列表管理中间方法
提供指纹计算、配置对比、统计分析等功能
"""
from utils.fingerprint import calculate_fingerprint
from tables.PrefixListDB import PrefixListDB
from tables.CollectDB import CollectDB
from function_collector.func_config import get_latest_config_by_ip
from lib_config import get_parser
import logging

logger = logging.getLogger(__name__)


def calculate_prefix_list_fingerprint(name, entries):
    """
    计算地址前缀列表配置指纹
    :param name: 前缀列表名称
    :param entries: 条目列表 [{"seq": 1000, "action": "permit", "prefix": "172.17.0.0/16", "ge": None, "le": None}, ...]
    :return: SHA256 指纹字符串
    """
    try:
        # 使用 utils 中的 calculate_fingerprint，包含 name 和 entries
        fingerprint = calculate_fingerprint({"name": name, "entries": entries})
        return fingerprint
    except Exception as err:
        logger.error(f"计算指纹失败: {err}")
        return None


def create_standard(data, username):
    """
    创建标准规则（包含指纹计算）
    :param data: {name, entries, description, is_active}
    :param username: 创建人
    :return: {success: bool, data: {id, fingerprint}, message: str}
    """
    try:
        # 校验必填参数
        if "name" not in data or "entries" not in data:
            return {"success": False, "message": "缺少必要参数: name, entries"}

        # 计算指纹
        entries_list = data["entries"].get("entries", []) if isinstance(data["entries"], dict) else data["entries"]
        fingerprint = calculate_prefix_list_fingerprint(data["name"], entries_list)

        if not fingerprint:
            return {"success": False, "message": "计算配置指纹失败"}

        # 准备数据
        create_data = {
            "name": data["name"],
            "fingerprint": fingerprint,
            "entries": {"entries": entries_list},  # 存储为统一格式
            "description": data.get("description", ""),
            "is_active": data.get("is_active", 1),
            "created_by": username
        }

        db = PrefixListDB()
        result = db.createStandard(create_data)

        if result != "failed":
            return {"success": True, "data": {"id": result, "fingerprint": fingerprint}, "message": "创建成功"}
        else:
            return {"success": False, "message": "创建失败，可能存在重复的规则"}

    except Exception as err:
        logger.error(f"创建标准规则失败: {err}")
        return {"success": False, "message": f"创建失败: {str(err)}"}


def update_standard(data, username):
    """
    更新标准规则（如果更新entries则重新计算指纹）
    :param data: {id, name, entries, description, is_active}
    :param username: 更新人
    :return: {success: bool, message: str}
    """
    try:
        if "id" not in data:
            return {"success": False, "message": "缺少参数: id"}

        # 如果更新了 entries，需要重新计算指纹
        if "entries" in data:
            entries_list = data["entries"].get("entries", []) if isinstance(data["entries"], dict) else data["entries"]

            # 获取当前规则信息以得到 name
            db = PrefixListDB()
            current = db.getStandardDetail({"id": data["id"]})
            if current == "failed":
                return {"success": False, "message": "规则不存在"}

            # 使用新的 name（如果提供）或当前的 name
            name = data.get("name", current["name"])
            fingerprint = calculate_prefix_list_fingerprint(name, entries_list)

            if not fingerprint:
                return {"success": False, "message": "计算配置指纹失败"}

            data["fingerprint"] = fingerprint
            data["entries"] = {"entries": entries_list}

        db = PrefixListDB()
        result = db.updateStandard(data)

        if result != "failed" and result > 0:
            return {"success": True, "message": "更新成功"}
        else:
            return {"success": False, "message": "更新失败，规则可能不存在"}

    except Exception as err:
        logger.error(f"更新标准规则失败: {err}")
        return {"success": False, "message": f"更新失败: {str(err)}"}


def delete_standard(standard_id):
    """
    删除标准规则
    :param standard_id: 标准规则ID
    :return: {success: bool, message: str}
    """
    try:
        db = PrefixListDB()
        result = db.deleteStandard({"id": standard_id})

        if result != "failed" and result > 0:
            return {"success": True, "message": "删除成功"}
        else:
            return {"success": False, "message": "删除失败，规则可能不存在"}

    except Exception as err:
        logger.error(f"删除标准规则失败: {err}")
        return {"success": False, "message": f"删除失败: {str(err)}"}


def get_standard_statistics(standard_id):
    """
    获取标准规则的设备应用统计
    :param standard_id: 标准规则ID
    :return: {success: bool, data: {total, matched, drifted, rate}, message: str}
    """
    try:
        # 获取标准规则详情
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        # 获取统计数据
        statistics = get_device_statistics_for_standard(
            standard["id"],
            standard["name"],
            standard["fingerprint"]
        )

        return {"success": True, "data": statistics, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取标准规则统计失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_standard_device_list(standard_id, filter_type='all'):
    """
    获取标准规则关联的设备列表
    :param standard_id: 标准规则ID
    :param filter_type: 过滤类型 'all' | 'matched' | 'drifted'
    :return: {success: bool, data: [], message: str}
    """
    try:
        # 获取标准规则详情
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        # 获取设备列表
        device_list = get_device_list_for_standard(
            standard["name"],
            standard["fingerprint"],
            filter_type
        )

        return {"success": True, "data": device_list, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取标准规则设备列表失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def compare_record_with_standard(standard_id, device_ip, pl_name):
    """
    对比设备配置与标准配置
    :param standard_id: 标准规则ID
    :param device_ip: 设备IP
    :param pl_name: 前缀列表名称
    :return: {success: bool, data: {standard, device, comparison}, message: str}
    """
    try:
        # 获取标准规则
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        # 获取设备配置
        records = db.getRecordsList({
            "device_ip": device_ip,
            "pl_name": pl_name
        })

        if records == "failed" or len(records) == 0:
            return {"success": False, "message": "设备配置不存在"}

        device_record = records[0]  # 取最新的记录

        # 对比配置
        standard_entries = standard["entries"].get("entries", []) if isinstance(standard["entries"], dict) else standard["entries"]
        device_entries = device_record["entries"]

        comparison = compare_configurations(standard_entries, device_entries)

        result = {
            "standard": {
                "id": standard["id"],
                "name": standard["name"],
                "fingerprint": standard["fingerprint"],
                "entries": standard_entries
            },
            "device": {
                "ip": device_record["device_ip"],
                "name": device_record["device_name"],
                "vendor": device_record["vendor"],
                "fingerprint": device_record["fingerprint"],
                "entries": device_entries,
                "collected_at": device_record["collected_at"]
            },
            "comparison": comparison
        }

        return {"success": True, "data": result, "message": "对比成功"}

    except Exception as err:
        logger.error(f"配置对比失败: {err}")
        return {"success": False, "message": f"对比失败: {str(err)}"}


def create_issue_record(standard_id, device_ip, device_name, device_vendor, remark, username):
    """
    创建问题处理记录
    :param standard_id: 标准规则ID
    :param device_ip: 设备IP
    :param device_name: 设备名称（可选，用于missing类型）
    :param device_vendor: 设备厂商（可选，用于missing类型）
    :param remark: 备注
    :param username: 创建人
    :return: {success: bool, data: {id}, message: str}
    """
    try:
        # 获取标准规则信息
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        # 获取设备配置记录
        records = db.getRecordsList({
            "device_ip": device_ip,
            "pl_name": standard["name"]
        })

        # 判断问题类型
        if records == "failed" or len(records) == 0:
            # 缺失配置
            issue_type = "missing"
            final_device_name = device_name or ""
            final_device_vendor = device_vendor or ""
            device_entries = []
        else:
            # 配置漂移
            device_record = records[0]
            issue_type = "drifted"
            final_device_name = device_record["device_name"]
            final_device_vendor = device_record["vendor"]
            device_entries = device_record["entries"]

        # 创建问题记录
        standard_entries = standard["entries"].get("entries", []) if isinstance(standard["entries"], dict) else standard["entries"]

        create_data = {
            "standard_id": standard_id,
            "standard_name": standard["name"],
            "device_ip": device_ip,
            "device_name": final_device_name,
            "device_vendor": final_device_vendor,
            "issue_type": issue_type,
            "standard_entries": standard_entries,
            "device_entries": device_entries,
            "created_by": username,
            "remark": remark
        }

        result = db.createIssueRecord(create_data)

        if result != "failed":
            return {"success": True, "data": {"id": result}, "message": "创建成功"}
        else:
            return {"success": False, "message": "创建失败"}

    except Exception as err:
        logger.error(f"创建问题处理记录失败: {err}")
        return {"success": False, "message": f"创建失败: {str(err)}"}


def batch_create_issues(standard_id, devices, username):
    """
    批量创建问题处理记录
    :param standard_id: 标准规则ID
    :param devices: 设备列表
    :param username: 创建人
    :return: {success: bool, data: {success: [], failed: []}, message: str}
    """
    try:
        # 获取标准规则信息
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        standard_entries = standard["entries"].get("entries", []) if isinstance(standard["entries"], dict) else standard["entries"]

        # 批量创建
        result = batch_create_issue_records(
            standard_id,
            standard["name"],
            standard_entries,
            devices,
            username
        )

        return {
            "success": True,
            "data": result,
            "message": f"创建完成，成功{len(result['success'])}条，失败{len(result['failed'])}条"
        }

    except Exception as err:
        logger.error(f"批量创建问题处理记录失败: {err}")
        return {"success": False, "message": f"批量创建失败: {str(err)}"}


def update_issue_status(issue_id, update_data):
    """
    更新问题处理记录状态
    :param issue_id: 问题记录ID
    :param update_data: 更新数据 {status, change_ticket_id, processed_at, remark}
    :return: {success: bool, message: str}
    """
    try:
        update_data["id"] = issue_id
        db = PrefixListDB()
        result = db.updateIssueRecordStatus(update_data)

        if result != "failed" and result > 0:
            return {"success": True, "message": "更新成功"}
        else:
            return {"success": False, "message": "更新失败，记录可能不存在"}

    except Exception as err:
        logger.error(f"更新问题处理记录状态失败: {err}")
        return {"success": False, "message": f"更新失败: {str(err)}"}


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
    :param filter_type: 过滤类型 'all' | 'matched' | 'matched_other' | 'drifted'
    :return: 设备列表
    """
    try:
        db = PrefixListDB()

        # 获取该名称的所有标准规则的指纹列表
        all_standards = db.getStandardsList({"name": standard_name})
        if all_standards == "failed":
            other_fingerprints = []
        else:
            other_fingerprints = [s["fingerprint"] for s in all_standards if s["fingerprint"] != standard_fingerprint]

        # 获取该名称的所有设备配置记录
        records = db.getRecordsList({"pl_name": standard_name})

        if records == "failed":
            return []

        device_list = []
        for record in records:
            # 判断匹配状态
            if record["fingerprint"] == standard_fingerprint:
                match_status = "matched"
            elif record["fingerprint"] in other_fingerprints:
                match_status = "matched_other"
            else:
                match_status = "drifted"

            # 根据过滤类型筛选
            if filter_type == 'all' or filter_type == match_status:
                # 计算条目数量
                entries = record.get("entries", {})
                if isinstance(entries, dict):
                    entry_count = len(entries.get("entries", []))
                elif isinstance(entries, list):
                    entry_count = len(entries)
                else:
                    entry_count = 0

                device_list.append({
                    "device_ip": record["device_ip"],
                    "device_name": record["device_name"],
                    "vendor": record["vendor"],
                    "fingerprint": record["fingerprint"],
                    "entry_count": entry_count,
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


def collect_and_update_prefix_lists(ip):
    """
    采集指定设备的前缀列表配置并更新到数据库
    :param ip: 设备IP地址
    :return: {success: bool, message: str, data: {device_info, prefix_lists}}
    """
    try:
        # 1. 查询设备信息，获取vendor
        db_collect = CollectDB()
        all_devices = db_collect.getDeviceList({"host": ip})

        if not all_devices or len(all_devices) == 0:
            return {"success": False, "message": f"未找到设备: {ip}"}

        device_info = all_devices[0]
        vendor = device_info.get("vendor")
        device_name = device_info.get("sysname", "")

        if not vendor:
            return {"success": False, "message": f"设备 {ip} 缺少vendor信息"}

        # 2. 获取最新配置
        config_data = get_latest_config_by_ip(ip)
        if not config_data:
            return {"success": False, "message": f"未找到设备 {ip} 的配置"}

        cfg = config_data.get("detail", "")
        if not cfg:
            return {"success": False, "message": f"设备 {ip} 的配置内容为空"}

        # 3. 使用parser解析配置
        parser = get_parser(vendor, cfg)
        result = parser.parse(sections=['prefix_lists'])

        prefix_lists = result.prefix_lists
        if not prefix_lists:
            return {"success": False, "message": f"设备 {ip} 未解析到前缀列表配置"}

        # 4. 删除该IP的旧记录
        db_prefix = PrefixListDB()
        delete_result = db_prefix.deleteRecordsByIP(ip)

        if delete_result == "failed":
            return {"success": False, "message": f"删除设备 {ip} 旧记录失败"}

        # 5. 准备批量插入数据
        records_to_insert = []
        failed_items = []

        for pl_config in prefix_lists:
            pl_name = pl_config.name
            entries = [entry.to_dict() for entry in pl_config.entries]

            # 计算指纹
            fingerprint = calculate_prefix_list_fingerprint(pl_name, entries)
            if not fingerprint:
                failed_items.append({"pl_name": pl_name, "reason": "计算指纹失败"})
                continue

            records_to_insert.append({
                "device_ip": ip,
                "device_name": device_name,
                "vendor": vendor,
                "pl_name": pl_name,
                "fingerprint": fingerprint,
                "entries": entries
            })

        # 6. 批量插入数据库
        insert_result = {"success": 0, "failed": 0, "failed_items": []}
        if records_to_insert:
            db_prefix_batch = PrefixListDB()
            insert_result = db_prefix_batch.addRecordsList(records_to_insert)
            failed_items.extend(insert_result.get("failed_items", []))

        # 7. 返回结果
        total_inserted = insert_result.get("success", 0)
        total_failed = len(failed_items)
        return {
            "success": True,
            "message": f"成功更新 {total_inserted} 个前缀列表配置",
            "data": {
                "device_info": {
                    "ip": ip,
                    "name": device_name,
                    "vendor": vendor
                },
                "prefix_lists": {
                    "total": len(prefix_lists),
                    "inserted": total_inserted,
                    "failed": total_failed,
                    "failed_items": failed_items
                }
            }
        }

    except Exception as err:
        logger.error(f"采集并更新前缀列表失败 [{ip}]: {err}")
        return {
            "success": False,
            "message": f"采集并更新前缀列表失败: {str(err)}"
        }

