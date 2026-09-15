import json
from lib_ssh.sshClient import run_ssh_command
from lib_snmp.snmp_collector import common_identify_vendor
from config.config import Config
from function_op.order_manage import create_order_with_devices

COMMON_COMMUNITY = Config.snmp_community


def run_cmd(ip, cmds, vendor=None):
    """
    执行命令接口（直接调用内部方法）
    :param ip: 设备IP
    :param cmds: 需要执行的命令
    :param vendor: 厂商，需要使用接口获取
    :return:
    """
    # 安全策略：只允许执行 display 或 show 开头的命令
    filtered_cmds = []
    for cmd in cmds:
        if cmd.lower().strip().startswith('dis') or cmd.lower().strip().startswith('show'):
            filtered_cmds.append(cmd)
        else:
            return f"安全策略限制：只允许执行 display/show 开头的命令，当前命令 '{cmd}' 被拒绝"

    try:
        if vendor is not None:
            result = run_ssh_command(host=ip, commands=filtered_cmds, vendor=vendor)
        else:
            result = run_ssh_command(host=ip, commands=filtered_cmds)

        if result and isinstance(result, dict):
            # 格式化输出结果
            if result.get('status', '') == 'success':
                result_data = result.get('data', {})
                msgs = "执行参数：\n ip: {}\n cmds:{}\n执行结果:\n{}".format(
                    ip,
                    str(filtered_cmds),
                    "\n".join(result_data.values())
                )
            else:
                msgs = f"执行参数：\n ip: {ip}\n cmds:{filtered_cmds}\n执行结果:{result}"
        else:
            msgs = f"执行参数：\n ip: {ip}\n cmds:{filtered_cmds}\n执行结果:命令执行失败"

        return msgs
    except Exception as e:
        return f"执行失败: {str(e)}"


def get_vendor(ip):
    """
    获取设备厂商信息
    :param ip: 设备IP
    :return:
    """
    # 可以通过 SNMP 获取厂商信息
    try:
        vendor_info = common_identify_vendor(ip, COMMON_COMMUNITY)
        return json.dumps({"code": 0, "data": {"vendor": vendor_info}}, ensure_ascii=False)
    except Exception as e:
        # 如果获取失败，返回未知
        return json.dumps({"code": -1, "message": f"获取厂商信息失败: {str(e)}"}, ensure_ascii=False)


def create_change_order(order_content, devices):
    """
    创建变更工单（MCP调用）

    :param order_content: 工单内容，格式：{
        "title": "工单标题",
        "descrip": "工单详细描述"
    }
    :param devices: 设备配置列表，格式：[
        {
            "ip": "设备IP",
            "cmd_exec": "执行命令",
            "cmd_roll": "回滚命令",
            "batch": 批次（可选，默认1）,
            "tag": "标签（可选）"
        }
    ]
    :return: JSON格式结果
    """
    try:
        # 参数验证
        if not order_content or not isinstance(order_content, dict):
            return json.dumps({"code": -1, "message": "order_content必须是字典类型"}, ensure_ascii=False)

        title = order_content.get("title")
        descrip = order_content.get("descrip", "")

        if not title:
            return json.dumps({"code": -1, "message": "order_content中缺少title字段"}, ensure_ascii=False)

        if not devices or not isinstance(devices, list) or len(devices) == 0:
            return json.dumps({"code": -1, "message": "devices必须是非空数组"}, ensure_ascii=False)

        # 验证每个设备的必需字段
        for idx, device in enumerate(devices):
            if not device.get("ip"):
                return json.dumps({"code": -1, "message": f"设备{idx+1}缺少ip字段"}, ensure_ascii=False)
            if not device.get("cmd_exec"):
                return json.dumps({"code": -1, "message": f"设备{idx+1}缺少cmd_exec字段"}, ensure_ascii=False)
            if not device.get("cmd_roll"):
                return json.dumps({"code": -1, "message": f"设备{idx+1}缺少cmd_roll字段"}, ensure_ascii=False)

        # 准备工单数据
        order_data = {
            "title": title,
            "descrip": descrip,
            "op_type": "2",  # 默认类型2
            "assigner": "all"  # 默认所有人可操作
        }

        # 准备设备数据
        devices_data = []
        for device in devices:
            devices_data.append({
                "ip": device["ip"],
                "batch": device.get("batch", 1),
                "cmd_exec": device["cmd_exec"],
                "cmd_roll": device["cmd_roll"],
                "tag": device.get("tag", ""),
                "is_auto": device.get("is_auto", 0)
            })

        # 调用创建工单方法，默认创建人为admin
        result = create_order_with_devices(order_data, devices_data, username="admin")

        if result.get("success"):
            return json.dumps({
                "code": 0,
                "message": result.get("message"),
                "data": result.get("data")
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "code": -1,
                "message": result.get("message")
            }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "code": -1,
            "message": f"创建工单失败: {str(e)}"
        }, ensure_ascii=False)
