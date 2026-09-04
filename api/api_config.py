from flask import Blueprint, request, g
from api.api_response import APIResponse
import logging
from function_collector.func_config import (
    get_config_list_by_device,
    get_config_detail_by_id,
    compare_configs_by_id,
    delete_config_by_id
)

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
config_bp = Blueprint('config', __name__, url_prefix='/config')


@config_bp.route('/get_list', methods=['POST'])
def get_config_list():
    """
    获取设备配置备份列表
    请求参数:
    {
        "ip": "10.0.0.1",  # 可选，设备IP
        "sysname": "xxx"   # 可选，设备名（支持正则）
    }
    返回所有匹配的配置记录，前端自行进行分页处理
    """
    try:
        data = request.json or {}
        logger.info(f"{str(g.user)}查询配置列表，条件{data}")

        # 至少需要ip或sysname其中一个
        if "ip" not in data and "sysname" not in data:
            return APIResponse.error(message="请提供ip或sysname参数")

        config_list = get_config_list_by_device(data)

        return APIResponse.success(data=config_list, message="查询成功")

    except Exception as e:
        logger.error(f"获取配置列表失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@config_bp.route('/get_detail', methods=['POST'])
def get_config_detail():
    """
    获取配置详情（包含完整配置内容）
    请求参数:
    {
        "log_id": 123  # 必填，配置记录ID
    }
    """
    try:
        data = request.json or {}
        log_id = data.get('log_id')

        if not log_id:
            return APIResponse.error(message="缺少参数 log_id")

        logger.info(f"{str(g.user)}查询配置详情，log_id={log_id}")

        config_detail = get_config_detail_by_id(log_id)

        if config_detail:
            return APIResponse.success(data=config_detail, message="查询成功")
        else:
            return APIResponse.error(message="配置不存在")

    except Exception as e:
        logger.error(f"获取配置详情失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@config_bp.route('/compare', methods=['POST'])
def compare_configs():
    """
    对比两个配置版本
    请求参数:
    {
        "src_id": 123,      # 必填，源配置ID
        "tar_id": 124,      # 必填，目标配置ID
        "full_diff": false  # 可选，是否显示完整对比，默认false（只显示变更部分）
    }
    """
    try:
        data = request.json or {}
        src_id = data.get('src_id')
        tar_id = data.get('tar_id')
        full_diff = data.get('full_diff', False)

        if not src_id or not tar_id:
            return APIResponse.error(message="缺少参数 src_id 或 tar_id")

        if src_id == tar_id:
            return APIResponse.error(message="源配置和目标配置不能相同")

        logger.info(f"{str(g.user)}对比配置，src_id={src_id}, tar_id={tar_id}")

        result = compare_configs_by_id(src_id, tar_id, full_diff)

        if result.get("html"):
            return APIResponse.success(data=result, message="对比成功")
        else:
            return APIResponse.error(message="配置对比失败")

    except Exception as e:
        logger.error(f"配置对比失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@config_bp.route('/get_latest', methods=['POST'])
def get_latest_config():
    """
    获取设备最新的配置
    请求参数:
    {
        "ip": "10.0.0.1"  # 必填，设备IP
    }
    """
    try:
        data = request.json or {}
        ip = data.get('ip')

        if not ip:
            return APIResponse.error(message="缺少参数 ip")

        logger.info(f"{str(g.user)}查询最新配置，ip={ip}")

        from tables.ConfigDB import ConfigDB
        db = ConfigDB()
        latest_config = db.get_latest_config(ip)

        if latest_config:
            return APIResponse.success(data=latest_config, message="查询成功")
        else:
            return APIResponse.error(message="未找到配置记录")

    except Exception as e:
        logger.error(f"获取最新配置失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@config_bp.route('/delete', methods=['POST'])
def delete_config():
    """
    删除配置记录
    """
    try:
        data = request.json or {}
        log_id = data.get('log_id')
        if not log_id:
            return APIResponse.error(message="缺少参数 log_id")

        logger.info(f"{str(g.user)}删除配置记录，log_id={log_id}")

        result = delete_config_by_id(log_id)

        if result == "success":
            return APIResponse.success(data=None, message="删除成功")
        else:
            return APIResponse.error(message="删除失败")

    except Exception as e:
        logger.error(f"删除配置记录失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")
