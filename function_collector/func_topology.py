from tables.TopologyDB import TopologyDB
from utils.utils import decorator_checkparams
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_topology_list():
    """
    获取拓扑列表
    :return: 列表数据 或 "failed"
    """
    try:
        db = TopologyDB()
        result = db.get_topology_list()
        return result

    except Exception as e:
        logger.error(f"获取拓扑列表失败: {e}")
        return "failed"


def get_topology_detail(topology_id):
    """
    获取拓扑详情
    :param topology_id: 拓扑ID
    :return: 拓扑数据 或 "failed"
    """
    try:
        db = TopologyDB()
        result = db.get_topology_by_id(topology_id)
        return result

    except Exception as e:
        logger.error(f"获取拓扑详情失败: {e}")
        return "failed"


@decorator_checkparams(key_array=["topology_name"])
def create_topology(data):
    """
    创建拓扑
    :param data: 拓扑数据
    :return: {"topology_id": xx, "version": 1} 或 "duplicate" 或 "failed"
    """
    try:
        # 检查名称是否已存在
        db_check = TopologyDB()
        existing = db_check.get_topology_by_name(data['topology_name'])

        if existing and existing != "failed":
            logger.warning(f"拓扑名称已存在: {data['topology_name']}")
            return "duplicate"

        # 设置默认值
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data.setdefault('created_at', now)
        data.setdefault('updated_at', now)
        data.setdefault('version', 1)
        data.setdefault('description', '')
        data.setdefault('category_types', [])
        data.setdefault('topology_json', '{}')

        db = TopologyDB()
        topology_id = db.create_topology(data)

        if topology_id and topology_id != "failed":
            return {
                "topology_id": topology_id,
                "version": 1
            }
        else:
            return "failed"

    except Exception as e:
        logger.error(f"创建拓扑失败: {e}")
        return "failed"


@decorator_checkparams(key_array=["topology_id"])
def update_topology(data):
    """
    更新拓扑
    :param data: 拓扑数据（必须包含topology_id和version）
    :return: success/version_conflict/not_found/duplicate/failed
    """
    try:
        # 检查拓扑是否存在
        db_check = TopologyDB()
        existing = db_check.get_topology_by_id(data['topology_id'])
        if not existing or existing == "failed":
            logger.warning(f"拓扑不存在: {data['topology_id']}")
            return "not_found"

        # 乐观锁检查
        if 'version' in data:
            if existing.get('version') != data['version']:
                logger.warning(f"版本冲突，当前版本: {existing.get('version')}, 提交版本: {data['version']}")
                return "version_conflict"

        # 如果修改了名称，检查新名称是否已存在
        if 'topology_name' in data and data['topology_name'] != existing.get('topology_name'):
            db_name = TopologyDB()
            name_check = db_name.get_topology_by_name(data['topology_name'])
            if name_check and name_check != "failed":
                logger.warning(f"拓扑名称已存在: {data['topology_name']}")
                return "duplicate"

        # 更新时间和版本号
        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data['version'] = existing.get('version', 1) + 1

        # 执行更新
        db_update = TopologyDB()
        result = db_update.update_topology(data)
        return result

    except Exception as e:
        logger.error(f"更新拓扑失败: {e}")
        return "failed"


def delete_topology(topology_id):
    """
    删除拓扑
    :param topology_id: 拓扑ID
    :return: success/not_found/failed
    """
    try:
        # 检查拓扑是否存在
        db_check = TopologyDB()
        existing = db_check.get_topology_by_id(topology_id)
        if not existing or existing == "failed":
            logger.warning(f"拓扑不存在: {topology_id}")
            return "not_found"

        # 执行删除
        db_delete = TopologyDB()
        result = db_delete.delete_topology(topology_id)
        return result

    except Exception as e:
        logger.error(f"删除拓扑失败: {e}")
        return "failed"
