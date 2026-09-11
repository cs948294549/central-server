from flask import Blueprint, request, g
from api.api_response import APIResponse
from tables.PrefixListDB import PrefixListDB
from function_policy.func_prefix import (
    calculate_prefix_list_fingerprint,
    get_device_statistics_for_standard,
    get_device_list_for_standard,
    compare_configurations,
    group_records_by_fingerprint,
    batch_create_issue_records
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


@prefix_list_bp.route('/standards/detail', methods=['POST'])
def get_standard_detail():
    """获取标准规则详情"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.bad_request(message="缺少参数: id")

        db = PrefixListDB()
        result = db.getStandardDetail(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败，规则不存在")

    except Exception as e:
        logger.error(f"查询标准规则详情异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/create', methods=['POST'])
def create_standard():
    """创建标准规则"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}创建标准规则，数据: {data}")

        # 校验必填参数
        if not data or "name" not in data or "entries" not in data:
            return APIResponse.bad_request(message="缺少必要参数: name, entries")

        # 计算指纹
        entries_list = data["entries"].get("entries", []) if isinstance(data["entries"], dict) else data["entries"]
        fingerprint = calculate_prefix_list_fingerprint(entries_list)

        if not fingerprint:
            return APIResponse.error(message="计算配置指纹失败")

        # 准备数据
        create_data = {
            "name": data["name"],
            "fingerprint": fingerprint,
            "entries": {"entries": entries_list},  # 存储为统一格式
            "description": data.get("description", ""),
            "is_active": data.get("is_active", 1),
            "created_by": str(g.user)
        }

        db = PrefixListDB()
        result = db.createStandard(create_data)

        if result != "failed":
            return APIResponse.success(data={"id": result, "fingerprint": fingerprint}, message="创建成功")
        else:
            return APIResponse.error(message="创建失败，可能存在重复的规则")

    except Exception as e:
        logger.error(f"创建标准规则异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/update', methods=['POST'])
def update_standard():
    """更新标准规则"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}更新标准规则，数据: {data}")

        if not data or "id" not in data:
            return APIResponse.bad_request(message="缺少参数: id")

        # 如果更新了 entries，需要重新计算指纹
        if "entries" in data:
            entries_list = data["entries"].get("entries", []) if isinstance(data["entries"], dict) else data["entries"]
            fingerprint = calculate_prefix_list_fingerprint(entries_list)

            if not fingerprint:
                return APIResponse.error(message="计算配置指纹失败")

            data["fingerprint"] = fingerprint
            data["entries"] = {"entries": entries_list}

        db = PrefixListDB()
        result = db.updateStandard(data)

        if result != "failed" and result > 0:
            return APIResponse.success(message="更新成功")
        else:
            return APIResponse.error(message="更新失败，规则可能不存在")

    except Exception as e:
        logger.error(f"更新标准规则异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/delete', methods=['POST'])
def delete_standard():
    """删除标准规则"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}删除标准规则，数据: {data}")

        if not data or "id" not in data:
            return APIResponse.bad_request(message="缺少参数: id")

        db = PrefixListDB()
        result = db.deleteStandard(data)

        if result != "failed" and result > 0:
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败，规则可能不存在")

    except Exception as e:
        logger.error(f"删除标准规则异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/statistics', methods=['POST'])
def get_standard_statistics():
    """获取标准规则的设备应用统计"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.bad_request(message="缺少参数: id")

        # 获取标准规则详情
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": data["id"]})

        if standard == "failed":
            return APIResponse.error(message="标准规则不存在")

        # 获取统计数据
        statistics = get_device_statistics_for_standard(
            standard["id"],
            standard["name"],
            standard["fingerprint"]
        )

        return APIResponse.success(data=statistics, message="查询成功")

    except Exception as e:
        logger.error(f"获取标准规则统计异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/standards/device_list', methods=['POST'])
def get_standard_device_list():
    """获取标准规则关联的设备列表"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.bad_request(message="缺少参数: id")

        # 获取标准规则详情
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": data["id"]})

        if standard == "failed":
            return APIResponse.error(message="标准规则不存在")

        # 获取设备列表
        filter_type = data.get("filter", "all")  # all | matched | drifted
        device_list = get_device_list_for_standard(
            standard["name"],
            standard["fingerprint"],
            filter_type
        )

        return APIResponse.success(data=device_list, message="查询成功")

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


@prefix_list_bp.route('/records/compare', methods=['POST'])
def compare_record_with_standard():
    """对比设备配置与标准配置"""
    try:
        data = request.json
        if not data or "standard_id" not in data or "device_ip" not in data or "pl_name" not in data:
            return APIResponse.bad_request(message="缺少参数: standard_id, device_ip, pl_name")

        # 获取标准规则
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": data["standard_id"]})

        if standard == "failed":
            return APIResponse.error(message="标准规则不存在")

        # 获取设备配置
        records = db.getRecordsList({
            "device_ip": data["device_ip"],
            "pl_name": data["pl_name"]
        })

        if records == "failed" or len(records) == 0:
            return APIResponse.error(message="设备配置不存在")

        device_record = records[0]  # 取最新的记录

        # 对比配置
        standard_entries = standard["entries"].get("entries", []) if isinstance(standard["entries"], dict) else standard["entries"]
        device_entries = device_record["entries"]

        comparison = compare_configurations(standard_entries, device_entries)

        result = {
            "standard": {
                "id": standard["id"],
                "name": standard["name"],
                "fingerprint": standard["fingerprint"],
                "entries": standard_entries
            },
            "device": {
                "ip": device_record["device_ip"],
                "name": device_record["device_name"],
                "vendor": device_record["vendor"],
                "fingerprint": device_record["fingerprint"],
                "entries": device_entries,
                "collected_at": device_record["collected_at"]
            },
            "comparison": comparison
        }

        return APIResponse.success(data=result, message="对比成功")

    except Exception as e:
        logger.error(f"配置对比异常: {e}")
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


@prefix_list_bp.route('/issues/detail', methods=['POST'])
def get_issue_detail():
    """获取问题处理记录详情"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.bad_request(message="缺少参数: id")

        db = PrefixListDB()
        result = db.getIssueRecordDetail(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败，记录不存在")

    except Exception as e:
        logger.error(f"查询问题处理记录详情异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/issues/create', methods=['POST'])
def create_issue_record():
    """创建问题处理记录"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}创建问题处理记录，数据: {data}")

        # 校验必填参数
        required = ["standard_id", "device_ip"]
        for param in required:
            if param not in data:
                return APIResponse.bad_request(message=f"缺少参数: {param}")

        # 获取标准规则信息
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": data["standard_id"]})

        if standard == "failed":
            return APIResponse.error(message="标准规则不存在")

        # 获取设备配置记录
        records = db.getRecordsList({
            "device_ip": data["device_ip"],
            "pl_name": standard["name"]
        })

        # 判断问题类型
        if records == "failed" or len(records) == 0:
            # 缺失配置
            issue_type = "missing"
            device_name = data.get("device_name", "")
            device_vendor = data.get("device_vendor", "")
            device_entries = []
        else:
            # 配置漂移
            device_record = records[0]
            issue_type = "drifted"
            device_name = device_record["device_name"]
            device_vendor = device_record["vendor"]
            device_entries = device_record["entries"]

        # 创建问题记录
        standard_entries = standard["entries"].get("entries", []) if isinstance(standard["entries"], dict) else standard["entries"]

        create_data = {
            "standard_id": data["standard_id"],
            "standard_name": standard["name"],
            "device_ip": data["device_ip"],
            "device_name": device_name,
            "device_vendor": device_vendor,
            "issue_type": issue_type,
            "standard_entries": standard_entries,
            "device_entries": device_entries,
            "created_by": str(g.user),
            "remark": data.get("remark", "")
        }

        result = db.createIssueRecord(create_data)

        if result != "failed":
            return APIResponse.success(data={"id": result}, message="创建成功")
        else:
            return APIResponse.error(message="创建失败")

    except Exception as e:
        logger.error(f"创建问题处理记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/issues/batch_create', methods=['POST'])
def batch_create_issue_records():
    """批量创建问题处理记录"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}批量创建问题处理记录，数据: {data}")

        # 校验必填参数
        if not data or "standard_id" not in data or "devices" not in data:
            return APIResponse.bad_request(message="缺少参数: standard_id, devices")

        # 获取标准规则信息
        db = PrefixListDB()
        standard = db.getStandardDetail({"id": data["standard_id"]})

        if standard == "failed":
            return APIResponse.error(message="标准规则不存在")

        standard_entries = standard["entries"].get("entries", []) if isinstance(standard["entries"], dict) else standard["entries"]

        # 批量创建
        result = batch_create_issue_records(
            data["standard_id"],
            standard["name"],
            standard_entries,
            data["devices"],
            str(g.user)
        )

        return APIResponse.success(data=result, message=f"创建完成，成功{len(result['success'])}条，失败{len(result['failed'])}条")

    except Exception as e:
        logger.error(f"批量创建问题处理记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@prefix_list_bp.route('/issues/update_status', methods=['POST'])
def update_issue_status():
    """更新问题处理记录状态"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}更新问题处理记录状态，数据: {data}")

        if not data or "id" not in data:
            return APIResponse.bad_request(message="缺少参数: id")

        db = PrefixListDB()
        result = db.updateIssueRecordStatus(data)

        if result != "failed" and result > 0:
            return APIResponse.success(message="更新成功")
        else:
            return APIResponse.error(message="更新失败，记录可能不存在")

    except Exception as e:
        logger.error(f"更新问题处理记录状态异常: {e}")
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
