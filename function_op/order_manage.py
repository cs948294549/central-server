"""
变更工单管理 - 工单业务逻辑层
"""
from tables.AlterationManageDB import AlterationManageDB
from function_collector.func_config import save_config_by_opid
from function_op import log_manage
import json
import logging
import time

logger = logging.getLogger(__name__)


def get_order_list(filters=None):
    """
    获取工单列表

    Args:
        filters: 筛选条件字典

    Returns:
        list: 工单列表
    """
    try:
        db = AlterationManageDB()
        result = db.get_op_order_list(filters or {})
        return result
    except Exception as e:
        logger.error(f"获取工单列表失败: {e}")
        return "failed"


def get_order_detail(op_id):
    """
    获取工单详情

    Args:
        op_id: 工单ID

    Returns:
        dict: 工单详情
    """
    try:
        db = AlterationManageDB()
        result = db.get_op_order_by_id(op_id)
        return result
    except Exception as e:
        logger.error(f"获取工单详情失败: {e}")
        return None


def add_order(data, username):
    """
    创建工单

    Args:
        data: 工单数据
        username: 创建人

    Returns:
        int/str: 成功返回工单ID,失败返回"failed"
    """
    try:
        data['username'] = username
        data['status'] = '00'  # 草稿状态

        db = AlterationManageDB()
        op_id = db.add_op_order(data)

        if op_id != "failed":
            # 记录日志
            log_manage.add_op_log(op_id, "01", username, "创建工单")

        return op_id
    except Exception as e:
        logger.error(f"创建工单失败: {e}")
        return "failed"


def update_order(op_id, data, username):
    """
    更新工单

    Args:
        op_id: 工单ID
        data: 更新数据
        username: 操作人

    Returns:
        str: "success" 或 "failed"
    """
    try:
        db = AlterationManageDB()
        result = db.update_op_order(op_id, data)

        if result == "success":
            # 记录日志
            log_manage.add_op_log(op_id, "02", username, "修改工单")

        return result
    except Exception as e:
        logger.error(f"更新工单失败: {e}")
        return "failed"


def delete_order(op_id):
    """
    删除工单（级联删除所有关联数据）

    Args:
        op_id: 工单ID

    Returns:
        str: "success" 或 "failed"
    """
    try:
        logger.info(f"开始删除工单: {op_id}")

        # 1. 删除关联的设备配置
        db1 = AlterationManageDB()
        result1 = db1.delete_op_devices_by_order(op_id)
        if result1 == "failed":
            logger.error(f"删除工单设备配置失败: op_id={op_id}")
            return "failed"

        # 2. 删除审批记录
        db2 = AlterationManageDB()
        result2 = db2.delete_op_approvals_by_order(op_id)
        if result2 == "failed":
            logger.error(f"删除工单审批记录失败: op_id={op_id}")
            return "failed"

        # 3. 删除操作日志
        db3 = AlterationManageDB()
        result3 = db3.delete_op_logs_by_order(op_id)
        if result3 == "failed":
            logger.error(f"删除工单操作日志失败: op_id={op_id}")
            return "failed"

        # 4. 最后删除工单本身
        db4 = AlterationManageDB()
        result4 = db4.delete_op_order(op_id)
        if result4 == "failed":
            logger.error(f"删除工单失败: op_id={op_id}")
            return "failed"

        logger.info(f"成功删除工单及所有关联数据: op_id={op_id}")
        return "success"
    except Exception as e:
        logger.error(f"删除工单失败: {e}", exc_info=True)
        return "failed"


