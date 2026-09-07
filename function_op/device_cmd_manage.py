"""
变更工单管理 - 设备管理业务逻辑层
"""
from tables.AlterationManageDB import AlterationManageDB
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


def batch_add_devices(devices_data):
    """
    批量添加设备

    Args:
        devices_data: 设备数据列表

    Returns:
        dict: {"code": 0/500, "msg": "消息", "success_count": 成功数量, "failed_count": 失败数量}
    """
    try:
        success_count = 0
        failed_count = 0

        for dev_data in devices_data:
            db = AlterationManageDB()
            result = db.add_op_device(dev_data)

            if result != "failed":
                success_count += 1
            else:
                failed_count += 1

        if failed_count == 0:
            return {"code": 0, "msg": "批量添加成功", "success_count": success_count, "failed_count": 0}
        elif success_count > 0:
            return {"code": 0, "msg": f"部分添加成功", "success_count": success_count, "failed_count": failed_count}
        else:
            return {"code": 500, "msg": "批量添加失败", "success_count": 0, "failed_count": failed_count}

    except Exception as e:
        logger.error(f"批量添加设备失败: {e}")
        return {"code": 500, "msg": f"批量添加失败: {str(e)}", "success_count": 0, "failed_count": len(devices_data)}


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
        # 获取设备信息
        db = AlterationManageDB()
        # 注意: AlterationManageDB 没有 get_op_device_by_id 方法
        # 需要先获取设备所属的工单，然后从列表中找到该设备
        # 这里暂时返回TODO提示

        # TODO: 实现命令执行逻辑
        # 1. 获取设备信息（IP、命令等）
        # 2. 调用网络设备执行接口
        # 3. 记录执行结果
        # 4. 更新设备状态

        logger.warning(f"设备命令执行功能待实现: dev_id={dev_id}, username={username}")
        return {"code": 500, "msg": "命令执行功能待实现", "output": ""}

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
        # TODO: 实现回滚逻辑
        # 1. 获取设备信息（IP、回滚命令等）
        # 2. 调用网络设备执行接口
        # 3. 记录执行结果
        # 4. 更新设备状态

        logger.warning(f"设备命令回滚功能待实现: dev_id={dev_id}, username={username}")
        return {"code": 500, "msg": "命令回滚功能待实现", "output": ""}

    except Exception as e:
        logger.error(f"回滚设备命令失败: {e}")
        return {"code": 500, "msg": f"回滚失败: {str(e)}", "output": ""}
