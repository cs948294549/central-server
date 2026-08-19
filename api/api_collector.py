from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_alarm import syslog_manage
import logging
from function_collector.func_search import func_fulltext, get_deviceslist, get_ex_portinfo, get_lldp_list
from function_collector.func_search import getfulltextDeviceGates_v4, getfulltextDeviceGates_v6, get_arp_list
from function_collector.func_search import get_mac_table_by_tor, get_device_sns
from function_snmp.snmpAgent import snmpget, snmpwalk
from config import Config

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
        switch_ip = data.get('switch_ip', None)
        if switch_ip:
            respond = get_mac_table_by_tor({"switch_ip": switch_ip})
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(data={}, message="缺少接入交换机IP")
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