from flask import Blueprint, request, g
from api.api_response import APIResponse
from tables.AccessListDB import AccessListDB
from tables.PolicyIssueDB import PolicyIssueDB
from function_policy import func_addrgroup
from function_policy import func_portgroup
from function_policy.func_access_list import (
    create_standard,
    update_standard,
    delete_standard,
    toggle_standard_active,
    get_standard_statistics,
    get_standard_device_list,
    compare_record_with_standard,
    compare_entries_text_diff,
    batch_create_issues,
    create_access_list_change_order,
    create_new_issue
)
from function_policy.func_issue import OBJECT_TYPE_ACL
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
acl_bp = Blueprint('acl', __name__, url_prefix='/acl')

# 地址组与端口组接口一致，只有库层实现不同，按 kind 分派
GROUP_MODULES = {
    "addrgroup": func_addrgroup,
    "portgroup": func_portgroup
}


def _get_username():
    """从请求上下文取当前用户名"""
    return g.user.get('username', 'unknown') if isinstance(g.user, dict) else str(g.user)


# ==================== 标准规则接口 ====================

@acl_bp.route('/standards/list', methods=['POST'])
def get_standards_list():
    """获取标准规则列表"""
    try:
        data = request.json or {}
        # 页面的搜索框走 keyword，库层按 name 查询
        if data.get("keyword") and not data.get("name"):
            data["name"] = data["keyword"]

        db = AccessListDB()
        result = db.getStandardsList(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"查询ACL标准规则列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/standards/detail', methods=['POST'])
def get_standard_detail():
    """获取标准规则详情"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        db = AccessListDB()
        result = db.getStandardDetail({"id": data["id"]})

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="标准规则不存在")

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


@acl_bp.route('/standards/toggle_active', methods=['POST'])
def toggle_standard_active_api():
    """切换标准规则的启用状态"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        result = toggle_standard_active(data["id"])

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"切换ACL标准规则状态异常: {e}")
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


# ==================== 地址组 / 端口组接口 ====================

def _get_group_module(kind):
    """按 kind 取得对应的组管理模块"""
    return GROUP_MODULES.get(kind)


