"""
地址组管理中间方法

地址组以组名被 ACL 规则引用而不展开，因此额外提供引用计数：
删除之前需要知道它被多少条标准规则引用，避免产生悬空引用。

条目结构与设备记录（采集侧）保持一致：{seq, kind:"network"|"host", addresses:[...], description}。
对应表：addrgroup_standards，见 tables/AddrGroupDB.py
"""
from utils.fingerprint import calculate_fingerprint
from tables.AddrGroupDB import AddrGroupDB
from tables.AccessListDB import AccessListDB
from function_policy.func_access_list import normalize_entries
from function_policy.func_issue import (
    OBJECT_TYPE_ADDRGROUP,
    batch_create_issue_records
)
import logging

logger = logging.getLogger(__name__)


def calculate_addrgroup_fingerprint(name, acl_type, entries):
    """
    计算地址组配置指纹
    :param name: 地址组名称
    :param acl_type: 地址族 ipv4 / ipv6
    :param entries: 条目列表
    :return: SHA256 指纹字符串
    """
    try:
        # acl_type 参与指纹：同名不同族是两条独立配置
        # 字段结构需与采集侧 func_access_list.calculate_group_fingerprint 保持一致，
        # 否则同一份配置在"标准规则"和"设备记录"两边算出的指纹不相等
        fingerprint = calculate_fingerprint({
            "group_name": name,
            "acl_type": acl_type,
            "entries": entries
        })
        return fingerprint
    except Exception as err:
        logger.error(f"计算地址组指纹失败: {err}")
        return None


def get_group_reference_count(name):
    """
    统计地址组被多少条 ACL 标准规则引用
    :param name: 地址组名称
    :return: 被引用的规则条数
    """
    try:
        db = AccessListDB()
        standards = db.getStandardsList({})

        if standards == "failed":
            return 0

        count = 0
        for standard in standards:
            for entry in standard.get("entries") or []:
                # 地址组只出现在源/目的地址位
                hit = any(
                    (entry.get(key) or {}).get("type") == "addrgroup"
                    and (entry.get(key) or {}).get("name") == name
                    for key in ("src", "dst")
                )
                if hit:
                    # 一条规则里引用多次也只算一条规则
                    count += 1
                    break

        return count

    except Exception as err:
        logger.error(f"统计地址组引用失败: {err}")
        return 0


def get_group_list(data):
    """
    获取地址组列表（附带引用计数）
    :param data: {keyword/name, acl_type, is_active}
    :return: {success: bool, data: [], message: str}
    """
    try:
        # 页面的搜索框走 keyword，库层按 name 查询
        query = {"acl_type": data.get("acl_type")}
        keyword = data.get("name") or data.get("keyword")
        if keyword:
            query["name"] = keyword
        if data.get("is_active") is not None and data.get("is_active") != "":
            query["is_active"] = data["is_active"]

        db = AddrGroupDB()
        result = db.getGroupsList(query)

        if result == "failed":
            return {"success": False, "message": "查询失败"}

        for group in result:
            group["ref_count"] = get_group_reference_count(group["name"])

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取地址组列表失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_group_detail(group_id):
    """
    获取地址组详情（附带引用计数）
    :param group_id: 规则ID
    :return: {success: bool, data: {}, message: str}
    """
    try:
        db = AddrGroupDB()
        result = db.getGroupDetail({"id": group_id})

        if result == "failed":
            return {"success": False, "message": "规则不存在"}

        result["ref_count"] = get_group_reference_count(result["name"])

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取地址组详情失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def create_group(data, username):
    """
    创建地址组标准规则（包含指纹计算）
    :param data: {name, acl_type, entries, description, is_active}
    :param username: 创建人
    :return: {success: bool, data: {id, fingerprint}, message: str}
    """
    try:
        if "name" not in data or "entries" not in data:
            return {"success": False, "message": "缺少必要参数: name, entries"}

        acl_type = data.get("acl_type", "ipv4")
        entries = data["entries"]

        fingerprint = calculate_addrgroup_fingerprint(data["name"], acl_type, entries)
        if not fingerprint:
            return {"success": False, "message": "计算配置指纹失败"}

        create_data = {
            "name": data["name"],
            "acl_type": acl_type,
            "fingerprint": fingerprint,
            "entries": entries,
            "description": data.get("description", ""),
            "is_active": data.get("is_active", 1),
            "created_by": username
        }

        db = AddrGroupDB()
        result = db.createGroup(create_data)

        if result != "failed":
            return {"success": True, "data": {"id": result, "fingerprint": fingerprint}, "message": "创建成功"}
        else:
            return {"success": False, "message": "创建失败，可能存在重复的规则"}

    except Exception as err:
        logger.error(f"创建地址组失败: {err}")
        return {"success": False, "message": f"创建失败: {str(err)}"}


