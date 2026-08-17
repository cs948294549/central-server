from flask import Blueprint, request, g
from api.api_response import APIResponse
# from Module.CommandDevice import get_config_interface, get_interface, get_transceiver
# from Module.CommandDevice import get_logging, get_arp_brief, get_routes
# from Module.CommandDevice import get_result_by_template
# from func.func_offline import clearDeviceSavedConfig
import json
from function_collector.func_command import get_result_by_template, get_config_interface, get_interface, get_transceiver, get_logging, get_arp_brief, get_routes

command = Blueprint("command", __name__)
'''
下发命令
'''
@command.route('/dis_common',methods=['POST'])
def dis_common_func():
    try:
        data = request.json
        if "ip" in data.keys() and "template_name" in data.keys():
            respond = get_result_by_template(ip=data["ip"], temp_name=data["template_name"])
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(message="缺失参数 query")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@command.route('/dis_cur_interface',methods=['POST'])
def dis_cur_interface():
    try:
        data = request.json
        if "ip" in data.keys() and "if_name" in data.keys():
            respond = get_config_interface(ip=data["ip"], if_name=data["if_name"])
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(message="缺失参数 query")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@command.route('/dis_interface',methods=['POST'])
def dis_interface():
    try:
        data = request.json
        if "ip" in data.keys() and "if_name" in data.keys():
            respond = get_interface(ip=data["ip"], if_name=data["if_name"])
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(message="缺失参数 query")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@command.route('/dis_transceiver',methods=['POST'])
def dis_transceiver():
    try:
        data = request.json
        if "ip" in data.keys() and "if_name" in data.keys():
            respond = get_transceiver(ip=data["ip"], if_name=data["if_name"])
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(message="缺失参数 query")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@command.route('/dis_logging', methods=['POST'])
def dis_logging():
    try:
        data = request.json
        if "ip" in data.keys() and "size" in data.keys():
            if data["size"]:
                if data["size"].strip() == "":
                    respond = get_logging(ip=data["ip"])
                else:
                    respond = get_logging(ip=data["ip"], size=data["size"])
            else:
                respond = get_logging(ip=data["ip"])
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(message="缺失参数 query")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))



@command.route('/dis_arp',methods=['POST'])
def dis_arp():
    try:
        data = request.json
        if "vlan_id" in data.keys() and "arp_ip" in data.keys():
            if data["arp_ip"].strip() == "":
                if data["vlan_id"].strip() == "":
                    respond = get_arp_brief(ip=data["ip"])
                else:
                    respond = get_arp_brief(ip=data["ip"], vlan_id=data["vlan_id"])
            else:
                respond = get_arp_brief(ip=data["ip"], arp_ip=data["arp_ip"])
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(message="缺失参数 query")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@command.route('/dis_routes', methods=['POST'])
def dis_routes():
    try:
        data = request.json
        if "ip" in data.keys() and "route" in data.keys():
            if data["route"]:
                if data["route"].strip() == "":
                    respond = get_routes(ip=data["ip"], route="0.0.0.0")
                else:
                    respond = get_routes(ip=data["ip"], route=data["route"])
            else:
                respond = get_routes(ip=data["ip"], route="0.0.0.0")
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(message="缺失参数 query")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))