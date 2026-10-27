"""
Wi-Fi AP 业务层：可摆放 AP 池 / AP 详情 / AP 下终端
数据来自 projects/collector 采集入库的 AP / 射频 / SSID / 终端快照，本层只读
"""
from tables.WifiDB import WifiDB
import logging

logger = logging.getLogger(__name__)


def get_ap_pool():
    """
    可摆放 AP 池，按 AC 分组，每个 AP 带已摆放的地图
    :return: {"success", "data": {"list": [{"ac_name", "aps"}]}, "message"}
    """
    try:
        placements = WifiDB().getPlacements()
        if placements == "failed":
            return {"success": False, "data": None, "message": "查询摆放关系失败"}
        placed = {}
        for row in placements:
            placed.setdefault(row.get("ap_mac"), []).append({
                "map_id": row.get("map_id"),
                "map_name": row.get("map_name") or "",
            })

        rows = WifiDB().getApPool()
        if rows == "failed":
            return {"success": False, "data": None, "message": "查询 AP 池失败"}

        groups = {}
        order = []
        for row in rows:
            ac_name = row.get("ac_name") or ""
            if ac_name not in groups:
                groups[ac_name] = []
                order.append(ac_name)
            groups[ac_name].append({
                "ap_mac": row.get("ap_mac"),
                "ap_name": row.get("ap_name") or "",
                "ap_group": row.get("ap_group") or "",
                "online_status": row.get("online_status") or "unknown",
                "client_count": int(row.get("client_count") or 0),
                "placed_maps": placed.get(row.get("ap_mac"), []),
            })

        result = [{"ac_name": ac_name, "aps": groups[ac_name]} for ac_name in order]
        return {"success": True, "data": {"list": result}, "message": "查询成功"}
    except Exception as err:
        logger.error(f"查询 AP 池异常: {err}")
        return {"success": False, "data": None, "message": f"查询 AP 池异常: {err}"}

def get_ap_detail(ap_mac):
    """
    AP 详情：基础信息 + 射频 + 开放 SSID
    :return: {"success", "data": {"base", "radios", "ssids"}, "message", "code"?}
    """
    try:
        ap_mac = str(ap_mac or "").strip().lower()
        base = WifiDB().getApBase(ap_mac)
        if base == "failed":
            return {"success": False, "data": None, "message": "查询 AP 失败"}
        if not base:
            return {"success": False, "data": None, "message": "AP 不存在", "code": 404}

        radios = WifiDB().getRadios(ap_mac)
        if radios == "failed":
            return {"success": False, "data": None, "message": "查询射频失败"}
        ssids = WifiDB().getSsids(ap_mac)
        if ssids == "failed":
            return {"success": False, "data": None, "message": "查询 SSID 失败"}

        base["radio_count"] = len(radios)
        base["online_status"] = base.get("online_status") or "unknown"
        base["client_count"] = int(base.get("client_count") or 0)
        base["last_seen_at"] = str(base.get("last_seen_at") or "")
        return {"success": True, "data": {"base": base, "radios": radios, "ssids": ssids}, "message": "查询成功"}
    except Exception as err:
        logger.error(f"查询 AP 详情异常: {err}")
        return {"success": False, "data": None, "message": f"查询 AP 详情异常: {err}"}

def get_ap_clients(ap_mac):
    """
    AP 下在线终端，数据时间取该 AP 的 last_seen_at
    :return: {"success", "data": {"list", "total", "data_time"}, "message"}
    """
    try:
        ap_mac = str(ap_mac or "").strip().lower()
        rows = WifiDB().getClients(ap_mac)
        if rows == "failed":
            return {"success": False, "data": None, "message": "查询终端失败"}

        base = WifiDB().getApBase(ap_mac)
        data_time = str(base.get("last_seen_at") or "") if isinstance(base, dict) else ""
        return {"success": True, "data": {"list": rows, "total": len(rows), "data_time": data_time}, "message": "查询成功"}
    except Exception as err:
        logger.error(f"查询 AP 终端异常: {err}")
        return {"success": False, "data": None, "message": f"查询 AP 终端异常: {err}"}
