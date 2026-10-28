"""
Wi-Fi 地图业务层：地图列表 / 详情 / 属性维护 / 布局保存 / 删除
图标指标来自 projects/collector 采集入库的 AP / 射频快照
"""
from tables.WifiDB import WifiDB
import logging

logger = logging.getLogger(__name__)


def get_map_list():
    """
    地图列表，按建筑分组，组内按 sort_num 排序；不带底图
    :return: {"success", "data": {"list": [{"building", "maps"}]}, "message"}
    """
    try:
        rows = WifiDB().getMapList()
        if rows == "failed":
            return {"success": False, "data": None, "message": "查询地图列表失败"}

        groups = {}
        order = []
        for row in rows:
            building = row.get("building") or ""
            if building not in groups:
                groups[building] = []
                order.append(building)
            groups[building].append({
                "map_id": row.get("map_id"),
                "map_name": row.get("map_name") or "",
                "building": building,
                "sort_num": int(row.get("sort_num") or 0),
                "ap_count": int(row.get("ap_count") or 0),
                "has_image": bool(row.get("has_image")),
            })

        result = []
        for building in order:
            maps = sorted(groups[building], key=lambda m: m["sort_num"])
            result.append({"building": building, "maps": maps})
        return {"success": True, "data": {"list": result}, "message": "查询成功"}
    except Exception as err:
        logger.error(f"查询地图列表异常: {err}")
        return {"success": False, "data": None, "message": f"查询地图列表异常: {err}"}

def get_map_detail(map_id):
    """
    地图详情：底图（data URI）+ 全部图标及最新指标、数据时间
    多射频取值：利用率 / 功率取最大值，信道与频段全部列出
    :return: {"success", "data": {map 字段, "image", "data_time", "markers"}, "message", "code"?}
    """
    try:
        detail = WifiDB().getMapDetail(int(map_id))
        if detail == "failed":
            return {"success": False, "data": None, "message": "查询地图详情失败"}
        if not detail:
            return {"success": False, "data": None, "message": "地图不存在", "code": 404}

        image_base64 = detail.pop("image_base64", "") or ""
        if not image_base64:
            detail["image"] = ""
        elif image_base64.startswith("/9j/"):
            detail["image"] = "data:image/jpeg;base64," + image_base64
        else:
            detail["image"] = "data:image/png;base64," + image_base64
        detail["image_width"] = int(detail.get("image_width") or 0)
        detail["image_height"] = int(detail.get("image_height") or 0)

        rows = WifiDB().getMapMarkers(int(map_id))
        if rows == "failed":
            return {"success": False, "data": None, "message": "查询地图图标失败"}
        macs = [row.get("ap_mac") for row in rows if row.get("ap_mac")]
        radios = WifiDB().getRadiosByAps(macs)
        if radios == "failed":
            return {"success": False, "data": None, "message": "查询射频数据失败"}

        radio_map = {}
        for radio in radios:
            radio_map.setdefault(radio.get("ap_mac"), []).append(radio)

        markers = []
        data_time = ""
        for row in rows:
            ap_radios = radio_map.get(row.get("ap_mac"), [])
            channels = [r.get("channel") for r in ap_radios if r.get("channel") not in (None, "")]
            bands = [r.get("band") for r in ap_radios if r.get("band") not in (None, "")]
            utils = [r.get("utilization") for r in ap_radios if r.get("utilization") is not None]
            powers = [r.get("tx_power") for r in ap_radios if r.get("tx_power") is not None]
            # 每个射频单独给一份，前端按射频各画一个利用率标签
            radios_detail = [{
                "radio_id": r.get("radio_id"),
                "band": r.get("band") or "",
                "channel": r.get("channel"),
                "utilization": r.get("utilization"),
                "tx_power": r.get("tx_power"),
            } for r in ap_radios]
            last_seen_at = str(row.get("last_seen_at") or "")
            if last_seen_at > data_time:
                data_time = last_seen_at
            markers.append({
                "ap_mac": row.get("ap_mac"),
                "ap_name": row.get("ap_name") or "",
                "display_name": row.get("display_name") or row.get("ap_name") or row.get("ap_mac"),
                "x_ratio": float(row.get("x_ratio") or 0),
                "y_ratio": float(row.get("y_ratio") or 0),
                "online_status": row.get("online_status") or "unknown",
                "radio_count": len(ap_radios),
                "channels": channels,
                "bands": bands,
                "radios": radios_detail,
                "utilization": max(utils) if utils else None,
                "tx_power": max(powers) if powers else None,
                "client_count": int(row.get("client_count") or 0),
                "last_seen_at": last_seen_at,
            })

        detail["data_time"] = data_time
        detail["markers"] = markers
        return {"success": True, "data": detail, "message": "查询成功"}
    except Exception as err:
        logger.error(f"查询地图详情异常: {err}")
        return {"success": False, "data": None, "message": f"查询地图详情异常: {err}"}

