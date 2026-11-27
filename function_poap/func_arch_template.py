"""
业务架构模板（配置模板）管理中间方法
api 层只调这里的函数，不直接碰 tables.ArchTemplateDB
"""
import logging

from tables.ArchTemplateDB import ArchTemplateDB

logger = logging.getLogger(__name__)


def get_template_list(data):
    """
    获取模板列表
    :param data: {keyword, arch_type, is_active, vendor, page, page_size}
    :return: {success: bool, data: {list, total}, message: str}
    """
    try:
        db = ArchTemplateDB()
        result = db.getTemplateList(data)

        if result == "failed":
            return {"success": False, "message": "查询失败"}

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取模板列表失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_template_detail(data):
    """
    获取模板详情
    :param data: {tid} 或 {id}
    :return: {success: bool, data: {}, message: str}
    """
    try:
        db = ArchTemplateDB()
        result = db.getTemplateDetail(data)

        if result == "failed":
            return {"success": False, "message": "模板不存在"}

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取模板详情失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def create_template(data):
    """
    创建模板
    :param data: {tid, name, arch_type, description, tags, created_by, configs}
    :return: {success: bool, data: {tid}, message: str}
    """
    try:
        if not data.get("tid") or not data.get("name"):
            return {"success": False, "message": "缺少必要参数：tid, name"}

        db = ArchTemplateDB()
        result = db.createTemplate(data)

        if result == "failed":
            return {"success": False, "message": "创建失败"}

        return {"success": True, "data": result, "message": "创建成功"}

    except Exception as err:
        logger.error(f"创建模板失败: {err}")
        return {"success": False, "message": f"创建失败: {str(err)}"}


def update_template(data):
    """
    更新模板
    :param data: {tid, name, arch_type, description, tags, is_active, updated_by, configs}
    :return: {success: bool, data: {tid, updated_vendors}, message: str}
    """
    try:
        if not data.get("tid"):
            return {"success": False, "message": "缺少参数 tid"}

        db = ArchTemplateDB()
        result = db.updateTemplate(data)

        if result == "failed":
            return {"success": False, "message": "更新失败"}

        return {"success": True, "data": result, "message": "更新成功"}

    except Exception as err:
        logger.error(f"更新模板失败: {err}")
        return {"success": False, "message": f"更新失败: {str(err)}"}


def delete_template(data):
    """
    删除模板（软删除）
    :param data: {tid}
    :return: {success: bool, message: str}
    """
    try:
        if not data.get("tid"):
            return {"success": False, "message": "缺少参数 tid"}

        db = ArchTemplateDB()
        result = db.deleteTemplate(data)

        if result == "failed":
            return {"success": False, "message": "删除失败"}

        return {"success": True, "message": "删除成功"}

    except Exception as err:
        logger.error(f"删除模板失败: {err}")
        return {"success": False, "message": f"删除失败: {str(err)}"}


def duplicate_template(data):
    """
    复制模板
    :param data: {tid（源模板）, new_tid, created_by}
    :return: {success: bool, data: {tid}, message: str}
    """
    try:
        if not data.get("tid") or not data.get("new_tid"):
            return {"success": False, "message": "缺少必要参数：tid, new_tid"}

        db = ArchTemplateDB()
        result = db.duplicateTemplate(data)

        if result == "failed":
            return {"success": False, "message": "复制失败"}

        return {"success": True, "data": result, "message": "复制成功"}

    except Exception as err:
        logger.error(f"复制模板失败: {err}")
        return {"success": False, "message": f"复制失败: {str(err)}"}


def get_snapshot_list(data):
    """
    获取某个模板某个厂商的版本历史
    :param data: {tid, vendor}
    :return: {success: bool, data: [], message: str}
    """
    try:
        if not data.get("tid") or not data.get("vendor"):
            return {"success": False, "message": "缺少参数 tid 或 vendor"}

        db = ArchTemplateDB()
        result = db.getSnapshotList(data)

        if result == "failed":
            return {"success": False, "message": "查询失败"}

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取版本历史失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_snapshot_detail(data):
    """
    获取指定版本快照
    :param data: {tid, vendor, version}
    :return: {success: bool, data: {}, message: str}
    """
    try:
        if not data.get("tid") or not data.get("vendor") or data.get("version") is None:
            return {"success": False, "message": "缺少参数 tid、vendor 或 version"}

        db = ArchTemplateDB()
        result = db.getSnapshot(data)

        if result == "failed":
            return {"success": False, "message": "快照不存在"}

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取版本快照失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}
