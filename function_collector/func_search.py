
import threading
from tables.CollectDB import CollectDB
import re

def func_fulltext(searchKeys):

    class T_thread(threading.Thread):
        def __init__(self, func, args=(), kwargs=()):
            super(T_thread, self).__init__()
            self.func = func
            self.args = args
            self.kwargs = kwargs

        def run(self):
            self.result = self.func(*self.args, *self.kwargs)

        def get_result(self):
            try:
                return self.result  # 如果子线程不使用join方法，此处可能会报没有self.result的错误
            except Exception:
                return None

    respond_full = {}

    # 设备列表中查找 设备名 或 ip 或描述
    def getDeviceList(query):
        search_keys = query.split()
        condition = {"ip": [], "sysname": [], "sysdesc": [], "syscontact": []}
        for key in search_keys:
            arp_reg = re.compile("[\d.]+")
            if arp_reg.match(key):
                condition["sysname"].append(key)
                condition["syscontact"].append(key)
                if "." in key:
                    condition["ip"].append(key)
            elif key in ["huawei", "h3c", "dell", "ruijie", "arista", "cisco", "nx-os"]:
                str_key = ""
                for m in key:
                    str_key += "[{}{}]".format(m, m.upper())
                condition["sysdesc"].append(str_key)
            else:
                condition["sysname"].append(key)
                condition["syscontact"].append(key)
        dev_list = {}
        if len(condition["ip"]) > 0:
            db_device = CollectDB()
            res_dev = db_device.getfulltextDeviceList({"ip": condition["ip"]})
            if res_dev == "failed":
                return "failed"
            for dev in res_dev:
                if dev["sysname"] not in dev_list.keys():
                    dev_list[dev["sysname"]] = dev

        if len(condition["syscontact"]) > 0:
            db_device = CollectDB()
            res_dev = db_device.getfulltextDeviceList({"syscontact": condition["syscontact"]})
            if res_dev == "failed":
                return "failed"
            for dev in res_dev:
                if dev["sysname"] not in dev_list.keys():
                    dev_list[dev["sysname"]] = dev

        if len(condition["sysname"]) > 0 or len(condition["sysdesc"]) > 0:
            db_device = CollectDB()
            res_dev = db_device.getfulltextDeviceList({"sysname": condition["sysname"], "sysdesc": condition["sysdesc"]})
            if res_dev == "failed":
                return "failed"
            for dev in res_dev:
                if dev["sysname"] not in dev_list.keys():
                    dev_list[dev["sysname"]] = dev
        return [i for i in dev_list.values()]

    # 网关的接口IP
    def getGateList(query):
        gate_list = {}

        reg_ip = re.compile(r'(([01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5])\.){3}([01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5])')
        if reg_ip.match(query):
            db_gate = CollectDB()
            res_gate = db_gate.getfulltextDeviceGates({"gatereg": "^{}$".format(query)})
            if res_gate == "failed":
                res_gate = []
        else:
            res_gate = []

        if len(res_gate) == 0:
            if reg_ip.match(query):
                db_gate = CollectDB()
                res_gate = db_gate.getfulltextDeviceGates({"gate": query})
                if res_gate == "failed":
                    res_gate = []
            else:
                res_gate = []

        if len(res_gate) == 0:
            db_gate = CollectDB()
            res_gate = db_gate.getfulltextDeviceGates({"gatereg": query})

        if res_gate == "failed":
            return "failed"
        for gate in res_gate:
            tag = gate["ip"] + "_" + gate["gateway"]
            if tag not in gate_list.keys():
                gate_list[tag] = gate
        return [i for i in gate_list.values()]

    # 网关的接口IP
    def getGateIPv6List(query):
        gate_list = {}
        db_gate = CollectDB()
        res_gate = db_gate.getfulltextDeviceGatesIPv6({"gatereg": query.lower()})
        if res_gate == "failed":
            return "failed"
        for gate in res_gate:
            tag = gate["ip"] + "_" + gate["gateway"]
            if tag not in gate_list.keys():
                gate_list[tag] = gate
        return [i for i in gate_list.values()]

    # sn信息
    def getSNList(query):
        sn_list = {}
        db_sn = CollectDB()
        res_sn = db_sn.getDeviceSNS({"sn_number": query, "limit": 1})
        if res_sn == "failed":
            return "failed"
        for sn in res_sn:
            tag = sn["ip"] + "_" + str(sn["sn_id"])
            if tag not in sn_list.keys():
                sn_list[tag] = sn
        return [i for i in sn_list.values()]

    # port 信息
    def getPortList(query):
        port_list = {}
        db_port = CollectDB()
        res_port = db_port.getPortInfo({"alias": query, "limit": 1})
        if res_port == "more" or res_port == "failed":
            return "failed"
        for port in res_port:
            tag = port["ip"] + "_" + str(port["port_id"])
            if tag not in port_list.keys():
                port_list[tag] = port
        return [i for i in port_list.values()]

    # arp 信息
    def getARPlist(query):
        arp_list = {}
        arp_reg = re.compile("[\d.]+")
        mac_reg1 = re.compile("(?:[0-9a-fA-F]{4}[-.]){2}[0-9a-fA-F]{4}")
        mac_reg2 = re.compile("(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")
        if arp_reg.match(query):
            db_arp = CollectDB()
            res_arp = db_arp.getfulltextDeviceARP({"arp_ip": query})
        elif mac_reg1.match(query):
            mac1_t = query.replace("-", "").replace(".", "").upper()
            b = re.findall(r'.{2}', mac1_t)
            searchK = ":".join(b)
            db_arp = CollectDB()
            res_arp = db_arp.getfulltextDeviceARP({"arp_mac": searchK})
        elif mac_reg2.match(query):
            mac1_t = query.replace("-", "").replace(":", "").upper()
            b = re.findall(r'.{2}', mac1_t)
            searchK = ":".join(b)
            db_arp = CollectDB()
            res_arp = db_arp.getfulltextDeviceARP({"arp_mac": searchK})
        else:
            return []

        if res_arp == "failed":
            return "failed"
        for arp in res_arp:
            tag = arp["ip"] + "_" + str(arp["arp_ip"])
            if tag not in arp_list.keys():
                arp_list[tag] = arp
        return [i for i in arp_list.values()]

    # mac信息
    def getMAClist(query):
        reg_ip = re.compile(r'(([01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5])\.){3}([01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5])')
        mac_reg1 = re.compile("(?:[0-9a-fA-F]{4}[-.]){2}[0-9a-fA-F]{4}")
        mac_reg2 = re.compile("(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")

        if reg_ip.match(query):
            db_arp = CollectDB()
            res_arp = db_arp.getfulltextDeviceMAC({"arp_ip": query})
            return res_arp
        elif mac_reg1.match(query):
            mac1_t = query.replace("-", "").replace(".", "").upper()
            b = re.findall(r'.{2}', mac1_t)
            searchK = ":".join(b)
            db_arp = CollectDB()
            res_arp = db_arp.getfulltextDeviceMAC({"arp_mac": searchK})
            return res_arp
        elif mac_reg2.match(query):
            mac1_t = query.replace("-", "").replace(":", "").upper()
            b = re.findall(r'.{2}', mac1_t)
            searchK = ":".join(b)
            db_arp = CollectDB()
            res_arp = db_arp.getfulltextDeviceMAC({"arp_mac": searchK})
            return res_arp
        else:
            return []

    # lldp信息 服务器名称
    def getLLDPlist(query):
        db_lldp = CollectDB()
        res_lldp = db_lldp.getLLDPs({"rem_name": query, "limit": "1"})
        return res_lldp


    if searchKeys.strip() == "":
        respond_full["device_list"] = getDeviceList(searchKeys)
        respond_full["gate_list"] = []
        respond_full["sn_list"] = []
        respond_full["port_list"] = []
        respond_full["arp_list"] = []
        respond_full["mac_list"] = []
        respond_full["lldp_list"] = []
    else:
        t_device_list = T_thread(func=getDeviceList, args=(searchKeys,))
        t_gate_list = T_thread(func=getGateList, args=(searchKeys,))
        t_gatev6_list = T_thread(func=getGateIPv6List, args=(searchKeys,))
        t_sn_list = T_thread(func=getSNList, args=(searchKeys,))
        t_port_list = T_thread(func=getPortList, args=(searchKeys,))
        t_arp_list = T_thread(func=getARPlist, args=(searchKeys,))
        t_mac_list = T_thread(func=getMAClist, args=(searchKeys,))
        t_lldp_list = T_thread(func=getLLDPlist, args=(searchKeys,))

        t_device_list.start()
        t_gate_list.start()
        t_gatev6_list.start()
        t_sn_list.start()
        t_port_list.start()
        t_arp_list.start()
        t_mac_list.start()
        t_lldp_list.start()

        t_device_list.join()
        t_gate_list.join()
        t_gatev6_list.join()
        t_sn_list.join()
        t_port_list.join()
        t_arp_list.join()
        t_mac_list.join()
        t_lldp_list.join()

        respond_full["device_list"] = t_device_list.get_result()
        respond_full["gate_list"] = t_gate_list.get_result()
        respond_full["gatev6_list"] = t_gatev6_list.get_result()
        respond_full["sn_list"] = t_sn_list.get_result()
        respond_full["port_list"] = t_port_list.get_result()
        respond_full["arp_list"] = t_arp_list.get_result()
        respond_full["mac_list"] = t_mac_list.get_result()
        respond_full["lldp_list"] = t_lldp_list.get_result()

    return respond_full


