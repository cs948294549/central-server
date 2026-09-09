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

# ==================== 状态常量定义 ====================
STATUS_DRAFT = "00"           # 草稿
STATUS_PENDING = "01"         # 待审批
STATUS_APPROVING = "02"       # 审批中
STATUS_APPROVED = "10"        # 审批通过
STATUS_READY = "20"           # 待变更
STATUS_CHANGING = "21"        # 变更中 - 唯一可执行命令的状态
STATUS_SUCCESS = "90"         # 变更完成
STATUS_FAILED = "91"          # 变更失败
STATUS_REJECTED = "92"        # 审批拒绝
STATUS_CANCELLED = "93"       # 已取消

# 状态显示名称映射
STATUS_NAME_MAP = {
    STATUS_DRAFT: "草稿",
    STATUS_PENDING: "待审批",
    STATUS_APPROVING: "审批中",
    STATUS_READY: "待变更",
    STATUS_CHANGING: "变更中",
    STATUS_SUCCESS: "已完成",
    STATUS_FAILED: "已失败",
    STATUS_REJECTED: "已拒绝",
    STATUS_CANCELLED: "已取消"
}


# ==================== 安全检查方法 ====================

def check_order_editable(op_id, username):
    """
    检查工单是否可编辑（仅草稿状态可编辑）

    Returns:
        tuple: (is_allowed: bool, error_response: APIResponse or None)
    """
    order_detail = order_manage.get_order_detail(op_id)
    if not order_detail or order_detail == "failed":
        return False, APIResponse.error(message="工单不存在")

    # 状态检查：只有草稿状态才能修改
    if order_detail.get('status') != STATUS_DRAFT:
        logger.warning(f"安全拦截: {username}尝试修改非草稿工单{op_id}，当前状态:{order_detail.get('status')}")
        return False, APIResponse.error(message=f"工单已提交(状态:{order_detail.get('status')})，内容已锁定不可修改。仅草稿状态可编辑")

    # 权限检查：只有创建人可以修改草稿
    creator = order_detail.get('username', '')
    if username != creator:
        logger.warning(f"安全拦截: {username}尝试修改他人工单{op_id}，创建人:{creator}")
        return False, APIResponse.error(message=f"无权限修改，仅创建人({creator})可修改草稿工单")

    return True, None


def check_order_executable(op_id, username):
    """
    检查工单是否可执行命令（仅变更中状态可执行）

    Returns:
        tuple: (is_allowed: bool, error_response: APIResponse or None)
    """
    order_detail = order_manage.get_order_detail(op_id)
    if not order_detail or order_detail == "failed":
        return False, APIResponse.error(message="工单不存在")

    # 状态检查：只有变更中状态才能执行命令
    current_status = order_detail.get('status', '')
    if current_status != STATUS_CHANGING:
        current_status_name = STATUS_NAME_MAP.get(current_status, current_status)
        logger.warning(f"安全拦截: {username}尝试在非变更中状态执行命令，工单{op_id}，当前状态={current_status_name}")
        return False, APIResponse.error(message=f"工单当前状态为'{current_status_name}'，仅在'变更中'状态才能执行命令。请先调用'/order/start'开始变更")

    # 权限检查：只有创建人或指定变更人可以执行
    creator = order_detail.get('username', '')
    assigner = order_detail.get('assigner', '')
    if username != creator and username != assigner:
        logger.warning(f"安全拦截: {username}尝试执行工单{op_id}，创建人={creator}，指定执行人={assigner}")
        return False, APIResponse.error(message=f"无权限执行，仅创建人({creator})和指定变更人({assigner})可执行")

    return True, None


def check_order_submittable(op_id, username):
    """
    检查是否可提交工单（仅创建人可提交）

    Returns:
        tuple: (is_allowed: bool, error_response: APIResponse or None)
    """
    order_detail = order_manage.get_order_detail(op_id)
    if not order_detail or order_detail == "failed":
        return False, APIResponse.error(message="工单不存在")

    # 权限检查：只有创建人可以提交
    creator = order_detail.get('username', '')
    if username != creator:
        logger.warning(f"安全拦截: {username}尝试提交他人工单{op_id}，创建人={creator}")
        return False, APIResponse.error(message=f"无权限提交，仅创建人({creator})可提交工单")

    return True, None


