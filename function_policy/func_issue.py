"""
策略配置问题处理通用方法

前缀列表 / ACL / 地址组 / 端口组 的问题处理流程完全一致：
都是「标准配置 vs 设备配置」的对比结果，区别只在 entries 的字段结构和命令编码方式。
因此状态流转、批量建记录、按类型生成变更工单这些通用逻辑集中在本模块；
各类型专有的部分（前缀看 prefix/ge/le，ACL 看 src/dst/port）留在各自模块，
按 object_type 惰性导入。

对应表：policy_issue_records，用 object_type 区分对象类型。
"""
from tables.PolicyIssueDB import PolicyIssueDB
from function_op.order_manage import create_order_with_devices
import logging

logger = logging.getLogger(__name__)

# 对象类型常量，与 policy_issue_records.object_type 取值一致
OBJECT_TYPE_PREFIX_LIST = "prefix_list"
OBJECT_TYPE_ACL = "acl"
OBJECT_TYPE_ADDRGROUP = "addrgroup"
OBJECT_TYPE_PORTGROUP = "portgroup"

# 对象类型的中文名，用于工单标题
OBJECT_TYPE_LABELS = {
    OBJECT_TYPE_PREFIX_LIST: "前缀列表",
    OBJECT_TYPE_ACL: "ACL",
    OBJECT_TYPE_ADDRGROUP: "地址组",
    OBJECT_TYPE_PORTGROUP: "端口组",
}


def get_object_type_label(object_type):
    """获取对象类型的中文名"""
    return OBJECT_TYPE_LABELS.get(object_type, object_type)


def _get_prepare_devices(object_type):
    """
    按对象类型取得命令生成函数

    各类型模块在生成命令上的差异（编码器入参、sections、缺失 encoder）封装在各自的
    prepare_xxx_devices 里，本模块只负责调度。惰性导入避免循环依赖。
    """
    if object_type == OBJECT_TYPE_PREFIX_LIST:
        from function_policy.func_prefix import prepare_prefix_list_devices
        return prepare_prefix_list_devices
    if object_type == OBJECT_TYPE_ACL:
        from function_policy.func_access_list import prepare_access_list_devices
        return prepare_access_list_devices
    if object_type == OBJECT_TYPE_ADDRGROUP:
        from function_policy.func_addrgroup import prepare_addrgroup_devices
        return prepare_addrgroup_devices
    if object_type == OBJECT_TYPE_PORTGROUP:
        from function_policy.func_portgroup import prepare_portgroup_devices
        return prepare_portgroup_devices
    return None


def get_issue_list(data):
    """
    获取问题处理记录列表（跨对象类型，object_type 为空查全部）
    :param data: 查询条件，见 PolicyIssueDB.getIssueRecordsList
    :return: {success: bool, data: [], message: str}
    """
    try:
        db = PolicyIssueDB()
        result = db.getIssueRecordsList(data or {})

        if result == "failed":
            return {"success": False, "message": "查询失败"}

        # 附带中文标签，前端无需再维护一份映射
        for record in result:
            record["object_type_label"] = get_object_type_label(record.get("object_type"))

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取问题处理记录列表失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_issue_detail(data):
    """
    获取问题处理记录详情
    :param data: {id}
    :return: {success: bool, data: {}, message: str}
    """
    try:
        if not data or "id" not in data:
            return {"success": False, "message": "缺少参数: id"}

        db = PolicyIssueDB()
        result = db.getIssueRecordDetail({"id": data["id"]})

        if result == "failed":
            return {"success": False, "message": "记录不存在"}

        result["object_type_label"] = get_object_type_label(result.get("object_type"))
        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取问题处理记录详情失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def delete_issue(data):
    """
    删除问题处理记录
    :param data: {id}
    :return: {success: bool, message: str}
    """
    try:
        if not data or "id" not in data:
            return {"success": False, "message": "缺少参数: id"}

        db = PolicyIssueDB()
        result = db.deleteIssueRecord({"id": data["id"]})

        if result != "failed" and result > 0:
            return {"success": True, "message": "删除成功"}
        return {"success": False, "message": "删除失败，记录可能不存在"}

    except Exception as err:
        logger.error(f"删除问题处理记录失败: {err}")
        return {"success": False, "message": f"删除失败: {str(err)}"}