def get_ex_portinfo(ip):
    db = CollectDB()
    gw_list = db.getfulltextDeviceGates({"ip": "^"+str(ip)+"$", "unlimit": "1", "and": "1"})
    gw_dict = {}
    if gw_list != "failed":
        for gw in gw_list:
            label = "{}_{}".format(gw["ip"], gw["port_id"])
            if label in gw_dict.keys():
                gw_dict[label].append("{}/{}".format(gw["gateway"], gw["mask"]))
            else:
                gw_dict[label] = []
                gw_dict[label].append("{}/{}".format(gw["gateway"], gw["mask"]))

    db = CollectDB()
    lldp_list = db.getLLDPs({"loc_ip": "^"+str(ip)+"$", })
    lldp_dict = {}
    if lldp_list != "failed":
        for lldp in lldp_list:
            label = "{}_{}".format(lldp["loc_ip"], lldp["loc_portname"])
            if label in lldp_dict.keys():
                lldp_dict[label].append("{}/{}".format(lldp["rem_ip"], lldp["rem_name"]))
            else:
                lldp_dict[label] = []
                lldp_dict[label].append("{}/{}".format(lldp["rem_ip"], lldp["rem_name"]))

    db = CollectDB()
    port_list = db.getPortInfo({"ip": "^" + str(ip) + "$"})
    respond = []
    if port_list!="failed":
        for port_info in port_list:
            gw_label = "{}_{}".format(port_info["ip"], port_info["port_id"])
            lldp_label = "{}_{}".format(port_info["ip"], port_info["if_name"])
            if gw_label in gw_dict.keys():
                port_info["gw_ips"] = "\n".join(gw_dict[gw_label])
            else:
                port_info["gw_ips"] = ""

            if lldp_label in lldp_dict.keys():
                port_info["lldp"] = "\n".join(lldp_dict[lldp_label])
            else:
                port_info["lldp"] = ""

            respond.append(port_info)
    else:
        return "failed"
    return respond


def get_deviceslist(search_data):
    db = CollectDB()
    device_list = db.getDeviceList(search_data)
    return device_list

def get_lldp_list(search_data):
    db = CollectDB()
    lldp_list = db.getLLDPs(search_data)
    return lldp_list


def getfulltextDeviceGates_v4(search_data):
    db = CollectDB()
    gateway_list = db.getfulltextDeviceGates(search_data)
    return gateway_list


def getfulltextDeviceGates_v6(search_data):
    db = CollectDB()
    gateway_list = db.getfulltextDeviceGatesIPv6(search_data)
    return gateway_list

def get_arp_list(search_data):
    db = CollectDB()
    arp_list = db.getARPList(search_data)
    return arp_list

def get_mac_table_by_tor(search_data):
    db = CollectDB()
    mac_table = db.getSwitchArpByDevIP(search_data)
    return mac_table

def get_device_sns(search_data):
    db = CollectDB()
    sns_list = db.getDeviceSNS(search_data)
    return sns_list