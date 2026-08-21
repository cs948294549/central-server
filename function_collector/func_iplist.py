from tables.IplistDB import IplistDB
from utils.utils import decorator_checkparams
import logging

logger = logging.getLogger(__name__)


@decorator_checkparams(key_array=[])
def get_iplist(data):
    """
    获取设备IP清单列表
    :param data: 包含search、admin_status等参数
    :return: 列表数据 或 "failed"
    """
    try:
        db = IplistDB()
        result = db.getIpList(data)
        return result

    except Exception as e:
        logger.error(f"获取设备IP清单列表失败: {e}")
        return "failed"


@decorator_checkparams(key_array=["ip", "sysname"])
def add_iplist(data):
    """
    添加设备IP
    :param data: 设备数据
    :return: success/failed
    """
    try:
        # 检查IP是否已存在
        db_check = IplistDB()
        existing = db_check.getIpByIp({"ip": data['ip']})

        if existing and existing != "failed":
            logger.warning(f"设备IP已存在: {data['ip']}")
            return "failed"

        db = IplistDB()
        result = db.addIp(data)

        if result == "failed":
            return "failed"
        else:
            return "success"

    except Exception as e:
        logger.error(f"添加设备IP失败: {e}")
        return "failed"


@decorator_checkparams(key_array=["ip", "sysname"])
def update_iplist(data):
    """
    更新设备IP信息
    :param data: 设备数据
    :return: success/failed
    """
    try:
        db = IplistDB()
        result = db.updateIp(data)
        return result

    except Exception as e:
        logger.error(f"更新设备IP失败: {e}")
        return "failed"


@decorator_checkparams(key_array=["ip"])
def delete_iplist(data):
    """
    删除设备IP
    :param data: 包含ip字段
    :return: success/failed
    """
    try:
        db = IplistDB()
        result = db.delIp(data)
        return result

    except Exception as e:
        logger.error(f"删除设备IP失败: {e}")
        return "failed"


@decorator_checkparams(key_array=["ip_list"])
def batch_delete_iplist(data):
    """
    批量删除设备IP
    :param data: 包含ip_list字段（IP地址列表）
    :return: success/failed
    """
    try:
        ip_list = data.get('ip_list', [])

        if not ip_list or not isinstance(ip_list, list):
            logger.warning("批量删除设备IP失败: ip_list为空或格式不正确")
            return "failed"

        db = IplistDB()
        result = db.batchDelIp(data)
        return result

    except Exception as e:
        logger.error(f"批量删除设备IP失败: {e}")
        return "failed"


def get_all_active_iplist():
    """
    获取所有状态为正常的设备IP列表
    :return: IP列表或"failed"
    """
    try:
        db = IplistDB()
        result = db.getAllActiveIps()
        return result

    except Exception as e:
        logger.error(f"获取所有正常设备IP失败: {e}")
        return "failed"

