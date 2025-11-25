import requests
import json
from config.config import secret, gate_url
import re
from functools import wraps
import time

ip_reg = re.compile(r'^((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){3}$')


def getDevByName(name):
    url = gate_url + "snmpdata_getdeviceslist"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {"sysname": "^{}$".format(name)}
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, name)
        return "failed"
    try:
        return json.loads(r.text)
    except:
        print("解析失败", r.text)
        return "failed"

def getDeviceListByNameAndType(search_info):
    """
    获取设备列表
    """
    url = gate_url + "snmpdata_getdeviceslist"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = search_info
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, search_info)
        return "failed"
    try:
        return json.loads(r.text)
    except:
        print("解析失败", r.text)
        return "failed"


def getDevByIP(ip):
    url = gate_url + "snmpdata_snmp_gates"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {"gatereg": "^{}$".format(ip)}
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, ip)
        return "failed"
    try:
        return json.loads(r.text)
    except:
        print("解析失败", r.text)
        return "failed"

def getDevByGate(ip):
    '''
    通过ip查找设备，并返回设备接口列表
    '''
    url = gate_url + "snmpdata_snmp_gates"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    if len(ip_reg.findall(ip)) > 0:
        body = {"gate": "{}".format(ip)}
    else:
        if ip[-1] == ".":
            if len(ip_reg.findall(ip+"1")) > 0:
                body = {"gate": "{}".format(ip+"1")}
            else:
                body = {"gatereg": "^{}".format(ip)}
        else:
            body = {"gatereg": "^{}".format(ip)}
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, ip)
        return "failed"
    try:
        respond = json.loads(r.text)
        msgs = []
        for i in range(0, len(respond)):
            if (respond[i]["ip"] == "59.111.252.124" or respond[i]["ip"] == "59.111.252.125") and (
                    respond[i]["if_name"] == "em0.0"):
                continue
            msgs.append(respond[i])
        return msgs
    except:
        print("解析失败", r.text)
        return "failed"

# 获取arp去堆叠设备列表，根据arp记录获取
def getARP_Unstack(ip):
    '''
    通过去堆叠网关设备，通过已有的arp信息
    '''
    url = gate_url + "snmpdata_snmp_arp_single"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {"gatereg": "^{}$".format(ip)}
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, ip)
        return "failed"
    try:
        respond = json.loads(r.text)
        return respond
    except:
        print("解析失败", r.text)
        return "failed"

# 查询arp所在交换机
def getARPlocationAtSW(ip):
    '''
    通过arp查找设备，并返回设备id及采集时间
    '''
    url = gate_url + "snmpdata_getarp_list"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {"arp_ip": "{}".format(ip)}
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, ip)
        return "failed"
    try:
        respond = json.loads(r.text)
        return respond
    except:
        print("解析失败", r.text)
        return "failed"

def getDevPort(ip):
    url = gate_url + "snmpdata_getportinfo"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body ={"oper_statu_ex":"1","ip":"^{}$".format(ip)}
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, ip)
        return "failed"
    try:
        return json.loads(r.text)
    except:
        print("解析失败", r.text)
        return "failed"


def alertSeer(data):
    # {"id": ,"name":"","ip":"","line":"","type":1,"status":1}
    APIURL = "http://network-in.netease.com/api/forward/poap_seer_kafka_submit_ticket"
    headers = {
        "key": "seer_portal",
        "secret": "901c05adaa9e5b205ed8d3cc03896997"
    }
    res = requests.post(APIURL, headers=headers, json=data).json()
    print(res)

# 接口调用次数统计
def sendAPI_log(logs):
    url = gate_url + "data_add_data_request"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "logs": logs
    }
    r = requests.post(url=url, headers=headers, json=body)
    return r.text

def add_logs(label,request_path,user):
    try:
        sendAPI_log([{
            "label": label,
            "request_path": request_path,
            "user": user,
            "request_time": int(time.time())}])
    except Exception as e:
        print("???===", e)

