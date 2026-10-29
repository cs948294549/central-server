from flask import Blueprint, request, g
from api.api_response import APIResponse
import logging
from function_collector.func_config import (
    get_config_list_by_device,
    get_config_detail_by_id,
    compare_configs_by_id,
    delete_config_by_id,
    get_latest_config_by_ip,
    get_device_config_diff,
    get_changed_devices,
    backup_config_by_ip
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

        latest_config = get_latest_config_by_ip(ip)

        if latest_config:
            return APIResponse.success(data=latest_config, message="查询成功")
        else:
            return APIResponse.error(message="未找到配置记录")

    except Exception as e:
        logger.error(f"获取最新配置失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@config_bp.route('/backup', methods=['POST'])
def backup_config():
    """
    手动备份单台设备配置（登录设备采集当前配置，与最新备份对比后保存）
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

        logger.info(f"{str(g.user)}手动备份设备配置，ip={ip}")

        result = backup_config_by_ip(ip)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "备份成功"))
        else:
            return APIResponse.error(message=result.get("message", "备份失败"))

    except Exception as e:
        logger.error(f"备份设备配置失败: {e}")
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


@config_bp.route('/get_changed_devices', methods=['POST'])
def get_changed_device_list():
    """
    获取最近发生过配置变更的设备列表
    判定依据：取每个IP最新一条配置记录，其 created_at 即该设备最近一次配置变更的时间
    请求参数:
    {
        "days": 7  # 可选，只统计最近N天内变更的设备，不传则返回所有有过变更记录的设备
    }
    返回字段与 /collector/getdeviceslist 一致
    """
    try:
        data = request.json or {}
        days = data.get('days')

        if days is not None:
            try:
                days = int(days)
            except (TypeError, ValueError):
                return APIResponse.error(message="参数 days 必须为整数")
            if days <= 0:
                return APIResponse.error(message="参数 days 必须大于0")

        logger.info(f"{str(g.user)}查询变更设备列表，days={days}")

        device_list = get_changed_devices(days)

        if device_list == "failed":
            return APIResponse.error(message="查询失败")

        return APIResponse.success(data=device_list, message="查询成功")

    except Exception as e:
        logger.error(f"获取变更设备列表失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@config_bp.route('/compare_by_order', methods=['POST'])
def compare_config_by_order():
    """
    获取设备在指定工单中的配置前后对比
    请求参数:
    {
        "ip": "10.0.0.1",      # 必填，设备IP
        "op_id": "123",        # 必填，工单ID
        "full_diff": false     # 可选，是否显示完整对比，默认false（只显示差异部分）
    }
    返回:
    {
        "html": "HTML格式的对比结果",
        "stats": {"added": 新增行数, "deleted": 删除行数, "modified": 修改行数},
        "before": {"log_id": xx, "ip": xx, "sysname": xx, "backup_time": xx},
        "after": {"log_id": xx, "ip": xx, "sysname": xx, "backup_time": xx}
    }
    """
    try:
        data = request.json or {}
        ip = data.get('ip')
        op_id = data.get('op_id')
        full_diff = data.get('full_diff', False)

        if not ip:
            return APIResponse.error(message="缺少参数 ip")
        if not op_id:
            return APIResponse.error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}查询设备配置对比，ip={ip}, op_id={op_id}, full_diff={full_diff}")

        result = get_device_config_diff(ip, op_id, full_diff)

        if result.get("html"):
            return APIResponse.success(data=result, message="对比成功")
        else:
            message = result.get("message", "配置对比失败")
            return APIResponse.error(message=message)

    except Exception as e:
        logger.error(f"获取设备配置对比失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")

