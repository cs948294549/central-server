"""
端口组管理中间方法

端口组以组名被 ACL 规则引用而不展开，因此额外提供引用计数：
删除之前需要知道它被多少条标准规则引用，避免产生悬空引用。
端口组还可以引用其他端口组（{type:"ref", name}），这里只统计被 ACL 规则引用的情况。

条目两种结构（设计文档 1.4）：{protocol, op, ports} 端口条目 / {type:"ref", name} 组引用。
对应表：portgroup_standards，见 tables/PortGroupDB.py
"""
from utils.fingerprint import calculate_fingerprint
from tables.PortGroupDB import PortGroupDB
from tables.AccessListDB import AccessListDB
import logging

logger = logging.getLogger(__name__)


def calculate_portgroup_fingerprint(name, acl_type, entries):
    """
    计算端口组配置指纹
    :param name: 端口组名称
    :param acl_type: 地址族 ipv4 / ipv6
    :param entries: 条目列表
    :return: SHA256 指纹字符串
    """
    try:
        # acl_type 参与指纹：同名不同族是两条独立配置
        fingerprint = calculate_fingerprint({
            "kind": "portgroup",
            "name": name,
            "acl_type": acl_type,
            "entries": entries
        })
        return fingerprint
    except Exception as err:
        logger.error(f"计算端口组指纹失败: {err}")
        return None


def get_group_reference_count(name):
    """
    统计端口组被多少条 ACL 标准规则引用
    :param name: 端口组名称
    :return: 被引用的规则条数
    """
    try:
        db = AccessListDB()
        standards = db.getStandardsList({})

        if standards == "failed":
            return 0

        count = 0
        for standard in standards:
            for entry in standard.get("entries") or []:
                # 端口组只出现在源/目的端口位
                hit = any(
                    (entry.get(key) or {}).get("type") == "portgroup"
                    and (entry.get(key) or {}).get("name") == name
                    for key in ("src_port", "dst_port")
                )
                if hit:
                    # 一条规则里引用多次也只算一条规则
                    count += 1
                    break

        return count

    except Exception as err:
        logger.error(f"统计端口组引用失败: {err}")
        return 0


def get_group_list(data):
    """
    获取端口组列表（附带引用计数）
    :param data: {keyword/name, acl_type, is_active}
    :return: {success: bool, data: [], message: str}
    """
    try:
        # 页面的搜索框走 keyword，库层按 name 查询
        query = {"acl_type": data.get("acl_type")}
        keyword = data.get("name") or data.get("keyword")
        if keyword:
            query["name"] = keyword
        if data.get("is_active") is not None and data.get("is_active") != "":
            query["is_active"] = data["is_active"]

        db = PortGroupDB()
        result = db.getGroupsList(query)

        if result == "failed":
            return {"success": False, "message": "查询失败"}

        for group in result:
            group["ref_count"] = get_group_reference_count(group["name"])

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取端口组列表失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def get_group_detail(group_id):
    """
    获取端口组详情（附带引用计数）
    :param group_id: 规则ID
    :return: {success: bool, data: {}, message: str}
    """
    try:
        db = PortGroupDB()
        result = db.getGroupDetail({"id": group_id})

        if result == "failed":
            return {"success": False, "message": "规则不存在"}

        result["ref_count"] = get_group_reference_count(result["name"])

        return {"success": True, "data": result, "message": "查询成功"}

    except Exception as err:
        logger.error(f"获取端口组详情失败: {err}")
        return {"success": False, "message": f"查询失败: {str(err)}"}


def create_group(data, username):
    """
    创建端口组标准规则（包含指纹计算）
    :param data: {name, acl_type, entries, description, is_active}
    :param username: 创建人
    :return: {success: bool, data: {id, fingerprint}, message: str}
    """
    try:
        if "name" not in data or "entries" not in data:
            return {"success": False, "message": "缺少必要参数: name, entries"}

        acl_type = data.get("acl_type", "ipv4")
        entries = data["entries"]

        fingerprint = calculate_portgroup_fingerprint(data["name"], acl_type, entries)
        if not fingerprint:
            return {"success": False, "message": "计算配置指纹失败"}

        create_data = {
            "name": data["name"],
            "acl_type": acl_type,
            "fingerprint": fingerprint,
            "entries": entries,
            "description": data.get("description", ""),
            "is_active": data.get("is_active", 1),
            "created_by": username
        }

        db = PortGroupDB()
        result = db.createGroup(create_data)

        if result != "failed":
            return {"success": True, "data": {"id": result, "fingerprint": fingerprint}, "message": "创建成功"}
        else:
            return {"success": False, "message": "创建失败，可能存在重复的规则"}

    except Exception as err:
        logger.error(f"创建端口组失败: {err}")
        return {"success": False, "message": f"创建失败: {str(err)}"}


def update_group(data, username):
    """
    更新端口组标准规则（如果更新 entries 或 name/acl_type 则重新计算指纹）
    :param data: {id, name, acl_type, entries, description, is_active}
    :param username: 更新人
    :return: {success: bool, message: str}
    """
    try:
        if "id" not in data:
            return {"success": False, "message": "缺少参数: id"}

        # 指纹依赖 name + acl_type + entries，任一变化都要重算
        if "entries" in data or "name" in data or "acl_type" in data:
            db = PortGroupDB()
            current = db.getGroupDetail({"id": data["id"]})
            if current == "failed":
                return {"success": False, "message": "规则不存在"}

            entries = data["entries"] if "entries" in data else current["entries"]
            name = data.get("name", current["name"])
            acl_type = data.get("acl_type", current["acl_type"])

            fingerprint = calculate_portgroup_fingerprint(name, acl_type, entries)
            if not fingerprint:
                return {"success": False, "message": "计算配置指纹失败"}

            data["fingerprint"] = fingerprint
            data["entries"] = entries

        db = PortGroupDB()
        result = db.updateGroup(data)

        if result != "failed" and result > 0:
            return {"success": True, "message": "更新成功"}
        else:
            return {"success": False, "message": "更新失败，规则可能不存在"}

    except Exception as err:
        logger.error(f"更新端口组失败: {err}")
        return {"success": False, "message": f"更新失败: {str(err)}"}


def delete_group(group_id):
    """
    删除端口组标准规则
    :param group_id: 规则ID
    :return: {success: bool, message: str}
    """
    try:
        db = PortGroupDB()
        result = db.deleteGroup({"id": group_id})

        if result != "failed" and result > 0:
            return {"success": True, "message": "删除成功"}
        else:
            return {"success": False, "message": "删除失败，规则可能不存在"}

    except Exception as err:
        logger.error(f"删除端口组失败: {err}")
        return {"success": False, "message": f"删除失败: {str(err)}"}


def toggle_group_active(group_id):
    """
    切换端口组标准规则的启用状态
    :param group_id: 规则ID
    :return: {success: bool, message: str}
    """
    try:
        db = PortGroupDB()
        current = db.getGroupDetail({"id": group_id})

        if current == "failed":
            return {"success": False, "message": "规则不存在"}

        new_value = 0 if current["is_active"] else 1

        db = PortGroupDB()
        result = db.updateGroup({"id": group_id, "is_active": new_value})

        if result != "failed" and result > 0:
            return {"success": True, "message": "状态更新成功"}
        else:
            return {"success": False, "message": "状态更新失败"}

    except Exception as err:
        logger.error(f"切换端口组状态失败: {err}")
        return {"success": False, "message": f"状态更新失败: {str(err)}"}