#获取端口配置列表
def getConfigInterfaceList(ip):
    '''
    通过查询分割配置，返回接口配置
    '''
    url = gate_url + "cfg_tool_get_analy_data"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {"ip": ip, "feature": "interface"}
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, ip)
        return "failed"
    try:
        respond = json.loads(r.text)
        return respond
    except:
        print("解析失败", r.text)
        return "failed"

#获取端口配置列表

def getDevListByName():
    url = gate_url + "snmpdata_getdeviceslist"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {"sysname": "^N"}
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e)
        return "failed"
    try:
        return json.loads(r.text)
    except:
        print("解析失败", r.text)
        return "failed"

def getLLDPList(info):
    '''
    通过查询分割配置，返回接口配置
    '''
    url = gate_url + "snmpdata_getlldps"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    # body = {
    #     # "loc_ip": ip,
    # }
    body = info
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e)
        return "failed"
    try:
        respond = json.loads(r.text)
        return respond
    except:
        print("解析失败", r.text)
        return "failed"

def getLocationServer(ip):
    "查询服务器接入位置"
    url = gate_url + "snmpdata_getserverlocation"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "query": {
            "arp_ip": ip,
        },
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e)
        return "failed"
    try:
        respond = json.loads(r.text)
        return respond
    except:
        print("解析失败", r.text)
        return "failed"
    pass


def getFullSearch(query):
    "查询服务器接入位置"
    url = gate_url + "fullsearch"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "query": query
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e)
        return "failed"
    try:
        respond = json.loads(r.text)
        return respond
    except:
        print("解析失败", r.text)
        return "failed"

def getPortUseBySysname(name):
    url = gate_url + "snmpdata_get_port_util"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "sysname": name
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e)
        return "failed"
    try:
        respond = json.loads(r.text)
        return respond
    except:
        print("解析失败", r.text)
        return "failed"


def getGatesByQuery(query):
    url = gate_url + "snmpdata_snmp_gates"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = query
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, query)
        return "failed"
    try:
        return json.loads(r.text)
    except:
        print("解析失败", r.text)
        return "failed"


def addDeviceCMD(cfg):
    '''
    通过ip精确查找设备，返回设备名
    '''
    url = gate_url + "auto_config_auto_task_add"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "ips": cfg["ips"],
        "exec_cmd": cfg["exec_cmd"],
        # "module_info": [],
        "rollback_cmd": cfg["rollback_cmd"],
        "title": cfg["title"],
        "task_desc": cfg["task_desc"],
        "comments": "autoconfig"
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
        return json.loads(r.text)
    except Exception as e:
        print("请求失败", e)
        return "failed"

# 设备配置预检查
def checkDeviceConfig(tar_cfg, ip):
    url = gate_url + "cfg_tool_get_compare_cfg"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "ip": ip,
        "target_cfg": tar_cfg,
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
        return json.loads(r.text)
    except Exception as e:
        print("请求失败", e)
        return "failed"

# 贵州snat白屏变更
def getSNAT_AddNat(body):
    url = gate_url + "cfg_tool_get_snat_cmd"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
        return json.loads(r.text)
    except Exception as e:
        print("请求失败", e)
        return "failed"

def getSNAT_CreateNat(body):
    url = gate_url + "cfg_tool_create_snat_cmd"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
        return json.loads(r.text)
    except Exception as e:
        print("请求失败", e)
        return "failed"

