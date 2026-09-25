import json
import requests
from config.config import Config
from function_collector.func_search import func_fulltext, get_deviceslist, getfulltextDeviceGates_v4
import re

ip_reg = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

def location_device(search_key):
    """
    通过设备名、SN、IP等信息快速搜索设备
    返回设备列表、ARP列表、LLDP信息、mac地址表、接口地址表等相关信息
    :param search_key: 搜索关键字（可模糊匹配）
    :return:
    """
    try:
        # 直接调用内部方法，不通过 HTTP
        result = func_fulltext(searchKeys=search_key)

        # 返回 JSON 格式的结果
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        else:
            return json.dumps({
                "code": 0,
                "msg": "查询成功",
                "data": result
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "code": -1,
            "msg": "搜索失败: " + str(e),
            "data": []
        }, ensure_ascii=False)

def search_device_list(sysname, sysdesc_reg=None):
    try:
        # 直接调用内部方法，不通过 HTTP
        if sysdesc_reg:
            result = get_deviceslist({"sysname": sysname, "sysdesc_reg": sysdesc_reg})
        else:
            result = get_deviceslist({"sysname": sysname})

        # 返回 JSON 格式的结果
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        else:
            return json.dumps({
                "code": 0,
                "msg": "查询成功",
                "data": result
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "code": -1,
            "msg": "搜索失败: " + str(e),
            "data": []
        }, ensure_ascii=False)

def query_cloud_bill(cloud_provider, month, tag_key="24H 网络带宽", tag_value="24H 网络带宽", include_details=False):
    """
    查询云平台账单
    :param cloud_provider: 云平台标识 (tencent/volcano)
    :param month: 账单月份 yyyy-MM
    :param tag_key: 标签键（可选，用于筛选）
    :param tag_value: 标签值（可选，用于筛选）
    :param include_details: 是否包含明细账单（默认False，节省返回内容）
    :return: 格式化的文本报告
    """
    try:
        if cloud_provider.lower() == "tencent":
            from function_clouds.tencent_bill import analyze_tencent_bill, format_tencent_report
            result = analyze_tencent_bill(
                month=month,
                tag_key=tag_key if tag_key else "",
                tag_value=tag_value if tag_value else "",
                include_details=include_details
            )
            return format_tencent_report(result)
        elif cloud_provider.lower() == "volcano":
            from function_clouds.volcano_bill import analyze_volcano_bill, format_volcano_report
            result = analyze_volcano_bill(
                month=month,
                tag_key=tag_key or "",
                tag_value=tag_value or "",
                include_details=include_details
            )
            return format_volcano_report(result)
        else:
            return f"❌ 不支持的云平台: {cloud_provider}\n当前支持: tencent（腾讯云）, volcano（火山云）"
    except Exception as e:
        return f"❌ 查询云账单失败: {str(e)}"


def searchServer(search_ip):
    if ip_reg.match(search_ip):
        try:
            url_server = "http://api-o2.vdian.net/v1/" + "servers"
            params_server = {
                "access-token": Config.cmdb_access_token,
                "pageNumber": 1,
                "pageSize": 20,
                "ip": search_ip
            }
            result_server = requests.get(url=url_server, params=params_server)
            server_info = {"ip": search_ip}
            _info_server = result_server.json().get("data",{}).get("list",[])[0]
            server_info["hostname"] = _info_server.get("hostname")
            server_info["groupName"] = _info_server.get("groupName")
            _groupName = server_info["groupName"]

            url_group = "http://api-o2.vdian.net/v1/" + "groups"
            params_group = {
                "access-token": Config.cmdb_access_token,
                "pageNumber": 1,
                "pageSize": 20,
                "name": _groupName
            }
            result_group = requests.get(url=url_group, params=params_group)
            _info_group = result_group.json().get("data",{}).get("list",[])[0]
            server_info["productId"] = _info_group.get("productId")
            _product_id = server_info["productId"]

            url_product = "http://api-o2.vdian.net/v1/" + "products"
            params_product = {
                "access-token": Config.cmdb_access_token,
                "pageNumber": 1,
                "pageSize": 20,
                "showAppUser": True,
                "id": _product_id
            }
            result_product = requests.get(url=url_product, params=params_product)
            _info_product = result_product.json().get("data", {}).get("list", [])[0]
            server_info["prd_name"] = _info_product["name"]
            server_info["prd_desc"] = _info_product["description"]
            server_info["devUserList"] = ",".join([str(_i["cn"])for _i in _info_product["devUserList"][0:3]])
            return server_info
        except Exception as e:
            print(str(e))
            return ""
    else:
        return ""

