"""
ACL 管理中间方法
提供指纹计算、配置对比、统计分析等功能

说明：
1. 三类对象（ACL / 地址组 / 端口组）在库表中独立存放，ACL 规则内以组名引用，采集时不展开
2. 地址组/端口组的设备配置采集到 addrgroup_records / portgroup_records
"""
from utils.fingerprint import calculate_fingerprint, sort_entries_by_seq
from tables.AccessListDB import AccessListDB
from tables.AddrGroupDB import AddrGroupDB
from tables.PortGroupDB import PortGroupDB
from tables.PolicyIssueDB import PolicyIssueDB
from tables.CollectDB import CollectDB
from function_collector.func_config import get_latest_config_by_ip
from function_tools.text_diff_tool import check_diff_simple
from lib_config import get_parser, get_encoder
from function_policy.func_issue import (
    OBJECT_TYPE_ACL,
    batch_create_issue_records,
    diff_entries_by_seq,
    build_device_commands,
    create_change_order
)
import json
import logging

logger = logging.getLogger(__name__)


def calculate_access_list_fingerprint(name, acl_type, entries):
    """
    计算 ACL 配置指纹
    :param name: ACL 名称
    :param acl_type: 地址族 ipv4 / ipv6
    :param entries: 条目列表
    :return: SHA256 指纹字符串
    """
    try:
        # acl_type 必须参与指纹：ip access-list 3999 与 ipv6 access-list 3999 是两条独立配置
        fingerprint = calculate_fingerprint({
            "name": name,
            "acl_type": acl_type,
            "entries": entries
        })
        return fingerprint
    except Exception as err:
        logger.error(f"计算指纹失败: {err}")
        return None


def calculate_group_fingerprint(name, acl_type, entries):
    """
    计算地址组/端口组配置指纹
    :param name: 组名
    :param acl_type: 地址族 ipv4 / ipv6
    :param entries: 条目列表
    :return: SHA256 指纹字符串
    """
    try:
        # acl_type 必须参与指纹：同名组在 v4/v6 下是不同的配置
        fingerprint = calculate_fingerprint({
            "group_name": name,
            "acl_type": acl_type,
            "entries": entries
        })
        return fingerprint
    except Exception as err:
        logger.error(f"计算组指纹失败: {err}")
        return None


def normalize_entries(entries):
    """
    统一 entries 形态为裸数组
    :param entries: 可能是 {"entries": [...]} 或 [...]
    :return: 条目列表
    """
    if isinstance(entries, dict):
        return entries.get("entries", [])
    if isinstance(entries, list):
        return entries
    return []


def entry_to_text(entry):
    """
    将标准化规则条目渲染为可读文本（用于差异对比展示）
    :param entry: AclEntry.to_dict() 的结果
    :return: 单行文本，如 "10 permit tcp 10.0.0.0/8 any eq 80"
    """
    def addr_text(spec):
        if not spec:
            return "any"
        spec_type = spec.get("type")
        if spec_type == "any":
            return "any"
        if spec_type == "addrgroup":
            return f"addrgroup {spec.get('name', '')}"
        return spec.get("address", "") or "any"

    def port_text(spec):
        if not spec:
            return ""
        spec_type = spec.get("type")
        if spec_type == "portgroup":
            return f"portgroup {spec.get('name', '')}"
        if spec_type == "direct":
            ports = " ".join(str(p) for p in spec.get("ports", []) if p is not None and p != "")
            return f"{spec.get('op', '')} {ports}".strip()
        return ""

    parts = [
        str(entry.get("seq", "")),
        entry.get("action", ""),
        entry.get("protocol", ""),
        addr_text(entry.get("src"))
    ]
    src_port = port_text(entry.get("src_port"))
    if src_port:
        parts.append(src_port)
    parts.append(addr_text(entry.get("dst")))
    dst_port = port_text(entry.get("dst_port"))
    if dst_port:
        parts.append(dst_port)

    options = entry.get("options") or {}
    for key in sorted(options.keys()):
        if options[key]:
            parts.append(key)

    return " ".join(p for p in parts if p != "")