def getSegmentNetwork(body):
    url = gate_url + "cfg_tool_get_segment_network"
    headers = {
        "key": "testsd",
        "secret": secret
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
        return json.loads(r.text)
    except Exception as e:
        print("请求失败", e)
        return "failed"


def addAutoConfigTask(op_task):
    '''
    建立工单接口
    configs: [
    {"ip":"xxxx", "cfg":"", "rollback":""}
    ]
    '''
    url = gate_url + "op_create_op_by_external"
    headers = {
        "key": "robot",
        "secret": "87b7cb79481f317bde90c116cf36084b"
    }
    body = {
        "op_type": op_task["op_type"],
        "title": op_task["title"],
        "descrip": op_task["descrip"],
        "configs": op_task["configs"]
    }
    if "op_user" in op_task.keys():
        body["op_user"] = op_task["op_user"]
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
        return json.loads(r.text)
    except Exception as e:
        print("请求失败", e)
        return "failed"


def createCode(code_str):
    url = "http://network.netease.com/api/forward/process_create_code"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "code_name": "get_sysname",
        "code_exec": code_str,
        "comment": "测试代码",
        "create_user": "陈松"
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def updateCode(code_id):
    url = "http://network.netease.com/api/forward/process_update_code"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "code_id": code_id,
        "code_name": "get_sysname1",
        "create_user": "陈松",
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def deleteCode(code_id):
    url = "http://network.netease.com/api/forward/process_delete_code"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "code_id": code_id,
        "create_user": "陈松",
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def getCodeList():
    url = "http://network.netease.com/api/forward/process_get_code_list"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {}

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def getCodeDetail(code_id):
    url = "http://network.netease.com/api/forward/process_get_code_detail"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "code_id": code_id
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def create_process():
    url = "http://network.netease.com/api/forward/process_create_process"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "code_id": 4,
        "params": "\nips = ['10.162.0.14','10.162.0.1','10.162.0.2','10.80.163.98']",
        "log_desc": "测试",
        "operator": "陈松"
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def update_process():
    url = "http://network.netease.com/api/forward/process_update_process"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "process_id": 1,
        "op_status": "01",
        "log_result": "测试",
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def delete_process(process_id):
    url = "http://network.netease.com/api/forward/process_delete_process"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "process_id": process_id
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def get_process():
    url = "http://network.netease.com/api/forward/process_get_process_list"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {}

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data


def execute_process():
    url = "http://network.netease.com/api/forward/process_execute"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "process_id": 3
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def status_process():
    url = "http://network.netease.com/api/forward/process_pro_status"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "process_id": 3
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data

def stop_process():
    url = "http://network.netease.com/api/forward/process_pro_stop"

    headers = {
        "key": "testsd",
        "secret": secret
    }

    body = {
        "process_id": 3
    }

    r = requests.post(url=url, headers=headers, json=body)
    data = json.loads(r.text)
    return data


if __name__ == '__main__':
    code_str = '''
import time

def getNameByIP(ip):
    d1 = getsysname(ip)
    return d1

result = []
for ip in ips:
    name = getNameByIP(ip)
    result.append(name)
    time.sleep(60)
print('Hello, World!')
print(result)
print('xxxxx')


import time

def getVersionByIP(ip):
    d1 = getVersion(ip)
    return d1

result = []
for ip in ips:
    version_info = getVersionByIP(ip)
    result.append(version_info)
print('开始采集设备版本信息')
t1 = time.time()
print(result)
print('结束采集设备版本信息, 耗时:', time.time() - t1)
'''
    # a1 = createCode(code_str)
    # print(a1)

    # a2 = updateCode("1")
    # print(a2)

    # a3 = deleteCode("4")
    # print(a3)

    # a4 = getCodeList()
    # print(a4)

    # a5 = getCodeDetail(3)
    # print(json.dumps(a5, indent=4, ensure_ascii=False))

    # a6 = create_process()
    # print(json.dumps(a6, indent=4, ensure_ascii=False))

    # a7 = update_process()
    # print(json.dumps(a7, indent=4, ensure_ascii=False))

    # a8 = delete_process(3)
    # print(json.dumps(a8, indent=4, ensure_ascii=False))

    # a9 = get_process()
    # print(json.dumps(a9, indent=4, ensure_ascii=False))

    # a10 = execute_process()
    # print(json.dumps(a10, indent=4, ensure_ascii=False))

    # a11 = status_process()
    # print(json.dumps(a11, indent=4, ensure_ascii=False))


    # a12 = stop_process()
    # print(json.dumps(a12, indent=4, ensure_ascii=False))



    pass