def check_order_takeover(op_id, username):
    """
    检查是否可接手工单（需在当前审批组内）

    Returns:
        tuple: (is_allowed: bool, error_response: APIResponse or None, order_detail: dict)
    """
    order_detail = order_manage.get_order_detail(op_id)
    if not order_detail or order_detail == "failed":
        return False, APIResponse.error(message="工单不存在"), None

    # 权限检查：检查当前用户是否在cur_group中
    cur_group = order_detail.get("cur_group", "")
    if username not in cur_group.split(","):
        logger.warning(f"安全拦截: {username}尝试接手工单{op_id}，当前审批组={cur_group}")
        return False, APIResponse.error(message="您不在当前审批组中，无权接手"), None

    return True, None, order_detail


def check_order_approvable(op_id, username):
    """
    检查是否可审批工单（需为接手人）

    Returns:
        tuple: (is_allowed: bool, error_response: APIResponse or None, order_detail: dict)
    """
    order_detail = order_manage.get_order_detail(op_id)
    if not order_detail or order_detail == "failed":
        return False, APIResponse.error(message="工单不存在"), None

    # 权限检查：只有接手人可以审批
    cur_user = order_detail.get("cur_user", "")
    if username != cur_user:
        logger.warning(f"安全拦截: {username}尝试审批工单{op_id}，接手人={cur_user}")
        return False, APIResponse.error(message=f"无权限审批，仅接手人({cur_user})可审批工单"), None

    return True, None, order_detail


def check_order_changeable(op_id, username):
    """
    检查是否可操作变更（开始/结束/取消）（需为创建人或指定执行人）

    Returns:
        tuple: (is_allowed: bool, error_response: APIResponse or None)
    """
    order_detail = order_manage.get_order_detail(op_id)
    if not order_detail or order_detail == "failed":
        return False, APIResponse.error(message="工单不存在")

    # 权限检查：只有创建人或指定执行人可以操作变更
    creator = order_detail.get('username', '')
    assigner = order_detail.get('assigner', '')
    if username != creator and username != assigner:
        logger.warning(f"安全拦截: {username}尝试操作变更工单{op_id}，创建人={creator}，指定执行人={assigner}")
        return False, APIResponse.error(message=f"无权限操作，仅创建人({creator})和指定执行人({assigner})可操作变更")

    return True, None


# ==================== 工单类型管理 ====================