def searchSwitch(search_ip):
    if ip_reg.match(search_ip):
        info = getfulltextDeviceGates_v4({"gatereg": "^{}$".format(search_ip)})
        return info
    else:
        return ""


def transIP(ip_text, search_type="switch"):
    """
    给文本里每一行的 IP 补上 CMDB 描述，格式：IP(描述)

    逐行处理，每行只取第一个匹配到的 IP，描述取不到时该行原样保留。

    :param ip_text: 原始文本，如 traceroute 输出
    :return: 处理后的文本
    """
    out_lines = []
    for line in ip_text.splitlines():
        match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", line)
        if not match:
            out_lines.append(line)
            continue

        desc = _ip_desc(match.group(), search_type)
        if not desc:
            out_lines.append(line)
            continue

        # 只在该行第一个 IP 后面插入描述，其余内容原样保留
        end = match.end()
        out_lines.append(line[:end] + "({})".format(desc) + line[end:])

    return "\n".join(out_lines)


def _ip_desc(search_ip, search_type="switch"):
    """查一个 IP 的描述：先按服务器查（产品描述 + 分组名），查不到再按交换机查。"""
    if search_type == "switch":
        switch_info = searchSwitch(search_ip=search_ip)
        if switch_info:
            switch_info = switch_info[0] if isinstance(switch_info, list) else switch_info
            return switch_info.get("sysname")
    else:
        server_info = searchServer(search_ip=search_ip)
        if isinstance(server_info, dict) and server_info:
            return server_info.get("prd_name") + "[{}]{}".format(server_info.get("devUserList"), server_info.get("prd_desc"))
    return ""


if __name__ == '__main__':
    pass
    # print(query_cloud_bill("tencent", "2026-09"))
    # 10.33.128.153
    # searchServer(search_ip="172.20.200.69")
    # searchSwitch(search_ip="172.20.200.69")
    # searchServer(search_ip="10.33.128.153")
    # aa = _ip_desc("10.33.128.153")
    # print(aa)
    # searchSwitch(search_ip="172.20.200.69")

  #   demo = """[出方向] 按源 IP Top 5
  # IP                              流量             字节数            包数     flows       占比
  # ---------------------------------------------------------------------------------
  # 10.35.195.143                4.1GB   4,426,040,000     2,850,000       285   14.29%
  # 10.35.5.223                  3.4GB   3,629,700,000     1,260,000       126   11.72%
  # 10.34.228.68                 3.2GB   3,424,890,000     1,170,000       117   11.06%
  # 10.33.146.126                3.0GB   3,207,160,000     1,940,000       194   10.35%
  # 10.33.18.23                  2.1GB   2,229,620,000       770,000        77    7.20%"""
  #
  #   print(transIP(demo, search_type="server"))
    ip_str='''
| 172.25.1.112  |     500 | 10:9F:4F:A2:72:38 |        11 | 2026-09-22 17:30:32 |                                                                                      
  | 172.25.1.6    |     500 | 10:9F:4F:A2:72:38 | 369098753 | 2026-09-22 17:30:33 |                                                                                      
  | 172.25.1.7    |     500 | 10:9F:4F:A2:72:38 | 369098753 | 2026-09-22 17:30:33 |                                                                                      
  | 172.25.250.16 |     500 | 10:9F:4F:A2:72:38 | 369098794 | 2026-09-22 17:30:33 |                                                                                      
  | 172.25.250.17 |     500 | 10:9F:4F:A2:72:38 | 369098794 | 2026-09-22 17:30:33 |
'''
    print(transIP(ip_str, search_type="switch"))



