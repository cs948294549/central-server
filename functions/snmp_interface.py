import requests
import json
from config.config import secret, gate_url
import re

def run_snmp_get(runconfig):
    url = gate_url + "fast_snmpget?ip={}".format(runconfig["ip"])
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "ip": runconfig["ip"],
        "oid": runconfig["oid"],
        "coding": runconfig["coding"]
    }
    if "community" in runconfig.keys():
        body["community"] = runconfig["community"]
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=180)
    except Exception as e:
        print("请求失败", e, runconfig)
        return "failed"
    try:
        return json.loads(r.text)
    except:
        print("解析失败", r.text)
        return "failed"

def run_snmp_walk(runconfig):
    url = gate_url + "fast_snmpwalk?ip={}".format(runconfig["ip"])
    headers = {
        "key": "testsd",
        "secret": secret
    }
    body = {
        "ip": runconfig["ip"],
        "oid": runconfig["oid"],
        "coding": runconfig["coding"]
    }
    if "community" in runconfig.keys():
        body["community"] = runconfig["community"]
    try:
        r = requests.post(url=url, headers=headers, json=body, timeout=30)
    except Exception as e:
        print("请求失败", e, runconfig)
        return "failed"
    try:
        return json.loads(r.text)
    except:
        print("解析失败", r.text)
        return "failed"


def getsysname(ip):
    sysname = run_snmp_get({"ip": ip, "oid": "1.3.6.1.2.1.1.5.0", "coding": "utf-8"})
    return sysname

def getassert(ip):
    devassert = run_snmp_get({"ip": ip, "oid": "1.3.6.1.2.1.1.6.0", "coding": "utf-8"})
    return devassert

def getDeviceType(ip):
    try:
        sysdesc = run_snmp_get({"ip": ip, "oid": "1.3.6.1.2.1.1.1.0", "coding": "utf-8"})
        check_desc = sysdesc.upper()
        if "H3C" in check_desc or "HPE" in check_desc:
            return 'h3c'
        elif "HUAWEI" in check_desc or "HUARONG" in check_desc or 'FUTUREMATRIX' in check_desc:
            return 'huawei'
        elif "CISCO" in check_desc:
            if "IOS XR" in check_desc:
                return "cisco-xr"
            else:
                return "cisco"
        elif "ARISTA" in check_desc:
            return "arista"
        elif "RUIJIE" in check_desc:
            return "ruijie"
        elif "DELL" in check_desc:
            return "dell"
        elif "JUNIPER" in check_desc:
            return "juniper"
        if "HILLSTONE" in check_desc:
            return "hillstone"
        else:
            return "unknown"
    except Exception as e:
        print("snmp型号判断异常", e)
        return "unknown"

def getPortStatus(ip, port_id):
    status = run_snmp_get({"ip": ip, "oid": "1.3.6.1.2.1.2.2.1.8.{}".format(port_id), "coding": "utf-8"})
    if status == "1":
        return True
    else:
        return False


