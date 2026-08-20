from function_snmp.snmp_collector import common_identify_vendor
from function_ssh.sshClient import run_ssh_command
from tables.CollectDB import CollectDB
from config.config import Config

COMMON_COMMUNITY = Config.snmp_community


show_template = {
    "dis_cu_interface": {
        "h3c": "dis cu int {0}",
        "huawei": "dis cu int {0}",
        "cisco_nx": "show run int {0}",
        "cisco_ios": "show run int {0}",
        "cisco-xr": "show run int {0}",
        "ruijie": "show run int {0}",
        "arista": "show run int {0}"
    },
    "dis_interface": {
        "h3c": "dis int {0}",
        "huawei": "dis int {0}",
        "cisco_nx": "show int {0}",
        "cisco_ios": "show int {0}",
        "cisco-xr": "show int {0}",
        "ruijie": "show int {0}",
        "arista": "show int {0}"
    },
    "dis_cu": {
        "h3c": "dis cu",
        "huawei": "dis cu",
        "cisco_nx": "show run",
        "cisco_ios": "show run",
        "cisco-xr": "show run",
        "ruijie": "show run",
        "arista": "show run",
        "juniper": "show configuration |display set |no-more",
        "dell": "show run",
        "hillstone": "show config"
    },
    "dis_logg": {
        "h3c": "dis logbuffer reverse size {0}",
        "huawei": "dis logbuffer size {0}",
        "cisco_nx": "show logging last {0}",
        "cisco_ios": "show logging last {0}",
        "cisco-xr": "show logging last {0}",
        "ruijie": "show logging reverse",
        "arista": "show logging {0}",
    },
    "dis_vlans": {
        "h3c": "dis vlan brief",
        "huawei": "dis vlan",
        "cisco_nx": "show vlan brief",
        "cisco_ios": "show vlan brief",
        "cisco-xr": "show vlan brief",
        "ruijie": "show vlan",
        "arista": "show vlan brief",
    },
    "dis_arp": {
        # xx / vlan xx
        "h3c": "dis arp {}",
        # network xx/ interface vlanif xx
        "huawei": "dis arp {}",
        # xx / vlan xx
        "cisco_nx": "show ip arp {}",
        "cisco_ios": "show ip arp {}",
        "cisco-xr": "show arp {}",
        # xx / vlan xx
        "ruijie": "show arp {}",
        # xx / inter vlan xx
        "arista": "show arp {}",
    },
    "dis_transceiver": {
        "h3c": "dis transceiver diagnosis interface {}",
        "huawei_ce": "dis interface {} transceiver verbose",
        "huawei_s": "display transceiver diagnosis interface {}",
        "cisco_nx": "show inter {} transceiver details",
        "cisco_ios": "show inter {} transceiver details",
        "cisco-xr": "show controllers {} phy",
        "ruijie": "show interface {} transceiver",
        "arista": "show inter {} transceiver detail"
    },
    "dis_routes": {
        "h3c": "dis ip routing-table {}",
        "huawei": "dis ip routing-table {}",
        "cisco_nx": "show ip route {}",
        "cisco_ios": "show ip route {}",
        "cisco-xr": "show ip route {}",
        "ruijie": "show ip route {}",
        "arista": "show ip route {}",
    },

    "dis_inventory": {
        "h3c": "dis device manuinfo",
        "huawei": "dis device manufacture-info",
        "cisco_nx": "show inventory",
        "cisco_ios": "show inventory",
        "cisco-xr": "admin show inventory",
        "ruijie": "show manuinfo",
        "arista": "show inventory",
    },
    "dis_fan": {
        "h3c": "dis fan",
        "huawei": "dis device fan",
        "cisco_nx": "show environment fan detail",
        "cisco_ios": "show environment fan detail",
        "cisco-xr": "admin show environment fan",
        "ruijie": "show fan",
        "arista": "show system environment cooling",
    },
    "dis_power": {
        "h3c": "dis power",
        "huawei": "dis device power",
        "cisco_nx": "show environment power detail",
        "cisco_ios": "show environment power detail",
        "cisco-xr": "admin show environment power",
        "ruijie": "show power",
        "arista": "show environment power",
    },
    "dis_board": {
        "h3c": "dis device",
        "huawei": "dis device board",
        "cisco_nx": "show module",
        "cisco_ios": "show module",
        "cisco-xr": "admin show platform",
        "ruijie": "show power",
        "arista": "show module",
    },
    "dis_link_aggr": {
        "h3c": "dis link-aggregation verbose",
        "huawei": "dis eth-trunk",
        "cisco_nx": "show port-channel summary",
        "cisco_ios": "show port-channel summary",
        "cisco-xr": "show bundle",
        "arista": "show port-channel detailed",
    },
    "dis_bgp_peer_v4": {
        "h3c": "dis bgp peer ipv4 ",
        "huawei": "dis bgp peer",
        "cisco_nx": "show bgp ipv4 unicast summary",
        "cisco_ios": "show bgp ipv4 unicast summary",
        "cisco-xr": "show bgp summary",
        "arista": "show ip bgp summary",
        "ruijie": "show bgp ipv4 unicast summary",
    },
    "dis_cpu": {
        "cisco_nx": "show processes cpu | i util",
        "cisco_ios": "show processes cpu | i util",
        "cisco-xr": "admin show cpu | i Utilization",
        "h3c": "dis cpu-usage ",
        "huawei": "dis cpu",
        "arista": "show processes top once| i %Cpu",
        "ruijie": "show cpu | i utilization",
    },
    "dis_mem": {
        "cisco_nx": "show processes memory shared",
        "cisco_ios": "show processes memory shared",
        "cisco-xr": "admin show memory summary",
        "h3c": "dis memory",
        "huawei": "dis memory",
        "arista": "show processes top once |i Mem",
        "ruijie": "show memory | i Memory",
    },

}