def copy_order(op_id, username):
    """
    复制工单

    Args:
        op_id: 原工单ID
        username: 操作人

    Returns:
        int/str: 成功返回新工单ID,失败返回"failed"
    """
    try:
        # 获取原工单信息
        db = AlterationManageDB()
        original_order = db.get_op_order_by_id(op_id)

        if not original_order:
            return "failed"

        # 创建新工单
        new_order_data = {
            "op_type": original_order["op_type"],
            "title": f"{original_order['title']}_副本",
            "descrip": original_order["descrip"],
            "username": username,
            "assigner": original_order["assigner"],
            "is_auto": original_order["is_auto"],
            "popo": original_order["popo"],
            "begin_time": original_order["begin_time"],
            "finish_time": original_order["finish_time"]
        }

        db2 = AlterationManageDB()
        new_op_id = db2.add_op_order(new_order_data)

        if new_op_id != "failed":
            # 复制设备列表
            db3 = AlterationManageDB()
            devices = db3.get_op_device_list(op_id)

            if devices and devices != "failed":
                for dev in devices:
                    dev_data = {
                        "op_id": new_op_id,
                        "batch": dev.get("batch", 1),
                        "ip": dev["ip"],
                        "sysname": dev["sysname"],
                        "model": dev["model"],
                        "asset_no": dev.get("asset_no", ""),
                        "cmd_exec": dev["cmd_exec"],
                        "cmd_roll": dev["cmd_roll"],
                        "tag": dev.get("tag", ""),
                        "is_auto": dev.get("is_auto", 0)
                    }
                    db4 = AlterationManageDB()
                    result = db4.add_op_device(dev_data)
                    if result == "failed":
                        logger.error(f"复制设备失败: op_id={new_op_id}, ip={dev['ip']}")


            # 记录日志
            log_manage.add_op_log(new_op_id, "01", username, f"从工单 {op_id} 复制创建")

        return new_op_id
    except Exception as e:
        logger.error(f"复制工单失败: {e}")
        return "failed"


def submit_order(op_id, username):
    """
    提交工单

    Args:
        op_id: 工单ID
        username: 操作人

    Returns:
        dict: {"code": 0/500, "msg": "消息"}
    """
    try:
        # 获取工单信息
        db = AlterationManageDB()
        order = db.get_op_order_by_id(op_id)

        if not order:
            return {"code": 500, "msg": "工单不存在"}

        # 获取工单类型配置
        type_db = AlterationManageDB()
        type_list = type_db.get_op_type_list({"pid": order["op_type"]})

        if not type_list or type_list == "failed" or len(type_list) == 0:
            return {"code": 500, "msg": "工单类型配置不存在"}

        type_cfg = type_list[0]

        # 构建 node_info
        node_list = [{
            "id": 1,
            "title": "提交工单",
            "event": "0",
            "description": "工单已提交",
            "data": ""
        }]

        cur_group = ""
        first_step_id = 2
        first_step_name = ""

        # 处理审批组1
        if type_cfg.get("op_group1"):
            group_db = AlterationManageDB()
            group_list = group_db.get_op_group_list({"pid": type_cfg["op_group1"]})

            if not group_list or group_list == "failed" or len(group_list) == 0:
                return {"code": 500, "msg": "审批组1配置不存在"}
            if len(group_list) > 1:
                return {"code": 500, "msg": "存在多个相同的审批组1，请检查"}

            group1_data = group_list[0]
            node_list.append({
                "id": 2,
                "title": "审批一",
                "event": "1",
                "description": f"待[{group1_data['name']}]接手",
                "data": group1_data
            })
            cur_group = group1_data["op_list"]
            first_step_name = "审批一"

            # 处理审批组2
            if type_cfg.get("op_group2"):
                group_db2 = AlterationManageDB()
                group_list2 = group_db2.get_op_group_list({"pid": type_cfg["op_group2"]})

                if not group_list2 or group_list2 == "failed" or len(group_list2) == 0:
                    return {"code": 500, "msg": "审批组2配置不存在"}
                if len(group_list2) > 1:
                    return {"code": 500, "msg": "存在多个相同的审批组2，请检查"}

                group2_data = group_list2[0]
                node_list.append({
                    "id": 3,
                    "title": "审批二",
                    "event": "1",
                    "description": f"待[{group2_data['name']}]接手",
                    "data": group2_data
                })

                # 处理审批组3
                if type_cfg.get("op_group3"):
                    group_db3 = AlterationManageDB()
                    group_list3 = group_db3.get_op_group_list({"pid": type_cfg["op_group3"]})

                    if not group_list3 or group_list3 == "failed" or len(group_list3) == 0:
                        return {"code": 500, "msg": "审批组3配置不存在"}
                    if len(group_list3) > 1:
                        return {"code": 500, "msg": "存在多个相同的审批组3，请检查"}

                    group3_data = group_list3[0]
                    node_list.append({
                        "id": 4,
                        "title": "审批三",
                        "event": "1",
                        "description": f"待[{group3_data['name']}]接手",
                        "data": group3_data
                    })

        # 添加变更节点
        node_list.append({
            "id": len(node_list) + 1,
            "title": "开始变更",
            "event": "",
            "description": "",
            "data": ""
        })
        node_list.append({
            "id": len(node_list) + 2,
            "title": "变更结束",
            "event": "",
            "description": "",
            "data": ""
        })

        # 更新工单状态
        update_db = AlterationManageDB()
        result = update_db.update_op_order(op_id, {
            "status": "01",
            "node_info": json.dumps(node_list, ensure_ascii=False),
            "cur_group": cur_group,
            "step_id": first_step_id,
            "step_name": first_step_name
        })

        if result == "success":
            # 记录日志
            log_manage.add_op_log(op_id, "03", username, "提交工单")

            # TODO: 发送通知

            return {"code": 0, "msg": "提交成功"}
        else:
            return {"code": 500, "msg": "提交失败"}

    except Exception as e:
        logger.error(f"提交工单失败: {e}")
        return {"code": 500, "msg": f"提交失败: {str(e)}"}