def _recollect_by_object_type(object_type, device_ip):
    """
    标记完成后按对象类型触发设备回采，失败不影响状态更新
    """
    try:
        if object_type == OBJECT_TYPE_PREFIX_LIST:
            from function_policy.func_prefix import collect_and_update_prefix_lists
            result = collect_and_update_prefix_lists(device_ip)
            logger.info(f"标记完成后触发前缀列表采集，设备: {device_ip}，结果: {result}")
        elif object_type == OBJECT_TYPE_ACL:
            from function_policy.func_access_list import collect_and_update_access_lists
            result = collect_and_update_access_lists(device_ip)
            logger.info(f"标记完成后触发 ACL 采集，设备: {device_ip}，结果: {result}")
        else:
            # 地址组/端口组随 ACL 采集更新，暂无独立回采入口
            logger.info(f"{get_object_type_label(object_type)} 暂不支持独立回采，跳过设备 {device_ip}")
    except Exception as err:
        logger.error(f"触发设备 {device_ip} 采集失败: {err}")


def change_issue_status(data):
    """
    更新问题处理记录状态（统一接口用）
    :param data: {id, status}
    :return: {success: bool, message: str}
    """
    try:
        if not data or "id" not in data or "status" not in data:
            return {"success": False, "message": "缺少参数: id 或 status"}

        status = data["status"]
        if status not in ('pending', 'processing', 'completed', 'ignored'):
            return {"success": False, "message": "无效的状态值"}

        db = PolicyIssueDB()
        record = db.getIssueRecordDetail({"id": data["id"]})

        if record == "failed":
            return {"success": False, "message": "记录不存在"}

        db = PolicyIssueDB()
        result = db.updateIssueStatus({"id": data["id"], "status": status})

        if result == "failed" or result <= 0:
            return {"success": False, "message": "更新失败，记录可能不存在"}

        # 标记完成后回采，确认设备配置是否已与标准一致
        if status == "completed" and record.get("device_ip"):
            _recollect_by_object_type(record.get("object_type"), record["device_ip"])

        return {"success": True, "message": "状态更新成功"}

    except Exception as err:
        logger.error(f"更新问题处理记录状态失败: {err}")
        return {"success": False, "message": f"更新失败: {str(err)}"}


def _get_standard_entries(object_type, standard_id):
    """
    按对象类型取标准规则的名称与条目
    :return: (standard_name, entries) 或 None
    """
    from function_policy.func_access_list import normalize_entries

    if object_type == OBJECT_TYPE_PREFIX_LIST:
        from tables.PrefixListDB import PrefixListDB
        standard = PrefixListDB().getStandardDetail({"id": standard_id})
    elif object_type == OBJECT_TYPE_ACL:
        from tables.AccessListDB import AccessListDB
        standard = AccessListDB().getStandardDetail({"id": standard_id})
    elif object_type == OBJECT_TYPE_ADDRGROUP:
        from tables.AddrGroupDB import AddrGroupDB
        standard = AddrGroupDB().getGroupDetail({"id": standard_id})
    elif object_type == OBJECT_TYPE_PORTGROUP:
        from tables.PortGroupDB import PortGroupDB
        standard = PortGroupDB().getGroupDetail({"id": standard_id})
    else:
        return None

    if standard == "failed":
        return None

    return standard["name"], normalize_entries(standard.get("entries"))


def compare_issue_text_diff(data):
    """
    配置差异对比（按对象类型分发到各自的渲染逻辑）

    取数优先级：
    1. 直接传入 src_entries / target_entries
    2. 传 issue_id：从问题记录取 device_entries / standard_entries
    3. 传 standard_id + device_ip：从标准规则与设备记录库取

    :param data: {object_type, issue_id | standard_id+device_ip | src_entries+target_entries, full_diff}
    :return: {success: bool, data: {html}, message: str}
    """
    try:
        object_type = (data or {}).get("object_type")
        if not object_type:
            return {"success": False, "message": "缺少参数: object_type"}

        full_diff = bool(data.get("full_diff"))

        if data.get("src_entries") is not None and data.get("target_entries") is not None:
            src_entries = data.get("src_entries")
            target_entries = data.get("target_entries")
        elif data.get("issue_id"):
            db = PolicyIssueDB()
            record = db.getIssueRecordDetail({"id": data["issue_id"]})
            if record == "failed":
                return {"success": False, "message": "记录不存在"}
            src_entries = record.get("device_entries") or []
            target_entries = record.get("standard_entries") or []
        elif data.get("standard_id") and data.get("device_ip"):
            src_entries, target_entries = _load_entries_for_compare(
                object_type, data["standard_id"], data["device_ip"]
            )
            if src_entries is None:
                return {"success": False, "message": "标准规则或设备配置不存在"}
        else:
            return {"success": False, "message": "缺少参数: issue_id 或 standard_id+device_ip"}

        if object_type == OBJECT_TYPE_PREFIX_LIST:
            from function_policy.func_prefix import compare_entries_text_diff
            return compare_entries_text_diff(src_entries, target_entries, full_diff=full_diff)
        if object_type == OBJECT_TYPE_ACL:
            from function_policy.func_access_list import compare_entries_text_diff
            return compare_entries_text_diff(src_entries, target_entries, full_diff=full_diff)
        if object_type == OBJECT_TYPE_ADDRGROUP:
            from function_policy.func_addrgroup import compare_group_text_diff
            return compare_group_text_diff(src_entries, target_entries, full_diff=full_diff)
        if object_type == OBJECT_TYPE_PORTGROUP:
            from function_policy.func_portgroup import compare_group_text_diff
            return compare_group_text_diff(src_entries, target_entries, full_diff=full_diff)

        return {"success": False, "message": f"不支持的对象类型: {object_type}"}

    except Exception as err:
        logger.error(f"配置差异对比失败: {err}")
        return {"success": False, "message": f"对比失败: {str(err)}"}


