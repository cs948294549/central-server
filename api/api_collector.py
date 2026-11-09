from flask import Blueprint, request, g
from api.api_response import APIResponse
import logging
from function_collector.func_search import func_fulltext, get_deviceslist, get_ex_portinfo, get_lldp_list, get_port_info
from function_collector.func_search import getfulltextDeviceGates_v4, getfulltextDeviceGates_v6, get_arp_list
from function_collector.func_search import get_mac_table_by_tor, get_device_sns, get_device_summary
from function_collector.func_zabbix import query_port_traffic
from lib_snmp.snmpAgent import snmpget, snmpwalk
from config.config import Config

COMMON_COMMUNITY = Config.snmp_community

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
collector_bp = Blueprint('collector', __name__, url_prefix='/collector')


@collector_bp.route('/getfullsearch',methods=['POST'])
def getfullsearch():
    try:
        query = request.json
        logger.info(f"{str(g.user)}搜索设备，条件{query}")
        if "query" in query.keys():
            respond = func_fulltext(query["query"])
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(message="缺失参数 query")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@collector_bp.route('/snmp_get',methods=['POST'])
def snmp_get():
    try:
        data = request.json
        ip = data.get('ip')
        community = data.get('community', COMMON_COMMUNITY)
        oid = data.get('oid')
        coding = data.get('coding', 'utf-8')
        ret = snmpget(ip=ip, community=community, oid=oid, coding=coding)
        return APIResponse.success(data=ret, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@collector_bp.route('/snmp_walk',methods=['POST'])
def snmp_walk():
    try:
        data = request.json
        ip = data.get('ip')
        community = data.get('community', COMMON_COMMUNITY)
        oid = data.get('oid')
        coding = data.get('coding', 'utf-8')
        ret = snmpwalk(ip=ip, community=community, oids=oid, coding=coding)
        return APIResponse.success(data=ret, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@collector_bp.route('/getdeviceslist',methods=['GET','POST'])
def getdeviceslist():
    try:
        if request.method == 'GET':
            dev_list = get_deviceslist({})
            return APIResponse.success(data=dev_list, message="查询成功")
        else:
            data = request.json
            dev_list = get_deviceslist(data)
            return APIResponse.success(data=dev_list, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@collector_bp.route('/getports_ex',methods=['POST'])
def getExPortInfo():
    try:
        data = request.json
        ip = data.get('ip')
        respond = get_ex_portinfo(ip=ip)
        return APIResponse.success(data=respond, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@collector_bp.route('/getportinfo',methods=['POST'])
def getportinfo():
    try:
        data = request.json
        respond = get_port_info(data)
        return APIResponse.success(data=respond, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@collector_bp.route('/getlldps',methods=['POST'])
def getlldps():
    try:
        data = request.json
        respond = get_lldp_list(data)
        return APIResponse.success(data=respond, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@collector_bp.route('/gates_v4',methods=['POST'])
def gates_v4():
    try:
        data = request.json
        respond = getfulltextDeviceGates_v4(data)
        return APIResponse.success(data=respond, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@collector_bp.route('/gates_v6',methods=['POST'])
def gates_v6():
    try:
        data = request.json
        respond = getfulltextDeviceGates_v6(data)
        return APIResponse.success(data=respond, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@collector_bp.route('/getarp_list',methods=['POST'])
def getarp_list():
    try:
        data = request.json
        respond = get_arp_list(data)
        return APIResponse.success(data=respond, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@collector_bp.route('/get_torarp',methods=['POST'])
def getTorARP_info():
    try:
        data = request.json
        query = {}
        for k in ("switch_ip", "sysname"):
            if data.get(k):
                query[k] = data.get(k)
        if query:
            respond = get_mac_table_by_tor(query)
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(data={}, message="缺少接入交换机IP或设备名")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@collector_bp.route('/getdevice_sn',methods=['POST'])
def getdevice_sn():
    try:
        data = request.json
        respond = get_device_sns(data)
        return APIResponse.success(data=respond, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@collector_bp.route('/port_traffic',methods=['POST'])
def port_traffic():
    """
    查询设备端口某个时间段的流量（数据来自 Zabbix）
    请求体：
    {
      "host": "pcs1_dc07_m01.vdian.net",   # 设备名，必填
      "port_id": "436207616",              # Zabbix 监控项里的接口索引，必填
      "start_time": 1794195800,           # 开始时间戳（秒），默认结束时间往前 1 小时
      "end_time": 1794199400              # 结束时间戳（秒），默认当前
    }
    """
    try:
        data = request.json or {}
        logger.info(f"{str(g.user)}查询端口流量，条件{data}")
        respond = query_port_traffic(
            host=data.get("host"),
            port_id=data.get("port_id"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
        )
        return APIResponse.success(data=respond, message="查询成功")
    except ValueError as e:
        return APIResponse.param_error(message=str(e))
    except Exception as e:
        logger.error(f"查询端口流量失败: {e}")
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@collector_bp.route('/device_summary',methods=['POST'])
def device_summary():
    """
    设备统计汇总
    通过 iplist 筛选 admin_status <> '1' 的设备，left join devices 获取采集时间
    采集时间距当前时间小于 30 分钟认为在线
    返回：{
      "total": 总设备数,
      "online": 在线设备数,
      "offline": 离线设备数,
      "vendors": [{"name": "Cisco", "count": 500, "type": "primary"}, ...]
    }
    """
    try:
        logger.info(f"{str(g.user)}查询设备统计汇总")
        respond = get_device_summary()
        if respond == "failed":
            return APIResponse.error(message="查询失败")
        return APIResponse.success(data=respond, message="查询成功")
    except Exception as e:
        logger.error(f"设备统计汇总失败: {e}")
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))