def takeover_order(op_id, username):
    """
    接手工单

    Args:
        op_id: 工单ID
        username: 操作人

    Returns:
        dict: {"code": 0/500, "msg": "消息"}
    """
    try:
        # 获取工单信息
        db = AlterationManageDB()
        order = db.get_op_order_by_id(op_id)

        if not order:
            return {"code": 500, "msg": "工单不存在"}

        # 检查当前用户是否在cur_group中
        cur_group = order.get("cur_group", "")
        if username not in cur_group.split(","):
            return {"code": 403, "msg": "您不在当前审批组中，无权接手"}

        # 解析并更新 node_info
        node_info = []
        node_info_str = order.get("node_info", "")
        if node_info_str:
            try:
                node_info = json.loads(node_info_str)
                # 更新当前步骤的描述
                current_step_id = order.get("step_id", 0)
                if current_step_id > 0 and current_step_id <= len(node_info):
                    node_info[current_step_id - 1]["description"] = f"{username} 已接手"
            except:
                pass

        # 更新工单状态
        update_data = {
            "status": "02",
            "cur_user": username
        }
        if node_info:
            update_data["node_info"] = json.dumps(node_info, ensure_ascii=False)

        update_db = AlterationManageDB()
        result = update_db.update_op_order(op_id, update_data)

        if result == "success":
            # 记录日志
            log_manage.add_op_log(op_id, "04", username, "接手工单")

            return {"code": 0, "msg": "接手成功"}
        else:
            return {"code": 500, "msg": "接手失败"}

    except Exception as e:
        logger.error(f"接手工单失败: {e}")
        return {"code": 500, "msg": f"接手失败: {str(e)}"}


