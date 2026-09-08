"""
变更工单管理 - 设备管理业务逻辑层
"""
from tables.AlterationManageDB import AlterationManageDB
from tables.CollectDB import CollectDB
from function_snmp.snmp_collector import identify_device_vendor
from function_ssh.sshClient import run_ssh_command
import logging

logger = logging.getLogger(__name__)


def get_device_list(op_id):
    """
    获取工单设备列表

    Args:
        op_id: 工单ID

    Returns:
        list: 设备列表
    """
    try:
        db = AlterationManageDB()
        result = db.get_op_device_list(op_id)
        return result
    except Exception as e:
        logger.error(f"获取设备列表失败: {e}")
        return "failed"


def add_device(data):
    """
    添加设备

    Args:
        data: 设备数据

    Returns:
        int/str: 成功返回设备ID,失败返回"failed"
    """
    try:
        db = AlterationManageDB()
        result = db.add_op_device(data)
        return result
    except Exception as e:
        logger.error(f"添加设备失败: {e}")
        return "failed"


def update_device(dev_id, data):
    """
    更新设备

    Args:
        dev_id: 设备ID
        data: 更新数据

    Returns:
        str: "success" 或 "failed"
    """
    try:
        db = AlterationManageDB()
        result = db.update_op_device(dev_id, data)
        return result
    except Exception as e:
        logger.error(f"更新设备失败: {e}")
        return "failed"


def delete_device(dev_id):
    """
    删除设备

    Args:
        dev_id: 设备ID

    Returns:
        str: "success" 或 "failed"
    """
    try:
        db = AlterationManageDB()
        result = db.delete_op_device(dev_id)
        return result
    except Exception as e:
        logger.error(f"删除设备失败: {e}")
        return "failed"

def execute_device_command(dev_id, username):
    """
    执行设备命令

    Args:
        dev_id: 设备ID
        username: 操作人

    Returns:
        dict: {"code": 0/500, "msg": "消息", "output": "命令输出"}
    """
    try:
        # 1. 获取设备命令信息
        alter_db = AlterationManageDB()
        device_info = alter_db.get_op_device_by_id(dev_id)

        if not device_info or device_info == "failed":
            return {"code": 500, "msg": "设备不存在", "output": ""}

        device_ip = device_info.get('ip')
        cmd_exec = device_info.get('cmd_exec', '')

        if not device_ip:
            return {"code": 500, "msg": "设备IP为空", "output": ""}

        if not cmd_exec or cmd_exec.strip() == '':
            return {"code": 500, "msg": "执行命令为空", "output": ""}

        # 2. 从CollectDB通过IP精确查询设备的sysdesc信息
        collect_db = CollectDB()
        devices = collect_db.getDeviceList({"host": device_ip})

        if not devices or len(devices) == 0:
            return {"code": 500, "msg": f"未在设备库中找到IP: {device_ip}", "output": ""}

        target_device = devices[0]
        sysdesc = target_device.get('sysdesc', '')

        # 3. 识别设备厂商
        vendor = identify_device_vendor(sysdesc)

        logger.info(f"执行设备命令: IP={device_ip}, vendor={vendor}, user={username}")

        # 4. 执行命令（支持多行命令）
        commands = [cmd.strip() for cmd in cmd_exec.split('\n') if cmd.strip()]
        result = run_ssh_command(host=device_ip, commands=commands, vendor=vendor)

        # 5. 更新设备状态和执行结果
        alter_db2 = AlterationManageDB()
        if result.get('status') == 'success':
            update_data = {
                'status': '10',  # 执行成功
                'result': str(result.get('output', ''))
            }
            alter_db2.update_op_device(dev_id, update_data)
            return {"code": 0, "msg": "执行成功", "output": result.get('output', '')}
        else:
            update_data = {
                'status': '90',  # 执行失败
                'result': str(result.get('error', ''))
            }
            alter_db2.update_op_device(dev_id, update_data)
            return {"code": 500, "msg": f"执行失败: {result.get('error', '')}", "output": result.get('error', '')}

    except Exception as e:
        logger.error(f"执行设备命令失败: {e}")
        return {"code": 500, "msg": f"执行失败: {str(e)}", "output": ""}


def rollback_device_command(dev_id, username):
    """
    回滚设备命令

    Args:
        dev_id: 设备ID
        username: 操作人

    Returns:
        dict: {"code": 0/500, "msg": "消息", "output": "命令输出"}
    """
    try:
        # 1. 获取设备命令信息
        alter_db = AlterationManageDB()
        device_info = alter_db.get_op_device_by_id(dev_id)

        if not device_info or device_info == "failed":
            return {"code": 500, "msg": "设备不存在", "output": ""}

        device_ip = device_info.get('ip')
        cmd_roll = device_info.get('cmd_roll', '')

        if not device_ip:
            return {"code": 500, "msg": "设备IP为空", "output": ""}

        if not cmd_roll or cmd_roll.strip() == '':
            return {"code": 500, "msg": "回滚命令为空", "output": ""}

        # 2. 从CollectDB通过IP精确查询设备的sysdesc信息
        collect_db = CollectDB()
        devices = collect_db.getDeviceList({"host": device_ip})

        if not devices or len(devices) == 0:
            return {"code": 500, "msg": f"未在设备库中找到IP: {device_ip}", "output": ""}

        target_device = devices[0]
        sysdesc = target_device.get('sysdesc', '')

        # 3. 识别设备厂商
        vendor = identify_device_vendor(sysdesc)

        logger.info(f"回滚设备命令: IP={device_ip}, vendor={vendor}, user={username}")

        # 4. 执行回滚命令（支持多行命令）
        commands = [cmd.strip() for cmd in cmd_roll.split('\n') if cmd.strip()]
        result = run_ssh_command(host=device_ip, commands=commands, vendor=vendor)

        # 5. 更新设备状态和执行结果
        alter_db2 = AlterationManageDB()
        if result.get('status') == 'success':
            update_data = {
                'status': '00',  # 回滚后恢复初始状态
                'result': f"[回滚成功]\n{result.get('output', '')}"
            }
            alter_db2.update_op_device(dev_id, update_data)
            return {"code": 0, "msg": "回滚成功", "output": result.get('output', '')}
        else:
            update_data = {
                'result': f"[回滚失败]\n{result.get('error', '')}"
            }
            alter_db2.update_op_device(dev_id, update_data)
            return {"code": 500, "msg": f"回滚失败: {result.get('error', '')}", "output": result.get('error', '')}

    except Exception as e:
        logger.error(f"回滚设备命令失败: {e}")
        return {"code": 500, "msg": f"回滚失败: {str(e)}", "output": ""}
