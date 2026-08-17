from flask import Blueprint
from flask import request, make_response
import json

from Module.CommandDevice import get_config_interface, get_interface, get_transceiver
from Module.CommandDevice import get_logging, get_arp_brief, get_routes
from Module.CommandDevice import get_result_by_template
from func.func_offline import clearDeviceSavedConfig

command = Blueprint("command", __name__)
'''
下发命令
'''

@command.route('/dis_cur_interface',methods=['POST'])
def dis_cur_interface():
    postdata = request.get_data(as_text=True)
    print(postdata)
    data = json.loads(postdata)
    if "ip" in data.keys() and "if_name" in data.keys():
        respond = get_config_interface(ip=data["ip"], if_name=data["if_name"])
        return respond
    else:
        return "failed"

@command.route('/dis_interface',methods=['POST'])
def dis_interface():
    postdata = request.get_data(as_text=True)
    print(postdata)
    data = json.loads(postdata)
    if "ip" in data.keys() and "if_name" in data.keys():
        respond = get_interface(ip=data["ip"], if_name=data["if_name"])
        return respond
    else:
        return "failed"

@command.route('/dis_transceiver',methods=['POST'])
def dis_transceiver():
    postdata = request.get_data(as_text=True)
    print(postdata)
    data = json.loads(postdata)
    if "ip" in data.keys() and "if_name" in data.keys():
        respond = get_transceiver(ip=data["ip"], if_name=data["if_name"])
        return respond
    else:
        return "failed"

@command.route('/dis_logging', methods=['POST'])
def dis_logging():
    postdata = request.get_data(as_text=True)
    print(postdata)
    data = json.loads(postdata)
    if "ip" in data.keys() and "size" in data.keys():
        if data["size"]:
            if data["size"].strip() == "":
                respond = get_logging(ip=data["ip"])
            else:
                respond = get_logging(ip=data["ip"], size=data["size"])
        else:
            respond = get_logging(ip=data["ip"])
        return respond
    else:
        return "failed"

@command.route('/dis_arp',methods=['POST'])
def dis_arp():
    postdata = request.get_data(as_text=True)
    print(postdata)
    data = json.loads(postdata)
    if "vlan_id" in data.keys() and "arp_ip" in data.keys():
        if data["arp_ip"].strip() == "":
            if data["vlan_id"].strip() == "":
                respond = get_arp_brief(ip=data["ip"])
            else:
                respond = get_arp_brief(ip=data["ip"], vlan_id=data["vlan_id"])
        else:
            respond = get_arp_brief(ip=data["ip"], arp_ip=data["arp_ip"])
        return respond
    else:
        return "failed"


@command.route('/dis_routes', methods=['POST'])
def dis_routes():
    postdata = request.get_data(as_text=True)
    print(postdata)
    data = json.loads(postdata)
    if "ip" in data.keys() and "route" in data.keys():
        if data["route"]:
            if data["route"].strip() == "":
                respond = get_routes(ip=data["ip"], route="0.0.0.0")
            else:
                respond = get_routes(ip=data["ip"], route=data["route"])
        else:
            respond = get_routes(ip=data["ip"], route="0.0.0.0")
        return respond
    else:
        return "failed"

@command.route('/dis_common',methods=['POST'])
def dis_common_func():
    postdata = request.get_data(as_text=True)
    print(postdata)
    data = json.loads(postdata)
    if "ip" in data.keys() and "template_name" in data.keys():
        respond = get_result_by_template(ip=data["ip"], temp_name=data["template_name"])
        return respond
    else:
        return "failed"

@command.route('/clear_cfg',methods=['POST'])
def clear_cfg():
    postdata = request.get_data(as_text=True)
    print(postdata)
    data = json.loads(postdata)
    if "ids" in data.keys():
        ids_strs = []
        for _id in data["ids"]:
            ids_strs.append(str(_id))
        failed_ips = clearDeviceSavedConfig(ids=ids_strs)
        return json.dumps({"failed_ips": failed_ips})
    else:
        return "failed"





# @command.route('/file_test', methods=['POST'])
# def file_test():
#     file = request.files.get("field1")
#     if file is None:
#         print("无上传文件")
#     else:
#         print(file)
#         file.save("xxxx")
#     return "hello"