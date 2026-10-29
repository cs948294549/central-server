"""
策略配置问题处理记录统一接口（跨 object_type）

前缀列表 / ACL / 地址组 / 端口组 的问题处理流程一致，差异按 object_type
在 function 层内部分发，本层只做参数校验与响应包装。
"""
from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_policy import func_issue
import logging

logger = logging.getLogger(__name__)

policy_issue_bp = Blueprint('policy_issue', __name__, url_prefix='/policy/issues')


def _get_username():
    """从鉴权上下文取当前用户名"""
    return g.user.get('username', 'unknown') if isinstance(g.user, dict) else str(g.user)


@policy_issue_bp.route('/list', methods=['POST'])
def get_issue_list():
    """获取问题处理记录列表，object_type 为空表示查全部类型"""
    try:
        data = request.json or {}
        result = func_issue.get_issue_list(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data", []), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"))

    except Exception as e:
        logger.error(f"获取问题处理记录列表失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"查询失败: {str(e)}")


@policy_issue_bp.route('/detail', methods=['POST'])
def get_issue_detail():
    """获取问题处理记录详情"""
    try:
        data = request.json or {}
        if "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        result = func_issue.get_issue_detail(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"))

    except Exception as e:
        logger.error(f"获取问题处理记录详情失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"查询失败: {str(e)}")


@policy_issue_bp.route('/delete', methods=['POST'])
def delete_issue():
    """删除问题处理记录"""
    try:
        data = request.json or {}
        if "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        result = func_issue.delete_issue(data)

        if result.get("success"):
            return APIResponse.success(message=result.get("message", "删除成功"))
        return APIResponse.error(message=result.get("message", "删除失败"))

    except Exception as e:
        logger.error(f"删除问题处理记录失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"删除失败: {str(e)}")


@policy_issue_bp.route('/update_status', methods=['POST'])
def update_issue_status():
    """更新问题处理记录状态，标记 completed 时按对象类型触发回采"""
    try:
        data = request.json or {}
        if "id" not in data or "status" not in data:
            return APIResponse.param_error(message="缺少参数: id 或 status")

        result = func_issue.change_issue_status(data)

        if result.get("success"):
            return APIResponse.success(message=result.get("message", "状态更新成功"))
        return APIResponse.error(message=result.get("message", "状态更新失败"))

    except Exception as e:
        logger.error(f"更新问题处理记录状态失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"更新失败: {str(e)}")


@policy_issue_bp.route('/recollect', methods=['POST'])
def recollect_device():
    """
    基于设备最新备份配置重新解析策略对象并更新记录表
    请求参数: {"object_type": "prefix_list/acl/addrgroup/portgroup", "device_ip": "10.0.0.1"}
    """
    try:
        data = request.json or {}
        for key in ("object_type", "device_ip"):
            if not data.get(key):
                return APIResponse.param_error(message=f"缺少参数: {key}")

        logger.info(f"{_get_username()}手动重新解析，object_type={data['object_type']}, device_ip={data['device_ip']}")

        result = func_issue.recollect_device(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "重新解析成功"))
        return APIResponse.error(message=result.get("message", "重新解析失败"))

    except Exception as e:
        logger.error(f"重新解析失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"重新解析失败: {str(e)}")


@policy_issue_bp.route('/compare/text_diff', methods=['POST'])
def compare_text_diff():
    """配置差异对比，支持 issue_id 或 standard_id + device_ip 或直接传 entries"""
    try:
        data = request.json or {}
        if "object_type" not in data:
            return APIResponse.param_error(message="缺少参数: object_type")

        result = func_issue.compare_issue_text_diff(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "对比成功"))
        return APIResponse.error(message=result.get("message", "对比失败"))

    except Exception as e:
        logger.error(f"配置差异对比失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"对比失败: {str(e)}")


@policy_issue_bp.route('/change_order/create', methods=['POST'])
def create_change_order():
    """
    创建变更工单

    支持两种入参：
    - {"issue_ids": [1, 2, 3], "title": "..."}
    - {"standard_id": 1, "device_ip": "1.1.1.1", "object_type": "acl", "title": "..."}
    """
    try:
        data = request.json or {}

        issue_ids = data.get("issue_ids") or []

        # 按标准规则 + 设备创建：先查是否已有待处理记录
        if not issue_ids and data.get("standard_id") and data.get("device_ip"):
            object_type = data.get("object_type")
            if not object_type:
                return APIResponse.param_error(message="缺少参数: object_type")

            records = func_issue.get_issue_list({
                "object_type": object_type,
                "standard_id": data["standard_id"],
                "device_ip": data["device_ip"]
            })
            if not records.get("success"):
                return APIResponse.error(message=records.get("message", "查询问题记录失败"))

            issue_ids = [r["id"] for r in records.get("data", []) if r.get("status") in ("pending", "processing")]

            if not issue_ids:
                return APIResponse.error(message="未找到待处理的问题记录，请先创建处理记录")

        if not issue_ids:
            return APIResponse.param_error(message="缺少参数: issue_ids 或 standard_id+device_ip")

        result = func_issue.create_change_order(issue_ids, _get_username(), data.get("title"))

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "工单创建成功"))
        return APIResponse.error(message=result.get("message", "工单创建失败"), data=result.get("data"))

    except Exception as e:
        logger.error(f"基于问题记录创建变更工单失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"创建工单失败: {str(e)}")


@policy_issue_bp.route('/new_issue', methods=['POST'])
def create_new_issue():
    """手动创建问题处理记录"""
    try:
        data = request.json or {}
        for key in ("object_type", "standard_id", "device_ip"):
            if key not in data:
                return APIResponse.param_error(message=f"缺少参数: {key}")

        result = func_issue.create_new_issue(data, _get_username())

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "创建成功"))
        return APIResponse.error(message=result.get("message", "创建失败"))

    except Exception as e:
        logger.error(f"创建问题处理记录失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"创建失败: {str(e)}")
