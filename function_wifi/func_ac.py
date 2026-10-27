"""
Wi-Fi AC 业务层：AC 增删改查、SNMP 连通测试、立即探测
快照数据由 projects/collector 定时采集入库，本层只读快照、不做采集
"""
from tables.WifiDB import WifiDB
from lib_snmp.snmpAgent import snmpget
from lib_snmp.snmp_collector import identify_device_vendor
import time
import logging

logger = logging.getLogger(__name__)


def get_ac_list():
    """
    AC 列表，community 一律回显 ******
    :return: {"success", "data": {"list", "total"}, "message"}
    """
    try:
        rows = WifiDB().getAcList()
        if rows == "failed":
            return {"success": False, "data": None, "message": "查询 AC 列表失败"}
        for row in rows:
            row["community"] = "******" if row.get("community") else ""
        return {"success": True, "data": {"list": rows, "total": len(rows)}, "message": "查询成功"}
    except Exception as err:
        logger.error(f"查询 AC 列表异常: {err}")
        return {"success": False, "data": None, "message": f"查询 AC 列表异常: {err}"}

def save_ac(data):
    """
    新增或修改 AC；带 ac_id 为修改，community 留空或为 ****** 表示不修改
    :return: {"success", "data": {"ok", "ac_id"}, "message", "code"?}
    """
    try:
        ac_id = int(data.get("ac_id") or 0)
        ac = {
            "ac_id": ac_id,
            "ac_name": str(data.get("ac_name") or "").strip(),
            "vendor": str(data.get("vendor") or "").strip().lower(),
            "mgmt_ip": str(data.get("mgmt_ip") or "").strip(),
            "model": str(data.get("model") or "").strip(),
            "community": str(data.get("community") or "").strip(),
        }
        if not ac["ac_name"] or not ac["mgmt_ip"]:
            return {"success": False, "data": None, "message": "AC 名称和管理 IP 不能为空", "code": 400}
        if ac["vendor"] not in ["huawei", "h3c", "ruijie"]:
            return {"success": False, "data": None, "message": "厂商只支持 huawei / h3c / ruijie", "code": 400}

        exists = WifiDB().checkAcExists(ac["ac_name"], ac["mgmt_ip"], ac_id)
        if exists == "failed":
            return {"success": False, "data": None, "message": "校验 AC 唯一性失败"}
        if exists == "name":
            return {"success": False, "data": None, "message": "AC 名称已存在", "code": 400}
        if exists == "ip":
            return {"success": False, "data": None, "message": "管理 IP 已存在", "code": 400}

        if ac_id:
            old = WifiDB().getAcById(ac_id)
            if old == "failed":
                return {"success": False, "data": None, "message": "查询 AC 失败"}
            if not old:
                return {"success": False, "data": None, "message": "AC 不存在", "code": 404}
            if not ac["community"] or ac["community"] == "******":
                ac.pop("community")
            result = WifiDB().updateAc(ac)
            if result == "failed":
                return {"success": False, "data": None, "message": "修改 AC 失败"}
            return {"success": True, "data": {"ok": True, "ac_id": ac_id}, "message": "修改成功"}

        if not ac["community"] or ac["community"] == "******":
            return {"success": False, "data": None, "message": "新增 AC 必须填写 Community", "code": 400}
        new_id = WifiDB().createAc(ac)
        if new_id == "failed":
            return {"success": False, "data": None, "message": "新增 AC 失败"}
        return {"success": True, "data": {"ok": True, "ac_id": new_id}, "message": "新增成功"}
    except Exception as err:
        logger.error(f"保存 AC 异常: {err}")
        return {"success": False, "data": None, "message": f"保存 AC 异常: {err}"}

