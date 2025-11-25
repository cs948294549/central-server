from functions.snmp_interface import getVersion, run_snmp_get, run_snmp_walk
from functions.ssh_interface import run_cmd
from functions.portal_interface import getDeviceListByNameAndType
import re
import json
import math
from elasticsearch import Elasticsearch, helpers
import datetime
from concurrent.futures.thread import ThreadPoolExecutor
import functools
import time
import pymysql
from config.config import db_seer

class DB_seer:
    def __init__(self):
        self.conn = pymysql.connect(host=db_seer["host"], user=db_seer["user"], password=db_seer["token"],
                                    port=db_seer["port"],
                                    database=db_seer["dbname"], charset="utf8")
        self.cursor = self.conn.cursor()

    def ping(self):
        self.conn.ping(reconnect=True)
        self.cursor = self.conn.cursor()


    def getAssetsByDeviceName(self, data):
        # group_id, name, op_list
        # select asset_no,device_name,sn,check_escape from asset_info where device_name="
        conditions = []

        serach_reg_key = [
            {"key": "op_list", "value": "op_list"},
            {"key": "name_reg", "value": "name"}
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append(key_item["value"] + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["device_name"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = "select asset_no,device_name,sn,check_escape from asset_info "
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["asset_no", "device_name", "sn", "check_escape"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as err:
            print("======DB_seer.getAssetsByDeviceName error========\n", err)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()




hosts = ["http://wg-es-online-4.gy.ntes:7000", "http://wg-es-online-5.gy.ntes:7000", "http://wg-es-online-6.gy.ntes:7000"]

g_es = Elasticsearch(hosts=hosts)
headers = {"Content-Type": "application/x-ndjson"}


def execAllFunctions(tasks, max_workers=8, callback=None):
    result = {}
    def cb(future, name):
        stdout = future.result()
        result[name] = stdout

    with ThreadPoolExecutor(max_workers=max_workers) as p:
        # 提交任务
        for task in tasks:
            future = p.submit(task["func"], *task["args"], **task["kwargs"])
            future.add_done_callback(functools.partial(cb, name=task["name"]))

    # 回调函数
    if callback:
        callback(result)

    return result


def writeDate(logs):
    # 指定一个文件夹
    try:
        # 创建索引
        action = [{
            "_index": "device_health",
            "_type": "_doc",  # 显式指定 type
            "_source": i,
        } for i in logs]
        ret = helpers.bulk(g_es, action)
        print("写入数据===", ret)
    except Exception as e:
        print(e)


'''
需要按设备类型依次检查以下相关指标
1. 电源状态（双电源冗余性）
2. 风扇转速与温度
3. 板卡在位状态		
4. CPU利用率（5/15分钟均值）[seer]	
5. 内存使用率（包括缓冲/缓存）[seer]	
6. 存储空间（flash利用率）（无）	
7. TCAM/硬件表项利用率（无）	
8. ARP/MAC表项容量（有采集、无告警）	
9. ECMP资源利用率（无）	
10. fib	防火墙会话容量预警（无）	
11. 路由表使用情况（无，含vpn里路由表）水位暂定50%	
12. 光模块状态	
13. 温度监控	
14. 端口吞吐量[seer]	
15. 端口丢包统计（暂定不做）[seer]		
16. 全链路延迟(待pingmesh二期落地后)[seer]		
17. 端口带宽快速增长或下降趋势[seer]		
18. BMP	[seer]	
19. PFC告警	
20. ECN告警	
21. QoS队列拥塞情况告警	
22. BGP/OSPF/IS-IS邻居状态	
23. BGP路由表规模异常（暂定50%）	
24. 标签转发路径（LSP）状态（暂定不做）	
25. STP拓扑变更计数	
26. VPC/MLAG/堆叠分裂检测	
27. VRRP/HSRP状态（倒换计数通过日志实现）	
28. BFD状态	
29. Track/NQA状态（贵州环境不涉及）	
30. NTP状态	
31. 纳管状态	
32. 防护状态	
33. 版本&补丁状态	
34. 维保情况
'''

def mw_to_dbm(mw):
    """
    转换mW为dBm
    """
    return 10*math.log10(mw/10000)

def dbm_to_mw(dbm):
    """
    转换dBm为mW
    """
    return 10**(dbm/10)

class BaseDriver:
    def __init__(self, device_info):
        self.device_info = device_info

    def get_functions(self, func_name):
        """
        获取指定设备类型下的函数

        [
            power_status, fan_status, board_status,
            storage_status, hardware_status, router_status,
            temperature_status, pfc_status, ecn_status,
            qos_status, bgp_status, bgp_route_status,
            stp_status, mlag_status, vrrp_status,
            bfd_status, ntp_status, acl_status,
            transceiver_status
        ]

        """
        if func_name == "power_status":
            return self.get_power_status()
        elif func_name == "fan_status":
            return self.get_fan_status()
        elif func_name == "board_status":
            return self.get_board_status()
        elif func_name == "storage_status":
            return self.get_storage_status()
        elif func_name == "hardware_status":
            return self.get_hardware_status()
        elif func_name == "router_status":
            return self.get_router_status()
        elif func_name == "temperature_status":
            return self.get_temperature_status()
        elif func_name == "pfc_status":
            return self.get_pfc_status()
        elif func_name == "ecn_status":
            return self.get_ecn_status()
        elif func_name == "qos_status":
            return self.get_qos_status()
        elif func_name == "bgp_status":
            return self.get_bgp_status()
        elif func_name == "bgp_route_status":
            return self.get_bgp_route_status()
        elif func_name == "stp_status":
            return self.get_stp_status()
        elif func_name == "mlag_status":
            return self.get_mlag_status()
        elif func_name == "vrrp_status":
            return self.get_vrrp_status()
        elif func_name == "bfd_status":
            return self.get_bfd_status()
        elif func_name == "ntp_status":
            return self.get_ntp_status()
        elif func_name == "acl_status":
            return self.get_acl_status()
        elif func_name == "transceiver_status":
            return self.get_transceiver_status()
        elif func_name == "interface_status":
            return self.get_interface_status()
        else:
            return {"status": "unknown", "data": "unknown function"}


    def get_power_status(self):
        """获取电源状态"""
        raise NotImplementedError

    def get_fan_status(self):
        """获取风扇状态"""
        raise NotImplementedError

    def get_board_status(self):
        """获取板卡状态"""
        raise NotImplementedError

    def get_storage_status(self):
        """获取存储状态"""
        raise NotImplementedError

    def get_hardware_status(self):
        """获取硬件状态"""
        raise NotImplementedError

    def get_router_status(self):
        """获取路由器状态"""
        raise NotImplementedError

    def get_temperature_status(self):
        """获取温度状态"""
        raise NotImplementedError

    def get_pfc_status(self):
        """获取PFC状态"""
        raise NotImplementedError

    def get_ecn_status(self):
        """获取ECN状态"""
        raise NotImplementedError

    def get_qos_status(self):
        """获取QoS状态"""
        raise NotImplementedError

    def get_bgp_status(self):
        """获取BGP状态"""
        raise NotImplementedError

    def get_bgp_route_status(self):
        """获取BGP路由状态"""
        raise NotImplementedError

    def get_stp_status(self):
        """获取STP状态"""
        raise NotImplementedError

    def get_mlag_status(self):
        """获取MLAG状态"""
        raise NotImplementedError

    def get_vrrp_status(self):
        """获取VRRP状态"""
        raise NotImplementedError

    def get_bfd_status(self):
        """获取BFD状态"""
        raise NotImplementedError

    def get_ntp_status(self):
        """获取NTP状态"""
        raise NotImplementedError

    def get_acl_status(self):
        """获取ACL状态"""
        raise NotImplementedError

    def get_transceiver_status(self):
        """获取光模块状态"""
        raise NotImplementedError

    def get_interface_status(self):
        """获取端口状态"""
        raise NotImplementedError

class AristaDriver(BaseDriver):
    def __init__(self, device_info):
        super().__init__(device_info)

    def get_power_status(self):
        """获取电源状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show system environment power']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                cl_flag = False
                for line in msg.split("\n"):
                    if "------" in line:
                        cl_flag = True
                        continue
                    if cl_flag is True:
                        if "PWR" in line:
                            if len(line.split()) > 0:
                                supply_id = line.split()[0]
                                if "OK" in line.upper():
                                    response.append({"supply_id": supply_id, "status": "normal"})
                                else:
                                    response.append({"supply_id": supply_id, "status": "abnormal"})
                            else:
                                continue
                        else:
                            continue

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if item['status'] == "abnormal":
                    all_status = "abnormal"
                    break
        if len(response) >= 2 and all_status == "normal":
            return {"status": "normal", "data": "电源模块正常"}
        else:
            return {"status": all_status, "data": "电源模块异常, 电源少于2个或状态异常"}

    def get_fan_status(self):
        """获取电源状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show system environment cooling']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                cl_flag = False
                for line in msg.split("\n"):
                    if "------" in line:
                        cl_flag = True
                        continue
                    if cl_flag is True:
                        if len(line.split()) > 4:
                            if "PowerSupply" in line:
                                break
                            fan_id = line.split()[0]
                            speed_cfg = line.split()[2]
                            speed_act = line.split()[3]
                            if "OK" in line.upper() and ("stable" in line.lower() or "fw override" in line.lower()):
                                fan_status = "normal"
                            else:
                                fan_status = "abnormal"
                            response.append(
                                {"fan_id": fan_id, "status": fan_status, "speed_cfg": speed_cfg, "speed_act": speed_act})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if item['status'] == "abnormal":
                    all_status = "abnormal"
                    break
                if int(item['speed_act'].replace("%", ""))-int(item['speed_cfg'].replace("%", ""))>10:
                    all_status = "abnormal"
                    break
        if all_status == "normal":
            return {"status": "normal", "data": "风扇正常"}
        else:
            return {"status": all_status, "data": "风扇异常或转速高于额定10%"}

    def get_board_status(self):
        """获取板卡状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) in ["7368"]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show module']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                cl_flag = False
                for line in msg.split("\n"):
                    if "Module" in line and "Status" in line:
                        cl_flag = True
                        continue
                    if "------" in line:
                        continue
                    if cl_flag is True:
                        if len(line.split()) > 3:
                            module_id = line.split()[0]
                            module_status = line.split()[1]
                            if "OK" in module_status.upper() or "active" in module_status.lower():
                                response.append({"module_id": module_id, "status": "normal"})
        else:
            return {"status": "normal", "data": "板卡正常"}

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if item['status'] == "abnormal":
                    all_status = "abnormal"
                    break
        if all_status == "normal":
            return {"status": "normal", "data": "板卡正常"}
        else:
            return {"status": all_status, "data": "板卡状态异常"}

    def get_storage_status(self):
        """获取存储状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['dir']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                re_mem_total = re.compile(r"(\d+)\s+bytes\s+total")
                re_mem_free = re.compile(r"(\d+)\s+bytes\s+free")
                if len(re_mem_total.findall(msg)) > 0 and len(re_mem_free.findall(msg)) > 0:
                    mem_total = re_mem_total.findall(msg)[0]
                    mem_free = re_mem_free.findall(msg)[0]
                    response.append({"mem_total": mem_total, "mem_free": mem_free})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            used_percent = int((int(response[0]['mem_total']) - int(response[0]['mem_free'])) / int(response[0]['mem_total']) * 100)
            response.append({"used_percent": used_percent})
            if used_percent >= 85:
                all_status = "abnormal"
            else:
                all_status = "normal"
        if all_status == "normal":
            return {"status": "normal", "data": "存储使用空间正常"}
        else:
            return {"status": all_status, "data": "存储使用空间高于85%"}

    def get_hardware_status(self):
        """获取硬件状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show hardware capacity']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                cl_flag = False
                for line in msg.split("\n"):
                    if "------" in line:
                        cl_flag = True
                        continue
                    if cl_flag is True:
                        if len(line.split()) > 6:
                            high_mark = line.split()[-1]
                            used_entry = line.split()[-6]
                            entry_id = line.split()[0]
                            response.append({
                                "entry_id": entry_id,
                                "used_entry": used_entry,
                                "high_mark": high_mark})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if str(item['high_mark']) == "0":
                    continue
                else:
                    if int(item['used_entry']) > int(item['high_mark']):
                        all_status = "abnormal"
                        break
        if all_status == "normal":
            return {"status": "normal", "data": "硬件表项正常"}
        else:
            return {"status": all_status, "data": "硬件表项存在异常，使用值高于额定值"}

    def get_router_status(self):
        """获取路由器状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show ip route vrf all summary', 'show ipv6 route vrf all summary']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                re_route_total = re.compile(r"Total\s+Routes\s+(\d+)")
                if len(re_route_total.findall(msg)) > 0:
                    for _sum in re_route_total.findall(msg):
                        response.append({"route_total": _sum})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            route_sum = 0
            for item in response:
                route_sum += int(item["route_total"])

            if str(hardware) in ["7368"]:
                used_percent = int(route_sum/3000000*100)
                response.append({"route_percent": used_percent, "route_total": route_sum})
                if used_percent >= 50:
                    all_status = "abnormal"
                else:
                    all_status = "normal"
            else:
                used_percent = int(route_sum / 1000000 * 100)
                response.append({"route_percent": used_percent, "route_total": route_sum})
                if used_percent >= 50:
                    all_status = "abnormal"
                else:
                    all_status = "normal"

        if all_status == "normal":
            return {"status": "normal", "data": "路由表项正常"}
        else:
            return {"status": all_status, "data": "路由表项存在异常，使用值高于额定值50%"}

    def get_temperature_status(self):
        """获取温度状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show system environment temperature']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                reg_temp = re.compile(r"^\d+\s+")
                reg_setpoint = re.compile(r"\(([\d.]+)\)")
                for line in msg.split("\n"):
                    if reg_temp.match(line):
                        data_array = re.split(r'\s{2,}', line)
                        if "N/A" in data_array[3]:
                            response.append({"temp_id": data_array[0], "temp_value": data_array[2],
                                             "temp_setpoint": data_array[3].split()[1]})
                        else:
                            response.append({"temp_id": data_array[0], "temp_value": data_array[2], "temp_setpoint": reg_setpoint.findall(data_array[3])[0]})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                try:
                    if float(item['temp_value']) <= float(item['temp_setpoint']):
                        continue
                    else:
                        all_status = "abnormal"
                        break
                except Exception as e:
                    print("异常项目==", item)
                    all_status = "abnormal"
                    break
        if all_status == "normal":
            return {"status": "normal", "data": "设备温度正常"}
        else:
            return {"status": all_status, "data": "设备温度存在异常，sensor值高于设定值"}

    def get_pfc_status(self):
        """获取PFC状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show priority-flow-control counters']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                cl_flag = False
                for line in msg.split("\n"):
                    if "RxPfc" in line:
                        cl_flag = True
                        continue
                    if cl_flag is True:
                        if len(line.split()) == 3:
                            response.append({"port": line.split()[0], "rx_pfc": line.split()[1], "tx_pfc": line.split()[2]})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if str(item['rx_pfc']) != "0" or str(item['tx_pfc']) != "0":
                    all_status = "abnormal"
                    break
        if all_status == "normal":
            return {"status": "normal", "data": "PFC表项正常"}
        else:
            return {"status": all_status, "data": "PFC表项存在异常, 接收或发送PFC计数器不为0"}

    def get_ecn_status(self):
        """获取ECN状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show qos ecn']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                if "ECN Disabled" in msg:
                    response.append({"status": "disabled"})
                else:
                    response.append({"status": "enabled"})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if item['status'] == "disabled":
                    all_status = "abnormal"
                    break
        if all_status == "normal":
            return {"status": "normal", "data": "ECN状态正常"}
        else:
            return {"status": all_status, "data": "ecn状态异常，或未开启qos ecn"}

    def get_qos_status(self):
        """获取QoS状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show run | include service-policy|ecn|priority-queue|wred']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                for line in msg.split("\n"):
                    if "show run " in line:
                        continue
                    if line.strip() != "":
                        response.append({"config": line})
            else:
                return {"status": "abnormal", "data": "执行查询命令失败"}
        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "abnormal"
        else:
            all_status = "normal"
        if all_status == "normal":
            return {"status": "normal", "data": "qos状态正常"}
        else:
            return {"status": all_status, "data": "qos状态异常或未开启qos"}

    def get_bgp_status(self):
        """获取BGP状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show ip bgp summary']})
            if ret != "failed":
                # 检查bgp
                reg_ip = re.compile(r"(?:\d+\.){3}\d+")
                cl_flag = False
                for line in ret["[0]show ip bgp summary"].split("\n"):
                    if "PfxRcd PfxAcc" in line:
                        cl_flag = True
                        continue
                    if cl_flag is True:
                        if "Estab" in line:
                            continue
                        else:
                            peer_data_array = reg_ip.findall(line)
                            if len(peer_data_array) > 0:
                                response.append({"peer_ip": peer_data_array[0], "status": "down"})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "normal"
        else:
            all_status = "abnormal"
        if all_status == "normal":
            return {"status": "normal", "data": "bgp状态正常"}
        else:
            return {"status": all_status, "data": "bgp状态异常，存在down的邻居"}

    def get_bgp_route_status(self):
        """获取BGP路由状态"""
        """获取硬件状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show hardware capacity']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                cl_flag = False
                for line in msg.split("\n"):
                    if "------" in line:
                        cl_flag = True
                        continue
                    if cl_flag is True:
                        if len(line.split()) > 6:
                            high_mark = line.split()[-1]
                            used_entry = line.split()[-6]
                            entry_id = line.split()[0]
                            response.append({
                                "entry_id": entry_id,
                                "used_entry": used_entry,
                                "high_mark": high_mark})

        # 条件判断
        all_status = "normal"
        used_percent = 0
        if len(response) == 0:
            all_status = "unknown"
        else:
            host_sum = 0
            alpm_sum = 0
            for item in response:
                if "Host" in item['entry_id'] and host_sum == 0:
                    host_sum = int(item['used_entry'])
                if "ALPM" in item['entry_id'] and alpm_sum == 0:
                    alpm_sum = int(item['used_entry'])
            used_sum = host_sum + alpm_sum
            if "7368" in str(hardware):
                used_percent = int(used_sum / 480000 * 100)
            else:
                used_percent = int(used_sum / 180000 * 100)

            if int(used_percent) >= 50:
                all_status = "abnormal"

        if all_status == "normal":
            return {"status": "normal", "data": "bgp路由表项数值正常，当前值{}%".format(used_percent)}
        else:
            return {"status": all_status, "data": "bgp路由表项存在异常，使用值高于额定值50%，当前值{}%".format(used_percent)}


    def get_stp_status(self):
        """获取STP状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show spanning-tree topology status detail']})
            if ret != "failed":
                # 检查stp
                msg = "\n".join(ret.values())
                if "Topology: NoStp" in msg:
                    response.append({"status": "disabled"})
                else:
                    response.append({"status": "enabled"})


        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if item['status'] == "enabled":
                    all_status = "abnormal"
                    break
        if all_status == "normal":
            return {"status": "normal", "data": "stp状态正常"}
        else:
            return {"status": all_status, "data": "stp状态异常，或未开启stp"}

    def get_mlag_status(self):
        """获取MLAG状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show mlag']})
            if ret != "failed":
                # 检查mlag
                msg = "\n".join(ret.values())
                mlag_info = {}
                for line in msg.split("\n"):
                    if "domain-id" in line:
                        domain_id = line.split(":")[1].strip()
                        mlag_info["domain_id"] = domain_id
                    if "state" in line:
                        state = line.split(":")[1].strip()
                        mlag_info["state"] = state
                        response.append(mlag_info)
                        break


        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if item['domain_id'].strip() == "":
                    continue
                else:
                    if item['state'] == "Disabled":
                        all_status = "abnormal"
                        break
        if all_status == "normal":
            return {"status": "normal", "data": "mlag状态正常"}
        else:
            return {"status": all_status, "data": "mlag状态异常, 存在状态为Disabled的mlag"}

    def get_vrrp_status(self):
        """获取VRRP状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show ip virtual-router']})
            if ret != "failed":
                # 检查vrrp
                msg = "\n".join(ret.values())
                cl_flag = False
                for line in msg.split("\n"):
                    if "------" in line:
                        cl_flag = True
                        continue
                    if cl_flag is True:
                        data_array = line.split()
                        if len(data_array) >= 3:
                            response.append({"interface": data_array[0], "status": data_array[-1]})
            else:
                return {"status": "abnormal", "data": "执行查询命令失败"}


        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "normal"
        else:
            for item in response:
                if item['status'] == "active":
                    continue
                else:
                    all_status = "abnormal"
                    break
        if all_status == "normal":
            return {"status": "normal", "data": "vrrp状态正常"}
        else:
            return {"status": all_status, "data": "vrrp状态异常, 存在非active的vrrp"}

    def get_bfd_status(self):
        """获取BFD状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show bfd peer ipv4']})
            if ret != "failed":
                # 检查bfd
                msg = "\n".join(ret.values())
                reg_ip = re.compile(r"^(?:\d+\.){3}\d+")
                for line in msg.split("\n"):
                    if reg_ip.match(line):
                        data_array = line.split()
                        response.append({"peer_ip": data_array[0], "status": data_array[-1], "interface": data_array[3]})
            else:
                return {"status": "abnormal", "data": "执行查询命令失败"}
        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "normal"
        else:
            for item in response:
                if item['status'] == "Up":
                    continue
                else:
                    if "VLAN" in item["interface"].upper():
                        continue
                    else:
                        all_status = "abnormal"
                        break
        if all_status == "normal":
            return {"status": "normal", "data": "bfd状态正常"}
        else:
            return {"status": all_status, "data": "bfd状态异常, 存在非Up的bfd"}

    def get_ntp_status(self):
        """获取NTP状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show ntp status']})
            if ret != "failed":
                # 检查ntp
                msg = "\n".join(ret.values())
                if "103.71.202.10" in msg:
                    response.append({"status": "enabled"})
                else:
                    response.append({"status": "disabled"})
            else:
                return {"status": "abnormal", "data": "执行查询命令失败"}

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if item['status'] == "enabled":
                    continue
                else:
                    all_status = "abnormal"
                    break
        if all_status == "normal":
            return {"status": "normal", "data": "ntp状态正常"}
        else:
            return {"status": all_status, "data": "ntp状态异常, 未查询到指定的ntp服务器(103.71.202.10)"}

    def get_acl_status(self):
        """获取ACL状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show ip access-lists 2000']})
            if ret != "failed":
                # 检查acl
                msg = "\n".join(ret.values())
                for line in msg.split("\n"):
                    if "103.71.202.0/25" in line:
                        if "match" in line:
                            response.append({"status": "match", "prefix": "103.71.202.0/25"})
                        else:
                            response.append({"status": "nomatch", "prefix": "103.71.202.0/25"})
                    if "10.60.255.96/27" in line:
                        if "match" in line:
                            response.append({"status": "match", "prefix": "10.60.255.96/27"})
                        else:
                            response.append({"status": "nomatch", "prefix": "10.60.255.96/27"})
            else:
                return {"status": "abnormal", "data": "执行查询命令失败"}

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            flag_match = {"fn": False, "ob": False, "matched": False}
            for item in response:
                if item['status'] == "match":
                    flag_match["matched"] = True
                if item['prefix'] == "103.71.202.0/25":
                    flag_match["fn"] = True
                if item['prefix'] == "10.60.255.96/27":
                    flag_match["ob"] = True
            response.append(flag_match)

            if flag_match["fn"] is True and flag_match["ob"] is True and flag_match["matched"] is True:
                all_status = "normal"
            else:
                all_status = "abnormal"

        if all_status == "normal":
            return {"status": "normal", "data": "acl状态正常"}
        else:
            return {"status": all_status, "data": "acl状态异常, 未匹配到指定的acl规则"}

    def get_transceiver_status(self):
        """获取transceiver状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show interfaces transceiver dom thresholds']})
            if ret != "failed":
                # 检查transceiver
                msg = "\n".join(ret.values())
                reg_port = re.compile(r'^Port\s+(\d+)')
                current_port = None
                current_channel = None
                current_info = {}
                for line in msg.split('\n'):
                    if reg_port.match(line):
                        if current_port is not None:
                            response.append(current_info)
                        current_port = "Port {}".format(reg_port.findall(line)[0])
                        current_info = {"Port": current_port}
                        continue
                    else:
                        if current_port is None:
                            continue
                        else:
                            if 'Last update' in line:
                                if "N/A" in line:
                                    current_port = None
                                    continue

                            if 'Temperature' in line:
                                temp_array = re.split('\s{2,}', line.strip())
                                current_info["Temperature"] = {"Value": temp_array[1], "High Alarm": temp_array[2],
                                                               "High Warn": temp_array[3], "Low Warn": temp_array[4],
                                                               "Low Alarm": temp_array[5], "Unit": temp_array[6]}
                            if 'Voltage' in line:
                                volt_array = re.split('\s{2,}', line.strip())
                                current_info["Voltage"] = {"Value": volt_array[1], "High Alarm": volt_array[2],
                                                           "High Warn": volt_array[3], "Low Warn": volt_array[4],
                                                           "Low Alarm": volt_array[5], "Unit": volt_array[6]}
                            if 'TX bias current' in line:
                                tx_bias_array = re.split('\s{2,}', line.strip())
                                if len(tx_bias_array) <= 4:
                                    current_channel = "TX bias current"
                                    continue
                                else:
                                    current_info["tx_bias_0"] = {"Value": tx_bias_array[1],
                                                                 "High Alarm": tx_bias_array[2],
                                                                 "High Warn": tx_bias_array[3],
                                                                 "Low Warn": tx_bias_array[4],
                                                                 "Low Alarm": tx_bias_array[5],
                                                                 "Unit": tx_bias_array[6]}
                            if 'Optical TX power' in line:
                                tx_power_array = re.split('\s{2,}', line.strip())
                                if len(tx_power_array) <= 4:
                                    current_channel = "Optical TX power"
                                    continue
                                else:
                                    current_info["tx_power_0"] = {"Value": tx_power_array[1],
                                                                  "High Alarm": tx_power_array[2],
                                                                  "High Warn": tx_power_array[3],
                                                                  "Low Warn": tx_power_array[4],
                                                                  "Low Alarm": tx_power_array[5],
                                                                  "Unit": tx_power_array[6]}
                            if 'Optical RX power' in line:
                                rx_power_array = re.split('\s{2,}', line.strip())
                                if len(rx_power_array) <= 4:
                                    current_channel = "Optical RX power"
                                    continue
                                else:
                                    current_info["rx_power_0"] = {"Value": rx_power_array[1],
                                                                  "High Alarm": rx_power_array[2],
                                                                  "High Warn": rx_power_array[3],
                                                                  "Low Warn": rx_power_array[4],
                                                                  "Low Alarm": rx_power_array[5],
                                                                  "Unit": rx_power_array[6]}

                            if "Channel" in line:
                                channel_array = re.split('\s{2,}', line.strip())
                                if current_channel is None:
                                    continue
                                else:
                                    if current_channel == "TX bias current":
                                        current_info["tx_bias_{}".format(channel_array[1])] = {
                                            "Value": channel_array[2], "High Alarm": channel_array[3],
                                            "High Warn": channel_array[4], "Low Warn": channel_array[5],
                                            "Low Alarm": channel_array[6], "Unit": channel_array[7]}
                                    if current_channel == "Optical TX power":
                                        current_info["tx_power_{}".format(channel_array[1])] = {
                                            "Value": channel_array[2], "High Alarm": channel_array[3],
                                            "High Warn": channel_array[4], "Low Warn": channel_array[5],
                                            "Low Alarm": channel_array[6], "Unit": channel_array[7]}
                                    if current_channel == "Optical RX power":
                                        current_info["rx_power_{}".format(channel_array[1])] = {
                                            "Value": channel_array[2], "High Alarm": channel_array[3],
                                            "High Warn": channel_array[4], "Low Warn": channel_array[5],
                                            "Low Alarm": channel_array[6], "Unit": channel_array[7]}

            else:
                return {"status": "abnormal", "data": "执行查询命令失败"}

        # 条件判断
        all_status = "normal"
        final_response = []
        port_list = []
        if len(response) == 0:
            all_status = "normal"
        else:
            for item in response:
                for key in item:
                    if key == "Port":
                        continue
                    else:
                        if "N/A" in str(item[key]):
                            continue
                        if float(item[key]["Value"]) >= float(item[key]["High Warn"]) or float(item[key]["Value"]) <= float(item[key]["Low Warn"]):
                            all_status = "abnormal"
                            final_response.append({"status": "abnormal", "key": key, "data": item["Port"]})
                            if item["Port"] not in port_list:
                                port_list.append(item["Port"])
        if all_status == "normal":
            return {"status": "normal", "data": "光模块状态正常"}
        else:
            return {"status": all_status, "data": "光模块存在异常指标，相关接口为{}".format(",".join(port_list))}


    def get_interface_status(self):
        """获取接口状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'arista', 'cmds': ['show interfaces status errdisabled', "show interfaces description | include error|bad|BAD|use"]})
            if ret != "failed":
                # 检查接口
                status_info = {}
                err_msg = list(ret.values())[0]
                if len(err_msg.split("\n")) > 1:
                    status_info["error_disabled"] = True
                else:
                    status_info["error_disabled"] = False

                desc_msg = list(ret.values())[1]
                if len(desc_msg.split("\n")) > 1:
                    status_info["bad_port"] = True
                else:
                    status_info["bad_port"] = False
                response.append(status_info)
            else:
                return {"status": "abnormal", "data": "执行查询命令失败"}

        # 条件判断
        all_status = "normal"
        padding = ""
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if item['error_disabled'] is True or item['bad_port'] is True:
                    all_status = "abnormal"
                    padding = "error_disabled: {} bad_port: {}".format(item['error_disabled'], item['bad_port'])
                    break
        if all_status == "normal":
            return {"status": "normal", "data": "接口状态正常"}
        else:
            return {"status": all_status, "data": "接口存在异常状态,{}".format(padding)}


class CiscoNXOSDriver(BaseDriver):
    def __init__(self, device_info):
        super().__init__(device_info)

    def get_power_status(self):
        """获取电源状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'cisco', 'cmds': ['show environment power']})
            if ret != "failed":
                # 检查电源
                msg = "\n".join(ret.values())
                print(msg)
                for line in msg.split("\n"):
                    if " W" in line:
                        data_array = re.split('\s{2,}', line.strip())
                        if len(data_array) >= 5:
                            response.append({"power": data_array[1], "status": data_array[-1]})
            else:
                return {"status": "abnormal", "data": "执行查询命令失败"}

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            return {"status": "abnormal", "data": "未查询到电源信息"}
        else:
            ok_sum = 0
            for item in response:
                if item['status'] == "Ok":
                    ok_sum += 1
                if item['status'] in ["Absent"]:
                    continue
                if item['status'] in ["Ok", "Powered-Up"]:
                    continue
                else:
                    all_status = "abnormal"
            if ok_sum < 2:
                return {"status": "abnormal", "data": "电源数量异常, 至少需要2个"}

        if all_status == "normal":
            return {"status": "normal", "data": "电源状态正常"}
        else:
            return {"status": all_status, "data": "电源状态异常，存在不为 Powered-Up或Ok的电源"}

    def get_fan_status(self):
        """获取风扇状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'cisco', 'cmds': ['show environment fan detail']})
            if ret != "failed":
                # 检查风扇
                msg = "\n".join(ret.values())
                fan_status_flag = False
                fan_speed_flag = False
                collect_falg = False
                for line in msg.split("\n"):
                    if "Status" in line:
                        fan_status_flag = True
                        fan_speed_flag = False
                        continue
                    if "--------------" in line:
                        collect_falg = True
                        continue
                    if "Speed(RPM)" in line:
                        fan_speed_flag = True
                        fan_status_flag = False
                        continue
                    if collect_falg is True:
                        if fan_status_flag is True:
                            data_array = re.split('\s{2,}', line.strip())
                            if "-to-" in line.strip():
                                response.append({"type": "fan_status", "data": data_array[-1]})
                        if fan_speed_flag is True:
                            data_array = re.split('\s{2,}', line.strip())
                            if "-to-" in line.strip():
                                # response.append({"type": "fan_speed",
                                #                  "name": "{}_{}".format(data_array[0], int(data_array[1][-1]) % 2),
                                #                  "speed_per": int(data_array[-2])})
                                response.append({"type": "fan_speed",
                                                 "name": "{}".format(data_array[1]),
                                                 "speed_per": int(data_array[-2])})
            else:
                return {"status": "abnormal", "data": "执行查询命令失败"}

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            return {"status": "abnormal", "data": "未查询到风扇信息"}
        else:
            ok_sum = 0
            speed_dict = {}
            for item in response:
                if item['type'] == "fan_status":

                    if item['data'] in ["Ok"]:
                        ok_sum += 1
                    else:
                        all_status = "abnormal"
                        return {"status": all_status, "data": "风扇存在状态不正确"}
                if item['type'] == "fan_speed":
                    if item["name"] not in speed_dict.keys():
                        speed_dict[item["name"]] = [item["speed_per"]]
                    else:
                        speed_dict[item["name"]].append(item["speed_per"])

            if ok_sum < 2:
                return {"status": "abnormal", "data": "风扇数量异常, 至少需要2个"}

            for fan_name in speed_dict.keys():
                check_speed = int(max(speed_dict[fan_name])-min(speed_dict[fan_name]))
                if int(check_speed) > 5:
                    all_status = "abnormal"
                    return {"status": all_status, "data": "风扇{}存在异常风扇转速".format(fan_name)}

        if all_status == "normal":
            return {"status": "normal", "data": "风扇状态正常"}
        else:
            return {"status": all_status, "data": "风扇状态异常，存在不为 Okay或Ok的风扇"}

    def get_board_status(self):
        """获取板卡状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'cisco', 'cmds': ['show module']})
            if ret != "failed":
                # 检查板卡
                msg = "\n".join(ret.values())
                module_status_flag = False
                collect_falg = False
                for line in msg.split("\n"):
                    if "Model" in line and "Status" in line and "Module-Type" in line:
                        module_status_flag = True
                        continue
                    if "---" in line and collect_falg is False:
                        collect_falg = True
                        continue
                    if collect_falg is True:
                        if "---" in line:
                            collect_falg = False
                            module_status_flag = False
                            continue
                        if "Mod " in line and module_status_flag is True:
                            collect_falg = False
                            module_status_flag = False
                            continue
                        if module_status_flag is True:
                            data_array = re.split('\s{2,}', line.strip())
                            print(data_array)
                            if len(data_array) >= 4:
                                response.append({"model": data_array[0], "name": data_array[2], "status": data_array[-1]})


        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            return {"status": "abnormal", "data": "未查询到板卡信息"}
        else:
            for item in response:
                if "ok" in item['status'] or "active *" in item['status'] or "standby" in item['status']:
                    pass
                else:
                    all_status = "abnormal"
        if all_status == "normal":
            return {"status": "normal", "data": "板卡状态正常"}
        else:
            return {"status": all_status, "data": "板卡状态异常，存在不为 ok或active的板卡"}

    def get_storage_status(self):
        """获取存储状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'cisco', 'cmds': ['dir']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                print(msg)
                re_mem_total = re.compile(r"(\d+)\s+bytes\s+total")
                re_mem_free = re.compile(r"(\d+)\s+bytes\s+free")
                if len(re_mem_total.findall(msg)) > 0 and len(re_mem_free.findall(msg)) > 0:
                    mem_total = re_mem_total.findall(msg)[0]
                    mem_free = re_mem_free.findall(msg)[0]
                    response.append({"mem_total": mem_total, "mem_free": mem_free})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            used_percent = int((int(response[0]['mem_total']) - int(response[0]['mem_free'])) / int(response[0]['mem_total']) * 100)
            response.append({"used_percent": used_percent})
            if used_percent >= 85:
                all_status = "abnormal"
            else:
                all_status = "normal"
        if all_status == "normal":
            return {"status": "normal", "data": "存储使用空间正常"}
        else:
            return {"status": all_status, "data": "存储使用空间高于85%"}

    def get_hardware_status(self):
        """获取硬件状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'cisco', 'cmds': [
                "show hardware capacity",
            ]})
            if ret != "failed":
                msg = "\n".join(ret.values())
                print(msg)
                cl_flag = False
                for line in msg.split("\n"):
                    if "------" in line:
                        cl_flag = True
                        continue
                    if cl_flag is True:
                        if len(line.split()) > 6:
                            high_mark = line.split()[-1]
                            used_entry = line.split()[-6]
                            entry_id = line.split()[0]
                            response.append({
                                "entry_id": entry_id,
                                "used_entry": used_entry,
                                "high_mark": high_mark})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            for item in response:
                if str(item['high_mark']) == "0":
                    continue
                else:
                    if int(item['used_entry']) > int(item['high_mark']):
                        all_status = "abnormal"
                        break
        if all_status == "normal":
            return {"status": "normal", "data": "硬件表项正常"}
        else:
            return {"status": all_status, "data": "硬件表项存在异常，使用值高于额定值"}

    def get_router_status(self):
        """获取路由器状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'cisco', 'cmds': ['show ip route summary']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                re_route_total = re.compile(r"Total\s+number\s+of\s+routes:\s+(\d+)")
                if len(re_route_total.findall(msg)) > 0:
                    for _sum in re_route_total.findall(msg):
                        response.append({"route_total": _sum})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            pass

        if all_status == "normal":
            return {"status": "normal", "data": "路由表项正常, 总数为{}".format(response[0]['route_total'])}
        else:
            return {"status": all_status, "data": "路由表项存在异常，使用值高于额定值50%"}

    def get_temperature_status(self):
        """获取温度状态"""
        target_ip = self.device_info['ip']
        hardware = self.device_info['hardware']
        response = []
        if str(hardware) not in [""]:
            ret = run_cmd({'ip': target_ip, "dev_type": 'cisco', 'cmds': ['show environment temperature']})
            if ret != "failed":
                msg = "\n".join(ret.values())
                print(msg)
                re_route_total = re.compile(r"Total\s+number\s+of\s+routes:\s+(\d+)")
                if len(re_route_total.findall(msg)) > 0:
                    for _sum in re_route_total.findall(msg):
                        response.append({"route_total": _sum})

        # 条件判断
        all_status = "normal"
        if len(response) == 0:
            all_status = "unknown"
        else:
            pass

        if all_status == "normal":
            return {"status": "normal", "data": "路由表项正常, 总数为{}".format(response[0]['route_total'])}
        else:
            return {"status": all_status, "data": "路由表项存在异常，使用值高于额定值50%"}