def update_group(data, username):
    """
    更新地址组标准规则（如果更新 entries 或 name/acl_type 则重新计算指纹）
    :param data: {id, name, acl_type, entries, description, is_active}
    :param username: 更新人
    :return: {success: bool, message: str}
    """
    try:
        if "id" not in data:
            return {"success": False, "message": "缺少参数: id"}

        # 指纹依赖 name + acl_type + entries，任一变化都要重算
        if "entries" in data or "name" in data or "acl_type" in data:
            db = AddrGroupDB()
            current = db.getGroupDetail({"id": data["id"]})
            if current == "failed":
                return {"success": False, "message": "规则不存在"}

            entries = data["entries"] if "entries" in data else current["entries"]
            name = data.get("name", current["name"])
            acl_type = data.get("acl_type", current["acl_type"])

            fingerprint = calculate_addrgroup_fingerprint(name, acl_type, entries)
            if not fingerprint:
                return {"success": False, "message": "计算配置指纹失败"}

            data["fingerprint"] = fingerprint
            data["entries"] = entries

        db = AddrGroupDB()
        result = db.updateGroup(data)

        if result != "failed" and result > 0:
            return {"success": True, "message": "更新成功"}
        else:
            return {"success": False, "message": "更新失败，规则可能不存在"}

    except Exception as err:
        logger.error(f"更新地址组失败: {err}")
        return {"success": False, "message": f"更新失败: {str(err)}"}


def delete_group(group_id):
    """
    删除地址组标准规则
    :param group_id: 规则ID
    :return: {success: bool, message: str}
    """
    try:
        db = AddrGroupDB()
        result = db.deleteGroup({"id": group_id})

        if result != "failed" and result > 0:
            return {"success": True, "message": "删除成功"}
        else:
            return {"success": False, "message": "删除失败，规则可能不存在"}

    except Exception as err:
        logger.error(f"删除地址组失败: {err}")
        return {"success": False, "message": f"删除失败: {str(err)}"}


def toggle_group_active(group_id):
    """
    切换地址组标准规则的启用状态
    :param group_id: 规则ID
    :return: {success: bool, message: str}
    """
    try:
        db = AddrGroupDB()
        current = db.getGroupDetail({"id": group_id})

        if current == "failed":
            return {"success": False, "message": "规则不存在"}

        new_value = 0 if current["is_active"] else 1

        db = AddrGroupDB()
        result = db.updateGroup({"id": group_id, "is_active": new_value})

        if result != "failed" and result > 0:
            return {"success": True, "message": "状态更新成功"}
        else:
            return {"success": False, "message": "状态更新失败"}

    except Exception as err:
        logger.error(f"切换地址组状态失败: {err}")
        return {"success": False, "message": f"状态更新失败: {str(err)}"}


