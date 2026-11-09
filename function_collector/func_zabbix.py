"""
Zabbix 接口流量查询

按设备名 + 接口索引，返回 net.if.in / net.if.out 两个监控项在指定时间段的历史数据。
参考实现：projects/collector/scripts/zabbix_check_monthly_95th_quota.py
"""

import logging
import re
import time

import requests

from config.config import Config

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 30
DEFAULT_RANGE = 3600  # 未传 start_time 时默认往前取 1 小时


def _zabbix_call(method, params):
    """调用 Zabbix JSON-RPC 接口，返回 result 字段"""
    conf = Config.zabbix_config
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    headers = {"Content-Type": "application/json",
               "Authorization": "Bearer {}".format(conf["api_token"])}
    resp = requests.post(conf["api_url"], json=payload, headers=headers, timeout=HTTP_TIMEOUT)
    result = resp.json()
    if "error" in result:
        raise RuntimeError("Zabbix 接口 {} 报错: {}".format(method, result["error"].get("data")))
    return result.get("result")


def parse_timestamp(value, field_name="时间"):
    """时间戳转 int，格式不对时抛出明确提示"""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError("{}时间戳错误: {}，需传秒级时间戳".format(field_name, value))


def parse_duration_to_seconds(value):
    """周期转秒：1m -> 60，30s -> 30，1h -> 3600，35d -> 3024000"""
    m = re.match(r"^(\d+)\s*([smhd]?)$", str(value or "").strip().lower())
    if not m:
        return 60
    unit = m.group(2) or "s"
    return max(int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit], 1)


def get_hostid(host):
    """按设备名取 hostid"""
    rows = _zabbix_call("host.get", {"filter": {"host": [str(host).strip()]}, "output": ["hostid"]})
    if not rows:
        raise ValueError("设备 {} 在 Zabbix 中不存在".format(host))
    return rows[0]["hostid"]


def get_item(hostid, item_key):
    """按监控项 key 取 itemid、采集周期、数据类型和数据保留期"""
    rows = _zabbix_call("item.get", {
        "hostids": hostid,
        "filter": {"key_": item_key},
        "output": ["itemid", "delay", "value_type", "history", "trends"],
    })
    if not rows:
        raise ValueError("设备上没有监控项 {}".format(item_key))
    return {
        "itemid": rows[0]["itemid"],
        "delay_seconds": parse_duration_to_seconds(rows[0].get("delay")),
        "value_type": int(rows[0].get("value_type", 3)),
        # 原始历史数据保留期，默认 35d
        "history_seconds": parse_duration_to_seconds(rows[0].get("history") or "35d"),
    }


def get_history(item, time_from, time_till):
    """取原始历史数据，按采集周期归并，同周期取最大值"""
    rows = _zabbix_call("history.get", {
        "itemids": item["itemid"],
        "time_from": time_from,
        "time_till": time_till,
        "output": "extend",
        "sortfield": "clock",
        "sortorder": "ASC",
        "history": item["value_type"],
    })

    # Zabbix 采集有 1~2s 抖动，同一周期会落进不同 clock，按采集周期分桶
    buckets = {}
    for row in rows:
        clock = int(row["clock"]) // item["delay_seconds"] * item["delay_seconds"]
        value = float(row["value"])
        if clock not in buckets or value > buckets[clock]:
            buckets[clock] = value

    return [{"clock": clock, "value": buckets[clock], "type": "history"} for clock in sorted(buckets)]


def get_trend(item, time_from, time_till):
    """取趋势数据，1 小时一个点，取该小时的最大值"""
    rows = _zabbix_call("trend.get", {
        "itemids": item["itemid"],
        "time_from": time_from,
        "time_till": time_till,
        "output": "extend",
    })
    points = []
    for row in rows:
        try:
            points.append({"clock": int(row["clock"]), "value": float(row["value_max"]), "type": "trend"})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(points, key=lambda point: point["clock"])


def get_points(item, time_from, time_till):
    """
    取时间段内的流量数据
    原始历史保留期（默认 35d）内取实际数据，超出部分取 trend 聚合数据；
    Args:
        time_from / time_till: 秒级时间戳
    Returns:
        list: [{"clock", "value", "type"}]，type 为 history 或 trend
    """
    cutoff = int(time.time()) - item["history_seconds"]
    points = []
    if time_from < cutoff:
        points.extend(get_trend(item, time_from, min(time_till, cutoff)))
    if time_till > cutoff:
        points.extend(get_history(item, max(time_from, cutoff), time_till))
    return points


def query_port_traffic(host, port_id, start_time=None, end_time=None):
    """
    查询设备端口某个时间段的 in/out 流量

    Args:
        host: 设备名
        port_id: 接口索引，如 436207616
        start_time: 开始时间戳（秒），默认结束时间往前 1 小时
        end_time: 结束时间戳（秒），默认当前

    Returns:
        dict: 含 net_if_in / net_if_out 两个监控项的数据
    """
    if not host:
        raise ValueError("缺失参数 host（设备名）")
    if port_id in (None, ""):
        raise ValueError("缺失参数 port_id（接口索引）")

    port_id = str(port_id).strip()
    now = int(time.time())
    time_till = min(parse_timestamp(end_time, "end_time") or now, now)
    time_from = parse_timestamp(start_time, "start_time") or (time_till - DEFAULT_RANGE)
    if time_from >= time_till:
        raise ValueError("start_time 必须早于 end_time")

    hostid = get_hostid(host)
    respond = {"host": host, "port_id": port_id, "start_time": time_from, "end_time": time_till}
    for direction in ("in", "out"):
        item = get_item(hostid, "net.if.{}[{}]".format(direction, port_id))
        points = get_points(item, time_from, time_till)
        respond["net_if_{}".format(direction)] = {
            "itemid": item["itemid"],
            # 时间戳落在保留期内的点 type=history（实际数据），之外的 type=trend（1 小时聚合）
            "points": points,
        }

    return respond

if __name__ == '__main__':
    import json
    dat = {
        "host": "pcs1_dc07_m01.vdian.net",  # 设备名，必填
        "port_id": "436207616",  # Zabbix 监控项里的接口索引，必填
        "start_time": 1794195800,  # 开始时间戳（秒），默认结束时间往前 1 小时
        "end_time": 1794199400  # 结束时间戳（秒），默认当前
    }
    ad = query_port_traffic(host=dat["host"], port_id=dat["port_id"], start_time=dat["start_time"], end_time=dat["end_time"])
    print(json.dumps(ad, indent=4))