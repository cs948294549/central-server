"""
变更工单管理 - 审批分组业务逻辑层
"""
from tables.AlterationManageDB import AlterationManageDB
import logging

logger = logging.getLogger(__name__)


def get_group_list(filters=None):
    """
    获取审批分组列表

    Args:
        filters: 筛选条件字典

    Returns:
        list: 审批分组列表
    """
    try:
        db = AlterationManageDB()
        result = db.get_op_group_list(filters or {})
        return result
    except Exception as e:
        logger.error(f"获取审批分组列表失败: {e}")
        return "failed"


def add_group(data):
    """
    创建审批分组

    Args:
        data: 审批分组数据

    Returns:
        int/str: 成功返回分组ID,失败返回"failed"
    """
    try:
        db = AlterationManageDB()
        result = db.add_op_group(data)
        return result
    except Exception as e:
        logger.error(f"创建审批分组失败: {e}")
        return "failed"


def update_group(group_id, data):
    """
    更新审批分组

    Args:
        group_id: 分组ID
        data: 更新数据

    Returns:
        str: "success" 或 "failed"
    """
    try:
        db = AlterationManageDB()
        result = db.update_op_group(group_id, data)
        return result
    except Exception as e:
        logger.error(f"更新审批分组失败: {e}")
        return "failed"


def delete_group(group_id):
    """
    删除审批分组

    Args:
        group_id: 分组ID

    Returns:
        str: "success" 或 "failed"
    """
    try:
        # TODO: 检查是否被工单类型引用
        db = AlterationManageDB()
        result = db.delete_op_group(group_id)
        return result
    except Exception as e:
        logger.error(f"删除审批分组失败: {e}")
        return "failed"