def approve_order(op_id, username, approve_status, comment=''):
    """
    审批工单

    Args:
        op_id: 工单ID
        username: 操作人
        approve_status: 审批状态 "10"=通过, "92"=拒绝
        comment: 审批意见

    Returns:
        dict: {"code": 0/500, "msg": "消息"}
    """
    try:
        comment_suffix = f"，意见：{comment}" if comment else ""

        # 获取工单信息
        db = AlterationManageDB()
        order = db.get_op_order_by_id(op_id)

        if not order:
            return {"code": 500, "msg": "工单不存在"}

        # 解析node_info
        try:
            node_info_str = order.get("node_info", "")
            if not node_info_str or node_info_str == "":
                return {"code": 500, "msg": "工单尚未提交，无法审批"}
            node_info = json.loads(node_info_str)
            if not node_info or len(node_info) == 0:
                return {"code": 500, "msg": "工单流程信息为空"}
        except Exception as e:
            logger.error(f"解析工单流程信息失败: {e}, node_info: {order.get('node_info', '')}")
            return {"code": 500, "msg": f"工单流程信息异常: {str(e)}"}

        # 获取当前节点
        current_step_id = order.get("step_id", 0)
        if current_step_id <= 0 or current_step_id > len(node_info):
            return {"code": 500, "msg": "工单流程状态异常"}

        current_node = node_info[current_step_id - 1]

        # 记录审批记录
        approval_db = AlterationManageDB()
        approval_db.add_op_approval({
            "op_id": op_id,
            "op_group": current_node.get("data", {}).get("pid", 0),
            "username": username,
            "status": approve_status
        })

        # 如果拒绝
        if approve_status == "92":
            # 更新当前节点描述为拒绝信息
            current_node["description"] = f"{username} 已拒绝"

            update_db = AlterationManageDB()
            result = update_db.update_op_order(op_id, {
                "status": "92",
                "step_id": current_step_id,  # 保持当前步骤ID
                "node_info": json.dumps(node_info, ensure_ascii=False)
            })

            if result == "success":
                # 记录日志
                log_manage.add_op_log(op_id, "06", username, f"审批拒绝{comment_suffix}")

                # TODO: 发送通知

                return {"code": 0, "msg": "审批完成"}
            else:
                return {"code": 500, "msg": "审批失败"}

        # 更新当前节点描述为已审批
        current_node["description"] = f"{username} 已审批"

        # 如果通过，检查是否还有下一轮审批
        next_step_id = current_step_id + 1
        has_next_approval = False

        if next_step_id <= len(node_info):
            next_node = node_info[next_step_id - 1]
            if next_node.get("event") == "1":
                has_next_approval = True

        update_db2 = AlterationManageDB()
        if has_next_approval:
            # 还有下一轮审批
            next_node = node_info[next_step_id - 1]
            result = update_db2.update_op_order(op_id, {
                "status": "01",
                "step_id": next_step_id,
                "step_name": next_node.get("title", ""),
                "cur_group": next_node.get("data", {}).get("op_list", ""),
                "cur_user": "",
                "node_info": json.dumps(node_info, ensure_ascii=False)
            })

            if result == "success":
                # 记录日志
                log_manage.add_op_log(op_id, "05", username, f"审批通过，进入下一轮审批{comment_suffix}")

                # TODO: 发送通知

                return {"code": 0, "msg": "审批通过，已进入下一轮审批"}
            else:
                return {"code": 500, "msg": "审批失败"}
        else:
            # 所有审批通过，找到"开始变更"节点的ID
            start_change_step_id = 0
            for i, node in enumerate(node_info):
                if node.get("title") == "开始变更":
                    start_change_step_id = node.get("id", i + 1)
                    break

            # 如果没有找到"开始变更"节点，使用下一个节点ID
            if start_change_step_id == 0:
                start_change_step_id = next_step_id

            result = update_db2.update_op_order(op_id, {
                "status": "20",
                "step_id": start_change_step_id,
                "cur_group": "",
                "cur_user": "",
                "node_info": json.dumps(node_info, ensure_ascii=False)
            })

            if result == "success":
                # 记录日志
                log_manage.add_op_log(op_id, "05", username, f"审批通过，所有审批流程完成{comment_suffix}")

                # TODO: 发送通知

                return {"code": 0, "msg": "审批通过，工单进入待变更状态"}
            else:
                return {"code": 500, "msg": "审批失败"}

    except Exception as e:
        logger.error(f"审批工单失败: {e}")
        return {"code": 500, "msg": f"审批失败: {str(e)}"}


