"""
在 esflow(ElastiFlow) 中按明细 IP 统计某个出口的流量。

搜索条件按"出口"分组成变量，新增出口只需在 GROUPS 里加一项。
默认分组：博兴出口（两台 bx-fw-bj01 防火墙，出方向接口）。

输出：出方向/入方向各自按 IP 汇总的 字节数 / 包数 / flow 条数，以及占比。
沿用 daos/elasticsearch_DB.py 里已建好的 ES 客户端(g_es)，首次使用时才连接，
因此本模块被 import 时不会产生连接 ES 的副作用。
"""
import warnings
from datetime import datetime, timedelta, timezone
from function_mcp.func_cmdb import transIP
SHANGHAI = timezone(timedelta(hours=8))

warnings.filterwarnings("ignore")  # 屏蔽 verify_certs=False / LibreSSL 的告警噪音

# ============================ 默认参数 ============================

DEFAULT_GROUP = "博兴出口"
DEFAULT_LAST_MINUTES = 15
DEFAULT_TOP_N = 5

# ============================ 出口分组 ============================

GROUPS = {
    "博兴出口": {
        "index": "elastiflow-*-ecs-*",
        "hosts": [
            "dc07-prod-dc07-bx-fw-bj01host-039671",
            "dc07-prod-dc07-bx-fw-bj01host-039672",
        ],
        "egress_regex": [r"出方向接口( .*)?"],
    },
    "M5机房出口": {
        "index": "elastiflow-*-ecs-*",
        "hosts": [
            "dc09_fw1",
            "dc09_fw2",
        ],
        "egress_regex": [r"出方向接口( .*)?"],
    },
    "M5到博兴": {
        "index": "elastiflow-*-ecs-*",
        "hosts": [
            "bbs1_dc07_m01",
            "bbs2_dc07_m01",
        ],
        "ingress_regex": [
            r"Ethernet1/5( .*)?",
            r"Ethernet1/6( .*)?",
        ],
    },
}

# ================================================================

BYTES_FIELD = "network.bytes"
PKTS_FIELD = "network.packets"

_ES = None


def _es():
    """延迟获取 ES 客户端。"""
    global _ES
    if _ES is None:
        from daos.elasticsearch_DB import g_es
        _ES = g_es
    return _ES


# ---------------------------- 基础工具 ----------------------------

def iso_utc(dt):
    """统一成 Kibana/ES 接受的 UTC ISO8601 毫秒格式，如 2026-09-18T08:06:26.874Z"""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{dt.microsecond // 1000:03d}Z"


def local_iso(value):
    """把北京时间字符串 / ISO 时间戳补成毫秒精度的 ISO8601，便于直接拼进查询。"""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:  # 带时区的按 UTC 归一到毫秒
        return iso_utc(dt)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def to_local(iso_str):
    """UTC 字符串 -> 北京时间，仅用于展示，查询本身必须用 UTC。"""
    dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def resolve_window(last_minutes=None, time_min=None, time_max=None):
    """把"最近 N 分钟"或显式区间解析成 (UTC 起, UTC 止)。"""
    if time_min:
        return local_iso(time_min), local_iso(time_max) if time_max else iso_utc(datetime.now(timezone.utc))
    if last_minutes is None:
        last_minutes = DEFAULT_LAST_MINUTES
    now = datetime.now(timezone.utc)
    return iso_utc(now - timedelta(minutes=last_minutes)), iso_utc(now)


def phrase_should(field, values):
    """生成 Kibana 风格的 bool.should + minimum_should_match:1 子句。"""
    return {
        "bool": {
            "should": [{"match_phrase": {field: v}} for v in values],
            "minimum_should_match": 1,
        }
    }


def regexp_should(field, patterns):
    """同 phrase_should，但用 regexp。多个接口名拆成多条 should，与 Kibana 一致。"""
    return {
        "bool": {
            "should": [{"regexp": {field: p}} for p in patterns],
            "minimum_should_match": 1,
        }
    }


def build_query(time_min, time_max, hosts=None, egress_regex=None, ingress_regex=None):
    """还原成 Kibana 实际下发的 DSL 结构：time range 走 must，其余过滤走 filter 数组。

    注意 hosts/接口条件必须放进 filter 数组并各自包一层 bool.should，
    不能写成顶层 should + minimum_should_match —— 那种写法在 filter 里还有其他
    子句时语义会变，容易查出空结果。
    """
    must = [{"range": {"@timestamp": {"gte": time_min, "lte": time_max}}}]
    filt = []

    if hosts:
        filt.append(phrase_should("host.name", hosts))
    if ingress_regex:
        filt.append(regexp_should("observer.ingress.interface.name", ingress_regex))
    if egress_regex:
        filt.append(regexp_should("observer.egress.interface.name", egress_regex))

    return {"bool": {"must": must, "filter": filt, "should": [], "must_not": []}}


def ip_aggs(field, top_n):
    """按某个 IP 字段聚合，同时带出字节/包/flow 数三个指标。"""
    return {
        field.split(".")[0]: {
            "terms": {"field": field, "size": top_n, "order": {"bytes": "desc"}},
            "aggs": {
                "bytes": {"sum": {"field": BYTES_FIELD}},
                "pkts": {"sum": {"field": PKTS_FIELD}},
            },
        }
    }


def fetch(index, time_min, time_max, top_n, hosts, egress_regex=None, ingress_regex=None):
    """按条件查 ES，返回原始响应(聚合结果)。"""
    return _es().search(
        index=index,
        query=build_query(time_min, time_max, hosts, egress_regex, ingress_regex),
        size=0,
        aggs={
            "total_bytes": {"sum": {"field": BYTES_FIELD}},
            "total_pkts": {"sum": {"field": PKTS_FIELD}},
            **ip_aggs("source.ip", top_n),
            **ip_aggs("destination.ip", top_n),
        },
    )


def rows(resp, key):
    """把某个聚合桶(source/destination)转成 [{ip, bytes, pkts, flows}, ...]。"""
    out = []
    for b in resp["aggregations"][key]["buckets"]:
        out.append({
            "ip": b["key_as_string"] if "key_as_string" in b else b["key"],
            "bytes": int(b["bytes"]["value"] or 0),
            "pkts": int(b["pkts"]["value"] or 0),
            "flows": b["doc_count"],
        })
    return out


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}EB"


