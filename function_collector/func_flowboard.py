from tables.FlowBoardDB import FlowBoardDB
from utils.utils import decorator_checkparams
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_flow_list():
    """
    获取看板列表
    :return: 列表数据 或 "failed"
    """
    try:
        db = FlowBoardDB()
        result = db.get_flow_list()
        return result

    except Exception as e:
        logger.error(f"获取看板列表失败: {e}")
        return "failed"


def get_flow_detail(flow_id):
    """
    获取看板详情
    :param flow_id: 看板ID
    :return: 看板数据 或 "failed"
    """
    try:
        db = FlowBoardDB()
        result = db.get_flow_by_id(flow_id)
        return result

    except Exception as e:
        logger.error(f"获取看板详情失败: {e}")
        return "failed"


@decorator_checkparams(key_array=["flow_name"])
def create_flow(data):
    """
    创建看板
    :param data: 看板数据
    :return: {"flow_id": xx, "version": 1} 或 "duplicate" 或 "failed"
    """
    try:
        db_check = FlowBoardDB()
        existing = db_check.get_flow_by_name(data['flow_name'])

        if existing and existing != "failed":
            logger.warning(f"看板名称已存在: {data['flow_name']}")
            return "duplicate"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data.setdefault('created_at', now)
        data.setdefault('updated_at', now)
        data.setdefault('version', 1)
        data.setdefault('description', '')
        data.setdefault('category_types', [])
        data.setdefault('flow_json', '{}')

        db = FlowBoardDB()
        flow_id = db.create_flow(data)

        if flow_id and flow_id != "failed":
            return {
                "flow_id": flow_id,
                "version": 1
            }
        else:
            return "failed"

    except Exception as e:
        logger.error(f"创建看板失败: {e}")
        return "failed"


@decorator_checkparams(key_array=["flow_id"])
def update_flow(data):
    """
    更新看板
    :param data: 看板数据（必须包含flow_id和version）
    :return: success/version_conflict/not_found/duplicate/failed
    """
    try:
        db_check = FlowBoardDB()
        existing = db_check.get_flow_by_id(data['flow_id'])
        if not existing or existing == "failed":
            logger.warning(f"看板不存在: {data['flow_id']}")
            return "not_found"

        if 'version' in data:
            if existing.get('version') != data['version']:
                logger.warning(f"版本冲突，当前版本: {existing.get('version')}, 提交版本: {data['version']}")
                return "version_conflict"

        if 'flow_name' in data and data['flow_name'] != existing.get('flow_name'):
            db_name = FlowBoardDB()
            name_check = db_name.get_flow_by_name(data['flow_name'])
            if name_check and name_check != "failed":
                logger.warning(f"看板名称已存在: {data['flow_name']}")
                return "duplicate"

        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data['version'] = existing.get('version', 1) + 1

        db_update = FlowBoardDB()
        result = db_update.update_flow(data)

        if result == "success":
            return {"version": data['version'], "updated_at": data['updated_at']}
        else:
            return result

    except Exception as e:
        logger.error(f"更新看板失败: {e}")
        return "failed"


def delete_flow(flow_id):
    """
    删除看板
    :param flow_id: 看板ID
    :return: success/not_found/failed
    """
    try:
        db_check = FlowBoardDB()
        existing = db_check.get_flow_by_id(flow_id)
        if not existing or existing == "failed":
            logger.warning(f"看板不存在: {flow_id}")
            return "not_found"

        db_delete = FlowBoardDB()
        result = db_delete.delete_flow(flow_id)
        return result

    except Exception as e:
        logger.error(f"删除看板失败: {e}")
        return "failed"