def start_change(op_id, username):
    """
    开始变更

    Args:
        op_id: 工单ID
        username: 操作人

    Returns:
        dict: {"code": 0/500, "msg": "消息"}
    """
    try:
        db = AlterationManageDB()
        result = db.update_op_order(op_id, {"status": "21"})

        if result == "success":
            # 记录日志
            log_manage.add_op_log(op_id, "07", username, "开始变更")

            # TODO: 发送通知

            return {"code": 0, "msg": "变更已开始"}
        else:
            return {"code": 500, "msg": "操作失败"}

    except Exception as e:
        logger.error(f"开始变更失败: {e}")
        return {"code": 500, "msg": f"操作失败: {str(e)}"}


def end_change(op_id, username, final_status):
    """
    结束变更

    Args:
        op_id: 工单ID
        username: 操作人
        final_status: 最终状态 "90"=成功, "91"=失败

    Returns:
        dict: {"code": 0/500, "msg": "消息"}
    """
    try:
        db = AlterationManageDB()
        result = db.update_op_order(op_id, {"status": final_status})

        if result == "success":
            # 记录日志
            status_text = "变更完成" if final_status == "90" else "变更失败"
            log_manage.add_op_log(op_id, "08", username, f"结束变更 - {status_text}")

            # TODO: 发送通知

            return {"code": 0, "msg": f"变更已结束 - {status_text}"}
        else:
            return {"code": 500, "msg": "操作失败"}

    except Exception as e:
        logger.error(f"结束变更失败: {e}")
        return {"code": 500, "msg": f"操作失败: {str(e)}"}


def cancel_change(op_id, username):
    """
    取消变更

    Args:
        op_id: 工单ID
        username: 操作人

    Returns:
        dict: {"code": 0/500, "msg": "消息"}
    """
    try:
        # 获取工单信息
        db = AlterationManageDB()
        order = db.get_op_order_by_id(op_id)

        if not order:
            return {"code": 500, "msg": "工单不存在"}

        # 解析 node_info
        node_info = []
        current_step_id = order.get("step_id", 0)
        try:
            node_info_str = order.get("node_info", "")
            if node_info_str:
                node_info = json.loads(node_info_str)
        except Exception as e:
            logger.error(f"解析 node_info 失败: {e}")

        # 如果有 node_info，添加"变更取消"节点，覆盖后续节点
        if node_info and len(node_info) > 0:
            # 找到当前步骤的索引
            current_index = current_step_id - 1 if current_step_id > 0 else 0

            # 截取到当前步骤（包含当前步骤）
            node_info = node_info[:current_index + 1]

            # 添加"变更取消"节点
            cancel_node_id = len(node_info) + 1
            node_info.append({
                "id": cancel_node_id,
                "title": "变更取消",
                "event": "",
                "description": f"{username} 取消变更",
                "data": ""
            })

            update_data = {
                "status": "93",
                "step_id": cancel_node_id,
                "node_info": json.dumps(node_info, ensure_ascii=False)
            }
        else:
            # 如果没有 node_info，只更新状态
            update_data = {
                "status": "93"
            }

        update_db = AlterationManageDB()
        result = update_db.update_op_order(op_id, update_data)

        if result == "success":
            # 记录日志
            log_manage.add_op_log(op_id, "09", username, "取消变更")

            # TODO: 发送通知

            return {"code": 0, "msg": "变更已取消"}
        else:
            return {"code": 500, "msg": "操作失败"}

    except Exception as e:
        logger.error(f"取消变更失败: {e}")
        return {"code": 500, "msg": f"取消失败: {str(e)}"}