@change_mgmt_bp.route('/type/list', methods=['POST'])
def get_type_list():
    """获取工单类型列表"""
    try:
        data = request.json or {}
        logger.info(f"{g.user.get('username', '')}查询工单类型列表")

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

        logger.info(f"{g.user.get('username', '')}创建工单类型: {data.get('name')}")

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

        logger.info(f"{g.user.get('username', '')}更新工单类型: {type_id}")

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

        logger.info(f"{g.user.get('username', '')}删除工单类型: {type_id}")

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
        logger.info(f"{g.user.get('username', '')}查询审批分组列表")

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

        logger.info(f"{g.user.get('username', '')}创建审批分组: {data.get('name')}")

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

        logger.info(f"{g.user.get('username', '')}更新审批分组: {group_id}")

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

        logger.info(f"{g.user.get('username', '')}删除审批分组: {group_id}")

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
        logger.info(f"{g.user.get('username', '')}查询通知群组列表")

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

        logger.info(f"{g.user.get('username', '')}创建通知群组: {data.get('name')}")

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

        logger.info(f"{g.user.get('username', '')}更新通知群组: {notify_id}")

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

        logger.info(f"{g.user.get('username', '')}删除通知群组: {notify_id}")

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
        logger.info(f"{g.user.get('username', '')}查询工单列表")

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

        logger.info(f"{g.user.get('username', '')}查询工单详情: {op_id}")

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

        logger.info(f"{g.user.get('username', '')}创建工单: {data.get('title')}")

        result = order_manage.add_order(data, g.user.get('username', ''))

        if result != "failed":
            return APIResponse.success(data={"op_id": result}, message="创建成功")
        else:
            return APIResponse.error(message="创建失败")

    except Exception as e:
        logger.error(f"创建工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/update', methods=['POST'])
def update_order():
    """更新工单 - 仅草稿状态允许修改"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        # 安全检查
        is_allowed, error_response = check_order_editable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}更新草稿工单: {op_id}")

        # 移除op_id，避免被更新
        update_data = {k: v for k, v in data.items() if k != 'op_id'}

        result = order_manage.update_order(op_id, update_data, username)

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

        current_username = g.user.get('username', '')
        current_rid = g.user.get('rid', '')
        logger.info(f"{current_username}删除工单: {op_id}")

        # 先查询工单信息，验证权限
        order_detail = order_manage.get_order_detail(op_id)
        if not order_detail:
            return APIResponse.error(message="工单不存在")

        # 判断是否为管理员
        is_admin = current_rid in ['system', 'admin']

        # 管理员可以删除任意工单，普通用户只能删除草稿状态且是自己创建的工单
        if not is_admin:
            if order_detail.get('status') != '00':
                return APIResponse.error(message="只能删除草稿状态的工单")
            if order_detail.get('username') != current_username:
                return APIResponse.error(message="只能删除自己创建的工单")

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

        logger.info(f"{g.user.get('username', '')}复制工单: {op_id}")

        result = order_manage.copy_order(op_id, g.user.get('username', ''))

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
    """提交工单 - 仅创建人可提交"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        # 安全检查
        is_allowed, error_response = check_order_submittable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}提交工单: {op_id}")

        result = order_manage.submit_order(op_id, username)

        if result.get("code") == 0:
            return APIResponse.success(message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"提交工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/takeover', methods=['POST'])
def takeover_order():
    """接手工单 - 需在当前审批组内"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        # 安全检查
        is_allowed, error_response, order_detail = check_order_takeover(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}接手工单: {op_id}")

        result = order_manage.takeover_order(op_id, username)

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
    """审批工单 - 仅接手人可审批"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        approve_status = data.get('status')  # "10": 通过, "92": 拒绝
        comment = data.get('comment', '')
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")
        if not approve_status or approve_status not in ["10", "92"]:
            return APIResponse.param_error(message="参数 status 必须为 10(通过) 或 92(拒绝)")

        # 安全检查
        is_allowed, error_response, order_detail = check_order_approvable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}审批工单: {op_id}, 结果: {approve_status}")

        result = order_manage.approve_order(op_id, username, approve_status, comment)

        if result.get("code") == 0:
            return APIResponse.success(message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"审批工单失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/start', methods=['POST'])
def start_change():
    """开始变更（变更前备份配置）- 仅创建人或指定执行人可操作"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        # 安全检查
        is_allowed, error_response = check_order_changeable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}开始变更: {op_id}")

        result = order_manage.start_change(op_id, username)

        if result.get("code") == 0:
            return APIResponse.success(data=result.get("data"), message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"开始变更失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/finish', methods=['POST'])
def finish_change():
    """结束变更（变更后备份配置）- 仅创建人或指定执行人可操作"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        status = data.get('status', '90')  # "90": 变更完成, "91": 变更失败
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")
        if status not in ["90", "91"]:
            return APIResponse.param_error(message="参数 status 必须为 90(变更完成) 或 91(变更失败)")

        # 安全检查
        is_allowed, error_response = check_order_changeable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}结束变更: {op_id}, 状态: {status}")

        result = order_manage.finish_change(op_id, username, status)

        if result.get("code") == 0:
            return APIResponse.success(data=result.get("data"), message=result.get("msg"))
        else:
            return APIResponse.error(message=result.get("msg"))

    except Exception as e:
        logger.error(f"结束变更失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/cancel', methods=['POST'])
def cancel_order():
    """取消变更 - 仅创建人或指定执行人可操作"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        # 安全检查
        is_allowed, error_response = check_order_changeable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}取消变更: {op_id}")

        result = order_manage.cancel_change(op_id, username)

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

        logger.info(f"{g.user.get('username', '')}查询设备列表: 工单{op_id}")

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
    """添加设备 - 仅草稿状态允许添加"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")
        if not data.get('ip'):
            return APIResponse.param_error(message="缺少参数 ip")

        # 安全检查
        is_allowed, error_response = check_order_editable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}添加设备: 工单{op_id}, IP={data.get('ip')}")

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
    """更新设备配置 - 仅草稿状态允许修改"""
    try:
        data = request.json or {}
        dev_id = data.get('pid')
        op_id = data.get('op_id')
        username = g.user.get('username', '')

        if not dev_id:
            return APIResponse.param_error(message="缺少参数 pid")
        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        # 安全检查
        is_allowed, error_response = check_order_editable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}更新设备配置: 设备{dev_id}, 工单{op_id}")

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
    """删除设备 - 仅草稿状态允许删除"""
    try:
        data = request.json or {}
        dev_id = data.get('pid')
        op_id = data.get('op_id')
        username = g.user.get('username', '')

        if not dev_id:
            return APIResponse.param_error(message="缺少参数 pid")
        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")

        # 安全检查
        is_allowed, error_response = check_order_editable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"{username}删除设备: 设备{dev_id}, 工单{op_id}")

        result = device_cmd_manage.delete_device(dev_id)

        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败")

    except Exception as e:
        logger.error(f"删除设备失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/execute/batch', methods=['POST'])
def execute_batch():
    """批次执行设备命令 - 仅变更中状态允许执行"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        device_ids = data.get('device_ids', [])
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")
        if not device_ids or not isinstance(device_ids, list):
            return APIResponse.param_error(message="缺少参数 device_ids 或格式错误")

        # 安全检查
        is_allowed, error_response = check_order_executable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"✅ 安全检查通过: {username}批次执行工单{op_id}, 设备数{len(device_ids)}")

        # 批量执行设备命令
        success_count = 0
        failed_count = 0
        for device_id in device_ids:
            result = device_cmd_manage.execute_device_command(device_id, username)
            if result.get('code') == 0:
                success_count += 1
            else:
                failed_count += 1
                logger.error(f"设备 {device_id} 执行失败: {result.get('msg')}")

        # 记录审计日志
        log_manage.add_op_log(
            op_id,
            "10",
            username,
            f"批次执行命令: {success_count}成功/{failed_count}失败，设备ID={','.join(map(str, device_ids))}"
        )

        return APIResponse.success(message=f"批次执行完成：成功{success_count}台，失败{failed_count}台")

    except Exception as e:
        logger.error(f"批次执行失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/execute/device', methods=['POST'])
def execute_device():
    """执行单个设备命令 - 仅变更中状态允许执行"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        device_id = data.get('device_id')
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")
        if not device_id:
            return APIResponse.param_error(message="缺少参数 device_id")

        # 安全检查
        is_allowed, error_response = check_order_executable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"✅ 安全检查通过: {username}执行设备{device_id}, 工单{op_id}")

        # 执行设备命令
        result = device_cmd_manage.execute_device_command(device_id, username)

        # 记录审计日志
        status_text = "成功" if result.get('code') == 0 else "失败"
        log_manage.add_op_log(
            op_id,
            "10",
            username,
            f"执行设备命令{status_text}: 设备ID={device_id}, 结果={result.get('msg', '')}"
        )

        if result.get('code') == 0:
            return APIResponse.success(data={"output": result.get('output')}, message=result.get('msg'))
        else:
            return APIResponse.error(message=result.get('msg'))

    except Exception as e:
        logger.error(f"执行设备失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")


