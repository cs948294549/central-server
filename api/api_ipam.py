from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_collector.func_ipam import (
    add_network_address,
    update_network_address,
    delete_network_address,
    get_network_address_list,
    get_network_address_tree,
    get_ipam_address_list,
    batch_add_ipam_address
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
