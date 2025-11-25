import re
import time

import requests
import json
from config.config import identy, secret, gate_url

def run_cmd(runconfig):
    url = gate_url + "fast_runcmd?ip={}".format(runconfig["ip"])
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "ip": runconfig["ip"],
        "cmds": runconfig["cmds"],
        "identy": identy
    }
    if "dev_type" in runconfig.keys():
        body["dev_type"] = runconfig["dev_type"]
    if "class_type" in runconfig.keys():
        body["class_type"] = runconfig["class_type"]
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, runconfig)
        return "failed"
    try:
        res = json.loads(r.text)
        if res == 403:
            return "failed"
        else:
            return res
    except:
        print("解析失败,执行命令功能==", r.text)
        return "failed"


def clearIP(ip, num):
    url = "http://network.netease.com/api/forward/fast_delpool?ip={}".format(num)
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "ip": ip
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, ip)
        return "failed"
    try:
        res = json.loads(r.text)
        if res == 403:
            return "failed"
        else:
            return res
    except:
        print("解析失败", r.text)
        return "failed"


def mmm():
    url = gate_url + "notify_send_mail"
    headers = {
        "key": "seer_portal",
        "secret": "901c05adaa9e5b205ed8d3cc03896997"
    }
    body = {
        "message_type": "SD",
        "receivers": ["chensong1@corp.netease.com"],
        "cc": ["zhangjicheng@corp.netease.com"],
        "title": "测试功能",
        "message": "<p>测试</p><p>test</p>"
    }
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e)
        return "failed"
    try:
        res = json.loads(r.text)
        if res == 403:
            return "failed"
        else:
            return res
    except:
        print("解析失败", r.text)
        return "failed"

from concurrent.futures.thread import ThreadPoolExecutor
import functools

def execAllFunctions(tasks, max_workers=8, notify_info=None):
    result = {}
    def cb(future, name):
        stdout = future.result()
        result[name] = stdout

    with ThreadPoolExecutor(max_workers=max_workers) as p:
        # 提交任务
        for task in tasks:
            future = p.submit(task["func"], *task["args"], **task["kwargs"])
            future.add_done_callback(functools.partial(cb, name=task["name"]))
    return result

if __name__ == '__main__':
    from func.snmp_interface import getDeviceType, getsysname

    # ip = "10.162.0.14"
    # tasks = [
    #     {
    #         "name": "exec_cmd_1",
    #         "func": run_cmd,
    #         "args": ({"ip": ip, "cmds": ["dis ip int bri", "sys", "vlan 10", "name test1"]},),
    #         "kwargs": {}
    #     },
    # ]

    cmds = ["dis cu | i snmp",  "", "dis ip int bri", "", "dis vlans", "","dis cu int vlan 2"]
    tasks = []
    ip = "10.80.163.143"
    for idx, item in enumerate(cmds):
        tasks.append({
            "name": ip+"_"+str(idx),
            "func": run_cmd,
            "args": ({"ip": ip, "dev_type": "h3c", "cmds": [item]},),
            "kwargs": {}
        })

    result = execAllFunctions(tasks, max_workers=8)
    print(json.dumps(result, indent=4))








