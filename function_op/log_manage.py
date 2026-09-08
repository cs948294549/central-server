"""
变更工单管理 - 日志管理业务逻辑层
"""
from tables.AlterationManageDB import AlterationManageDB
import logging

logger = logging.getLogger(__name__)


def get_log_list(op_id):
    """
    获取工单日志列表

    Args:
        op_id: 工单ID

    Returns:
        list: 日志列表
    """
    try:
        db = AlterationManageDB()
        result = db.get_op_log_list(op_id)
        return result
    except Exception as e:
        logger.error(f"获取日志列表失败: {e}")
        return "failed"


def add_op_log(op_id, tag, username, action):
    """
    记录工单操作日志，将操作人替换为中文名并拼接到日志内容中

    Args:
        op_id: 工单ID
        tag: 日志标签
        username: 操作人（登录名）
        action: 操作描述（不含用户名前缀）

    Returns:
        int/str: 成功返回日志ID,失败返回"failed"
    """
    try:
        db = AlterationManageDB()
        subname = db.get_username_subname(username)
        display_name = subname if subname else username

        db2 = AlterationManageDB()
        result = db2.add_op_log({
            "op_id": op_id,
            "tag": tag,
            "msg": f"{display_name} {action}",
            "username": display_name
        })
        return result
    except Exception as e:
        logger.error(f"添加操作日志失败: {e}")
        return "failed"


def get_approval_list(op_id):
    """
    获取审批记录列表

    Args:
        op_id: 工单ID

    Returns:
        list: 审批记录列表
    """
    try:
        db = AlterationManageDB()
        result = db.get_op_approval_list(op_id)
        return result
    except Exception as e:
        logger.error(f"获取审批记录失败: {e}")
        return "failed"
