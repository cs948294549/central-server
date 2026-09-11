from flask import Blueprint, request, g
from api.api_response import APIResponse
from tables.PrefixListDB import PrefixListDB
from function_policy.func_prefix import (
    create_standard,
    update_standard,
    delete_standard,
    get_standard_statistics,
    get_standard_device_list,
    batch_create_issues,
    group_records_by_fingerprint,
    compare_entries_text_diff
)
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
prefix_list_bp = Blueprint('prefix_list', __name__, url_prefix='/prefix_list')


# ==================== 标准规则接口 ====================

@prefix_list_bp.route('/standards/list', methods=['POST'])
def get_standards_list():
    """获取标准规则列表"""
    try:
        data = request.json or {}
        db = PrefixListDB()
        result = db.getStandardsList(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"查询标准规则列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/create', methods=['POST'])
def create_standard_api():
    """创建标准规则"""
    try:
        data = request.json
        username = g.user.get('username', 'unknown') if isinstance(g.user, dict) else str(g.user)
        logger.info(f"{username}创建标准规则，数据: {data}")

        result = create_standard(data, username)

        if result["success"]:
            return APIResponse.success(data=result.get("data"), message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"创建标准规则异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/update', methods=['POST'])
def update_standard_api():
    """更新标准规则"""
    try:
        data = request.json
        username = g.user.get('username', 'unknown') if isinstance(g.user, dict) else str(g.user)
        logger.info(f"{username}更新标准规则，数据: {data}")

        result = update_standard(data, username)

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"更新标准规则异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/delete', methods=['POST'])
def delete_standard_api():
    """删除标准规则"""
    try:
        data = request.json
        username = g.user.get('username', 'unknown') if isinstance(g.user, dict) else str(g.user)
        logger.info(f"{username}删除标准规则，数据: {data}")

        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        result = delete_standard(data["id"])

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"删除标准规则异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/statistics', methods=['POST'])
def get_standard_statistics_api():
    """获取标准规则的设备应用统计"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        result = get_standard_statistics(data["id"])

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"获取标准规则统计异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/device_list', methods=['POST'])
def get_standard_device_list_api():
    """获取标准规则关联的设备列表"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        filter_type = data.get("filter", "all")
        result = get_standard_device_list(data["id"], filter_type)

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"获取标准规则设备列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 设备配置记录接口 ====================

@prefix_list_bp.route('/records/list', methods=['POST'])
def get_records_list():
    """获取设备配置记录列表"""
    try:
        data = request.json or {}
        db = PrefixListDB()
        result = db.getRecordsList(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"查询设备配置记录列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/records/grouped_by_fingerprint', methods=['POST'])
def get_records_grouped():
    """获取按指纹分组的设备配置记录"""
    try:
        data = request.json or {}
        db = PrefixListDB()
        records = db.getRecordsList(data)

        if records == "failed":
            return APIResponse.error(message="查询失败")

        # 按指纹分组
        grouped = group_records_by_fingerprint(records)

        # 转换为列表格式
        result = []
        for fingerprint, devices in grouped.items():
            result.append({
                "fingerprint": fingerprint,
                "count": len(devices),
                "devices": devices
            })

        return APIResponse.success(data=result, message="查询成功")

    except Exception as e:
        logger.error(f"查询分组记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 问题处理记录接口 ====================

@prefix_list_bp.route('/issues/list', methods=['POST'])
def get_issues_list():
    """获取问题处理记录列表"""
    try:
        data = request.json or {}
        db = PrefixListDB()
        result = db.getIssueRecordsList(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"查询问题处理记录列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/issues/batch_create', methods=['POST'])
def batch_create_issue_records_api():
    """批量创建问题处理记录"""
    try:
        data = request.json
        username = g.user.get('username', 'unknown') if isinstance(g.user, dict) else str(g.user)
        logger.info(f"{username}批量创建问题处理记录，数据: {data}")

        if not data or "standard_id" not in data or "devices" not in data:
            return APIResponse.param_error(message="缺少参数: standard_id, devices")

        result = batch_create_issues(
            data["standard_id"],
            data["devices"],
            username
        )

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"批量创建问题处理记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/issues/statistics', methods=['POST'])
def get_issues_statistics():
    """获取问题处理记录统计"""
    try:
        db = PrefixListDB()
        result = db.getIssueStatistics({})

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取问题处理记录统计异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/issues/delete', methods=['POST'])
def delete_issue_record():
    """删除问题处理记录"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        issue_id = data["id"]
        db = PrefixListDB()
        result = db.deleteIssueRecord({"id": issue_id})

        if result != "failed" and result > 0:
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败，记录可能不存在")

    except Exception as e:
        logger.error(f"删除问题处理记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/compare/text_diff', methods=['POST'])
def compare_text_diff():
    """
    前缀列表配置文本对比接口
    """
    try:
        data = request.json
        if not data or "src_entries" not in data or "target_entries" not in data:
            return APIResponse.param_error(message="缺少参数: src_entries, target_entries")

        src_entries = data["src_entries"]
        target_entries = data["target_entries"]
        full_diff = data.get("full_diff", False)

        result = compare_entries_text_diff(src_entries, target_entries, full_diff)

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"文本对比异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")
