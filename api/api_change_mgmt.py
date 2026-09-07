from flask import Blueprint, request, g
from api.api_response import APIResponse
import logging
import json
import time
from function_op import type_manage, group_manage, notify_manage, order_manage, device_cmd_manage, log_manage

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
change_mgmt_bp = Blueprint('change_mgmt', __name__, url_prefix='/op')


# ==================== 工单类型管理 ====================

@change_mgmt_bp.route('/type/list', methods=['POST'])
def get_type_list():
    """获取工单类型列表"""
    try:
        data = request.json or {}
        logger.info(f"{str(g.user)}查询工单类型列表")

        result = type_manage.get_type_list(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取工单类型列表失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/type/add', methods=['POST'])
def add_type():
    """创建工单类型"""
    try:
        data = request.json or {}

        if not data.get('name'):
            return APIResponse.param_error(message="缺少参数 name")

        logger.info(f"{str(g.user)}创建工单类型: {data.get('name')}")

        result = type_manage.add_type(data)

        if result != "failed":
            return APIResponse.success(data={"pid": result}, message="创建成功")
        else:
            return APIResponse.error(message="创建失败")

    except Exception as e:
        logger.error(f"创建工单类型失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/type/update', methods=['POST'])
def update_type():
    """更新工单类型"""
    try:
        data = request.json or {}
        type_id = data.get('pid')

        if not type_id:
            return APIResponse.param_error(message="缺少参数 pid")
        if not data.get('name'):
            return APIResponse.param_error(message="缺少参数 name")

        logger.info(f"{str(g.user)}更新工单类型: {type_id}")

        result = type_manage.update_type(type_id, data)

        if result == "success":
            return APIResponse.success(message="更新成功")
        else:
            return APIResponse.error(message="更新失败")

    except Exception as e:
        logger.error(f"更新工单类型失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/type/delete', methods=['POST'])
def delete_type():
    """删除工单类型"""
    try:
        data = request.json or {}
        type_id = data.get('pid')

        if not type_id:
            return APIResponse.param_error(message="缺少参数 pid")

        logger.info(f"{str(g.user)}删除工单类型: {type_id}")

        result = type_manage.delete_type(type_id)

        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败")

    except Exception as e:
        logger.error(f"删除工单类型失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


# ==================== 审批分组管理 ====================

@change_mgmt_bp.route('/group/list', methods=['POST'])
def get_group_list():
    """获取审批分组列表"""
    try:
        data = request.json or {}
        logger.info(f"{str(g.user)}查询审批分组列表")

        result = group_manage.get_group_list(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取审批分组列表失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/group/add', methods=['POST'])
def add_group():
    """创建审批分组"""
    try:
        data = request.json or {}

        if not data.get('name'):
            return APIResponse.param_error(message="缺少参数 name")

        logger.info(f"{str(g.user)}创建审批分组: {data.get('name')}")

        result = group_manage.add_group(data)

        if result != "failed":
            return APIResponse.success(data={"pid": result}, message="创建成功")
        else:
            return APIResponse.error(message="创建失败")

    except Exception as e:
        logger.error(f"创建审批分组失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/group/update', methods=['POST'])
def update_group():
    """更新审批分组"""
    try:
        data = request.json or {}
        group_id = data.get('pid')

        if not group_id:
            return APIResponse.param_error(message="缺少参数 pid")
        if not data.get('name'):
            return APIResponse.param_error(message="缺少参数 name")

        logger.info(f"{str(g.user)}更新审批分组: {group_id}")

        result = group_manage.update_group(group_id, data)

        if result == "success":
            return APIResponse.success(message="更新成功")
        else:
            return APIResponse.error(message="更新失败")

    except Exception as e:
        logger.error(f"更新审批分组失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/group/delete', methods=['POST'])
def delete_group():
    """删除审批分组"""
    try:
        data = request.json or {}
        group_id = data.get('pid')

        if not group_id:
            return APIResponse.param_error(message="缺少参数 pid")

        logger.info(f"{str(g.user)}删除审批分组: {group_id}")

        result = group_manage.delete_group(group_id)

        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败")

    except Exception as e:
        logger.error(f"删除审批分组失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


# ==================== 通知群组管理 ====================

@change_mgmt_bp.route('/notify/list', methods=['POST'])
def get_notify_list():
    """获取通知群组列表"""
    try:
        data = request.json or {}
        logger.info(f"{str(g.user)}查询通知群组列表")

        result = notify_manage.get_notify_list(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取通知群组列表失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/notify/add', methods=['POST'])
def add_notify():
    """创建通知群组"""
    try:
        data = request.json or {}

        if not data.get('name'):
            return APIResponse.param_error(message="缺少参数 name")
        if not data.get('target'):
            return APIResponse.param_error(message="缺少参数 target")

        logger.info(f"{str(g.user)}创建通知群组: {data.get('name')}")

        result = notify_manage.add_notify(data)

        if result != "failed":
            return APIResponse.success(data={"pid": result}, message="创建成功")
        else:
            return APIResponse.error(message="创建失败")

    except Exception as e:
        logger.error(f"创建通知群组失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/notify/update', methods=['POST'])
def update_notify():
    """更新通知群组"""
    try:
        data = request.json or {}
        notify_id = data.get('pid')

        if not notify_id:
            return APIResponse.param_error(message="缺少参数 pid")
        if not data.get('name'):
            return APIResponse.param_error(message="缺少参数 name")
        if not data.get('target'):
            return APIResponse.param_error(message="缺少参数 target")

        logger.info(f"{str(g.user)}更新通知群组: {notify_id}")

        result = notify_manage.update_notify(notify_id, data)

        if result == "success":
            return APIResponse.success(message="更新成功")
        else:
            return APIResponse.error(message="更新失败")

    except Exception as e:
        logger.error(f"更新通知群组失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/notify/delete', methods=['POST'])
def delete_notify():
    """删除通知群组"""
    try:
        data = request.json or {}
        notify_id = data.get('pid')

        if not notify_id:
            return APIResponse.param_error(message="缺少参数 pid")

        logger.info(f"{str(g.user)}删除通知群组: {notify_id}")

        result = notify_manage.delete_notify(notify_id)

        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败")

    except Exception as e:
        logger.error(f"删除通知群组失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


# ==================== 工单管理 ====================

@change_mgmt_bp.route('/order/list', methods=['POST'])
def get_order_list():
    """获取工单列表"""
    try:
        data = request.json or {}
        logger.info(f"{str(g.user)}查询工单列表")

        result = order_manage.get_order_list(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取工单列表失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/detail', methods=['POST'])
def get_order_detail():
    """获取工单详情"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}查询工单详情: {op_id}")

        result = order_manage.get_order_detail(op_id)

        if result:
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="工单不存在")

    except Exception as e:
        logger.error(f"获取工单详情失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/add', methods=['POST'])
def add_order():
    """创建工单"""
    try:
        data = request.json or {}

        if not data.get('op_type'):
            return APIResponse.param_error(message="缺少参数 op_type")
        if not data.get('title'):
            return APIResponse.param_error(message="缺少参数 title")

        logger.info(f"{str(g.user)}创建工单: {data.get('title')}")

        result = order_manage.add_order(data, str(g.user))

        if result != "failed":
            return APIResponse.success(data={"op_id": result}, message="创建成功")
        else:
            return APIResponse.error(message="创建失败")

    except Exception as e:
        logger.error(f"创建工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/update', methods=['POST'])
def update_order():
    """更新工单"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}更新工单: {op_id}")

        # 移除op_id，避免被更新
        update_data = {k: v for k, v in data.items() if k != 'op_id'}

        result = order_manage.update_order(op_id, update_data, str(g.user))

        if result == "success":
            return APIResponse.success(message="更新成功")
        else:
            return APIResponse.error(message="更新失败")

    except Exception as e:
        logger.error(f"更新工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/delete', methods=['POST'])
def delete_order():
    """删除工单"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}删除工单: {op_id}")

        result = order_manage.delete_order(op_id)

        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败")

    except Exception as e:
        logger.error(f"删除工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/copy', methods=['POST'])
def copy_order():
    """复制工单"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}复制工单: {op_id}")

        result = order_manage.copy_order(op_id, str(g.user))

        if result != "failed":
            return APIResponse.success(data={"op_id": result}, message="复制成功")
        else:
            return APIResponse.error(message="复制失败")

    except Exception as e:
        logger.error(f"复制工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


# ==================== 工单流程操作 ====================

@change_mgmt_bp.route('/order/submit', methods=['POST'])
def submit_order():
    """提交工单"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}提交工单: {op_id}")

        result = order_manage.submit_order(op_id, str(g.user))

        if result.get("code") == 0:
            return APIResponse.success(message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"提交工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/takeover', methods=['POST'])
def takeover_order():
    """接手工单"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}接手工单: {op_id}")

        result = order_manage.takeover_order(op_id, str(g.user))

        if result.get("code") == 0:
            return APIResponse.success(message=result.get("msg"))
        elif result.get("code") == 403:
            return APIResponse.forbidden_error(message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"接手工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/approve', methods=['POST'])
def approve_order():
    """审批工单"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        approve_status = data.get('status')  # "10": 通过, "92": 拒绝

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")
        if not approve_status or approve_status not in ["10", "92"]:
            return APIResponse.param_error(message="参数 status 必须为 10(通过) 或 92(拒绝)")

        logger.info(f"{str(g.user)}审批工单: {op_id}, 结果: {approve_status}")

        result = order_manage.approve_order(op_id, str(g.user), approve_status)

        if result.get("code") == 0:
            return APIResponse.success(message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"审批工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/start', methods=['POST'])
def start_order():
    """开始变更"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}开始变更: {op_id}")

        result = order_manage.start_change(op_id, str(g.user))

        if result.get("code") == 0:
            return APIResponse.success(message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"开始变更失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/end', methods=['POST'])
def end_order():
    """结束变更"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        final_status = data.get('status', '90')  # "90": 成功, "91": 失败

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")
        if final_status not in ["90", "91"]:
            return APIResponse.param_error(message="参数 status 必须为 90(成功) 或 91(失败)")

        logger.info(f"{str(g.user)}结束变更: {op_id}, 结果: {final_status}")

        result = order_manage.end_change(op_id, str(g.user), final_status)

        if result.get("code") == 0:
            return APIResponse.success(message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"结束变更失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/cancel', methods=['POST'])
def cancel_order():
    """取消变更"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}取消变更: {op_id}")

        result = order_manage.cancel_change(op_id, str(g.user))

        if result.get("code") == 0:
            return APIResponse.success(message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"取消变更失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


# ==================== 设备命令管理 ====================

@change_mgmt_bp.route('/device/list', methods=['POST'])
def get_device_list():
    """获取工单的设备列表"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}查询设备列表: 工单{op_id}")

        result = device_cmd_manage.get_device_list(op_id)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取设备列表失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/device/add', methods=['POST'])
def add_device():
    """添加设备"""
    try:
        data = request.json or {}

        if not data.get('op_id'):
            return APIResponse.param_error(message="缺少参数 op_id")
        if not data.get('ip'):
            return APIResponse.param_error(message="缺少参数 ip")

        logger.info(f"{str(g.user)}添加设备: {data.get('ip')}")

        result = device_cmd_manage.add_device(data)

        if result != "failed":
            return APIResponse.success(data={"pid": result}, message="添加成功")
        else:
            return APIResponse.error(message="添加失败")

    except Exception as e:
        logger.error(f"添加设备失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/device/update', methods=['POST'])
def update_device():
    """更新设备"""
    try:
        data = request.json or {}
        dev_id = data.get('pid')

        if not dev_id:
            return APIResponse.param_error(message="缺少参数 pid")

        logger.info(f"{str(g.user)}更新设备: {dev_id}")

        # 移除pid，避免被更新
        update_data = {k: v for k, v in data.items() if k != 'pid'}

        result = device_cmd_manage.update_device(dev_id, update_data)

        if result == "success":
            return APIResponse.success(message="更新成功")
        else:
            return APIResponse.error(message="更新失败")

    except Exception as e:
        logger.error(f"更新设备失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/device/delete', methods=['POST'])
def delete_device():
    """删除设备"""
    try:
        data = request.json or {}
        dev_id = data.get('pid')

        if not dev_id:
            return APIResponse.param_error(message="缺少参数 pid")

        logger.info(f"{str(g.user)}删除设备: {dev_id}")

        result = device_cmd_manage.delete_device(dev_id)

        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败")

    except Exception as e:
        logger.error(f"删除设备失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


# ==================== 日志查询 ====================

@change_mgmt_bp.route('/log/list', methods=['POST'])
def get_log_list():
    """获取工单日志"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}查询工单日志: {op_id}")

        result = log_manage.get_log_list(op_id)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取工单日志失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/approval/list', methods=['POST'])
def get_approval_list():
    """获取审批记录"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        logger.info(f"{str(g.user)}查询审批记录: {op_id}")

        result = log_manage.get_approval_list(op_id)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取审批记录失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")