# ---------------------------- 核心查询 ----------------------------

def query_traffic(group, last_minutes=None, time_min=None, time_max=None, top_n=None):
    """查询一个出口分组的流量，返回结构化结果（不格式化）。

    group: GROUPS 里的分组名。
    返回 dict，失败时 ok=False 且 error 说明原因。
    """
    if group not in GROUPS:
        return {"ok": False, "group": group,
                "error": f"未知分组: {group}；可选分组: {', '.join(GROUPS)}"}
    cfg = GROUPS[group]

    hosts = cfg.get("hosts")
    egress_regex = cfg.get("egress_regex")
    ingress_regex = cfg.get("ingress_regex")
    t_min, t_max = resolve_window(last_minutes, time_min, time_max)
    if top_n is None:
        top_n = DEFAULT_TOP_N

    resp = fetch(cfg["index"], t_min, t_max, top_n, hosts, egress_regex, ingress_regex)

    return {
        "ok": True,
        "error": None,
        "group": group,
        "index": cfg["index"],
        "hosts": hosts,
        "egress_regex": egress_regex,
        "ingress_regex": ingress_regex,
        "time_min": t_min,
        "time_max": t_max,
        "top_n": top_n,
        "hits": resp["hits"]["total"]["value"],
        "total_bytes": int(resp["aggregations"]["total_bytes"]["value"] or 0),
        "total_pkts": int(resp["aggregations"]["total_pkts"]["value"] or 0),
        "source": rows(resp, "source"),
        "destination": rows(resp, "destination"),
    }


def format_traffic(result):
    """把 query_traffic 的结果渲染成文本。"""
    if not result.get("ok"):
        return f"查询失败: {result.get('error')}"

    lines = []
    add = lines.append
    add("=" * 83)
    add(f"esflow 明细 IP 流量统计  [{result['group']}]")
    add(f"  索引模式 : {result['index']}")
    add(f"  时间窗口 : {to_local(result['time_min'])} ~ {to_local(result['time_max'])}  (北京时间)")
    add(f"             {result['time_min']} ~ {result['time_max']}  (UTC, 实际下发给 ES 的值)")
    hosts = result.get("hosts")
    add(f"  源设备   : {', '.join(hosts) if hosts else '(不限)'}")
    add(f"  出接口   : {result.get('egress_regex') if result.get('egress_regex') else '(不限)'}")
    add(f"  入接口   : {result.get('ingress_regex') if result.get('ingress_regex') else '(不限)'}")
    add("=" * 83)

    add(f"\n命中 flow 记录 : {result['hits']:,} 条")
    add(f"总字节数       : {result['total_bytes']:,} ({human(result['total_bytes'])})")
    add(f"总包数         : {result['total_pkts']:,}")

    if not result["hits"]:
        add("\n时间窗口内没有任何记录，先确认该分组的索引/设备/接口条件是否正确。")
        return "\n".join(lines)

    total_bytes = result["total_bytes"]
    src = result["source"]
    dst = result["destination"]

    add(table_text(f"[出方向] 按源 IP Top {len(src)}", src, total_bytes))
    add(table_text(f"[入方向] 按目的 IP Top {len(dst)}", dst, total_bytes))

    # 未进 Top-N 的部分单独交代，避免看起来像"总流量只有这些"
    for name, data in (("源 IP", src), ("目的 IP", dst)):
        rest = total_bytes - sum(r["bytes"] for r in data)
        if rest > 0:
            add(f"\n  注:{name} Top {len(data)} 之外的流量 {human(rest)} "
                f"({rest / total_bytes * 100:.2f}%)，加大 top_n 可查看")

    return "\n".join(lines)


def table_text(title, data, total_bytes):
    lines = [f"\n{title}",
             f"  {'IP':<22}{'流量':>12}{'字节数':>16}{'包数':>14}{'flows':>10}{'占比':>9}",
             "  " + "-" * 81]
    for r in data:
        pct = (r["bytes"] / total_bytes * 100) if total_bytes else 0
        lines.append(f"  {r['ip']:<22}{human(r['bytes']):>12}{r['bytes']:>16,}"
                     f"{r['pkts']:>14,}{r['flows']:>10,}{pct:>8.2f}%")
    return "\n".join(lines)


# ---------------------------- MCP 入口 ----------------------------

def query_flow_traffic(group=None, top_n=None):
    """
    查询某个出口最近 15 分钟的明细 IP 流量统计（按源 IP / 目的 IP Top N 汇总）。

    :param group: 出口分组名，默认"博兴出口"；可选：博兴出口 / M5机房出口 / M5到博兴
    :param top_n: 每个方向返回前 N 个 IP，默认 5
    :return: 报表文本（每个 IP 已补上 CMDB 归属描述）
    """
    group = group or DEFAULT_GROUP
    try:
        result = query_traffic(group, top_n=top_n)
    except Exception as e:
        return f"查询失败 [{group}]: {type(e).__name__}: {e}"
    return transIP(format_traffic(result), search_type="server")


if __name__ == '__main__':
    # 博兴出口 M5机房出口
    test = query_flow_traffic(group="博兴出口", top_n=10)
    print(test)