def delete_ac(ac_id):
    """
    删除 AC，级联删除该 AC 下 AP / 射频 / SSID / 终端及地图图标
    :return: {"success", "data": {"ok"}, "message", "code"?}
    """
    try:
        result = WifiDB().deleteAc(int(ac_id))
        if result == "failed":
            return {"success": False, "data": None, "message": "删除 AC 失败"}
        if not result:
            return {"success": False, "data": None, "message": "AC 不存在", "code": 404}
        return {"success": True, "data": {"ok": True}, "message": "删除成功"}
    except Exception as err:
        logger.error(f"删除 AC 异常: {err}")
        return {"success": False, "data": None, "message": f"删除 AC 异常: {err}"}

def test_ac(data):
    """
    SNMP 连通测试：取 sysDescr + sysName，不入库
    编辑态 community 留空或为 ****** 时使用库里已存的 community
    :return: {"success", "data": {"ok", "sysname", "sysdescr", "vendor_detect", "elapsed_ms"}, "message"}
    """
    try:
        mgmt_ip = str(data.get("mgmt_ip") or "").strip()
        community = str(data.get("community") or "").strip()
        ac_id = int(data.get("ac_id") or 0)
        if (not community or community == "******") and ac_id:
            old = WifiDB().getAcById(ac_id)
            if old == "failed":
                return {"success": False, "data": None, "message": "查询 AC 失败"}
            if not old:
                return {"success": False, "data": None, "message": "AC 不存在", "code": 404}
            community = old.get("community") or ""
            mgmt_ip = mgmt_ip or old.get("mgmt_ip") or ""
        if not mgmt_ip or not community or community == "******":
            return {"success": False, "data": None, "message": "管理 IP 和 Community 不能为空", "code": 400}

        start = time.time()
        sysdescr = snmpget(mgmt_ip, community, "1.3.6.1.2.1.1.1.0")
        sysname = snmpget(mgmt_ip, community, "1.3.6.1.2.1.1.5.0")
        elapsed_ms = int((time.time() - start) * 1000)
        if sysdescr is None and sysname is None:
            return {"success": False, "data": None, "message": "SNMP 无响应，请检查 IP / Community / ACL"}

        sysdescr = str(sysdescr or "").strip()
        sysname = str(sysname or "").strip()
        vendor_detect = identify_device_vendor(sysdescr) if sysdescr else ""
        return {
            "success": True,
            "data": {"ok": True, "sysname": sysname, "sysdescr": sysdescr, "vendor_detect": vendor_detect, "elapsed_ms": elapsed_ms},
            "message": "连通成功",
        }
    except Exception as err:
        logger.error(f"测试 AC 连通异常: {err}")
        return {"success": False, "data": None, "message": f"测试 AC 连通异常: {err}"}

def collect_ac(ac_id):
    """
    立即探测：只做 SNMP 连通探测并回写 last_status，快照仍由 projects/collector 每 5 分钟采集
    :return: {"success", "data": {"ok", "ap_count", "elapsed_ms"}, "message", "code"?}
    """
    try:
        ac = WifiDB().getAcById(int(ac_id))
        if ac == "failed":
            return {"success": False, "data": None, "message": "查询 AC 失败"}
        if not ac:
            return {"success": False, "data": None, "message": "AC 不存在", "code": 404}

        start = time.time()
        sysname = snmpget(ac.get("mgmt_ip"), ac.get("community") or "", "1.3.6.1.2.1.1.5.0")
        elapsed_ms = int((time.time() - start) * 1000)
        status = "offline" if sysname is None else "online"
        if WifiDB().updateAcStatus(int(ac_id), status) == "failed":
            return {"success": False, "data": None, "message": "回写 AC 状态失败"}
        if status == "offline":
            return {"success": False, "data": None, "message": "SNMP 无响应，已标记为 offline"}

        ap_count = WifiDB().getApCountByAc(int(ac_id))
        if ap_count == "failed":
            ap_count = 0
        return {
            "success": True,
            "data": {"ok": True, "ap_count": ap_count, "elapsed_ms": elapsed_ms},
            "message": "AC 在线，AP / 终端快照由采集服务每 5 分钟刷新",
        }
    except Exception as err:
        logger.error(f"探测 AC 异常: {err}")
        return {"success": False, "data": None, "message": f"探测 AC 异常: {err}"}