def get_standard_list(data):
    """
    获取标准规则列表
    :param data: {keyword/name, acl_type, is_active, ...}，keyword 兼容页面搜索框
    :return: {success: bool, data: [], message: str}
    """
    try:
        query = dict(data or {})
        # 页面的搜索框走 keyword，库层按 name 查询
        if query.get("keyword") and not query.get("name"):
            query["name"] = query["keyword"]

        db = AccessListDB()
        result = db.getStandardsList(query)

        if result == "failed":
            return {"success": False, "message": "查询失败"}

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取ACL标准规则列表失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_standard_detail(standard_id):
    """
    获取标准规则详情
    :param standard_id: 规则ID
    :return: {success: bool, data: {}, message: str}
    """
    try:
        db = AccessListDB()
        result = db.getStandardDetail({"id": standard_id})

        if result == "failed":
            return {"success": False, "message": "标准规则不存在"}

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取ACL标准规则详情失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_records_list(data):
    """
    获取设备配置记录列表
    :param data: {device_ip, standard_name, fingerprint, ...}
    :return: {success: bool, data: [], message: str}
    """
    try:
        query = dict(data or {})

        # 列表页的 ACL 名称筛选用模糊匹配，精确查询仍走 acl_name
        if query.get("acl_name"):
            query["acl_name_like"] = query.pop("acl_name")

        db = AccessListDB()
        result = db.getRecordsList(query)

        if result == "failed":
            return {"success": False, "message": "查询失败"}

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取ACL设备配置记录列表失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def create_standard(data, username):
    """
    创建标准规则（包含指纹计算）
    :param data: {name, acl_number, acl_type, acl_kind, entries, description, is_active}
    :param username: 创建人
    :return: {success: bool, data: {id, fingerprint}, message: str}
    """
    try:
        # 校验必填参数
        if "name" not in data or "entries" not in data:
            return {"success": False, "message": "缺少必要参数: name, entries"}

        acl_type = data.get("acl_type", "ipv4")
        entries_list = normalize_entries(data["entries"])
        # 条目先按 seq 排序，保证存储顺序、指纹、后续命令生成口径一致
        entries_list = sort_entries_by_seq(entries_list)

        # 计算指纹
        fingerprint = calculate_access_list_fingerprint(data["name"], acl_type, entries_list)
        if not fingerprint:
            return {"success": False, "message": "计算配置指纹失败"}

        # 准备数据
        create_data = {
            "name": data["name"],
            "acl_number": data.get("acl_number"),
            "acl_type": acl_type,
            "acl_kind": data.get("acl_kind"),
            "fingerprint": fingerprint,
            "entries": entries_list,
            "description": data.get("description", ""),
            "is_active": data.get("is_active", 1),
            "created_by": username
        }

        db = AccessListDB()
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
    更新标准规则（如果更新 entries 或 name/acl_type 则重新计算指纹）
    :param data: {id, name, acl_number, acl_type, acl_kind, entries, description, is_active}
    :param username: 更新人
    :return: {success: bool, message: str}
    """
    try:
        if "id" not in data:
            return {"success": False, "message": "缺少参数: id"}

        # 指纹依赖 name + acl_type + entries，任一变化都要重算
        if "entries" in data or "name" in data or "acl_type" in data:
            db = AccessListDB()
            current = db.getStandardDetail({"id": data["id"]})
            if current == "failed":
                return {"success": False, "message": "规则不存在"}

            if "entries" in data:
                entries_list = normalize_entries(data["entries"])
            else:
                entries_list = normalize_entries(current["entries"])

            # 条目先按 seq 排序，保证存储顺序、指纹、后续命令生成口径一致
            entries_list = sort_entries_by_seq(entries_list)

            name = data.get("name", current["name"])
            acl_type = data.get("acl_type", current["acl_type"])

            fingerprint = calculate_access_list_fingerprint(name, acl_type, entries_list)
            if not fingerprint:
                return {"success": False, "message": "计算配置指纹失败"}

            data["fingerprint"] = fingerprint
            data["entries"] = entries_list

        db = AccessListDB()
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
        db = AccessListDB()
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
    :return: {success: bool, data: {total, matched, matched_other, drifted, rate}, message: str}
    """
    try:
        db = AccessListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        statistics = get_device_statistics_for_standard(
            standard["name"],
            standard["acl_type"],
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
    :param filter_type: 过滤类型 'all' | 'matched' | 'matched_other' | 'drifted'
    :return: {success: bool, data: [], message: str}
    """
    try:
        db = AccessListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        device_list = get_device_list_for_standard(
            standard["name"],
            standard["acl_type"],
            standard["fingerprint"],
            filter_type
        )

        return {"success": True, "data": device_list, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取标准规则设备列表失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def compare_record_with_standard(standard_id, device_ip):
    """
    对比设备配置与标准配置
    :param standard_id: 标准规则ID
    :param device_ip: 设备IP
    :return: {success: bool, data: {standard, device, comparison}, message: str}
    """
    try:
        db = AccessListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        # 按名称 + 地址族定位设备上的同一个 ACL
        # DB 方法各自在 finally 关闭连接，同一实例不能连续调用两次
        db2 = AccessListDB()
        records = db2.getRecordsList({
            "device_ip": device_ip,
            "acl_name": standard["name"],
            "acl_type": standard["acl_type"]
        })

        if records == "failed" or len(records) == 0:
            return {"success": False, "message": "设备配置不存在"}

        device_record = records[0]  # 取最新的记录

        standard_entries = normalize_entries(standard["entries"])
        device_entries = normalize_entries(device_record["entries"])

        comparison = compare_configurations(standard_entries, device_entries)

        result = {
            "standard": {
                "id": standard["id"],
                "name": standard["name"],
                "acl_type": standard["acl_type"],
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
    :param device_name: 设备名称（可选，用于 missing 类型）
    :param device_vendor: 设备厂商（可选，用于 missing 类型）
    :param remark: 备注
    :param username: 创建人
    :return: {success: bool, data: {id}, message: str}
    """
    try:
        db = AccessListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        db2 = AccessListDB()
        records = db2.getRecordsList({
            "device_ip": device_ip,
            "acl_name": standard["name"],
            "acl_type": standard["acl_type"]
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
            device_entries = normalize_entries(device_record["entries"])

        standard_entries = normalize_entries(standard["entries"])

        create_data = {
            "object_type": OBJECT_TYPE_ACL,
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

        issue_db = PolicyIssueDB()
        result = issue_db.createIssueRecord(create_data)

        if result != "failed":
            return {"success": True, "data": {"id": result}, "message": "创建成功"}
        else:
            return {"success": False, "message": "创建失败"}

    except Exception as err:
        logger.error(f"创建问题处理记录失败: {err}")
        return {"success": False, "message": f"创建失败: {str(err)}"}


def batch_create_issues(standard_id, devices, username, remark=""):
    """
    批量创建问题处理记录
    :param standard_id: 标准规则ID
    :param devices: 设备列表
    :param username: 创建人
    :param remark: 统一备注
    :return: {success: bool, data: {success: [], failed: []}, message: str}
    """
    try:
        db = AccessListDB()
        standard = db.getStandardDetail({"id": standard_id})

        if standard == "failed":
            return {"success": False, "message": "标准规则不存在"}

        standard_entries = normalize_entries(standard["entries"])

        # 为每个设备添加统一的备注
        devices_with_remark = []
        for device in devices:
            device_copy = device.copy()
            device_copy["remark"] = remark
            devices_with_remark.append(device_copy)

        result = batch_create_issue_records(
            OBJECT_TYPE_ACL,
            standard_id,
            standard["name"],
            standard_entries,
            devices_with_remark,
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


def get_device_statistics_for_standard(standard_name, acl_type, standard_fingerprint):
    """
    获取标准规则的设备应用统计
    :param standard_name: 标准规则名称（用于查询 records 表的 acl_name）
    :param acl_type: 地址族（同名不同族是两条独立 ACL）
    :param standard_fingerprint: 标准指纹
    :return: {total, matched, matched_other, drifted, rate}
    """
    try:
        # 获取同名的其他标准规则的指纹（同名同族不同内容，视为"匹配其他"）
        db1 = AccessListDB()
        all_standards = db1.getStandardsList({"name": standard_name, "acl_type": acl_type})
        if all_standards == "failed":
            other_fingerprints = []
        else:
            other_fingerprints = [s["fingerprint"] for s in all_standards if s["fingerprint"] != standard_fingerprint]

        # 查询该 ACL 名称下的所有设备记录
        db2 = AccessListDB()
        records = db2.getRecordsList({"acl_name": standard_name, "acl_type": acl_type})

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


def get_device_list_for_standard(standard_name, acl_type, standard_fingerprint, filter_type='all'):
    """
    获取标准规则关联的设备列表
    :param standard_name: 标准规则名称
    :param acl_type: 地址族
    :param standard_fingerprint: 标准指纹
    :param filter_type: 过滤类型 'all' | 'matched' | 'matched_other' | 'drifted'
    :return: 设备列表
    """
    try:
        db1 = AccessListDB()
        all_standards = db1.getStandardsList({"name": standard_name, "acl_type": acl_type})
        if all_standards == "failed":
            other_fingerprints = []
        else:
            other_fingerprints = [s["fingerprint"] for s in all_standards if s["fingerprint"] != standard_fingerprint]

        db2 = AccessListDB()
        records = db2.getRecordsList({"acl_name": standard_name, "acl_type": acl_type})

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
                device_entry = device_dict[seq]
                # 整条规则逐字段比对（seq/action/protocol/src/src_port/dst/dst_port/options）
                if _entry_signature(entry) != _entry_signature(device_entry):
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


def _entry_signature(entry):
    """
    生成条目的可比签名（忽略 seq，seq 已经作为比对 key）
    :param entry: 规则条目
    :return: 规范化 JSON 字符串
    """
    return json.dumps({
        "action": entry.get("action"),
        "protocol": entry.get("protocol"),
        "src": entry.get("src"),
        "src_port": entry.get("src_port"),
        "dst": entry.get("dst"),
        "dst_port": entry.get("dst_port"),
        "options": entry.get("options") or {}
    }, sort_keys=True, ensure_ascii=False)


def collect_and_update_access_lists(ip):
    """
    采集指定设备的 ACL / 地址组 / 端口组配置并更新到数据库
    :param ip: 设备IP地址
    :return: {success: bool, message: str, data: {device_info, access_lists, address_groups, port_groups}}
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

        # 该厂商尚未实现的配置项，解析结果为空不代表设备上真没配置，不能拿来清库
        sections = [s for s in ('access_lists', 'address_groups', 'port_groups')
                    if s in parser.available_sections]
        if not sections:
            return {"success": False, "message": f"设备 {ip} 的厂商 {vendor} 暂不支持ACL/地址组/端口组解析"}

        result = parser.parse(sections=sections)

        access_lists = result.access_lists
        address_groups = result.address_groups
        port_groups = result.port_groups

        # 配置树为空说明配置文本本身不可用（缩进异常等），此时不能拿空结果去清库
        if not parser.config_tree:
            return {"success": False, "message": f"设备 {ip} 配置解析失败，保留历史记录"}

        # 4. 删除该IP的旧记录
        # 即使本次未解析到对应配置也要删除：设备上已把配置删干净时，库里不能留着历史数据
        if 'access_lists' in sections and AccessListDB().deleteRecordsByIP(ip) == "failed":
            return {"success": False, "message": f"删除设备 {ip} ACL旧记录失败"}

        if 'address_groups' in sections and AddrGroupDB().deleteRecordsByIP(ip) == "failed":
            return {"success": False, "message": f"删除设备 {ip} 地址组旧记录失败"}

        if 'port_groups' in sections and PortGroupDB().deleteRecordsByIP(ip) == "failed":
            return {"success": False, "message": f"删除设备 {ip} 端口组旧记录失败"}

        # 5. 准备各对象的批量插入数据
        acl_records = []
        addrgroup_records = []
        portgroup_records = []
        failed_items = []

        for acl_config in access_lists:
            acl_name = acl_config.acl_name
            acl_type = acl_config.acl_type or "ipv4"
            entries = [entry.to_dict() for entry in acl_config.entries]
            # 设备回显顺序不保证按 seq 递增，统一排一次再算指纹和入库
            entries = sort_entries_by_seq(entries)

            # 计算指纹
            fingerprint = calculate_access_list_fingerprint(acl_name, acl_type, entries)
            if not fingerprint:
                failed_items.append({"object": "acl", "name": acl_name, "reason": "计算指纹失败"})
                continue

            acl_records.append({
                "device_ip": ip,
                "device_name": device_name,
                "vendor": vendor,
                "acl_name": acl_name,
                "acl_number": acl_config.acl_number,
                "acl_type": acl_type,
                "acl_kind": acl_config.acl_kind,
                "fingerprint": fingerprint,
                "entries": entries
            })

        for group in address_groups:
            group_name = group.name
            acl_type = group.addr_type or "ipv4"
            entries = [entry.to_dict() for entry in group.entries]
            # 设备回显顺序不保证按 seq 递增，统一排一次再算指纹和入库
            entries = sort_entries_by_seq(entries)

            fingerprint = calculate_group_fingerprint(group_name, acl_type, entries)
            if not fingerprint:
                failed_items.append({"object": "addrgroup", "name": group_name, "reason": "计算指纹失败"})
                continue

            addrgroup_records.append({
                "device_ip": ip,
                "device_name": device_name,
                "vendor": vendor,
                "group_name": group_name,
                "fingerprint": fingerprint,
                "entries": entries
            })

        for group in port_groups:
            group_name = group.name
            entries = [entry.to_dict() for entry in group.entries]
            # 设备回显顺序不保证按 seq 递增，统一排一次再算指纹和入库
            entries = sort_entries_by_seq(entries)

            fingerprint = calculate_group_fingerprint(group_name, "ipv4", entries)
            if not fingerprint:
                failed_items.append({"object": "portgroup", "name": group_name, "reason": "计算指纹失败"})
                continue

            portgroup_records.append({
                "device_ip": ip,
                "device_name": device_name,
                "vendor": vendor,
                "group_name": group_name,
                "fingerprint": fingerprint,
                "entries": entries
            })

        # 6. 批量插入数据库
        def _insert(db_class, records, label):
            """批量插入并汇总失败项"""
            if not records:
                return 0
            insert_result = db_class().addRecordsList(records)
            for item in insert_result.get("failed_items", []):
                failed_items.append({"object": label, **item})
            return insert_result.get("success", 0)

        acl_inserted = _insert(AccessListDB, acl_records, "acl")
        addr_inserted = _insert(AddrGroupDB, addrgroup_records, "addrgroup")
        port_inserted = _insert(PortGroupDB, portgroup_records, "portgroup")

        # 7. 返回结果
        return {
            "success": True,
            "message": (f"成功更新 ACL {acl_inserted} 条、地址组 {addr_inserted} 条、"
                        f"端口组 {port_inserted} 条"),
            "data": {
                "device_info": {
                    "ip": ip,
                    "name": device_name,
                    "vendor": vendor
                },
                "access_lists": {
                    "total": len(access_lists),
                    "inserted": acl_inserted,
                    "failed": len([i for i in failed_items if i.get("object") == "acl"]),
                    "failed_items": [i for i in failed_items if i.get("object") == "acl"]
                },
                "address_groups": {
                    "total": len(address_groups),
                    "inserted": addr_inserted,
                    "failed": len([i for i in failed_items if i.get("object") == "addrgroup"]),
                    "failed_items": [i for i in failed_items if i.get("object") == "addrgroup"]
                },
                "port_groups": {
                    "total": len(port_groups),
                    "inserted": port_inserted,
                    "failed": len([i for i in failed_items if i.get("object") == "portgroup"]),
                    "failed_items": [i for i in failed_items if i.get("object") == "portgroup"]
                }
            }
        }

    except Exception as err:
        logger.error(f"采集并更新ACL失败 [{ip}]: {err}")
        return {
            "success": False,
            "message": f"采集并更新ACL失败: {str(err)}"
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
        # 先按 seq 排序，否则仅顺序不同的两侧会被整段判定为差异
        src_list = sort_entries_by_seq(normalize_entries(src_entries))
        target_list = sort_entries_by_seq(normalize_entries(target_entries))
        src_text = "\n".join(entry_to_text(e) for e in src_list)
        target_text = "\n".join(entry_to_text(e) for e in target_list)

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


def prepare_access_list_devices(record):
    """
    为单条 ACL 问题记录生成变更命令

    :param record: 问题记录（已含 object_type=acl）
    :return: {"cmd_exec", "cmd_roll", "tag"} 或 {"skipped": True}
    """
    device_ip = record.get("device_ip")
    vendor = record.get("device_vendor", "cisco_nx")
    acl_name = record.get("standard_name", "")
    standard_entries = record.get("standard_entries", [])
    device_entries = record.get("device_entries", [])

    logger.info(f"处理设备 {device_ip}, vendor={vendor}, acl={acl_name}")
    logger.info(f"  标准条目数: {len(standard_entries)}, 设备条目数: {len(device_entries)}")

    diff = diff_entries_by_seq(standard_entries, device_entries, _entry_signature)

    if not diff["add"] and not diff["delete"]:
        return {"skipped": True}

    logger.info(f"设备 {device_ip}: 添加 {len(diff['add'])} 条，删除 {len(diff['delete'])} 条")

    encoder = get_encoder(vendor)

    def append_name_type(record, entries):
        # 问题记录不存 acl_type / acl_kind，从标准规则回查；取不到按 ipv4 named 处理
        standard = AccessListDB().getStandardDetail({"id": record.get("standard_id")})
        if standard == "failed":
            acl_type, acl_kind, acl_number = "ipv4", "named", None
        else:
            acl_type = standard.get("acl_type") or "ipv4"
            acl_kind = standard.get("acl_kind") or "named"
            acl_number = standard.get("acl_number")

        return {
            "access_lists": [{
                "acl_name": record.get("standard_name", ""),
                "acl_number": acl_number,
                "acl_type": acl_type,
                "acl_kind": acl_kind,
                "entries": entries
            }]
        }

    commands = build_device_commands(
        record,
        diff,
        encoder,
        sections=['access_lists'],
        entry_diff_applier=append_name_type
    )

    commands["tag"] = f"acl:{acl_name}"

    return commands

