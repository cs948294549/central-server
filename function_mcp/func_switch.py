import json
from function_ssh.sshClient import run_ssh_command
from function_snmp.snmp_collector import common_identify_vendor
from config.config import Config

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
