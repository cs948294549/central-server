from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_collector.func_ipam import (
    add_network_address,
    batch_add_network_address,
    update_network_address,
    delete_network_address,
    get_network_address_list,
    get_network_address_tree,
    get_ipam_address_list,
    batch_add_ipam_address,
    delete_ipam_address,
    get_tree_folder_list,
    add_tree_folder,
    update_tree_folder,
    delete_tree_folder,
    move_tree_folder_member
)
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
ipam_bp = Blueprint('ipam', __name__, url_prefix='/ipam')


# ==================== 网络地址管理 ====================

@ipam_bp.route('/add_address', methods=['POST'])
def add_address():
    """添加网络地址"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}添加网络地址，数据: {data}")
        result = add_network_address(data)
        if result == "success":
            return APIResponse.success(message="添加成功")
        else:
            return APIResponse.error(message="添加失败")
    except Exception as e:
        logger.error(f"添加网络地址异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/batch_add_address', methods=['POST'])
def batch_add_address():
    """批量添加网络地址"""
    try:
        data = request.json
        networks = data.get("networks", [])
        logger.info(f"{str(g.user)}批量添加网络地址，数量: {len(networks)}")

        if not isinstance(networks, list) or len(networks) == 0:
            return APIResponse.error(message="networks参数必须是非空列表")

        result = batch_add_network_address(networks)

        if result["status"] == "success":
            return APIResponse.success(data=result, message=result["message"])
        else:
            return APIResponse.error(data=result, message=result["message"])
    except Exception as e:
        logger.error(f"批量添加网络地址异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/update_address', methods=['POST'])
def update_address():
    """更新网络地址"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}更新网络地址，数据: {data}")
        result = update_network_address(data)
        if result == "success":
            return APIResponse.success(message="更新成功")
        else:
            return APIResponse.error(message="更新失败")
    except Exception as e:
        logger.error(f"更新网络地址异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/del_address', methods=['POST'])
def del_address():
    """删除网络地址"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}删除网络地址，数据: {data}")
        result = delete_network_address(data)
        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败")
    except Exception as e:
        logger.error(f"删除网络地址异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/get_address', methods=['POST'])
def get_address():
    """查询网络地址列表"""
    try:
        data = request.json
        result = get_network_address_list(data)
        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")
    except Exception as e:
        logger.error(f"查询网络地址列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/get_address_tree', methods=['POST'])
def get_address_tree():
    """获取网络地址树形结构"""
    try:
        data = request.json
        result = get_network_address_tree(data)
        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")
    except Exception as e:
        logger.error(f"查询网络地址树形结构异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== 网段树文件夹 ====================

@ipam_bp.route('/folder/list', methods=['POST'])
def folder_list():
    """查询文件夹列表"""
    try:
        data = request.json or {}
        result = get_tree_folder_list(data)
        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")
    except Exception as e:
        logger.error(f"查询网段文件夹异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/folder/add', methods=['POST'])
def folder_add():
    """新增文件夹"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}新增网段文件夹，数据: {data}")
        result = add_tree_folder(data)
        if result == "success":
            return APIResponse.success(message="新增成功")
        else:
            return APIResponse.error(message="新增失败，名称不能为空或重复")
    except Exception as e:
        logger.error(f"新增网段文件夹异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/folder/update', methods=['POST'])
def folder_update():
    """修改文件夹"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}修改网段文件夹，数据: {data}")
        result = update_tree_folder(data)
        if result == "success":
            return APIResponse.success(message="修改成功")
        else:
            return APIResponse.error(message="修改失败，名称不能为空或重复")
    except Exception as e:
        logger.error(f"修改网段文件夹异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/folder/delete', methods=['POST'])
def folder_delete():
    """删除文件夹"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}删除网段文件夹，数据: {data}")
        result = delete_tree_folder(data)
        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败")
    except Exception as e:
        logger.error(f"删除网段文件夹异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/folder/move', methods=['POST'])
def folder_move():
    """网段批量移入/移出文件夹"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}网段移入/移出文件夹，数据: {data}")
        result = move_tree_folder_member(data)
        if result == "success":
            return APIResponse.success(message="操作成功")
        else:
            return APIResponse.error(message="操作失败")
    except Exception as e:
        logger.error(f"网段移入/移出文件夹异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


# ==================== IP地址管理 ====================

@ipam_bp.route('/get_ipam_address', methods=['POST'])
def get_ipam_address():
    """查询IP地址列表"""
    try:
        data = request.json
        result = get_ipam_address_list(data)
        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")
    except Exception as e:
        logger.error(f"查询IP地址列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/batch_add_ipaddr', methods=['POST'])
def batch_add_ipaddr():
    """批量添加IP地址"""
    try:
        data = request.json
        data_list = data.get("data_list", [])
        logger.info(f"{str(g.user)}批量添加IP地址，数量: {len(data_list)}")
        result = batch_add_ipam_address(data_list)
        if result == "success":
            return APIResponse.success(message=f"批量添加成功，共 {len(data_list)} 条")
        else:
            return APIResponse.error(message="批量添加失败")
    except Exception as e:
        logger.error(f"批量添加IP地址异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@ipam_bp.route('/del_ipam_address', methods=['POST'])
def del_ipam_address():
    """删除IP地址"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}删除IP地址，数据: {data}")
        result = delete_ipam_address(data)
        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败")
    except Exception as e:
        logger.error(f"删除IP地址异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")
