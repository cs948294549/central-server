from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_collector.func_topology import (
    get_topology_list,
    get_topology_detail,
    create_topology,
    update_topology,
    delete_topology
)
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
topology_bp = Blueprint('topology', __name__, url_prefix='/topology')


@topology_bp.route('/list', methods=['POST'])
def get_list():
    """获取拓扑列表"""
    try:
        result = get_topology_list()

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"查询拓扑列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@topology_bp.route('/detail', methods=['POST'])
def get_detail():
    """获取拓扑详情"""
    try:
        data = request.json
        if not data or not data.get('topology_id'):
            return APIResponse.param_error(message="拓扑ID不能为空")

        result = get_topology_detail(data['topology_id'])

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败，拓扑不存在")

    except Exception as e:
        logger.error(f"查询拓扑详情异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@topology_bp.route('/create', methods=['POST'])
def create():
    """创建拓扑"""
    try:
        data = request.json
        if not data:
            return APIResponse.param_error(message="请求数据不能为空")

        # 验证必要字段
        if not data.get('topology_name'):
            return APIResponse.param_error(message="拓扑名称不能为空")

        # 设置创建人
        data['created_by'] = str(g.user) if hasattr(g, 'user') else 'system'
        data['updated_by'] = data['created_by']

        logger.info(f"{data['created_by']}创建拓扑，名称: {data.get('topology_name')}")

        result = create_topology(data)

        if isinstance(result, dict) and result.get('topology_id'):
            return APIResponse.success(data=result, message="创建成功")
        elif result == "duplicate":
            return APIResponse.error(message="拓扑名称已存在")
        else:
            return APIResponse.error(message="创建失败")

    except Exception as e:
        logger.error(f"创建拓扑异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@topology_bp.route('/update', methods=['POST'])
def update():
    """更新拓扑"""
    try:
        data = request.json
        if not data:
            return APIResponse.param_error(message="请求数据不能为空")

        # 验证必要字段
        if not data.get('topology_id'):
            return APIResponse.param_error(message="拓扑ID不能为空")

        # 设置更新人
        data['updated_by'] = str(g.user) if hasattr(g, 'user') else 'system'

        logger.info(f"{data['updated_by']}更新拓扑，ID: {data.get('topology_id')}")

        result = update_topology(data)

        if result == "success":
            return APIResponse.success(message="更新成功")
        elif result == "version_conflict":
            return APIResponse.error(message="数据已被他人修改，请刷新后重试")
        elif result == "not_found":
            return APIResponse.error(message="拓扑不存在")
        elif result == "duplicate":
            return APIResponse.error(message="拓扑名称已存在")
        else:
            return APIResponse.error(message="更新失败")

    except Exception as e:
        logger.error(f"更新拓扑异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@topology_bp.route('/delete', methods=['POST'])
def delete():
    """删除拓扑"""
    try:
        data = request.json
        if not data or not data.get('topology_id'):
            return APIResponse.param_error(message="拓扑ID不能为空")

        username = str(g.user) if hasattr(g, 'user') else 'system'
        logger.info(f"{username}删除拓扑，ID: {data['topology_id']}")

        result = delete_topology(data['topology_id'])

        if result == "success":
            return APIResponse.success(message="删除成功")
        elif result == "not_found":
            return APIResponse.error(message="拓扑不存在")
        else:
            return APIResponse.error(message="删除失败")

    except Exception as e:
        logger.error(f"删除拓扑异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")