def save_map_info(data):
    """
    新增或修改地图属性与底图；带 map_id 为修改，image 为空表示不换底图
    image 可带 data: 前缀，存库前去掉；底图限制 2MB，map_name 全局唯一
    :return: {"success", "data": {"ok", "map_id"}, "message", "code"?}
    """
    try:
        map_id = int(data.get("map_id") or 0)
        info = {
            "map_id": map_id,
            "map_name": str(data.get("map_name") or "").strip(),
            "building": str(data.get("building") or "").strip(),
            "sort_num": int(data.get("sort_num") or 0),
            "image_width": int(data.get("image_width") or 0),
            "image_height": int(data.get("image_height") or 0),
        }
        if not info["map_name"]:
            return {"success": False, "data": None, "message": "地图名称不能为空", "code": 400}

        image = str(data.get("image") or "").strip()
        if "base64," in image:
            image = image.split("base64,", 1)[1]
        if image and len(image) * 3 / 4 > 2 * 1024 * 1024:
            return {"success": False, "data": None, "message": "底图不能超过 2MB", "code": 400}

        exists = WifiDB().checkMapName(info["map_name"], map_id)
        if exists == "failed":
            return {"success": False, "data": None, "message": "校验地图名称失败"}
        if exists:
            return {"success": False, "data": None, "message": "地图名称已存在", "code": 400}

        if map_id:
            old = WifiDB().getMapDetail(map_id)
            if old == "failed":
                return {"success": False, "data": None, "message": "查询地图失败"}
            if not old:
                return {"success": False, "data": None, "message": "地图不存在", "code": 404}
            if image:
                info["image_base64"] = image
            if WifiDB().updateMapInfo(info) == "failed":
                return {"success": False, "data": None, "message": "修改地图失败"}
            return {"success": True, "data": {"ok": True, "map_id": map_id}, "message": "修改成功"}

        if not image:
            return {"success": False, "data": None, "message": "新增地图必须上传底图", "code": 400}
        info["image_base64"] = image
        new_id = WifiDB().createMap(info)
        if new_id == "failed":
            return {"success": False, "data": None, "message": "新增地图失败"}
        return {"success": True, "data": {"ok": True, "map_id": new_id}, "message": "新增成功"}
    except Exception as err:
        logger.error(f"保存地图属性异常: {err}")
        return {"success": False, "data": None, "message": f"保存地图属性异常: {err}"}

def save_map_layout(data):
    """
    保存地图布局：图标全量替换，带 version 乐观锁；可选带 image_width / image_height 更新实际尺寸
    :return: {"success", "data": {"ok", "version"}, "message", "code"?}
    """
    try:
        map_id = int(data.get("map_id") or 0)
        version = data.get("version")
        markers = data.get("markers")
        if not map_id or version is None or not isinstance(markers, list):
            return {"success": False, "data": None, "message": "缺少参数: map_id / version / markers", "code": 400}

        items = []
        for marker in markers:
            ap_mac = str(marker.get("ap_mac") or "").strip().lower()
            if not ap_mac:
                continue
            items.append({
                "ap_mac": ap_mac,
                "x_ratio": round(min(max(float(marker.get("x_ratio") or 0), 0), 1), 6),
                "y_ratio": round(min(max(float(marker.get("y_ratio") or 0), 0), 1), 6),
                "display_name": str(marker.get("display_name") or "").strip(),
            })

        result = WifiDB().saveMapLayout(
            map_id,
            int(version),
            items,
            int(data.get("image_width") or 0),
            int(data.get("image_height") or 0),
        )
        if result == "failed":
            return {"success": False, "data": None, "message": "保存地图布局失败"}
        if result == "notfound":
            return {"success": False, "data": None, "message": "地图不存在", "code": 404}
        if result == "conflict":
            return {"success": False, "data": None, "message": "地图已被他人修改，请刷新", "code": 409}
        return {"success": True, "data": {"ok": True, "version": result}, "message": "保存成功"}
    except Exception as err:
        logger.error(f"保存地图布局异常: {err}")
        return {"success": False, "data": None, "message": f"保存地图布局异常: {err}"}

def delete_map(map_id):
    """
    删除地图，连带删除图上图标，不删 AP 数据
    :return: {"success", "data": {"ok"}, "message", "code"?}
    """
    try:
        result = WifiDB().deleteMap(int(map_id))
        if result == "failed":
            return {"success": False, "data": None, "message": "删除地图失败"}
        if not result:
            return {"success": False, "data": None, "message": "地图不存在", "code": 404}
        return {"success": True, "data": {"ok": True}, "message": "删除成功"}
    except Exception as err:
        logger.error(f"删除地图异常: {err}")
        return {"success": False, "data": None, "message": f"删除地图异常: {err}"}