def getVersion(ip):
    '''
    华为
        版本
        1.3.6.1.4.1.2011.5.25.19.1.4.2.1.5
        补丁
        1.3.6.1.4.1.2011.5.25.19.1.8.5.1.1.4
    华三
        1.3.6.1.4.1.25506.2.3.1.7.2.1.5=4时为补丁
        补丁
        1.3.6.1.4.1.25506.2.3.1.7.2.1.10
    :param ip:
    :return:
    '''
    try:
        print("处理ip===", ip)
        sysname = getsysname(ip=ip)
        dev_assert = getassert(ip=ip)
        dev_type = getDeviceType(ip=ip)
        if dev_type == "huawei":
            patch_array = run_snmp_walk({
                "ip": ip,
                "oid": "1.3.6.1.4.1.2011.5.25.19.1.8.5.1.1.4",
                "coding": "utf-8",
            })
            patch = list(patch_array.values())[0]
            if patch.strip() == "None":
                patch = ""

            sys_desc = run_snmp_get({
                "ip": ip,
                "oid": "1.3.6.1.2.1.1.1.0",
                "coding": "utf-8",
            })

            reg_patch = re.compile(r'Version\s+(?:\S+)\s+\(?([^)]+)\)?')
            reg_model = re.compile(r'(?:(?:HUAWEI)|(?:Huarong)|(?:FUTUREMATRIX))\s*((?:\S+-)+\S+)', re.I)
            desc_array = sys_desc.strip().split("\n")
            if "\n" in sys_desc:
                hardware = desc_array[0].strip()
                if "HUAWEI" in hardware.upper() or "HUARONG" in hardware.upper() or "FUTUREMATRIX" in hardware.upper():
                    hardware = ""
            else:
                hardware = ""
            version_array = reg_patch.findall(sys_desc)
            version = ""
            # 优先寻找 version中的设备型号
            if len(version_array) > 0:
                version_str = version_array[0]
                version = version_str.split()[1]
                if version_str.split()[0].upper() not in hardware.upper():
                    mode_array = reg_model.findall(sys_desc)
                    if len(mode_array) > 0:
                        hardware = mode_array[0]
                    else:
                        hardware = version_str.split()[0]
            # hardware = hardware.replace("-48S4Q-", "").strip()
            return {"ip": ip, "sysname": sysname, "dev_type": dev_type, "hardware": hardware, "version": version, "patches": patch, "assert": dev_assert}
        elif dev_type == "h3c":
            sys_desc = run_snmp_get({
                "ip": ip,
                "oid": "1.3.6.1.2.1.1.1.0",
                "coding": "utf-8",
            })

            phy_type = run_snmp_walk({
                "ip": ip,
                "oid": "1.3.6.1.2.1.47.1.1.1.1.5",
                "coding": "utf-8",
            })

            pids = []
            for oid, value in phy_type.items():

                if value == "3":
                    pids.append(oid.split(".")[-1])
                elif value == "9":
                    pids.append(oid.split(".")[-1])

            hardware = ""
            x_oid = ""

            for oid in pids:
                hardware_str = run_snmp_get({
                    "ip": ip,
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.13.{}".format(oid),
                    "coding": "utf-8"
                })
                if hardware_str.strip() != "":
                    hardware = hardware_str.strip()
                    x_oid = oid
                    break

            version = run_snmp_get({
                "ip": ip,
                "oid": "1.3.6.1.2.1.47.1.1.1.1.10.{}".format(x_oid),
                "coding": "utf-8"
            })

            # 预处理，去除厂商标记
            hardware = hardware.replace("H3C", "").replace("HPE", "").strip()
            # 仅保留版本号di
            re_versions = re.compile(r'.*(Release.*)')
            re_features = re.compile(r'.*(Feature.*)')
            if "Release" not in version:
                if "Feature" in version:
                    version = re_features.findall(version)[0].strip().replace("Feature", "Release")
                else:
                    version = re_versions.findall(sys_desc)[0].strip()
            else:
                version = re_versions.findall(version)[0].strip()

            patch_name = ""
            patch_type = run_snmp_walk({
                "ip": ip,
                "oid": "1.3.6.1.4.1.25506.2.3.1.7.2.1.5",
                "coding": "utf-8",
            })
            patch_pids = []
            for key, value in patch_type.items():
                if value == "4":
                    patch_pids.append(key.split(".")[-1])
            patch_names = []
            for pid in patch_pids:
                patch_status = run_snmp_get({
                    "ip": ip,
                    "oid": "1.3.6.1.4.1.25506.2.3.1.7.2.1.7.{}".format(pid),
                    "coding": "utf-8"
                })
                if patch_status == "1":
                    patch_name = run_snmp_get({
                        "ip": ip,
                        "oid": "1.3.6.1.4.1.25506.2.3.1.7.2.1.2.{}".format(pid),
                        "coding": "utf-8"
                    })
                    patch_name = patch_name.upper()
                    patch_names.append(patch_name)
                    # break
            reg_patch = re.compile(r'-?([^-]+)\.BIN')
            if len(patch_names) > 0:
                reg_data = reg_patch.findall(patch_names[-1])
                if len(reg_data) > 0:
                    print("all_patch==", reg_data)
                    patch = reg_data[0]
                else:
                    patch = ""
            else:
                patch = ""

            return {"ip": ip, "sysname": sysname, "dev_type": dev_type, "hardware": hardware, "version": version, "patches": patch, "assert": dev_assert}

        elif dev_type == "dell":
            sys_desc = run_snmp_get({
                "ip": ip,
                "oid": "1.3.6.1.2.1.1.1.0",
                "coding": "utf-8",
            })
            re_version = re.compile(r'Software\s+Version:\s+(\S+)')
            version = re_version.findall(sys_desc)[0]
            hardware = "Force10"
            return {"ip": ip, "sysname": sysname, "dev_type": dev_type, "hardware": hardware, "version": version,
                    "patches": "", "assert": dev_assert}

        elif dev_type == "hillstone":
            sys_desc = run_snmp_get({
                "ip": ip,
                "oid": "1.3.6.1.2.1.1.1.0",
                "coding": "utf-8",
            })
            re_hardware = re.compile(r'Hillstone.*\s+((?:[A-Z0-9]+-)+(?:[A-Z0-9]+))')
            hardware = re_hardware.findall(sys_desc)[0]
            sys_version = run_snmp_get({
                "ip": ip,
                "oid": "1.3.6.1.4.1.28557.2.2.1.2.0",
                "coding": "utf-8",
            })
            re_version = re.compile(r'Version\s+\S+\s+(\S+)')
            version = re_version.findall(sys_version)[0]
            return {"ip": ip, "sysname": sysname, "dev_type": dev_type, "hardware": hardware, "version": version,
                    "patches": "", "assert": dev_assert}

        elif dev_type == "cisco-xr":
            sys_desc = run_snmp_get({
                "ip": ip,
                "oid": "1.3.6.1.2.1.1.1.0",
                "coding": "utf-8",
            })
            re_version = re.compile(r'Version\s+([\d\.]+)')
            version = re_version.findall(sys_desc)[0]

            re_hardware = re.compile(r'Cisco\s+IOS\s+XR\s+Software\s+\(([^)]+)\)')
            hardware = re_hardware.findall(sys_desc)[0]

            return {"ip": ip, "sysname": sysname, "dev_type": dev_type, "hardware": hardware, "version": version,
                    "patches": "", "assert": dev_assert}
        elif "cisco" in dev_type:
            print("处理其他==", ip)
            phy_type = run_snmp_walk({
                "ip": ip,
                "oid": "1.3.6.1.2.1.47.1.1.1.1.5",
                "coding": "utf-8",
            })

            oid_11 = []
            oid_3 = []
            oid_9 = []
            for oid, value in phy_type.items():
                if value is not None:
                    type_str = value.strip()
                    if type_str == "11":
                        oid_11.append(oid.split(".")[-1])
                    elif type_str == "3":
                        oid_3.append(oid.split(".")[-1])
                    elif type_str == "9":
                        oid_9.append(oid.split(".")[-1])
                    else:
                        continue
            # 获取型号
            # 优先处理11
            hardware = ""
            for x_oid in oid_11:
                hardware_str = run_snmp_get({
                    "ip": ip,
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.13.{}".format(x_oid),
                    "coding": "utf-8"
                })
                if hardware_str.strip() != "" and hardware_str.strip() != "N/A":
                    hardware = hardware_str.strip()
                    break
            if hardware.strip() == "":
                for x_oid in oid_3:
                    hardware_str = run_snmp_get({
                        "ip": ip,
                        "oid": "1.3.6.1.2.1.47.1.1.1.1.13.{}".format(x_oid),
                        "coding": "utf-8"
                    })
                    if hardware_str.strip() != "" and hardware_str.strip() != "N/A":
                        hardware = hardware_str.strip()
                        break

            if hardware.strip() == "":
                for x_oid in oid_9:
                    hardware_str = run_snmp_get({
                        "ip": ip,
                        "oid": "1.3.6.1.2.1.47.1.1.1.1.13.{}".format(x_oid),
                        "coding": "utf-8"
                    })
                    if hardware_str.strip() != "" and hardware_str.strip() != "N/A":
                        hardware = hardware_str.strip()
                        break

            version = ""
            for x_oid in oid_11:
                version_str = run_snmp_get({
                    "ip": ip,
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.10.{}".format(x_oid),
                    "coding": "utf-8"
                })
                if version_str.strip() != "":
                    version = version_str.strip()
                    break
            if version.strip() == "":
                for x_oid in oid_3:
                    version_str = run_snmp_get({
                        "ip": ip,
                        "oid": "1.3.6.1.2.1.47.1.1.1.1.10.{}".format(x_oid),
                        "coding": "utf-8"
                    })
                    if version_str.strip() != "":
                        version = version_str.strip()
                        break

            if version.strip() == "":
                for x_oid in oid_9:
                    version_str = run_snmp_get({
                        "ip": ip,
                        "oid": "1.3.6.1.2.1.47.1.1.1.1.10.{}".format(x_oid),
                        "coding": "utf-8"
                    })
                    if version_str.strip() != "":
                        version = version_str.strip()
                        break

            # 预处理，去除厂商标记
            hardware = hardware.replace("Chassis", "").strip()

            return {"ip": ip, "sysname": sysname, "dev_type": dev_type, "hardware": hardware, "version": version,
                    "patches": "", "assert": dev_assert}
        elif "juniper" in dev_type:
            phy_type = run_snmp_walk({
                "ip": ip,
                "oid": "1.3.6.1.2.1.47.1.1.1.1.5",
                "coding": "utf-8",
            })

            pids = []
            for oid, value in phy_type.items():
                if value == "3":
                    pids.append(oid.split(".")[-1])
                elif value == "9":
                    pids.append(oid.split(".")[-1])

            hardware = ""
            x_oid = ""
            if hardware.strip() == "":
                for oid in pids:
                    hardware_str = run_snmp_get({
                        "ip": ip,
                        "oid": "1.3.6.1.2.1.47.1.1.1.1.7.{}".format(oid),
                        "coding": "utf-8"
                    })
                    if hardware_str.strip() != "" and hardware_str.strip() != "N/A":
                        hardware = hardware_str.strip()
                        x_oid = oid
                        break
            hardware = "MX960"
            version = run_snmp_get({
                "ip": ip,
                "oid": "1.3.6.1.2.1.47.1.1.1.1.10.{}".format(x_oid),
                "coding": "utf-8"
            })
            if version.strip() == "":
                for oid in pids:
                    version_str = run_snmp_get({
                        "ip": ip,
                        "oid": "1.3.6.1.2.1.47.1.1.1.1.10.{}".format(oid),
                        "coding": "utf-8"
                    })
                    if version_str.strip() != "":
                        version = version_str.strip()
                        break
            # 预处理，去除厂商标记
            hardware = hardware.replace("Chassis", "").strip()

            return {"ip": ip, "sysname": sysname, "dev_type": dev_type, "hardware": hardware, "version": version, "patches": "", "assert": dev_assert}
        else:
            print("处理其他==", ip)
            phy_type = run_snmp_walk({
                "ip": ip,
                "oid": "1.3.6.1.2.1.47.1.1.1.1.5",
                "coding": "utf-8",
            })

            pids = []
            for oid, value in phy_type.items():
                if value == "3":
                    pids.append(oid.split(".")[-1])
                elif value == "9":
                    pids.append(oid.split(".")[-1])

            hardware = ""
            x_oid = ""
            for oid in pids:
                hardware_str = run_snmp_get({
                    "ip": ip,
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.13.{}".format(oid),
                    "coding": "utf-8"
                })
                if hardware_str.strip() != "" and hardware_str.strip() != "N/A":
                    hardware = hardware_str.strip()
                    x_oid = oid
                    break

            if hardware.strip() == "":
                for oid in pids:
                    hardware_str = run_snmp_get({
                        "ip": ip,
                        "oid": "1.3.6.1.2.1.47.1.1.1.1.7.{}".format(oid),
                        "coding": "utf-8"
                    })
                    if hardware_str.strip() != "" and hardware_str.strip() != "N/A":
                        hardware = hardware_str.strip()
                        x_oid = oid
                        break
            version = run_snmp_get({
                "ip": ip,
                "oid": "1.3.6.1.2.1.47.1.1.1.1.10.{}".format(x_oid),
                "coding": "utf-8"
            })
            if version.strip() == "":
                for oid in pids:
                    version_str = run_snmp_get({
                        "ip": ip,
                        "oid": "1.3.6.1.2.1.47.1.1.1.1.10.{}".format(oid),
                        "coding": "utf-8"
                    })
                    if version_str.strip() != "":
                        version = version_str.strip()
                        break
            # 预处理，去除厂商标记
            hardware = hardware.replace("Chassis", "").strip()

            return {"ip": ip, "sysname": sysname, "dev_type": dev_type, "hardware": hardware, "version": version, "patches": "", "assert": dev_assert}
    except Exception as e:
        print("异常===", e)
        return "unknown"

if __name__ == '__main__':
    # import time
    # ip = "10.60.209.33"
    # arp_ip = "117.135.207.165"
    # while True:
    #     status = run_snmp_get({"ip": ip, "oid": "1.3.6.1.2.1.4.22.1.2.2180.{}".format(arp_ip), "coding": "utf-9"})
    #     print(status)
    #     time.sleep(1)
    #
    # aa = getVersion(ip="10.162.0.14")
    # print(aa)

    with open("../h3c_ips.txt", "r") as f:
        ips = f.readlines()
    ips = [x.strip() for x in ips]
    for ip in ips[:10]:
        ver = getVersion(ip=ip)
        print(ver)