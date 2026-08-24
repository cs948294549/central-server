from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_collector.func_flowboard import (
    get_flow_list,
    get_flow_detail,
    create_flow,
    update_flow,
    delete_flow
)
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
flowboard_bp = Blueprint('flowboard', __name__, url_prefix='/flowboard')


@flowboard_bp.route('/list', methods=['POST'])
def get_list():
    """获取看板列表"""
    try:
        result = get_flow_list()

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败")

    except Exception as e:
        logger.error(f"查询看板列表异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@flowboard_bp.route('/detail', methods=['POST'])
def get_detail():
    """获取看板详情"""
    try:
        data = request.json
        if not data or not data.get('flow_id'):
            return APIResponse.param_error(message="看板ID不能为空")

        result = get_flow_detail(data['flow_id'])

        if result != "failed":
            return APIResponse.success(data=result, message="查询成功")
        else:
            return APIResponse.error(message="查询失败，看板不存在")

    except Exception as e:
        logger.error(f"查询看板详情异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@flowboard_bp.route('/create', methods=['POST'])
def create():
    """创建看板"""
    try:
        data = request.json
        if not data:
            return APIResponse.param_error(message="请求数据不能为空")

        if not data.get('flow_name'):
            return APIResponse.param_error(message="看板名称不能为空")

        username = g.user.get('username') if hasattr(g, 'user') and isinstance(g.user, dict) else 'system'
        data['created_by'] = username
        data['updated_by'] = username

        logger.info(f"{username}创建流量看板，名称: {data.get('flow_name')}")

        result = create_flow(data)

        if isinstance(result, dict) and result.get('flow_id'):
            return APIResponse.success(data=result, message="创建成功")
        elif result == "duplicate":
            return APIResponse.error(message="看板名称已存在")
        else:
            return APIResponse.error(message="创建失败")

    except Exception as e:
        logger.error(f"创建看板异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@flowboard_bp.route('/update', methods=['POST'])
def update():
    """更新看板"""
    try:
        data = request.json
        if not data:
            return APIResponse.param_error(message="请求数据不能为空")

        if not data.get('flow_id'):
            return APIResponse.param_error(message="看板ID不能为空")

        username = g.user.get('username') if hasattr(g, 'user') and isinstance(g.user, dict) else 'system'
        data['updated_by'] = username

        logger.info(f"{username}更新流量看板，ID: {data.get('flow_id')}")

        result = update_flow(data)

        if isinstance(result, dict):
            return APIResponse.success(data=result, message="更新成功")
        elif result == "version_conflict":
            return APIResponse.error(message="数据已被他人修改，请刷新后重试")
        elif result == "not_found":
            return APIResponse.error(message="看板不存在")
        elif result == "duplicate":
            return APIResponse.error(message="看板名称已存在")
        else:
            return APIResponse.error(message="更新失败")

    except Exception as e:
        logger.error(f"更新看板异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@flowboard_bp.route('/delete', methods=['POST'])
def delete():
    """删除看板"""
    try:
        data = request.json
        if not data or not data.get('flow_id'):
            return APIResponse.param_error(message="看板ID不能为空")

        username = g.user.get('username') if hasattr(g, 'user') and isinstance(g.user, dict) else 'system'
        logger.info(f"{username}删除流量看板，ID: {data['flow_id']}")

        result = delete_flow(data['flow_id'])

        if result == "success":
            return APIResponse.success(message="删除成功")
        elif result == "not_found":
            return APIResponse.error(message="看板不存在")
        else:
            return APIResponse.error(message="删除失败")

    except Exception as e:
        logger.error(f"删除看板异常: {e}")
        return APIResponse.server_error(message=f"接口异常: {str(e)}")
