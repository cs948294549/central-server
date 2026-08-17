import re

from function_snmp.snmp_collector import common_identify_vendor
from function_ssh.sshClient import run_ssh_command
from config import Config

COMMON_COMMUNITY = Config.snmp_community


show_template = {
    "dis_cu_interface": {
        "h3c": "dis cu int {0}",
        "huawei": "dis cu int {0}",
        "cisco": "show run int {0}",
        "cisco-xr": "show run int {0}",
        "ruijie": "show run int {0}",
        "arista": "show run int {0}"
    },
    "dis_interface": {
        "h3c": "dis int {0}",
        "huawei": "dis int {0}",
        "cisco": "show int {0}",
        "cisco-xr": "show int {0}",
        "ruijie": "show int {0}",
        "arista": "show int {0}"
    },
    "dis_cu": {
        "h3c": "dis cu",
        "huawei": "dis cu",
        "cisco": "show run",
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
        "cisco": "show logging last {0}",
        "cisco-xr": "show logging last {0}",
        "ruijie": "show logging reverse",
        "arista": "show logging {0}",
    },
    "dis_vlans": {
        "h3c": "dis vlan brief",
        "huawei": "dis vlan",
        "cisco": "show vlan brief",
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
        "cisco": "show ip arp {}",
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
        "cisco": "show inter {} transceiver details",
        "cisco-xr": "show controllers {} phy",
        "ruijie": "show interface {} transceiver",
        "arista": "show inter {} transceiver detail"
    },
    "dis_routes": {
        "h3c": "dis ip routing-table {}",
        "huawei": "dis ip routing-table {}",
        "cisco": "show ip route {}",
        "cisco-xr": "show ip route {}",
        "ruijie": "show ip route {}",
        "arista": "show ip route {}",
    },

    "dis_inventory": {
        "h3c": "dis device manuinfo",
        "huawei": "dis device manufacture-info",
        "cisco": "show inventory",
        "cisco-xr": "admin show inventory",
        "ruijie": "show manuinfo",
        "arista": "show inventory",
    },
    "dis_fan": {
        "h3c": "dis fan",
        "huawei": "dis device fan",
        "cisco": "show environment fan detail",
        "cisco-xr": "admin show environment fan",
        "ruijie": "show fan",
        "arista": "show system environment cooling",
    },
    "dis_power": {
        "h3c": "dis power",
        "huawei": "dis device power",
        "cisco": "show environment power detail",
        "cisco-xr": "admin show environment power",
        "ruijie": "show power",
        "arista": "show environment power",
    },
    "dis_board": {
        "h3c": "dis device",
        "huawei": "dis device board",
        "cisco": "show module",
        "cisco-xr": "admin show platform",
        "ruijie": "show power",
        "arista": "show module",
    },
    "dis_link_aggr": {
        "h3c": "dis link-aggregation verbose",
        "huawei": "dis eth-trunk",
        "cisco": "show port-channel summary",
        "cisco-xr": "show bundle",
        "arista": "show port-channel detailed",
    },
    "dis_bgp_peer_v4": {
        "h3c": "dis bgp peer ipv4 ",
        "huawei": "dis bgp peer",
        "cisco": "show bgp ipv4 unicast summary",
        "cisco-xr": "show bgp summary",
        "arista": "show ip bgp summary",
        "ruijie": "show bgp ipv4 unicast summary",
    },
    "dis_cpu": {
        "cisco": "show processes cpu | i util",
        "cisco-xr": "admin show cpu | i Utilization",
        "h3c": "dis cpu-usage ",
        "huawei": "dis cpu",
        "arista": "show processes top once| i %Cpu",
        "ruijie": "show cpu | i utilization",
    },
    "dis_mem": {
        "cisco": "show processes memory shared",
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
        if respond != "failed":
            return "\n".join(respond.values())
        else:
            return "failed"
    else:
        return "unknown"



# 查端口配置
def get_config_interface(ip, if_name):
    dev_type = common_identify_vendor(ip)
    isflag, cmd = common_function(dev_type, "dis_cu_interface")
    if isflag:
        if_name = if_name.replace("\n", "")
        final_cmd = cmd.format(if_name)
        cmds = [final_cmd]
        respond = run_ssh_command(host=ip, commands=cmds, vendor=dev_type)
        if respond != "failed":
            return "\n".join(respond.values())
        else:
            return "failed"
    else:
        return "unknown"

# 查全部配置
# def get_config_cu(ip):
#     dev_type = getDeviceType(ip)
#     isflag, cmd = common_function(dev_type, "dis_cu")
#     if isflag:
#         cmds = [cmd]
#         respond = run_cmd({"ip": ip, "dev_type": dev_type, "cmds": cmds})
#         if respond != "failed":
#             return "\n".join(respond.values())
#         else:
#             return "failed"
#     else:
#         return "unknown"

# 查日志信息
def get_logging(ip, size=200):
    dev_type = getDeviceType(ip)
    isflag, cmd = common_function(dev_type, "dis_logg")
    if isflag:
        final_cmd = cmd.format(int(size))
        cmds = [final_cmd]
        respond = run_cmd({"ip": ip, "dev_type": dev_type, "cmds": cmds})
        if respond != "failed":
            return "\n".join(respond.values())
        else:
            return "failed"
    else:
        return "unknown"


if __name__ == '__main__':
    res = exec_diy_cmds("59.111.252.124", "display chassis hardware detail")
    print(res)