def _load_entries_for_compare(object_type, standard_id, device_ip):
    """
    从标准规则与设备记录库取出两侧条目
    :return: (device_entries, standard_entries)；任一侧缺失返回 (None, None)
    """
    from function_policy.func_access_list import normalize_entries

    if object_type == OBJECT_TYPE_PREFIX_LIST:
        from tables.PrefixListDB import PrefixListDB
        standard = PrefixListDB().getStandardDetail({"id": standard_id})
        records = PrefixListDB().getRecordsList({"device_ip": device_ip, "pl_name": standard["name"]}) \
            if standard != "failed" else "failed"
    elif object_type == OBJECT_TYPE_ACL:
        from tables.AccessListDB import AccessListDB
        standard = AccessListDB().getStandardDetail({"id": standard_id})
        # 同名 ACL 在 v4/v6 下是两条独立配置，必须带 acl_type 过滤
        records = AccessListDB().getRecordsList({
            "device_ip": device_ip,
            "acl_name": standard["name"],
            "acl_type": standard.get("acl_type")
        }) if standard != "failed" else "failed"
    elif object_type in (OBJECT_TYPE_ADDRGROUP, OBJECT_TYPE_PORTGROUP):
        if object_type == OBJECT_TYPE_ADDRGROUP:
            from tables.AddrGroupDB import AddrGroupDB
            db_cls = AddrGroupDB
        else:
            from tables.PortGroupDB import PortGroupDB
            db_cls = PortGroupDB
        standard = db_cls().getGroupDetail({"id": standard_id})
        records = db_cls().getRecordsList({"device_ip": device_ip, "group_name": standard["name"]}) \
            if standard != "failed" else "failed"
    else:
        return None, None

    if standard == "failed" or records == "failed" or len(records) == 0:
        return None, None

    return normalize_entries(records[0].get("entries")), normalize_entries(standard.get("entries"))


def create_new_issue(data, username):
    """
    手动创建问题处理记录（缺失配置类型）
    :param data: {object_type, standard_id, device_ip, device_name, device_vendor, remark}
    :param username: 创建人
    :return: {success: bool, data: {id}, message: str}
    """
    try:
        if not data or not data.get("object_type") or not data.get("standard_id") or not data.get("device_ip"):
            return {"success": False, "message": "缺少参数: object_type, standard_id, device_ip"}

        object_type = data["object_type"]
        device_ip = data["device_ip"]

        standard_info = _get_standard_entries(object_type, data["standard_id"])
        if not standard_info:
            return {"success": False, "message": "标准规则不存在"}
        standard_name, standard_entries = standard_info

        device_name = data.get("device_name", "")
        device_vendor = data.get("device_vendor", "")
        if not device_name or not device_vendor:
            from tables.CollectDB import CollectDB
            devices = CollectDB().getDeviceList({"host": device_ip})
            if devices and len(devices) > 0:
                device_name = device_name or devices[0].get("sysname", device_ip)
                device_vendor = device_vendor or devices[0].get("vendor", "unknown")
        if not device_name:
            return {"success": False, "message": f"设备 {device_ip} 不存在"}

        db = PolicyIssueDB()
        result = db.createIssueRecord({
            "object_type": object_type,
            "standard_id": data["standard_id"],
            "standard_name": standard_name,
            "device_ip": device_ip,
            "device_name": device_name,
            "device_vendor": device_vendor or "unknown",
            "issue_type": "missing",
            "standard_entries": standard_entries,
            "device_entries": [],
            "created_by": username,
            "remark": data.get("remark", "")
        })

        if result != "failed":
            return {"success": True, "data": {"id": result}, "message": "创建成功"}
        return {"success": False, "message": "创建失败"}

    except Exception as err:
        logger.error(f"创建新问题记录失败: {err}")
        return {"success": False, "message": f"创建失败: {str(err)}"}


