from tables.IpamDB import IpamDB
from utils.utils import decorator_checkparams
from utils.ipaddr import ip2decimalism, getstartend, length2netmask
import logging

logger = logging.getLogger(__name__)

# ==================== 网络地址管理 ====================

@decorator_checkparams(key_array=["ip", "mask", "status", "location", "isp", "role", "label", "comment", "manage_user"])
def add_network_address(data):
    """添加网络地址"""
    db = IpamDB()
    result = db.add_network_item(data)
    return result


@decorator_checkparams(key_array=["ip", "mask"])
def update_network_address(data):
    """更新网络地址"""
    db = IpamDB()
    result = db.update_network_item(data)
    return result


@decorator_checkparams(key_array=["ip", "mask"])
def delete_network_address(data):
    """删除网络地址"""
    db = IpamDB()
    result = db.delete_network_item(data)
    return result


@decorator_checkparams(key_array=[])
def get_network_address_list(data):
    """查询网络地址列表"""
    db = IpamDB()
    result = db.get_network_list(data)
    return result


@decorator_checkparams(key_array=[])
def get_network_address_tree(data):
    """获取网络地址树形结构"""
    db = IpamDB()
    result = db.get_network_list(data)

    if result == "failed":
        return "failed"

    # 一次性查询所有已使用的IP地址
    db_ipaddr = IpamDB()
    all_used_ips = db_ipaddr.get_ipaddr_list({})

    # 将IP地址转换为集合，方便快速查找
    used_ip_set = set()
    if all_used_ips != "failed" and isinstance(all_used_ips, list):
        used_ip_set = set(int(ip["ip_deci"]) for ip in all_used_ips if ip.get("ip_deci"))

    logger.info(f"共查询到 {len(used_ip_set)} 个已使用的IP地址")

    # 构建树形结构
    tree_data = sorted(result, key=lambda x: (ip2decimalism(x["ip"]), int(x["mask"])))

    tree = []
    for item in tree_data:
        new_item = item.copy()
        new_item["id"] = item["ip"] + "_" + item["mask"]
        new_item["start"] = item["start_ip"]
        new_item["end"] = item["end_ip"]
        new_item["children"] = []

        # 计算使用率：统计该网段范围内有多少已使用的IP
        start_ip = int(item["start_ip"])
        end_ip = int(item["end_ip"])
        total_ips = end_ip - start_ip - 1  # 排除网络地址和广播地址

        if total_ips > 0:
            # 统计该范围内已使用的IP数量
            used_count = sum(1 for ip_deci in used_ip_set if start_ip < ip_deci < end_ip)
            used_per = round((used_count / total_ips) * 100, 2)
            new_item["used_per"] = str(used_per)
            logger.debug(f"网段 {item['ip']}/{item['mask']}: 总IP={total_ips}, 已使用={used_count}, 使用率={used_per}%")
        else:
            new_item["used_per"] = "0"

        tree_stack = [tree]

        while len(tree_stack) > 0:
            child_array = tree_stack.pop()
            is_child = False

            for node in child_array:
                if int(node["start"]) <= int(new_item["start"]) and int(new_item["end"]) <= int(node["end"]):
                    if "children" not in node:
                        node["children"] = []
                    tree_stack.append(node["children"])
                    is_child = True
                    break

            if is_child is False:
                child_array.append(new_item)

    return tree


# ==================== IP地址管理 ====================

@decorator_checkparams(key_array=[])
def get_ipam_address_list(data):
    """查询IP地址列表"""
    db = IpamDB()
    result = db.get_ipaddr_list(data)
    return result


def batch_add_ipam_address(data_list):
    """批量添加IP地址"""
    if not isinstance(data_list, list):
        return "failed"

    db = IpamDB()
    result = db.add_ipaddr_batch(data_list)
    return result


@decorator_checkparams(key_array=["ip_deci"])
def delete_ipam_address(data):
    """删除IP地址"""
    db = IpamDB()
    result = db.delete_ipaddr_item(data)
    return result