def common_function(dev_type, func):
    if func in show_template.keys():
        config = show_template[func]
        if dev_type in config.keys():
            return True, config[dev_type]
        else:
            return False, "no dev_type"

    else:
        return False, "no function"

def get_result_by_template(ip, temp_name):
    dev_type = common_identify_vendor(ip, community=COMMON_COMMUNITY)
    isflag, cmd = common_function(dev_type, temp_name)
    if isflag:
        cmds = [cmd]
        respond = run_ssh_command(host=ip, commands=cmds, vendor=dev_type)
        # {"status": "failed", "msg": "命令列表不正确", "data": {}}
        if respond["status"]=="success":
            return "\n".join(respond["data"].values())
        else:
            return "执行失败"
    else:
        return "未适配设备"


# 查端口配置
def get_config_interface(ip, if_name):
    dev_type = common_identify_vendor(ip, community=COMMON_COMMUNITY)
    isflag, cmd = common_function(dev_type, "dis_cu_interface")
    if isflag:
        if_name = if_name.replace("\n", "")
        final_cmd = cmd.format(if_name)
        cmds = [final_cmd]
        respond = run_ssh_command(host=ip, commands=cmds, vendor=dev_type)
        # {"status": "failed", "msg": "命令列表不正确", "data": {}}
        if respond["status"] == "success":
            return "\n".join(respond["data"].values())
        else:
            return "执行失败"
    else:
        return "未适配设备"

# 查询接口状态
def get_interface(ip, if_name):
    dev_type = common_identify_vendor(ip, community=COMMON_COMMUNITY)
    isflag, cmd = common_function(dev_type, "dis_interface")
    if isflag:
        final_cmd = cmd.format(if_name.replace("\n", ""))
        cmds = [final_cmd]
        respond = run_ssh_command(host=ip, commands=cmds, vendor=dev_type)
        # {"status": "failed", "msg": "命令列表不正确", "data": {}}
        if respond["status"] == "success":
            return "\n".join(respond["data"].values())
        else:
            return "执行失败"
    else:
        return "未适配设备"

# 查日志信息
def get_logging(ip, size=200):
    dev_type = common_identify_vendor(ip, community=COMMON_COMMUNITY)
    isflag, cmd = common_function(dev_type, "dis_logg")
    if isflag:
        final_cmd = cmd.format(int(size))
        cmds = [final_cmd]
        respond = run_ssh_command(host=ip, commands=cmds, vendor=dev_type)
        # {"status": "failed", "msg": "命令列表不正确", "data": {}}
        if respond["status"] == "success":
            return "\n".join(respond["data"].values())
        else:
            return "执行失败"
    else:
        return "未适配设备"


