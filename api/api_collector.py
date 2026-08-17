from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_alarm import syslog_manage
import logging
from function_collector.func_search import func_fulltext, get_deviceslist, get_ex_portinfo
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

'''
getDevs
getPorts_ex
getCurrentInterface
getInterface
getTransceiver
getLogging
getARPs
getRoutes
getCommonFunction
getLLDPS
setInterfaceStatus

'''
