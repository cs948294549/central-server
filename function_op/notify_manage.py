"""
变更工单管理 - 通知群组业务逻辑层
"""
from tables.AlterationManageDB import AlterationManageDB
import logging

logger = logging.getLogger(__name__)


def get_notify_list(filters=None):
    """
    获取通知群组列表

    Args:
        filters: 筛选条件字典

    Returns:
        list: 通知群组列表
    """
    try:
        db = AlterationManageDB()
        result = db.get_notify_group_list(filters or {})
        return result
    except Exception as e:
        logger.error(f"获取通知群组列表失败: {e}")
        return "failed"


def add_notify(data):
    """
    创建通知群组

    Args:
        data: 通知群组数据

    Returns:
        int/str: 成功返回群组ID,失败返回"failed"
    """
    try:
        db = AlterationManageDB()
        result = db.add_notify_group(data)
        return result
    except Exception as e:
        logger.error(f"创建通知群组失败: {e}")
        return "failed"


def update_notify(notify_id, data):
    """
    更新通知群组

    Args:
        notify_id: 群组ID
        data: 更新数据

    Returns:
        str: "success" 或 "failed"
    """
    try:
        db = AlterationManageDB()
        result = db.update_notify_group(notify_id, data)
        return result
    except Exception as e:
        logger.error(f"更新通知群组失败: {e}")
        return "failed"


def delete_notify(notify_id):
    """
    删除通知群组

    Args:
        notify_id: 群组ID

    Returns:
        str: "success" 或 "failed"
    """
    try:
        db = AlterationManageDB()
        result = db.delete_notify_group(notify_id)
        return result
    except Exception as e:
        logger.error(f"删除通知群组失败: {e}")
        return "failed"