@change_mgmt_bp.route('/order/rollback/device', methods=['POST'])
def rollback_device():
    """回滚单个设备命令 - 仅变更中状态允许回滚"""
    try:
        data = request.json or {}
        op_id = data.get('op_id')
        device_id = data.get('device_id')
        username = g.user.get('username', '')

        if not op_id:
            return APIResponse.param_error(message="缺少参数 op_id")
        if not device_id:
            return APIResponse.param_error(message="缺少参数 device_id")

        # 安全检查
        is_allowed, error_response = check_order_executable(op_id, username)
        if not is_allowed:
            return error_response

        logger.info(f"✅ 安全检查通过: {username}回滚设备{device_id}, 工单{op_id}")

        # 回滚设备命令
        result = device_cmd_manage.rollback_device_command(device_id, username)

        # 记录审计日志
        status_text = "成功" if result.get('code') == 0 else "失败"
        log_manage.add_op_log(
            op_id,
            "11",
            username,
            f"回滚设备命令{status_text}: 设备ID={device_id}, 结果={result.get('msg', '')}"
        )

        if result.get('code') == 0:
            return APIResponse.success(data={"output": result.get('output')}, message=result.get('msg'))
        else:
            return APIResponse.error(message=result.get('msg'))

    except Exception as e:
        logger.error(f"回滚设备失败: {e}")
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

        logger.info(f"{g.user.get('username', '')}查询工单日志: {op_id}")

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

        logger.info(f"{g.user.get('username', '')}查询审批记录: {op_id}")

        result = log_manage.get_approval_list(op_id)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"获取审批记录失败: {e}")
        return APIResponse.server_error(message=f"接口异常，异常原因: {str(e)}")
