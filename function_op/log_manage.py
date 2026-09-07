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


def add_log(data):
    """
    添加日志记录

    Args:
        data: 日志数据
            - op_id: 工单ID
            - tag: 日志标签
            - msg: 日志内容
            - username: 操作人

    Returns:
        int/str: 成功返回日志ID,失败返回"failed"
    """
    try:
        db = AlterationManageDB()
        result = db.add_op_log(data)
        return result
    except Exception as e:
        logger.error(f"添加日志失败: {e}")
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
