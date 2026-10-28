"""
Wi-Fi 地图接口：AC 管理 / 地图维护 / AP 详情

本层只做参数校验和响应封装，业务逻辑走 function_wifi，不直接引用 tables。
AP / 射频 / SSID / 终端快照由 projects/collector 采集入库，本服务只读。
"""
from flask import Blueprint, request
from api.api_response import APIResponse
from function_wifi import func_ac, func_map, func_ap
import logging

logger = logging.getLogger(__name__)

wifi_bp = Blueprint('wifi', __name__, url_prefix='/wifi')


@wifi_bp.route('/ac/list', methods=['POST'])
def get_ac_list():
    """AC 列表，community 回显 ******"""
    try:
        result = func_ac.get_ac_list()

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"查询 AC 列表失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/ac/save', methods=['POST'])
def save_ac():
    """新增或修改 AC，带 ac_id 为修改"""
    try:
        data = request.get_json(silent=True) or {}
        result = func_ac.save_ac(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "保存成功"))
        return APIResponse.error(message=result.get("message", "保存失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"保存 AC 失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")



@wifi_bp.route('/ac/delete', methods=['POST'])
def delete_ac():
    """删除 AC，级联删除 AP 快照及地图图标"""
    try:
        data = request.get_json(silent=True) or {}
        ac_id = data.get("ac_id")
        if not ac_id:
            return APIResponse.param_error(message="缺少参数: ac_id")

        result = func_ac.delete_ac(ac_id)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "删除成功"))
        return APIResponse.error(message=result.get("message", "删除失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"删除 AC 失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/ac/test', methods=['POST'])
def test_ac():
    """SNMP 连通测试，不入库"""
    try:
        data = request.get_json(silent=True) or {}
        result = func_ac.test_ac(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "连通成功"))
        return APIResponse.error(message=result.get("message", "连通失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"测试 AC 连通失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/ac/collect', methods=['POST'])
def collect_ac():
    """立即探测：SNMP 连通探测并回写 last_status，不做采集"""
    try:
        data = request.get_json(silent=True) or {}
        ac_id = data.get("ac_id")
        if not ac_id:
            return APIResponse.param_error(message="缺少参数: ac_id")

        result = func_ac.collect_ac(ac_id)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "探测成功"))
        return APIResponse.error(message=result.get("message", "探测失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"探测 AC 失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")



@wifi_bp.route('/map/list', methods=['POST'])
def get_map_list():
    """地图列表，按建筑分组，不带底图"""
    try:
        result = func_map.get_map_list()

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"查询地图列表失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/map/detail', methods=['POST'])
def get_map_detail():
    """地图详情：底图 data URI + 图标及最新指标"""
    try:
        data = request.get_json(silent=True) or {}
        map_id = data.get("map_id")
        if not map_id:
            return APIResponse.param_error(message="缺少参数: map_id")

        result = func_map.get_map_detail(map_id)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"查询地图详情失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/map/info', methods=['POST'])
def save_map_info():
    """新增或修改地图属性与底图，带 map_id 为修改"""
    try:
        data = request.get_json(silent=True) or {}
        result = func_map.save_map_info(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "保存成功"))
        return APIResponse.error(message=result.get("message", "保存失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"保存地图属性失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/map/save', methods=['POST'])
def save_map_layout():
    """保存地图布局，图标全量替换，version 乐观锁"""
    try:
        data = request.get_json(silent=True) or {}
        result = func_map.save_map_layout(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "保存成功"))
        return APIResponse.error(message=result.get("message", "保存失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"保存地图布局失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")



@wifi_bp.route('/map/delete', methods=['POST'])
def delete_map():
    """删除地图，连带删除图上图标，不删 AP 数据"""
    try:
        data = request.get_json(silent=True) or {}
        map_id = data.get("map_id")
        if not map_id:
            return APIResponse.param_error(message="缺少参数: map_id")

        result = func_map.delete_map(map_id)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "删除成功"))
        return APIResponse.error(message=result.get("message", "删除失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"删除地图失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/ap/pool', methods=['POST'])
def get_ap_pool():
    """可摆放 AP 池，按 AC 分组"""
    try:
        result = func_ap.get_ap_pool()

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"查询 AP 池失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/ap/list', methods=['POST'])
def get_ap_list():
    """AP 列表，支持名称 / MAC / IP / SN / 型号 / 分组 / 版本模糊筛选，AC / 状态精确筛选"""
    try:
        data = request.get_json(silent=True) or {}
        result = func_ap.get_ap_list(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"查询 AP 列表失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/client/list', methods=['POST'])
def get_client_list():
    """终端列表，支持 IP / 用户名 / MAC / AP 名称 / SSID / 频段模糊筛选，AC / 状态精确筛选"""
    try:
        data = request.get_json(silent=True) or {}
        result = func_ap.get_client_list(data)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"查询终端列表失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/ap/detail', methods=['POST'])
def get_ap_detail():
    """AP 详情：基础信息 + 射频 + SSID"""
    try:
        data = request.get_json(silent=True) or {}
        ap_mac = data.get("ap_mac")
        if not ap_mac:
            return APIResponse.param_error(message="缺少参数: ap_mac")

        result = func_ap.get_ap_detail(ap_mac)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"查询 AP 详情失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")


@wifi_bp.route('/ap/clients', methods=['POST'])
def get_ap_clients():
    """AP 下在线终端"""
    try:
        data = request.get_json(silent=True) or {}
        ap_mac = data.get("ap_mac")
        if not ap_mac:
            return APIResponse.param_error(message="缺少参数: ap_mac")

        result = func_ap.get_ap_clients(ap_mac)

        if result.get("success"):
            return APIResponse.success(data=result.get("data"), message=result.get("message", "查询成功"))
        return APIResponse.error(message=result.get("message", "查询失败"), code=result.get("code", 1))

    except Exception as e:
        logger.error(f"查询 AP 终端失败: {e}", exc_info=True)
        return APIResponse.server_error(message=f"接口异常: {str(e)}")
