"""ACL 标准规则、设备配置记录、问题处理记录接口"""
from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_policy.func_access_list import (
    get_standard_list,
    get_standard_detail,
    get_records_list,
    create_standard,
    update_standard,
    delete_standard,
    get_standard_statistics,
    get_standard_device_list,
    compare_record_with_standard,
    compare_entries_text_diff,
    batch_create_issues
)
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
acl_bp = Blueprint('acl', __name__, url_prefix='/acl')


def _get_username():
    """从请求上下文取当前用户名"""
    return g.user.get('username', 'unknown') if isinstance(g.user, dict) else str(g.user)


# ==================== 标准规则接口 ====================

@acl_bp.route('/standards/list', methods=['POST'])
def get_standards_list():
    """获取标准规则列表"""
    try:
        data = request.json or {}
        result = get_standard_list(data)

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"查询ACL标准规则列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/standards/detail', methods=['POST'])
def get_standard_detail_api():
    """获取标准规则详情"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        result = get_standard_detail(data["id"])

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"查询ACL标准规则详情异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/standards/create', methods=['POST'])
def create_standard_api():
    """创建标准规则"""
    try:
        data = request.json
        username = _get_username()
        logger.info(f"{username}创建ACL标准规则，数据: {data}")

        result = create_standard(data, username)

        if result["success"]:
            return APIResponse.success(data=result.get("data"), message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"创建ACL标准规则异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/standards/update', methods=['POST'])
def update_standard_api():
    """更新标准规则"""
    try:
        data = request.json
        username = _get_username()
        logger.info(f"{username}更新ACL标准规则，数据: {data}")

        result = update_standard(data, username)

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"更新ACL标准规则异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/standards/delete', methods=['POST'])
def delete_standard_api():
    """删除标准规则"""
    try:
        data = request.json
        username = _get_username()
        logger.info(f"{username}删除ACL标准规则，数据: {data}")

        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        result = delete_standard(data["id"])

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"删除ACL标准规则异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/standards/statistics', methods=['POST'])
def get_standard_statistics_api():
    """获取标准规则的设备应用统计"""
    try:
        data = request.json
        # 页面传 standard_id，中间层接收裸 id
        standard_id = data.get("standard_id") or data.get("id") if data else None
        if not standard_id:
            return APIResponse.param_error(message="缺少参数: standard_id")

        result = get_standard_statistics(standard_id)

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"获取ACL标准规则统计异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/standards/device_list', methods=['POST'])
def get_standard_device_list_api():
    """获取标准规则关联的设备列表"""
    try:
        data = request.json
        standard_id = data.get("standard_id") or data.get("id") if data else None
        if not standard_id:
            return APIResponse.param_error(message="缺少参数: standard_id")

        filter_type = data.get("filter", "all")
        result = get_standard_device_list(standard_id, filter_type)

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"获取ACL标准规则设备列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 设备配置记录接口 ====================

@acl_bp.route('/records/list', methods=['POST'])
def get_records_list():
    """获取设备配置记录列表"""
    try:
        data = request.json or {}
        result = get_records_list(data)

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"查询ACL设备配置记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/compare/text_diff', methods=['POST'])
def compare_text_diff():
    """
    配置文本对比，由页面传入两侧条目。
    """
    try:
        data = request.json
        if not data:
            return APIResponse.param_error(message="缺少参数")
        if "src_entries" in data and "target_entries" in data:
            src_entries = data["src_entries"]
            target_entries = data["target_entries"]
        else:
            standard_id = data.get("standard_id") or data.get("id")
            device_ip = data.get("device_ip")
            if not standard_id or not device_ip:
                return APIResponse.param_error(message="缺少参数: standard_id, device_ip")
            compared = compare_record_with_standard(standard_id, device_ip)
            if not compared["success"]:
                return APIResponse.error(message=compared["message"])
            src_entries = compared["data"]["standard"]["entries"]
            target_entries = compared["data"]["device"]["entries"]

        result = compare_entries_text_diff(src_entries, target_entries, data.get("full_diff", False))
        if result["success"]:
            return APIResponse.success(data={"diff_html": result["data"]["html"]}, message=result["message"])
        return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"ACL文本对比异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 问题处理记录接口 ====================

@acl_bp.route('/issues/batch_create', methods=['POST'])
def batch_create_issue_records_api():
    """批量创建问题处理记录"""
    try:
        data = request.json
        username = _get_username()
        logger.info(f"{username}批量创建ACL问题处理记录，数据: {data}")

        if not data or "standard_id" not in data or "devices" not in data:
            return APIResponse.param_error(message="缺少参数: standard_id, devices")

        result = batch_create_issues(
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
        logger.error(f"批量创建ACL问题处理记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")
