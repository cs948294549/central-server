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
