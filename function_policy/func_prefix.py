"""
地址前缀列表管理中间方法
提供指纹计算、配置对比、统计分析等功能
"""
from utils.fingerprint import calculate_fingerprint
from tables.PrefixListDB import PrefixListDB
from tables.CollectDB import CollectDB
from function_collector.func_config import get_latest_config_by_ip
from function_tools.text_diff_tool import check_diff_simple
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
    :return: {total, matched, matched_other, drifted, rate}
    """
    try:
        # 获取该名称的所有标准规则的指纹列表
        db1 = PrefixListDB()
        all_standards = db1.getStandardsList({"name": standard_name})
        if all_standards == "failed":
            other_fingerprints = []
        else:
            other_fingerprints = [s["fingerprint"] for s in all_standards if s["fingerprint"] != standard_fingerprint]

        # 查询该前缀列表名称的所有设备记录
        db2 = PrefixListDB()
        records = db2.getRecordsList({"pl_name": standard_name})

        if records == "failed":
            return {"total": 0, "matched": 0, "matched_other": 0, "drifted": 0, "rate": 0}

        total = len(records)
        matched = 0
        matched_other = 0
        drifted = 0

        for record in records:
            if record["fingerprint"] == standard_fingerprint:
                matched += 1
            elif record["fingerprint"] in other_fingerprints:
                matched_other += 1
            else:
                drifted += 1

        rate = round((matched / total * 100) if total > 0 else 0, 1)

        return {
            "total": total,
            "matched": matched,
            "matched_other": matched_other,
            "drifted": drifted,
            "rate": rate
        }

    except Exception as err:
        logger.error(f"获取设备统计失败: {err}")
        return {"total": 0, "matched": 0, "matched_other": 0, "drifted": 0, "rate": 0}


def get_device_list_for_standard(standard_name, standard_fingerprint, filter_type='all'):
    """
    获取标准规则关联的设备列表
    :param standard_name: 标准规则名称
    :param standard_fingerprint: 标准指纹
    :param filter_type: 过滤类型 'all' | 'matched' | 'matched_other' | 'drifted'
    :return: 设备列表
    """
    try:
        # 获取该名称的所有标准规则的指纹列表
        db1 = PrefixListDB()
        all_standards = db1.getStandardsList({"name": standard_name})
        if all_standards == "failed":
            other_fingerprints = []
        else:
            other_fingerprints = [s["fingerprint"] for s in all_standards if s["fingerprint"] != standard_fingerprint]

        # 获取该名称的所有设备配置记录（使用新的数据库连接）
        db2 = PrefixListDB()
        records = db2.getRecordsList({"pl_name": standard_name})

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
                    entry_list = entries.get("entries", [])
                elif isinstance(entries, list):
                    entry_count = len(entries)
                    entry_list = entries
                else:
                    entry_count = 0
                    entry_list = []

                device_list.append({
                    "device_ip": record["device_ip"],
                    "device_name": record["device_name"],
                    "vendor": record["vendor"],
                    "fingerprint": record["fingerprint"],
                    "entry_count": entry_count,
                    "entries": entry_list,
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


def compare_entries_text_diff(src_entries, target_entries, full_diff=False):
    """
    对比两组配置条目并生成HTML格式的文本差异
    :param src_entries: 源配置条目列表（显示在左侧）
    :param target_entries: 目标配置条目列表（显示在右侧）
    :param full_diff: True=完整对比, False=上下文对比
    :return: {"success": bool, "data": {"html": str}, "message": str}
    """
    try:
        # 将entries转换为文本格式
        def entries_to_text(entries):
            lines = []
            for entry in entries:
                line_parts = [f"seq {entry.get('seq', '')}", entry.get('action', '')]
                line_parts.append(entry.get('prefix', ''))
                if entry.get('ge'):
                    line_parts.append(f"ge {entry['ge']}")
                if entry.get('le'):
                    line_parts.append(f"le {entry['le']}")
                lines.append(" ".join(line_parts))
            return "\n".join(lines)

        src_text = entries_to_text(src_entries)
        target_text = entries_to_text(target_entries)

        # 调用text_diff_tool进行对比
        html_result = check_diff_simple(src_text, target_text, full_diff=full_diff)

        return {
            "success": True,
            "data": {"html": html_result},
            "message": "对比成功"
        }

    except Exception as err:
        logger.error(f"文本对比失败: {err}")
        return {
            "success": False,
            "message": f"文本对比失败: {str(err)}"
        }


def create_prefix_list_change_order(issue_ids, username):
    """
    根据问题处理记录创建前缀列表变更工单

    :param issue_ids: 问题处理记录ID列表
    :param username: 创建人
    :return: {"success": bool, "data": {"op_id": str}, "message": str}
    """
    try:
        from function_op.order_manage import create_order_with_devices
        from lib_config import get_encoder
        from tables.PrefixListDB import PrefixListDB

        if not issue_ids or len(issue_ids) == 0:
            return {"success": False, "message": "缺少参数: issue_ids"}

        logger.info(f"开始处理前缀列表变更工单，issue_ids: {issue_ids}")

        # 1. 查询所有问题记录
        db = PrefixListDB()
        issue_records = []
        not_found_ids = []

        for issue_id in issue_ids:
            logger.info(f"查询问题记录 ID: {issue_id}")
            record = db.getIssueRecordDetail({"id": issue_id})
            if record and record != "failed":
                issue_records.append(record)
                logger.info(f"问题记录 {issue_id} 查询成功: device_ip={record.get('device_ip')}, standard_name={record.get('standard_name')}")
            else:
                not_found_ids.append(issue_id)
                logger.warning(f"问题记录 {issue_id} 不存在")

        if not_found_ids:
            return {
                "success": False,
                "message": f"以下问题记录不存在: {', '.join(map(str, not_found_ids))}"
            }

        if len(issue_records) == 0:
            return {"success": False, "message": "未找到有效的问题记录"}

        logger.info(f"成功查询到 {len(issue_records)} 条问题记录")

        # 2. 准备工单基本信息
        order_data = {
            "title": f"前缀列表配置变更-{len(issue_records)}台设备",
            "descrip": f"根据 {len(issue_records)} 条问题记录创建的变更工单",
            "op_type": "2"  # 固定为2
        }

        # 3. 为每个设备生成配置命令
        devices_data = []
        failed_devices = []
        skipped_devices = []

        for record in issue_records:
            try:
                device_ip = record.get("device_ip")
                vendor = record.get("device_vendor", "cisco")
                prefix_list_name = record.get("standard_name", "")
                standard_entries = record.get("standard_entries", [])
                device_entries = record.get("device_entries", [])

                logger.info(f"处理设备 {device_ip}, vendor={vendor}, prefix_list={prefix_list_name}")
                logger.info(f"  标准条目数: {len(standard_entries)}, 设备条目数: {len(device_entries)}")

                # 对比标准条目和设备条目，找出需要添加和删除的
                # 设备条目中有但标准条目中没有的 -> 需要删除
                # 标准条目中有但设备条目中没有的 -> 需要添加

                # 将entries转换为可比较的格式（使用seq作为key）
                device_entries_map = {entry.get("seq"): entry for entry in device_entries}
                standard_entries_map = {entry.get("seq"): entry for entry in standard_entries}

                add_entries = []
                delete_entries = []

                # 找出需要添加的（标准中有但设备中没有）
                for seq, entry in standard_entries_map.items():
                    if seq not in device_entries_map:
                        add_entries.append(entry)
                        logger.info(f"  需要添加条目 seq={seq}: {entry}")

                # 找出需要删除的（设备中有但标准中没有）
                for seq, entry in device_entries_map.items():
                    if seq not in standard_entries_map:
                        delete_entries.append(entry)
                        logger.info(f"  需要删除条目 seq={seq}: {entry}")

                # 如果没有需要变更的内容，跳过
                if not add_entries and not delete_entries:
                    logger.info(f"设备 {device_ip} 配置已与标准一致，跳过")
                    skipped_devices.append(device_ip)
                    continue

                logger.info(f"设备 {device_ip}: 添加 {len(add_entries)} 条，删除 {len(delete_entries)} 条")

                # 获取对应厂商的编码器
                encoder = get_encoder(vendor)

                # 生成删除配置命令
                cmd_delete = ""
                if delete_entries:
                    delete_data = {
                        "prefix_lists": [{
                            "name": prefix_list_name,
                            "entries": delete_entries
                        }]
                    }
                    cmd_delete = encoder.encode(delete_data, sections=['prefix_lists'], operation='delete')
                    logger.info(f"  删除命令:\n{cmd_delete}")

                # 生成添加配置命令
                cmd_add = ""
                if add_entries:
                    add_data = {
                        "prefix_lists": [{
                            "name": prefix_list_name,
                            "entries": add_entries
                        }]
                    }
                    cmd_add = encoder.encode(add_data, sections=['prefix_lists'], operation='add')
                    logger.info(f"  添加命令:\n{cmd_add}")

                # 合并执行命令（先删除后添加）
                cmd_exec_parts = []
                if cmd_delete:
                    cmd_exec_parts.append(cmd_delete)
                if cmd_add:
                    cmd_exec_parts.append(cmd_add)
                cmd_exec = "\n".join(cmd_exec_parts)

                # 生成回滚命令（反向操作）
                cmd_roll_parts = []
                if cmd_add:
                    cmd_roll_parts.append(encoder.encode(add_data, sections=['prefix_lists'], operation='delete'))
                if cmd_delete:
                    cmd_roll_parts.append(encoder.encode(delete_data, sections=['prefix_lists'], operation='add'))
                cmd_roll = "\n".join(cmd_roll_parts)

                logger.info(f"  回滚命令:\n{cmd_roll}")

                # 添加到设备列表
                devices_data.append({
                    "ip": device_ip,
                    "batch": 1,
                    "cmd_exec": cmd_exec,
                    "cmd_roll": cmd_roll,
                    "tag": f"prefix-list:{prefix_list_name}"
                })

                logger.info(f"设备 {device_ip} 配置生成成功")

            except Exception as e:
                logger.error(f"处理问题记录 {record.get('id')} 配置生成失败: {e}", exc_info=True)
                failed_devices.append(record.get('device_ip'))

        if len(devices_data) == 0:
            message = "所有设备配置生成失败或无需变更"
            if skipped_devices:
                message += f"（跳过 {len(skipped_devices)} 台已一致的设备）"
            return {
                "success": False,
                "message": message,
                "data": {
                    "failed_devices": failed_devices,
                    "skipped_devices": skipped_devices
                }
            }

        logger.info(f"共生成 {len(devices_data)} 台设备的配置命令")

        # 4. 打印提交内容（暂不创建工单）
        logger.info("="*80)
        logger.info("工单基本信息:")
        logger.info(f"  标题: {order_data['title']}")
        logger.info(f"  描述: {order_data['descrip']}")
        logger.info(f"  类型: {order_data['op_type']}")
        logger.info("")
        logger.info("设备配置列表:")
        for idx, device in enumerate(devices_data, 1):
            logger.info(f"  设备 {idx}: {device['ip']}")
            logger.info(f"    批次: {device['batch']}")
            logger.info(f"    标签: {device['tag']}")
            logger.info(f"    执行命令:\n{device['cmd_exec']}")
            logger.info(f"    回滚命令:\n{device['cmd_roll']}")
            logger.info("")
        logger.info("="*80)

        # 返回预览结果
        result = {
            "success": True,
            "message": f"配置生成成功，共 {len(devices_data)} 台设备（预览模式，未创建工单）",
            "data": {
                "order_data": order_data,
                "devices_data": devices_data,
                "device_count": len(devices_data),
                "failed_devices": failed_devices,
                "skipped_devices": skipped_devices
            }
        }

        if failed_devices:
            result["message"] += f"，配置生成失败: {', '.join(failed_devices)}"

        if skipped_devices:
            result["message"] += f"，跳过已一致设备: {len(skipped_devices)} 台"

        return result

        # TODO: 验证通过后，取消下面的注释以启用工单创建
        # result = create_order_with_devices(order_data, devices_data, username)
        # if failed_devices and result.get("success"):
        #     result["message"] += f"，配置生成失败: {', '.join(failed_devices)}"
        #     if "data" in result:
        #         result["data"]["config_failed_devices"] = failed_devices
        # if skipped_devices and result.get("success"):
        #     result["message"] += f"，跳过已一致设备: {len(skipped_devices)} 台"
        #     if "data" in result:
        #         result["data"]["skipped_devices"] = skipped_devices
        # return result

    except Exception as err:
        logger.error(f"创建前缀列表变更工单失败: {err}", exc_info=True)
        return {
            "success": False,
            "message": f"创建工单失败: {str(err)}"
        }