def backup_devices_config(op_id):
    """
    备份工单下所有设备的配置

    Args:
        op_id: 工单ID

    Returns:
        dict: {"success": bool, "total": 总数, "success_count": 成功数, "failed_count": 失败数, "details": []}
    """
    try:
        # 获取工单下的所有设备
        device_db = AlterationManageDB()
        devices = device_db.get_op_device_list(op_id)

        if not devices or devices == "failed" or len(devices) == 0:
            logger.info(f"工单 {op_id} 下没有设备配置，跳过备份步骤")
            return {
                "success": True,
                "total": 0,
                "success_count": 0,
                "failed_count": 0,
                "details": [],
                "message": "工单下没有设备，跳过配置备份"
            }

        # 按IP去重（多批次可能包含重复设备）
        unique_devices = {}
        for device in devices:
            ip = device.get("ip", "")
            if ip and ip not in unique_devices:
                unique_devices[ip] = device

        devices_to_backup = list(unique_devices.values())
        logger.info(f"工单 {op_id} 共 {len(devices)} 台设备，去重后 {len(devices_to_backup)} 台，准备备份配置")

        # 备份所有设备配置
        backup_results = []
        success_count = 0
        failed_count = 0

        for device in devices_to_backup:
            ip = device.get("ip", "")
            sysname = device.get("sysname", "")

            logger.info(f"正在备份设备 {ip}({sysname}) 配置...")
            result = save_config_by_opid(ip, op_id)

            backup_result = {
                "ip": ip,
                "sysname": sysname,
                "status": result.get("status", "failed"),
                "message": result.get("message", "")
            }
            backup_results.append(backup_result)

            if result.get("status") == "success":
                success_count += 1
            else:
                failed_count += 1

        logger.info(f"工单 {op_id} 配置备份完成: {success_count}成功/{failed_count}失败")

        return {
            "success": True,
            "total": len(devices_to_backup),
            "success_count": success_count,
            "failed_count": failed_count,
            "details": backup_results
        }

    except Exception as e:
        logger.error(f"备份设备配置失败: {e}", exc_info=True)
        return {
            "success": False,
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "details": [],
            "message": str(e)
        }


def start_change(op_id, username):
    """
    开始变更（变更前备份配置）

    Args:
        op_id: 工单ID
        username: 操作人

    Returns:
        dict: {"code": 0/500, "msg": "消息", "data": {"total": 总数, "success": 成功数, "failed": 失败数, "details": []}}
    """
    try:
        # 获取工单信息
        db = AlterationManageDB()
        order = db.get_op_order_by_id(op_id)

        if not order:
            return {"code": 500, "msg": "工单不存在"}

        # 权限检查：只有创建人或指定执行人可以开始变更
        creator = order.get("username", "")
        assigner = order.get("assigner", "")
        if username != creator and username != assigner:
            return {"code": 403, "msg": "无权限操作，仅创建人和指定执行人可以开始变更"}

        # 检查工单状态是否允许开始变更
        if order.get("status") not in ["20"]:
            return {"code": 500, "msg": f"工单当前状态({order.get('status')})不允许开始变更"}

        # 备份所有设备配置
        backup_result = backup_devices_config(op_id)

        if not backup_result.get("success"):
            return {"code": 500, "msg": backup_result.get("message", "备份配置失败")}

        # 解析 node_info 找到"开始变更"节点的 ID
        node_info = []
        change_step_id = 0
        try:
            node_info_str = order.get("node_info", "")
            if node_info_str:
                node_info = json.loads(node_info_str)
                # 找到标题为"开始变更"的节点
                for node in node_info:
                    if node.get("title") == "开始变更":
                        change_step_id = node.get("id", 0)
                        # 更新节点描述
                        node["description"] = f"{username} 开始变更"
                        break
        except Exception as e:
            logger.error(f"解析 node_info 失败: {e}")

        # 更新工单状态为变更中
        update_data = {
            "status": "21",
            "begin_time": str(int(time.time()))
        }

        # 如果找到了"开始变更"节点，更新 step_id 和 node_info
        if change_step_id > 0:
            update_data["step_id"] = change_step_id
            if node_info:
                update_data["node_info"] = json.dumps(node_info, ensure_ascii=False)

        update_db = AlterationManageDB()
        update_result = update_db.update_op_order(op_id, update_data)

        if update_result == "success":
            # 记录日志
            success_count = backup_result.get("success_count", 0)
            failed_count = backup_result.get("failed_count", 0)

            log_manage.add_op_log(op_id, "07", username, f"开始变更 - 备份完成({success_count}成功/{failed_count}失败)")

            return {
                "code": 0,
                "msg": f"开始变更成功，配置备份完成({success_count}成功/{failed_count}失败)",
                "data": {
                    "total": backup_result.get("total", 0),
                    "success": success_count,
                    "failed": failed_count,
                    "details": backup_result.get("details", [])
                }
            }
        else:
            return {"code": 500, "msg": "更新工单状态失败"}

    except Exception as e:
        logger.error(f"开始变更失败: {e}", exc_info=True)
        return {"code": 500, "msg": f"开始变更失败: {str(e)}"}


