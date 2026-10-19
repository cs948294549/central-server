"""端口组接口

本层只做参数校验和响应封装，业务逻辑一律走 function_policy.func_portgroup，
不直接引用 tables 下的库层方法。
"""
from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_policy import func_portgroup
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
portgroup_bp = Blueprint('portgroup', __name__, url_prefix='/acl/portgroup')


def _get_username():
    """从请求上下文取当前用户名"""
    return g.user.get('username', 'unknown') if isinstance(g.user, dict) else str(g.user)


def _require_standard_id(data):
    """取 standard_id，兼容页面直接传 id 的写法"""
    return data.get("standard_id") or data.get("id")


# ==================== 标准规则接口 ====================

@portgroup_bp.route('/standards/list', methods=['POST'])
def get_group_list():
    """获取端口组列表"""
    try:
        result = func_portgroup.get_group_list(request.json or {})

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"查询端口组列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@portgroup_bp.route('/standards/detail', methods=['POST'])
def get_group_detail():
    """获取端口组详情"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        result = func_portgroup.get_group_detail(data["id"])

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"查询端口组详情异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@portgroup_bp.route('/standards/create', methods=['POST'])
def create_group():
    """创建端口组"""
    try:
        data = request.json
        username = _get_username()
        logger.info(f"{username}创建端口组，数据: {data}")

        result = func_portgroup.create_group(data, username)

        if result["success"]:
            return APIResponse.success(data=result.get("data"), message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"创建端口组异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@portgroup_bp.route('/standards/update', methods=['POST'])
def update_group():
    """更新端口组"""
    try:
        data = request.json
        username = _get_username()
        logger.info(f"{username}更新端口组，数据: {data}")

        result = func_portgroup.update_group(data, username)

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"更新端口组异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@portgroup_bp.route('/standards/delete', methods=['POST'])
def delete_group():
    """删除端口组"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        username = _get_username()
        logger.info(f"{username}删除端口组，ID: {data['id']}")

        result = func_portgroup.delete_group(data["id"])

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"删除端口组异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")

@portgroup_bp.route('/standards/statistics', methods=['POST'])
def get_group_statistics():
    """获取端口组的设备应用统计"""
    try:
        data = request.json
        standard_id = _require_standard_id(data) if data else None
        if not standard_id:
            return APIResponse.param_error(message="缺少参数: standard_id")

        result = func_portgroup.get_group_statistics(standard_id)

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"获取端口组统计异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@portgroup_bp.route('/standards/device_list', methods=['POST'])
def get_group_device_list():
    """获取端口组关联的设备列表"""
    try:
        data = request.json
        standard_id = _require_standard_id(data) if data else None
        if not standard_id:
            return APIResponse.param_error(message="缺少参数: standard_id")

        result = func_portgroup.get_group_device_list(standard_id, data.get("filter", "all"))

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"获取端口组设备列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 设备配置记录接口 ====================

@portgroup_bp.route('/records/list', methods=['POST'])
def get_group_records_list():
    """获取端口组的设备配置记录列表"""
    try:
        result = func_portgroup.get_group_records_list(request.json or {})

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"查询端口组设备记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 对比与问题记录接口 ====================

@portgroup_bp.route('/compare/text_diff', methods=['POST'])
def compare_text_diff():
    """
    端口组配置文本对比接口

    页面只传 standard_id + device_ip，两侧条目由服务端自行解析。
    同时兼容直接传 src_entries / target_entries 的用法。
    """
    try:
        data = request.json
        if not data:
            return APIResponse.param_error(message="缺少参数")

        if "src_entries" in data and "target_entries" in data:
            src_entries = data["src_entries"]
            target_entries = data["target_entries"]
        else:
            standard_id = _require_standard_id(data)
            device_ip = data.get("device_ip")
            if not standard_id or not device_ip:
                return APIResponse.param_error(message="缺少参数: standard_id, device_ip")

            compared = func_portgroup.compare_group_with_standard(standard_id, device_ip)
            if not compared["success"]:
                return APIResponse.error(message=compared["message"])

            src_entries = compared["data"]["standard"]["entries"]
            target_entries = compared["data"]["device"]["entries"]

        result = func_portgroup.compare_group_text_diff(src_entries, target_entries, data.get("full_diff", False))

        if result["success"]:
            # 页面读取 diff_html，中间层返回的键名是 html
            return APIResponse.success(
                data={"diff_html": result["data"]["html"]},
                message=result["message"]
            )
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"端口组文本对比异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@portgroup_bp.route('/issues/batch_create', methods=['POST'])
def batch_create_issue_records():
    """批量创建端口组问题处理记录"""
    try:
        data = request.json
        username = _get_username()
        logger.info(f"{username}批量创建端口组问题处理记录，数据: {data}")

        if not data or "standard_id" not in data or "devices" not in data:
            return APIResponse.param_error(message="缺少参数: standard_id, devices")

        result = func_portgroup.batch_create_group_issues(
            data["standard_id"],
            data["devices"],
            username,
            data.get("remark", "")
        )

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"批量创建端口组问题记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")
