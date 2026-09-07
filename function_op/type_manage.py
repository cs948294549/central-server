"""
变更工单管理 - 工单类型业务逻辑层
"""
from tables.AlterationManageDB import AlterationManageDB
import logging

logger = logging.getLogger(__name__)


def get_type_list(filters=None):
    """
    获取工单类型列表

    Args:
        filters: 筛选条件字典

    Returns:
        list: 工单类型列表
    """
    try:
        db = AlterationManageDB()
        result = db.get_op_type_list(filters or {})
        return result
    except Exception as e:
        logger.error(f"获取工单类型列表失败: {e}")
        return "failed"


def add_type(data):
    """
    创建工单类型

    Args:
        data: 工单类型数据

    Returns:
        int/str: 成功返回类型ID,失败返回"failed"
    """
    try:
        db = AlterationManageDB()
        result = db.add_op_type(data)
        return result
    except Exception as e:
        logger.error(f"创建工单类型失败: {e}")
        return "failed"


def update_type(type_id, data):
    """
    更新工单类型

    Args:
        type_id: 类型ID
        data: 更新数据

    Returns:
        str: "success" 或 "failed"
    """
    try:
        db = AlterationManageDB()
        result = db.update_op_type(type_id, data)
        return result
    except Exception as e:
        logger.error(f"更新工单类型失败: {e}")
        return "failed"


def delete_type(type_id):
    """
    删除工单类型

    Args:
        type_id: 类型ID

    Returns:
        str: "success" 或 "failed"
    """
    try:
        # TODO: 检查是否有关联的工单
        db = AlterationManageDB()
        result = db.delete_op_type(type_id)
        return result
    except Exception as e:
        logger.error(f"删除工单类型失败: {e}")
        return "failed"
