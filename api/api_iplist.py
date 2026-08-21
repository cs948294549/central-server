from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_collector.func_iplist import (
    get_iplist,
    add_iplist,
    update_iplist,
    delete_iplist,
    batch_delete_iplist,
    batch_add_or_update_iplist
)
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
iplist_bp = Blueprint('iplist', __name__, url_prefix='/iplist')


@iplist_bp.route('/get_list', methods=['POST'])
def get_list():
    """获取设备IP清单列表"""
    try:
        data = request.json or {}
        result = get_iplist(data)

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"查询设备IP清单列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@iplist_bp.route('/add', methods=['POST'])
def add():
    """新增设备IP"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}新增设备IP，数据: {data}")

        result = add_iplist(data)

        if result == "success":
            return APIResponse.success(message="新增成功")
        else:
            return APIResponse.error(message="新增失败，IP可能已存在")

    except Exception as e:
        logger.error(f"新增设备IP异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@iplist_bp.route('/update', methods=['POST'])
def update():
    """更新设备IP信息"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}更新设备IP，数据: {data}")

        result = update_iplist(data)

        if result == "success":
            return APIResponse.success(message="更新成功")
        else:
            return APIResponse.error(message="更新失败，IP可能不存在")

    except Exception as e:
        logger.error(f"更新设备IP异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@iplist_bp.route('/delete', methods=['POST'])
def delete():
    """删除设备IP"""
    try:
        data = request.json
        logger.info(f"{str(g.user)}删除设备IP，数据: {data}")

        result = delete_iplist(data)

        if result == "success":
            return APIResponse.success(message="删除成功")
        else:
            return APIResponse.error(message="删除失败，IP可能不存在")

    except Exception as e:
        logger.error(f"删除设备IP异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@iplist_bp.route('/batch_delete', methods=['POST'])
def batch_delete():
    """批量删除设备IP"""
    try:
        data = request.json
        ip_list = data.get('ip_list', [])
        logger.info(f"{str(g.user)}批量删除设备IP，数量: {len(ip_list)}")

        result = batch_delete_iplist(data)

        if result == "success":
            return APIResponse.success(message=f"批量删除成功，共 {len(ip_list)} 条")
        else:
            return APIResponse.error(message="批量删除失败")

    except Exception as e:
        logger.error(f"批量删除设备IP异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@iplist_bp.route('/batch_add_or_update', methods=['POST'])
def batch_add_or_update():
    """批量添加或更新设备IP"""
    try:
        data = request.json
        ip_list = data.get('ip_list', [])
        logger.info(f"{str(g.user)}批量添加或更新设备IP，数量: {len(ip_list)}")

        result = batch_add_or_update_iplist(data)

        if result == "success":
            return APIResponse.success(message=f"批量处理成功，共 {len(ip_list)} 条")
        else:
            return APIResponse.error(message="批量处理失败")

    except Exception as e:
        logger.error(f"批量添加或更新设备IP异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")
