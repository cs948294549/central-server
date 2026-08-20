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

    # 构建树形结构
    tree_data = sorted(result, key=lambda x: (ip2decimalism(x["ip"]), int(x["mask"])))

    tree = []
    for item in tree_data:
        new_item = item.copy()
        new_item["id"] = item["ip"] + "_" + item["mask"]
        new_item["start"] = item["start_ip"]
        new_item["end"] = item["end_ip"]
        new_item["children"] = []

        # 计算使用率
        start_ip = int(item["start_ip"])
        end_ip = int(item["end_ip"])
        total_ips = end_ip - start_ip - 1  # 排除网络地址和广播地址

        if total_ips > 0:
            # 查询该网段内已使用的IP数量（每次查询创建新的数据库连接）
            query_data = {
                "start_ip": start_ip,
                "end_ip": end_ip
            }
            db_ipaddr = IpamDB()
            used_ips = db_ipaddr.get_ipaddr_list(query_data)
            if used_ips != "failed" and isinstance(used_ips, list):
                used_count = len(used_ips)
                used_per = round((used_count / total_ips) * 100, 2)
                new_item["used_per"] = str(used_per)
                logger.debug(f"网段 {item['ip']}/{item['mask']}: 总IP={total_ips}, 已使用={used_count}, 使用率={used_per}%")
            else:
                new_item["used_per"] = "0"
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