# 查询arp详情
def get_arp_brief(ip, vlan_id=None, arp_ip=None):
    dev_type = common_identify_vendor(ip, community=COMMON_COMMUNITY)
    isflag, cmd = common_function(dev_type, "dis_arp")
    if isflag:
        if dev_type in ["h3c", "cisco_nx", "cisco_ios", "cisco-xr", "ruijie"]:
            if arp_ip is not None:
                final_cmd = cmd.format(str(arp_ip).replace("\n", ""))
            elif vlan_id is not None:
                final_cmd = cmd.format(" vlan "+str(int(vlan_id)))
            else:
                final_cmd = cmd.format("")
        elif dev_type in ["huawei"]:
            if arp_ip is not None:
                final_cmd = cmd.format(" network "+str(arp_ip).replace("\n", ""))
            elif vlan_id is not None:
                final_cmd = cmd.format(" interface vlanif "+str(int(vlan_id)))
            else:
                final_cmd = cmd.format("")
        elif dev_type in ["arista"]:
            if arp_ip is not None:
                final_cmd = cmd.format(str(arp_ip).replace("\n", ""))
            elif vlan_id is not None:
                final_cmd = cmd.format(" inter vlan "+str(int(vlan_id)))
            else:
                final_cmd = cmd.format("")
        else:
            final_cmd = cmd.format("")
        cmds = [final_cmd]
        respond = run_ssh_command(host=ip, commands=cmds, vendor=dev_type)
        # {"status": "failed", "msg": "命令列表不正确", "data": {}}
        if respond["status"] == "success":
            return "\n".join(respond["data"].values())
        else:
            return "执行失败"
    else:
        return "未适配设备"

# 查询收发光
def get_transceiver(ip, if_name):
    dev_type = common_identify_vendor(ip, community=COMMON_COMMUNITY)
    db = CollectDB()
    dev_list = db.getDeviceList({"host": ip})
    if len(dev_list) > 0:
        dev_version = dev_list[0]
    else:
        return "未适配设备"
    if dev_type in ["huawei"]:
        if "CE" in dev_version["hardware"] or "FM" in dev_version["hardware"]:
            isflag, cmd = common_function("huawei_ce", "dis_transceiver")
        else:
            isflag, cmd = common_function("huawei_s", "dis_transceiver")
    else:
        isflag, cmd = common_function(dev_type, "dis_transceiver")

    if isflag:
        final_cmd = cmd.format(if_name.replace("\n", ""))
        cmds = [final_cmd]
        respond = run_ssh_command(host=ip, commands=cmds, vendor=dev_type)
        # {"status": "failed", "msg": "命令列表不正确", "data": {}}
        if respond["status"] == "success":
            return "\n".join(respond["data"].values())
        else:
            return "执行失败"
    else:
        return "未适配设备"

# 查询路由
def get_routes(ip, route):
    dev_type = common_identify_vendor(ip, community=COMMON_COMMUNITY)
    isflag, cmd = common_function(dev_type, "dis_routes")
    if isflag:
        final_cmd = cmd.format(route.replace("\n", ""))
        cmds = [final_cmd]
        respond = run_ssh_command(host=ip, commands=cmds, vendor=dev_type)
        # {"status": "failed", "msg": "命令列表不正确", "data": {}}
        if respond["status"] == "success":
            return "\n".join(respond["data"].values())
        else:
            return "执行失败"
    else:
        return "未适配设备"

def exec_diy_cmds(ip, cmds):
    dev_type = common_identify_vendor(ip, community=COMMON_COMMUNITY)

    filtered_cmds = []
    cmd_str = str(cmds).strip()
    if cmd_str.lower().strip().startswith('dis') or cmd_str.lower().strip().startswith('sh'):
        filtered_cmds.append(cmd_str)
    else:
        return f"安全策略限制：只允许执行display开头的命令，当前命令 '{cmd_str}' 被拒绝"

    respond = run_ssh_command(host=ip, commands=filtered_cmds, vendor=dev_type)
    # {"status": "failed", "msg": "命令列表不正确", "data": {}}
    if respond["status"] == "success":
        return "\n".join(respond["data"].values())
    else:
        return "执行失败"


if __name__ == '__main__':
    res = exec_diy_cmds("59.111.252.124", "display chassis hardware detail")
    print(res)