def batch_create_issue_records(object_type, standard_id, standard_name, standard_entries, device_list, created_by):
    """
    批量创建问题处理记录
    :param object_type: 对象类型（prefix_list / acl / addrgroup / portgroup）
    :param standard_id: 标准规则ID
    :param standard_name: 标准规则名称
    :param standard_entries: 标准配置条目（调用方保证已规范化）
    :param device_list: 设备列表 [{device_ip, device_name, vendor, device_entries, remark}]
    :param created_by: 创建人
    :return: {success: [], failed: []}
    """
    try:
        success = []
        failed = []

        for device in device_list:
            try:
                # 设备无该配置 -> 缺失；有但不一致 -> 漂移
                if not device.get("device_entries") or len(device["device_entries"]) == 0:
                    issue_type = "missing"
                else:
                    issue_type = "drifted"

                db = PolicyIssueDB()
                result = db.createIssueRecord({
                    "object_type": object_type,
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
        logger.error(f"批量创建问题处理记录失败: {err}")
        return {"success": [], "failed": []}


def diff_entries_by_seq(standard_entries, device_entries, entry_signature):
    """
    按 seq 对比标准条目与设备条目，得出需要增删的条目

    策略：
    1. 标准中有但设备中没有的 -> 添加
    2. 设备中有但标准中没有的 -> 删除
    3. seq 相同但内容不同的 -> 先删除旧的，再添加新的

    :param standard_entries: 标准配置条目
    :param device_entries: 设备配置条目
    :param entry_signature: 生成条目可比签名的函数，由各类型模块提供，
                            用于判断 seq 相同的两条规则内容是否一致
    :return: {"add": [], "delete": []}
    """
    device_map = {entry.get("seq"): entry for entry in device_entries}
    standard_map = {entry.get("seq"): entry for entry in standard_entries}

    add_entries = []
    delete_entries = []

    for seq, std_entry in standard_map.items():
        if seq not in device_map:
            add_entries.append(std_entry)
        elif entry_signature(std_entry) != entry_signature(device_map[seq]):
            # 内容不一致，先删除旧规则再添加新规则
            delete_entries.append(device_map[seq])
            add_entries.append(std_entry)

    for seq, dev_entry in device_map.items():
        if seq not in standard_map:
            delete_entries.append(dev_entry)

    return {"add": add_entries, "delete": delete_entries}


def build_device_commands(record, diff, encoder, sections, entry_diff_applier):
    """
    为单台设备生成变更命令

    :param record: 问题记录
    :param diff: {"add": [], "delete": []}
    :param encoder: 该厂商的编码器
    :param sections: 编码器入参，如 ['prefix_lists'] / ['access_lists']
    :param entry_diff_applier: 把增删条目转成编码器入参的函数，由各类型模块提供
    :return: {"cmd_exec": str, "cmd_roll": str}
    """
    add_entries = diff["add"]
    delete_entries = diff["delete"]

    cmd_delete = ""
    delete_data = None
    if delete_entries:
        delete_data = entry_diff_applier(record, delete_entries)
        cmd_delete = encoder.encode(delete_data, sections=sections, operation='delete')

    cmd_add = ""
    add_data = None
    if add_entries:
        add_data = entry_diff_applier(record, add_entries)
        cmd_add = encoder.encode(add_data, sections=sections, operation='add')

    # 先删除后添加
    cmd_exec = "\n".join([c for c in [cmd_delete, cmd_add] if c])

    # 回滚命令为反向操作
    cmd_roll_parts = []
    if add_data:
        cmd_roll_parts.append(encoder.encode(add_data, sections=sections, operation='delete'))
    if delete_data:
        cmd_roll_parts.append(encoder.encode(delete_data, sections=sections, operation='add'))
    cmd_roll = "\n".join([c for c in cmd_roll_parts if c])

    return {"cmd_exec": cmd_exec, "cmd_roll": cmd_roll}


def create_change_order(issue_ids, username, title=None):
    """
    根据问题处理记录创建变更工单

    一个工单只允许包含同一种 object_type，按类型分派到对应的命令生成函数。

    :param issue_ids: 问题处理记录ID列表
    :param username: 创建人
    :param title: 工单标题（可选，不提供则自动生成）
    :return: {"success": bool, "data": {"op_id": str}, "message": str}
    """
    try:
        if not issue_ids or len(issue_ids) == 0:
            return {"success": False, "message": "缺少参数: issue_ids"}

        logger.info(f"开始处理变更工单，issue_ids: {issue_ids}, title: {title}")

        # 1. 一次性查询所有问题记录
        db = PolicyIssueDB()
        query_result = db.getIssuesByIds(issue_ids)

        if query_result == "failed":
            return {"success": False, "message": "查询问题记录失败"}

        issue_records = query_result["records"]
        if query_result["not_found"]:
            return {
                "success": False,
                "message": f"以下问题记录不存在: {', '.join(map(str, query_result['not_found']))}"
            }

        if len(issue_records) == 0:
            return {"success": False, "message": "未找到有效的问题记录"}

        logger.info(f"成功查询到 {len(issue_records)} 条问题记录")

        # 2. 一个工单只处理一种对象类型，避免命令生成逻辑混淆
        object_types = {r.get("object_type") for r in issue_records}
        if len(object_types) > 1:
            return {
                "success": False,
                "message": f"一个工单只能包含同一种对象类型，当前包含: {', '.join(sorted(object_types))}"
            }
        object_type = object_types.pop()
        type_label = get_object_type_label(object_type)

        prepare_devices = _get_prepare_devices(object_type)

        # 3. 准备工单基本信息
        order_data = {
            "title": title if title else f"{type_label}配置变更-{len(issue_records)}台设备",
            "descrip": f"根据 {len(issue_records)} 条问题记录创建的变更工单（对象类型: {type_label}）",
            "op_type": "2"
        }

        # 4. 逐设备生成配置命令
        devices_data = []
        failed_devices = []
        skipped_devices = []
        warned_devices = []

        for record in issue_records:
            device_ip = record.get("device_ip")
            try:
                if prepare_devices is None:
                    # 该类型尚无命令生成逻辑，仍建工单但命令留空
                    logger.warning(f"{type_label} 类型尚未实现命令生成，问题记录 {record.get('id')} 命令为空")
                    warned_devices.append(device_ip)
                    devices_data.append({
                        "ip": device_ip,
                        "batch": 1,
                        "cmd_exec": "",
                        "cmd_roll": "",
                        "tag": f"{object_type}:{record.get('standard_name', '')}"
                    })
                    continue

                prepared = prepare_devices(record)

                if prepared.get("skipped"):
                    skipped_devices.append(device_ip)
                    continue

                if prepared.get("warning"):
                    logger.warning(f"设备 {device_ip} 命令生成告警: {prepared['warning']}")
                    warned_devices.append(device_ip)

                devices_data.append({
                    "ip": device_ip,
                    "batch": 1,
                    "cmd_exec": prepared.get("cmd_exec", ""),
                    "cmd_roll": prepared.get("cmd_roll", ""),
                    "tag": prepared.get("tag", f"{object_type}:{record.get('standard_name', '')}")
                })

            except Exception as e:
                logger.error(f"处理问题记录 {record.get('id')} 配置生成失败: {e}", exc_info=True)
                failed_devices.append(device_ip)

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

        # 5. 调用通用工单创建方法
        result = create_order_with_devices(order_data, devices_data, username)

        if failed_devices and result.get("success"):
            result["message"] += f"，配置生成失败: {', '.join(failed_devices)}"
            if "data" in result:
                result["data"]["config_failed_devices"] = failed_devices

        if skipped_devices and result.get("success"):
            result["message"] += f"，跳过已一致设备: {len(skipped_devices)} 台"
            if "data" in result:
                result["data"]["skipped_devices"] = skipped_devices

        if warned_devices and result.get("success"):
            result["message"] += f"，{len(warned_devices)} 台设备未生成命令（缺少 encoder）"
            if "data" in result:
                result["data"]["command_warning_devices"] = warned_devices

        return result

    except Exception as err:
        logger.error(f"创建变更工单失败: {err}", exc_info=True)
        return {
            "success": False,
            "message": f"创建工单失败: {str(err)}"
        }
