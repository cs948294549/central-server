from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_poap import (
    get_template_list,
    get_template_detail,
    create_template,
    update_template,
    delete_template,
    duplicate_template,
    get_snapshot_list,
    get_snapshot_detail,
)

# 创建蓝图
arch_template_bp = Blueprint('arch_template', __name__, url_prefix='/arch_template')


@arch_template_bp.route('/list', methods=['GET'])
def getTemplateList():
    """
    获取模板列表
    Query Params:
        keyword: str (可选，模糊搜索)
        arch_type: str (可选)
        is_active: int (可选，0/1)
        vendor: str (可选，只返回支持该厂商的模板)
        page: int (可选，默认 1)
        page_size: int (可选，默认 20)
    """
    try:
        data = {
            "keyword": request.args.get("keyword", ""),
            "arch_type": request.args.get("arch_type", ""),
            "vendor": request.args.get("vendor", ""),
            "page": request.args.get("page", 1),
            "page_size": request.args.get("page_size", 20)
        }
        is_active = request.args.get("is_active")
        if is_active is not None:
            data["is_active"] = int(is_active)

        result = get_template_list(data)

        if not result["success"]:
            return APIResponse.error(message=result["message"])

        return APIResponse.success(data=result["data"], message=result["message"])

    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@arch_template_bp.route('/detail', methods=['GET'])
def getTemplateDetail():
    """
    获取模板详情
    Query Params:
        tid: str (模板 ID)
    """
    try:
        tid = request.args.get("tid")
        if not tid:
            return APIResponse.param_error(message="缺少参数 tid")

        result = get_template_detail({"tid": tid})

        if not result["success"]:
            return APIResponse.error(message=result["message"])

        return APIResponse.success(data=result["data"], message=result["message"])

    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@arch_template_bp.route('/create', methods=['POST'])
def createTemplate():
    """
    创建模板
    Body: {
        tid: str (UUID),
        name: str,
        arch_type: str (可选),
        description: str (可选),
        tags: list (可选),
        has_z_side: int (0/1),
        min_expand_unit: int (可选，默认 1，每次扩容的最小设备台数，如双归为 2),
        configs: {
            厂商: {config_a: str, config_z: str, params: list}
        }
    }
    """
    try:
        data = request.json or {}
        if not data.get("tid") or not data.get("name"):
            return APIResponse.param_error(message="缺少必要参数：tid, name")

        # 注入操作人
        data["created_by"] = g.user.get("username", "") if hasattr(g, "user") else ""

        result = create_template(data)

        if not result["success"]:
            return APIResponse.error(message=result["message"])

        return APIResponse.success(data=result["data"], message=result["message"])

    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@arch_template_bp.route('/update', methods=['POST'])
def updateTemplate():
    """
    更新模板
    Body: {
        tid: str,
        name: str (可选),
        arch_type: str (可选),
        description: str (可选),
        tags: list (可选),
        is_active: int (可选),
        has_z_side: int (可选),
        min_expand_unit: int (可选),
        configs: {
            厂商: {
                config_a: str,
                config_z: str,
                params: list,
                increment_version: bool (可选，默认 true),
                change_summary: str (可选)
            }
        } (可选)
    }
    """
    try:
        data = request.json or {}
        if not data.get("tid"):
            return APIResponse.param_error(message="缺少参数 tid")

        # 注入操作人
        data["updated_by"] = g.user.get("username", "") if hasattr(g, "user") else ""

        result = update_template(data)

        if not result["success"]:
            return APIResponse.error(message=result["message"])

        return APIResponse.success(data=result["data"], message=result["message"])

    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@arch_template_bp.route('/delete', methods=['POST'])
def deleteTemplate():
    """
    删除模板（软删除）
    Body: {tid: str}
    """
    try:
        data = request.json or {}
        if not data.get("tid"):
            return APIResponse.param_error(message="缺少参数 tid")

        result = delete_template(data)

        if not result["success"]:
            return APIResponse.error(message=result["message"])

        return APIResponse.success(message=result["message"])

    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@arch_template_bp.route('/duplicate', methods=['POST'])
def duplicateTemplate():
    """
    复制模板
    Body: {
        tid: str (源模板),
        new_tid: str (新模板 ID)
    }
    """
    try:
        data = request.json or {}
        if not data.get("tid") or not data.get("new_tid"):
            return APIResponse.param_error(message="缺少必要参数：tid, new_tid")

        # 注入操作人
        data["created_by"] = g.user.get("username", "") if hasattr(g, "user") else ""

        result = duplicate_template(data)

        if not result["success"]:
            return APIResponse.error(message=result["message"])

        return APIResponse.success(data=result["data"], message=result["message"])

    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@arch_template_bp.route('/snapshot/list', methods=['GET'])
def getSnapshotList():
    """
    获取某个模板某个厂商的版本历史
    Query Params:
        tid: str
        vendor: str
    """
    try:
        tid = request.args.get("tid")
        vendor = request.args.get("vendor")

        if not tid or not vendor:
            return APIResponse.param_error(message="缺少参数 tid 或 vendor")

        result = get_snapshot_list({"tid": tid, "vendor": vendor})

        if not result["success"]:
            return APIResponse.error(message=result["message"])

        return APIResponse.success(data=result["data"], message=result["message"])

    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@arch_template_bp.route('/snapshot/detail', methods=['GET'])
def getSnapshotDetail():
    """
    获取指定版本快照
    Query Params:
        tid: str
        vendor: str
        version: int
    """
    try:
        tid = request.args.get("tid")
        vendor = request.args.get("vendor")
        version = request.args.get("version")

        if not tid or not vendor or not version:
            return APIResponse.param_error(message="缺少参数 tid、vendor 或 version")

        result = get_snapshot_detail({"tid": tid, "vendor": vendor, "version": int(version)})

        if not result["success"]:
            return APIResponse.error(message=result["message"])

        return APIResponse.success(data=result["data"], message=result["message"])

    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))
