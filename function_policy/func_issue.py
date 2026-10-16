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
    return None


def update_issue_status(issue_id, update_data):
    """
    更新问题处理记录状态
    :param issue_id: 问题记录ID
    :param update_data: 更新数据 {status, change_ticket_id, processed_at, remark}
    :return: {success: bool, message: str}
    """
    try:
        update_data["id"] = issue_id
        db = PolicyIssueDB()
        result = db.updateIssueRecordStatus(update_data)

        if result != "failed" and result > 0:
            return {"success": True, "message": "更新成功"}
        else:
            return {"success": False, "message": "更新失败，记录可能不存在"}

    except Exception as err:
        logger.error(f"更新问题处理记录状态失败: {err}")
        return {"success": False, "message": f"更新失败: {str(err)}"}


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