def finish_change(op_id, username, status="90"):
    """
    结束变更（变更后备份配置）

    Args:
        op_id: 工单ID
        username: 操作人
        status: 结束状态 "90"=变更完成, "91"=变更失败

    Returns:
        dict: {"code": 0/500, "msg": "消息", "data": {"total": 总数, "success": 成功数, "failed": 失败数, "details": []}}
    """
    try:
        # 获取工单信息
        db = AlterationManageDB()
        order = db.get_op_order_by_id(op_id)

        if not order:
            return {"code": 500, "msg": "工单不存在"}

        # 权限检查：只有创建人或指定执行人可以结束变更
        creator = order.get("username", "")
        assigner = order.get("assigner", "")
        if username != creator and username != assigner:
            return {"code": 403, "msg": "无权限操作，仅创建人和指定执行人可以结束变更"}

        # 检查工单状态是否允许结束变更
        if order.get("status") not in ["21"]:
            return {"code": 500, "msg": f"工单当前状态({order.get('status')})不允许结束变更"}

        # 备份所有设备配置
        backup_result = backup_devices_config(op_id)

        if not backup_result.get("success"):
            return {"code": 500, "msg": backup_result.get("message", "备份配置失败")}

        # 解析 node_info 找到"变更结束"节点的 ID
        node_info = []
        finish_step_id = 0
        try:
            node_info_str = order.get("node_info", "")
            if node_info_str:
                node_info = json.loads(node_info_str)
                # 找到标题为"变更结束"的节点
                for node in node_info:
                    if node.get("title") == "变更结束":
                        finish_step_id = node.get("id", 0)
                        # 更新节点描述
                        node["description"] = f"{username} 结束变更"
                        break
        except Exception as e:
            logger.error(f"解析 node_info 失败: {e}")

        # 更新工单状态
        status_text = "变更完成" if status == "90" else "变更失败"
        update_data = {
            "status": status,
            "finish_time": str(int(time.time()))
        }

        # 如果找到了"变更结束"节点，更新 step_id 和 node_info
        if finish_step_id > 0:
            update_data["step_id"] = finish_step_id
            if node_info:
                update_data["node_info"] = json.dumps(node_info, ensure_ascii=False)

        update_db = AlterationManageDB()
        update_result = update_db.update_op_order(op_id, update_data)

        if update_result == "success":
            # 记录日志
            success_count = backup_result.get("success_count", 0)
            failed_count = backup_result.get("failed_count", 0)

            log_manage.add_op_log(op_id, "08", username, f"结束变更 - {status_text} - 备份完成({success_count}成功/{failed_count}失败)")

            return {
                "code": 0,
                "msg": f"{status_text}，配置备份完成({success_count}成功/{failed_count}失败)",
                "data": {
                    "total": backup_result.get("total", 0),
                    "success": success_count,
                    "failed": failed_count,
                    "details": backup_result.get("details", [])
                }
            }
        else:
            return {"code": 500, "msg": "更新工单状态失败"}

    except Exception as e:
        logger.error(f"结束变更失败: {e}", exc_info=True)
        return {"code": 500, "msg": f"结束变更失败: {str(e)}"}

        return {"code": 500, "msg": f"操作失败: {str(e)}"}