driver_map = {
    "arista": AristaDriver,
    "cisco": CiscoNXOSDriver,
}

def get_driver(ip):
    """根据设备类型获取对应的驱动"""
    device_info = getVersion(ip=ip)
    print("当前设备===", device_info)
    if device_info == "unknown":
        print("unknown device type {}".format(ip))
        return None, None
    else:
        dev_type = device_info['dev_type']
        if dev_type in driver_map:
            return driver_map[dev_type](device_info), device_info
        else:
            print("unsupported device type {}".format(ip))
            return None, None


def inspect_device(ip):
    """检查设备状态"""
    dr, device_info = get_driver(ip)
    if dr is None:
        return {"status": "unknown", "data": "unsupported device type"}
    else:
        check_list = [
            "power_status", "fan_status", "board_status",
            "storage_status", "hardware_status", "router_status",
            "temperature_status", "pfc_status", "ecn_status",
            "qos_status", "bgp_status", "bgp_route_status",
            "stp_status", "mlag_status", "vrrp_status",
            "bfd_status", "ntp_status", "acl_status",
            "transceiver_status", "interface_status"
        ]
        score_dict = {
            "power_status": 10,
            "fan_status": 8,
            "board_status": 15,
            "storage_status": 0,
            "hardware_status": 5,
            "router_status": 5,
            "temperature_status": 8,
            "pfc_status": 0,
            "ecn_status": 0,
            "qos_status": 0,
            "bgp_status": 5,
            "bgp_route_status": 5,
            "stp_status": 0,
            "mlag_status": 5,
            "vrrp_status": 5,
            "bfd_status": 5,
            "ntp_status": 5,
            "acl_status": 0,
            "transceiver_status": 4,
            "management_status": 5,
            "interface_status": 5
        }

        response = {
            "datetime": "{}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "timestamp": int(time.time())*1000,
            "device_ip": ip,
            "device_name": device_info['sysname'],
            "device_facturer": device_info['dev_type'],
            "device_model": device_info['hardware'],
            "sn": "",
            "asset_no": "",
            "score": 100,
            "nomal_item": "",
            "error_num": 0,
            "error_item": "",
            "message": ""
        }
        error_items = []
        nomal_items = []
        error_messages = []

        # 查先知库检查健康度
        db = DB_seer()
        health_info_list = db.getAssetsByDeviceName({"device_name": device_info['sysname']})
        if len(health_info_list) > 0:
            # 存在健康信息
            health_flag = True
            sns = []
            assert_nos = []
            for item in health_info_list:
                if str(item['check_escape']) != "0":
                    health_flag = False
                if str(item['asset_no']) not in assert_nos:
                    assert_nos.append(str(item['asset_no']))
                if str(item['sn']) not in sns:
                    sns.append(str(item['sn']))
            # asset_no,device_name,sn
            if len(sns) > 0:
                response['sn'] = ",".join(sns)
            if len(assert_nos) > 0:
                response['asset_no'] = ",".join(assert_nos)

            if health_flag is True:
                if "management_status" not in nomal_items:
                    nomal_items.append("management_status")
            else:
                if "management_status" in score_dict:
                    response['score'] -= score_dict["management_status"]
                else:
                    print("unknown item {} for score".format("management_status"))
                response['error_num'] += 1
                error_items.append("management_status")
                error_messages.append("模块: {}  异常原因: 管理状态信息异常".format("management_status"))
        else:
            # 健康信息不存在
            if "management_status" in score_dict:
                response['score'] -= score_dict["management_status"]
            else:
                print("unknown item {} for score".format("management_status"))
            response['error_num'] += 1
            error_items.append("management_status")
            error_messages.append("模块: {}  异常原因: 管理状态信息不存在".format("management_status"))

        for item in check_list:
            try:
                ret = dr.get_functions(item)
                print(item, ret)
            except Exception as e:
                print("error: {} {} {}".format(ip, item, str(e)))
                continue

            if ret['status'] == "normal":
                if item not in nomal_items:
                    nomal_items.append(item)
            else:
                if item in score_dict:
                    response['score'] -= score_dict[item]
                else:
                    print("unknown item {} for score".format(item))

                response['error_num'] += 1
                error_messages.append("模块: {}  异常原因: {}".format(item, ret['data']))
                error_items.append(item)

        response['message'] = "\n".join(error_messages)
        response['error_item'] = ",".join(error_items)
        response['nomal_item'] = ",".join(nomal_items)

        print("response===", response)
        return response

if __name__ == '__main__':
    # dr = get_driver(ip="10.80.200.4")
    dr, device_info = get_driver(ip="10.80.200.75")
    # dr, device_info = get_driver(ip="10.163.15.73")
    sd = dr.get_functions("temperature_status")
    print(json.dumps(sd, indent=4, ensure_ascii=False))

    # info = inspect_device(ip="10.163.13.100")
    # print(info)
    # writeDate([info])

    # dev_list = getDeviceListByNameAndType({"sysname": "^NGY", "sysdesc": "Arista"})
    # tasks = []
    # for item in dev_list:
    #     tasks.append({
    #                 "name": "exec_cmd_{}".format(item["ip"]),
    #                 "func": inspect_device,
    #                 "args": (item["ip"],),
    #                 "kwargs": {}
    #             })
    #
    # result = execAllFunctions(tasks)
    # writeDate(list(result.values()))