def get_group_statistics(standard_id):
    """
    获取地址组的设备应用统计
    :param standard_id: 标准规则ID
    :return: {total, matched, matched_other, drifted, rate}
    """
    try:
        db = AddrGroupDB()
        standard = db.getGroupDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        return {
            "success": True,
            "data": get_device_statistics_for_group(
                standard["name"],
                standard["acl_type"],
                standard["fingerprint"]
            ),
            "message": "查询成功"
        }

    except Exception as err:
        logger.error(f"获取地址组统计失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_group_device_list(standard_id, filter_type='all'):
    """
    获取地址组关联的设备列表
    :param standard_id: 标准规则ID
    :param filter_type: 过滤类型 'all' | 'matched' | 'matched_other' | 'drifted'
    :return: {success: bool, data: [], message: str}
    """
    try:
        db = AddrGroupDB()
        standard = db.getGroupDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        return {
            "success": True,
            "data": get_device_list_for_group(
                standard["name"],
                standard["acl_type"],
                standard["fingerprint"],
                filter_type
            ),
            "message": "查询成功"
        }

    except Exception as err:
        logger.error(f"获取地址组设备列表失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_group_records_list(data):
    """
    获取地址组的设备配置记录列表
    :param data: {device_ip, group_name, fingerprint}
    :return: {success: bool, data: [], message: str}
    """
    try:
        query = {}
        for key in ("device_ip", "group_name", "fingerprint"):
            if data.get(key):
                query[key] = data[key]

        db = AddrGroupDB()
        result = db.getRecordsList(query)

        if result == "failed":
            return {"success": False, "message": "查询失败"}

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取地址组设备记录失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_device_statistics_for_group(group_name, acl_type, standard_fingerprint):
    """
    获取地址组的设备应用统计
    :param group_name: 地址组名称（用于查询 records 表的 group_name）
    :param acl_type: 地址族
    :param standard_fingerprint: 标准指纹
    :return: {total, matched, matched_other, drifted, rate}
    """
    try:
        # 同名同族但内容不同的其他标准规则，设备命中的算"匹配其他"
        db1 = AddrGroupDB()
        all_standards = db1.getGroupsList({"name": group_name, "acl_type": acl_type})
        if all_standards == "failed":
            other_fingerprints = []
        else:
            other_fingerprints = [s["fingerprint"] for s in all_standards if s["fingerprint"] != standard_fingerprint]

        db2 = AddrGroupDB()
        records = db2.getRecordsList({"group_name": group_name})

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
        logger.error(f"获取地址组设备统计失败: {err}")
        return {"total": 0, "matched": 0, "matched_other": 0, "drifted": 0, "rate": 0}


def get_device_list_for_group(group_name, acl_type, standard_fingerprint, filter_type='all'):
    """
    获取地址组关联的设备列表
    :param group_name: 地址组名称
    :param acl_type: 地址族
    :param standard_fingerprint: 标准指纹
    :param filter_type: 过滤类型 'all' | 'matched' | 'matched_other' | 'drifted'
    :return: 设备列表
    """
    try:
        db1 = AddrGroupDB()
        all_standards = db1.getGroupsList({"name": group_name, "acl_type": acl_type})
        if all_standards == "failed":
            other_fingerprints = []
        else:
            other_fingerprints = [s["fingerprint"] for s in all_standards if s["fingerprint"] != standard_fingerprint]

        db2 = AddrGroupDB()
        records = db2.getRecordsList({"group_name": group_name})

        if records == "failed":
            return []

        device_list = []
        for record in records:
            if record["fingerprint"] == standard_fingerprint:
                match_status = "matched"
            elif record["fingerprint"] in other_fingerprints:
                match_status = "matched_other"
            else:
                match_status = "drifted"

            if filter_type == 'all' or filter_type == match_status:
                entries = normalize_entries(record.get("entries"))
                device_list.append({
                    "device_ip": record["device_ip"],
                    "device_name": record["device_name"],
                    "vendor": record["vendor"],
                    "fingerprint": record["fingerprint"],
                    "entry_count": len(entries),
                    "entries": entries,
                    "match_status": match_status,
                    "collected_at": record["collected_at"]
                })

        return device_list

    except Exception as err:
        logger.error(f"获取地址组设备列表失败: {err}")
        return []


def compare_group_with_standard(standard_id, device_ip):
    """
    对比设备配置与地址组标准配置
    :param standard_id: 标准规则ID
    :param device_ip: 设备IP
    :return: {success: bool, data: {standard, device}, message: str}
    """
    try:
        db = AddrGroupDB()
        standard = db.getGroupDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        # DB 方法各自在 finally 关闭连接，同一实例不能连续调用两次
        records = AddrGroupDB().getRecordsList({
            "device_ip": device_ip,
            "group_name": standard["name"]
        })

        if records == "failed" or len(records) == 0:
            return {"success": False, "message": "设备配置不存在"}

        device_record = records[0]  # 取最新的记录

        result = {
            "standard": {
                "id": standard["id"],
                "name": standard["name"],
                "acl_type": standard["acl_type"],
                "fingerprint": standard["fingerprint"],
                "entries": normalize_entries(standard["entries"])
            },
            "device": {
                "ip": device_record["device_ip"],
                "name": device_record["device_name"],
                "vendor": device_record["vendor"],
                "fingerprint": device_record["fingerprint"],
                "entries": normalize_entries(device_record["entries"]),
                "collected_at": device_record["collected_at"]
            }
        }

        return {"success": True, "data": result, "message": "对比成功"}

    except Exception as err:
        logger.error(f"地址组配置对比失败: {err}")
        return {"success": False, "message": f"对比失败: {str(err)}"}


def group_entry_to_text(entry):
    """
    将地址组条目渲染为可读文本（用于差异对比展示）
    :param entry: {seq, kind:"network"|"host", addresses:[...], description}
    :return: 单行文本，如 "10.0.0.0/8"
    """
    if not entry:
        return ""

    addresses = entry.get("addresses") or []
    return ", ".join(addresses)


def compare_group_text_diff(src_entries, target_entries, full_diff=False):
    """
    对比两组地址组条目并生成HTML格式的文本差异
    :param src_entries: 源条目列表（显示在左侧，通常是标准配置）
    :param target_entries: 目标条目列表（显示在右侧，通常是设备配置）
    :param full_diff: True=完整对比, False=上下文对比
    :return: {"success": bool, "data": {"html": str}, "message": str}
    """
    try:
        from function_tools.text_diff_tool import check_diff_simple

        src_text = "\n".join(group_entry_to_text(e) for e in normalize_entries(src_entries))
        target_text = "\n".join(group_entry_to_text(e) for e in normalize_entries(target_entries))

        html_result = check_diff_simple(src_text, target_text, full_diff=full_diff)

        return {"success": True, "data": {"html": html_result}, "message": "对比成功"}

    except Exception as err:
        logger.error(f"地址组文本对比失败: {err}")
        return {"success": False, "message": f"对比失败: {str(err)}"}


def batch_create_group_issues(standard_id, devices, username, remark=""):
    """
    批量创建地址组问题处理记录
    :param standard_id: 标准规则ID
    :param devices: 设备列表 [{device_ip, device_name, vendor, device_entries}]
    :param username: 创建人
    :param remark: 统一备注
    :return: {success: bool, data: {created, success, failed}, message: str}
    """
    try:
        db = AddrGroupDB()
        standard = db.getGroupDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        devices_with_remark = []
        for device in devices:
            device_copy = device.copy()
            device_copy["remark"] = remark
            devices_with_remark.append(device_copy)

        result = batch_create_issue_records(
            OBJECT_TYPE_ADDRGROUP,
            standard_id,
            standard["name"],
            normalize_entries(standard["entries"]),
            devices_with_remark,
            username
        )

        return {
            "success": True,
            "data": {
                "created": len(result["success"]),
                "success": result["success"],
                "failed": result["failed"]
            },
            "message": f"创建完成，成功{len(result['success'])}条，失败{len(result['failed'])}条"
        }

    except Exception as err:
        logger.error(f"批量创建地址组问题记录失败: {err}")
        return {"success": False, "message": f"批量创建失败: {str(err)}"}