@acl_bp.route('/groups/list', methods=['POST'])
def get_group_list():
    """获取地址组或端口组列表"""
    try:
        data = request.json or {}
        module = _get_group_module(data.get("kind"))
        if not module:
            return APIResponse.param_error(message="无效的 kind，可选: addrgroup, portgroup")

        result = module.get_group_list(data)

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"查询组列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/groups/detail', methods=['POST'])
def get_group_detail():
    """获取地址组或端口组详情"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        module = _get_group_module(data.get("kind"))
        if not module:
            return APIResponse.param_error(message="无效的 kind，可选: addrgroup, portgroup")

        result = module.get_group_detail(data["id"])

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"查询组详情异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/groups/create', methods=['POST'])
def create_group_api():
    """创建地址组或端口组"""
    try:
        data = request.json
        username = _get_username()

        module = _get_group_module(data.get("kind") if data else None)
        if not module:
            return APIResponse.param_error(message="无效的 kind，可选: addrgroup, portgroup")

        logger.info(f"{username}创建{data.get('kind')}，数据: {data}")
        result = module.create_group(data, username)

        if result["success"]:
            return APIResponse.success(data=result.get("data"), message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"创建组异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/groups/update', methods=['POST'])
def update_group_api():
    """更新地址组或端口组"""
    try:
        data = request.json
        username = _get_username()

        module = _get_group_module(data.get("kind") if data else None)
        if not module:
            return APIResponse.param_error(message="无效的 kind，可选: addrgroup, portgroup")

        logger.info(f"{username}更新{data.get('kind')}，数据: {data}")
        result = module.update_group(data, username)

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"更新组异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/groups/delete', methods=['POST'])
def delete_group_api():
    """删除地址组或端口组"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        module = _get_group_module(data.get("kind"))
        if not module:
            return APIResponse.param_error(message="无效的 kind，可选: addrgroup, portgroup")

        username = _get_username()
        logger.info(f"{username}删除{data.get('kind')}，ID: {data['id']}")
        result = module.delete_group(data["id"])

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"删除组异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/groups/toggle_active', methods=['POST'])
def toggle_group_active_api():
    """切换地址组或端口组的启用状态"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        module = _get_group_module(data.get("kind"))
        if not module:
            return APIResponse.param_error(message="无效的 kind，可选: addrgroup, portgroup")

        result = module.toggle_group_active(data["id"])

        if result["success"]:
            return APIResponse.success(message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"切换组状态异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 设备配置记录接口 ====================

@acl_bp.route('/records/list', methods=['POST'])
def get_records_list():
    """获取设备配置记录列表"""
    try:
        data = request.json or {}
        db = AccessListDB()
        result = db.getRecordsList(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"查询ACL设备配置记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 问题处理记录接口 ====================

@acl_bp.route('/issues/list', methods=['POST'])
def get_issues_list():
    """获取问题处理记录列表（只返回 ACL 类）"""
    try:
        data = request.json or {}
        # 问题记录表为多类型共用，本蓝图固定只查 ACL
        data["object_type"] = OBJECT_TYPE_ACL

        db = PolicyIssueDB()
        result = db.getIssueRecordsList(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"查询ACL问题处理记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


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


@acl_bp.route('/issues/new_issue', methods=['POST'])
def create_new_issue_record():
    """创建新的问题处理记录（手动创建缺失配置类型）"""
    try:
        data = request.json
        username = _get_username()
        logger.info(f"{username}创建ACL新问题记录，数据: {data}")

        if not data or "device_ip" not in data or "standard_id" not in data:
            return APIResponse.param_error(message="缺少参数: device_ip, standard_id")

        result = create_new_issue(
            data["device_ip"],
            data["standard_id"],
            username,
            data.get("remark", "")
        )

        if result["success"]:
            return APIResponse.success(data=result["data"], message=result["message"])
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"创建ACL新问题记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/issues/statistics', methods=['POST'])
def get_issues_statistics():
    """获取问题处理记录统计（只统计 ACL 类）"""
    try:
        db = PolicyIssueDB()
        result = db.getIssueStatistics({"object_type": OBJECT_TYPE_ACL})

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取ACL问题处理记录统计异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/issues/delete', methods=['POST'])
def delete_issue_record():
    """删除问题处理记录"""
    try:
        data = request.json
        if not data or "id" not in data:
            return APIResponse.param_error(message="缺少参数: id")

        db = PolicyIssueDB()
        result = db.deleteIssueRecord({"id": data["id"]})

        if result != "failed" and result > 0:
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败，记录可能不存在")

    except Exception as e:
        logger.error(f"删除ACL问题处理记录异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/issues/update_status', methods=['POST'])
def update_issue_status():
    """更新问题处理记录状态"""
    try:
        data = request.json
        if not data or "id" not in data or "status" not in data:
            return APIResponse.param_error(message="缺少参数: id 或 status")

        issue_id = data["id"]
        status = data["status"]

        # 验证状态值
        if status not in ['pending', 'processing', 'completed', 'ignored']:
            return APIResponse.param_error(message="无效的状态值")

        # 获取issue记录，查询设备IP
        db_query = PolicyIssueDB()
        issue_records = db_query.getIssueRecordsList({"id": issue_id, "object_type": OBJECT_TYPE_ACL})

        if not issue_records or len(issue_records) == 0:
            return APIResponse.error(message="记录不存在")

        # 更新状态
        db_update = PolicyIssueDB()
        result = db_update.updateIssueStatus({"id": issue_id, "status": status})

        if result != "failed" and result > 0:
            # 如果标记为已完成，触发采集更新
            if status == 'completed':
                device_ip = issue_records[0].get("device_ip")
                if device_ip:
                    from function_policy.func_access_list import collect_and_update_access_lists
                    try:
                        collect_result = collect_and_update_access_lists(device_ip)
                        logger.info(f"标记完成后触发ACL采集，设备: {device_ip}，结果: {collect_result}")
                    except Exception as e:
                        logger.error(f"触发ACL采集失败: {e}")
                        # 采集失败不影响状态更新成功的返回

            return APIResponse.success(message="状态更新成功")
        else:
            return APIResponse.error(message="状态更新失败，记录可能不存在")

    except Exception as e:
        logger.error(f"更新ACL问题处理记录状态异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 对比与变更工单接口 ====================

@acl_bp.route('/compare/text_diff', methods=['POST'])
def compare_text_diff():
    """
    ACL 配置文本对比接口

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
            standard_id = data.get("standard_id") or data.get("id")
            device_ip = data.get("device_ip")
            if not standard_id or not device_ip:
                return APIResponse.param_error(message="缺少参数: standard_id, device_ip")

            compared = compare_record_with_standard(standard_id, device_ip)
            if not compared["success"]:
                return APIResponse.error(message=compared["message"])

            src_entries = compared["data"]["standard"]["entries"]
            target_entries = compared["data"]["device"]["entries"]

        full_diff = data.get("full_diff", False)
        result = compare_entries_text_diff(src_entries, target_entries, full_diff)

        if result["success"]:
            # 页面读取 diff_html，中间层返回的键名是 html
            return APIResponse.success(
                data={"diff_html": result["data"]["html"]},
                message=result["message"]
            )
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"ACL文本对比异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/change_order/create', methods=['POST'])
def create_change_order():
    """
    创建 ACL 变更工单

    页面有两种入口：单条记录传 standard_id + device_ip，
    批量传 issue_ids。前者需要在服务端补齐对应的问题记录。
    """
    try:
        data = request.json
        username = _get_username()

        if not data:
            return APIResponse.param_error(message="缺少参数")

        issue_ids = data.get("issue_ids")

        if not issue_ids:
            standard_id = data.get("standard_id")
            device_ip = data.get("device_ip")
            if not standard_id or not device_ip:
                return APIResponse.param_error(message="缺少参数: issue_ids 或 standard_id + device_ip")

            # 该设备上这条 ACL 的待处理记录
            db = PolicyIssueDB()
            records = db.getIssueRecordsList({
                "object_type": OBJECT_TYPE_ACL,
                "standard_id": standard_id,
                "device_ip": device_ip
            })

            if records == "failed":
                return APIResponse.error(message="查询问题记录失败")

            pending = [r["id"] for r in records if r.get("status") == "pending"]
            if len(pending) == 0:
                return APIResponse.error(message="该设备没有待处理的问题记录")

            issue_ids = pending

        if not isinstance(issue_ids, list) or len(issue_ids) == 0:
            return APIResponse.param_error(message="issue_ids必须是非空数组")

        title = data.get("title")
        logger.info(f"{username}创建ACL变更工单，问题记录ID: {issue_ids}, 标题: {title}")

        result = create_access_list_change_order(issue_ids, username, title)

        if result["success"]:
            result_data = result.get("data") or {}
            return APIResponse.success(
                data={
                    "order_id": result_data.get("op_id"),
                    "device_count": result_data.get("device_count", 0),
                    "message": result["message"]
                },
                message=result["message"]
            )
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"创建ACL变更工单异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@acl_bp.route('/change_order/batch_create', methods=['POST'])
def batch_create_change_order():
    """
    批量创建 ACL 变更工单

    页面 acl_issue.vue 的批量建单入口调用的是 batchCreateIssueRecords，
    实际动作是建变更工单，因此这里返回 created 给页面统计。
    """
    try:
        data = request.json
        username = _get_username()

        if not data or "issue_ids" not in data:
            return APIResponse.param_error(message="缺少参数: issue_ids")

        issue_ids = data["issue_ids"]
        if not isinstance(issue_ids, list) or len(issue_ids) == 0:
            return APIResponse.param_error(message="issue_ids必须是非空数组")

        entities = data.get("entities")
        if entities:
            # 按实体拆成多个工单，回滚/执行粒度更细
            order_ids = []
            failed = []
            for entity in entities:
                ids = entity.get("issue_ids", [])
                if not ids:
                    continue
                result = create_access_list_change_order(ids, username, entity.get("title"))
                if result["success"]:
                    order_ids.append((result.get("data") or {}).get("op_id"))
                else:
                    failed.append({"issue_ids": ids, "message": result["message"]})

            if len(order_ids) == 0:
                return APIResponse.error(message=f"创建失败: {failed}")

            message = f"已创建 {len(order_ids)} 个变更工单"
            if failed:
                message += f"，{len(failed)} 个失败"
            return APIResponse.success(
                data={"created": len(order_ids), "order_ids": order_ids, "failed": failed},
                message=message
            )

        logger.info(f"{username}批量创建ACL变更工单，问题记录ID: {issue_ids}")
        result = create_access_list_change_order(issue_ids, username, data.get("title"))

        if result["success"]:
            result_data = result.get("data") or {}
            return APIResponse.success(
                data={
                    "created": len(issue_ids),
                    "order_id": result_data.get("op_id"),
                    "device_count": result_data.get("device_count", 0),
                    "message": result["message"]
                },
                message=result["message"]
            )
        else:
            return APIResponse.error(message=result["message"])

    except Exception as e:
        logger.error(f"批量创建ACL变更工单异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")
