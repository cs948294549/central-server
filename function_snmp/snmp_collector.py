"""
SNMP请求封装模块

提供统一的SNMP请求接口，简化SNMP操作的调用方式
"""
import logging
from function_snmp.snmpAgent import snmpget, snmpwalk

logger = logging.getLogger(__name__)

# 厂商标识符映射，用于自动识别厂商
VENDOR_IDENTIFIERS = {
    'cisco_xr': ['ios xr'],
    'cisco_ios': ['ios'],
    'cisco_nx': ['nx-os', 'nxos', 'cisco', 'catos'],
    'huawei': ['huawei', 'vrp', 'quidway', 'huarong', 'futurematrix'],
    'h3c': ['h3c', '3com', 'hp'],
    'juniper': ['juniper', 'junos'],
    'arista': ['arista', 'eos']
}

def identify_device_vendor(sys_descr: str) -> str:
    """
    根据系统描述自动识别设备厂商

    Args:
        sys_descr: 系统描述字符串

    Returns:
        str: 识别出的厂商名称，默认为'unknown'
    """
    sys_descr_lower = sys_descr.lower() if sys_descr else ''

    for vendor, identifiers in VENDOR_IDENTIFIERS.items():
        for identifier in identifiers:
            if identifier.lower() in sys_descr_lower:
                return vendor

    return 'unknown'

def common_identify_vendor(ip: str, community: str):
    sys_descr = snmpget(ip, community, "1.3.6.1.2.1.1.1.0")
    if not sys_descr:
        logger.warning("设备{} 采集设备描述失败".format(ip))
        return None
    else:
        vendor = identify_device_vendor(sys_descr)
        return vendor

if __name__ == '__main__':
    import time
    a = snmpwalk("192.168.110.153", "public", "1.3.6.1.2.1.4.22.1.2")
    print(a)