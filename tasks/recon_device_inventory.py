"""
设备对账定时任务（PRD-01）

功能：对齐 Ocean（CMDB）、Zabbix、netops 平台采集三个来源的设备清单，
逐台输出差异类型与处理依据。

执行流程：
1. 采集三源数据（Ocean / Zabbix / 平台采集），统一为标准设备记录
2. 按归一化设备名匹配三源记录，识别同一台设备
3. 按 PRD-01 第五章规则分类 A~I
4. 应用豁免清单与容差规则
5. 落库快照、设备明细、差异明细
6. 推送本次新增的差异

口径说明：
- Ocean 侧只取 status 为「正常」且设备名非空的记录，其余视为已下线/已清理，不参与对账。
- Zabbix / 平台能采集到的设备，Ocean 的 operationStatus 不应为 入库/待报废。
  对账结果用于反向修正 CMDB（补登记 / 恢复状态），不用于反向下线监控。

使用方式：
1. 作为定时任务：在 config/task_config.yaml 中配置
2. 单独运行：python3 tasks/recon_device_inventory.py

前置条件：
- Ocean 数据入口已接入（collect_ocean_devices）
- Zabbix 数据入口已接入（collect_zabbix_hosts，认证取 Config.zabbix_config）
- 平台设备入口已接入（collect_platform_devices，读 iplist/devices 表）
- 网段扫描暂搁置（scan_managed_subnets），PRD-01 3.3 / 3.4
- recon_snapshot / recon_device / recon_diff 表尚未建表，persist_* 需先实现
"""
import json
import logging
import sys
import time
from pathlib import Path

import requests

from config.config import Config


# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)



# ============================================
# 任务配置
# ============================================

TASK_CONFIG = {
    "enabled": True,
    "batch_id": None,               # 为空时按执行时间生成
    "time_window_minutes": 60,      # 三源采集允许的时间差（PRD 第四章"快照问题"）
    "offline_confirm_rounds": 2,    # 连续 N 次对账缺失才判定下线（容差规则）
    "exempt_file": "config/recon_exempt.json",  # 豁免清单（差异类型 H）
    "ocean_page_size": 100,         # Ocean 分页大小
    "ocean_max_pages": 500,         # 分页上限，防止接口异常导致死循环
    "zabbix_group_names": [         # Zabbix 交换机/防火墙主机组（精确匹配），必填
        "bj-office", "cq-office", "dg-office", "hz-office", "sz-office",
        "ts-office", "ts-hengfeng-office", "wf-office",
        "dc03-switch", "dc05-switch", "dc07-switch", "dc09-switch", "dc19-switch",
    ],
    "http_timeout": 30,             # HTTP 请求超时（秒）
}

# Zabbix 中只挂了这些模板的主机不是真设备（如 ping 监控组），排除
# 只匹配"唯一模板"的情况：挂了该模板同时还有设备模板的主机仍保留
ZABBIX_SKIP_ONLY_TEMPLATES = ("wjf 1s ICMP Ping Alarm",)

# Ocean 接口地址
OCEAN_API_BASE = "http://api-o2.vdian.net/v1"

# Ocean 状态口径：status 只有「正常」算在线，其余（待报废/维修等）一律视为不在线
OCEAN_STATUS_ONLINE = "正常"

# Ocean operationStatus 口径：Zabbix / 平台采集得到的设备，不应为以下取值
OCEAN_STATUS_ACTIVE = "正常"
OCEAN_STATUS_INVALID = ("入库", "待报废")

# Ocean manufacturer 字段编码（当前样本中为整型，映射待补全，未知编码原样展示）
OCEAN_MANUFACTURERS = {}

# 数据来源标识
SOURCE_OCEAN = "ocean"
SOURCE_ZABBIX = "zabbix"
SOURCE_PLATFORM = "platform"    # netops 平台采集器（iplist/devices 表）
SOURCE_SCAN = "scan"            # 网段扫描，暂未启用

# 差异类型（对应 PRD-01 第五章）
DIFF_A = "A"  # 三方一致（Ocean 正常 + Zabbix + 平台采集）
DIFF_B = "B"  # Ocean 正常、Zabbix 有、平台无：平台未纳管
DIFF_C = "C"  # Ocean 正常、Zabbix 无、平台有：未纳入监控
DIFF_D = "D"  # 仅 Ocean 正常：疑似僵尸资产
DIFF_E = "E"  # Ocean 未登记、Zabbix 有：补登记 CMDB
DIFF_F = "F"  # Ocean 未登记、平台有：补登记 CMDB
DIFF_H = "H"  # 豁免
DIFF_I = "I"  # Ocean 状态过期：采得到但 operationStatus 为 入库/待报废

DIFF_TYPE_DESC = {
    DIFF_A: "三方一致",
    DIFF_B: "平台未纳管（Zabbix 有、平台无）",
    DIFF_C: "未纳入监控（平台有、Zabbix 无）",
    DIFF_D: "CMDB 独有，疑似僵尸资产",
    DIFF_E: "CMDB 未登记（仅 Zabbix 有）",
    DIFF_F: "CMDB 未登记（仅平台有）",
    DIFF_H: "豁免",
    DIFF_I: "CMDB 状态过期（采得到但状态为入库/待报废）",
}


# ============================================
# 一、数据接入层：三源 Connector
#
# 三个函数统一返回设备记录列表，每条记录的结构：
# {
#     "source": "ocean/zabbix/platform",
#     "key": "来源侧主键",
#     "name": "设备名",
#     "ip": "管理IP",
#     "vendor_model": "厂商/型号，可为空",
#     "location": "机房/机柜，可为空",
#     "status": "来源侧状态：在库/下架/可用/不可用等",
#     "collected_at": 采集时间戳（int）
# }
# ============================================

def collect_ocean_devices():
    """
    从 Ocean（CMDB）分页拉取网络设备列表（全量，不按状态过滤）

    接口：GET /v1/assetNetDevices?access-token=&pageSize=&pageNumber=
    返回字段：data.list[]、data.totalPages、data.totalSize、status.success

    拉全量的原因：Zabbix / 平台采集得到的设备，Ocean 状态不应为 入库/待报废。
    只有拿到全量才能区分"CMDB 未登记"和"CMDB 状态过期"，两者的修正动作不同。
    """
    url = "{}/assetNetDevices".format(OCEAN_API_BASE)
    page_size = TASK_CONFIG["ocean_page_size"]
    max_pages = TASK_CONFIG["ocean_max_pages"]
    collected_at = int(time.time())

    records = []
    seen_ids = set()
    skipped_unnamed = 0
    skipped_offline = 0
    status_dist = {}

    for page_number in range(1, max_pages + 1):
        try:
            resp = requests.get(
                url,
                params={
                    "access-token": Config.cmdb_access_token,
                    "pageSize": page_size,
                    "pageNumber": page_number,
                },
                timeout=TASK_CONFIG["http_timeout"],
            )
            result = resp.json()
        except Exception as e:
            logger.error(f"Ocean 接口请求失败 page={page_number}: {e}")
            return []

        if not result.get("status", {}).get("success"):
            logger.error(f"Ocean 接口返回失败 page={page_number}: {result.get('status')}")
            return []

        data = result.get("data") or {}
        items = data.get("list") or []
        total_pages = data.get("totalPages") or 0

        for item in items:
            key = str(item.get("id", ""))
            if key and key in seen_ids:
                continue
            seen_ids.add(key)
            # 设备名被清空的记录无法按名匹配，不参与对账
            if not (item.get("deviceName") or "").strip():
                skipped_unnamed += 1
                continue
            status = (item.get("operationStatus") or "").strip()
            status_dist[status] = status_dist.get(status, 0) + 1
            if status and status != OCEAN_STATUS_ONLINE:
                skipped_offline += 1

            # 不在线记录仍保留：它证明 CMDB 已登记该设备，只是状态待修正，
            # 若在此丢弃会被误判为「CMDB 未登记」（E/F）。分类时再剔除
            records.append(_map_ocean_record(item, key, collected_at))

        # 最后一页：数据不足一页，或已到接口声明的总页数
        if len(items) < page_size or page_number >= total_pages:
            break

    active = sum(1 for r in records if r.get("operation_status") == OCEAN_STATUS_ACTIVE)
    logger.info(
        f"Ocean 拉取完成：参与匹配 {len(records)} 台（operationStatus 正常 {active} 台），"
        f"其中不在线 {skipped_offline} 台不产生差异，跳过设备名为空 {skipped_unnamed} 台"
    )
    logger.info(f"Ocean status 字段分布: {status_dist}")
    return records


def _map_ocean_record(item, key, collected_at):
    """Ocean 原始记录转标准设备记录"""
    return {
        "source": SOURCE_OCEAN,
        "key": key,
        "name": item.get("deviceName") or "",
        "ip": normalize_ip(item.get("manageIp")),
        "vendor_model": " ".join(
            filter(None, [OCEAN_MANUFACTURERS.get(item.get("manufacturer"), ""), item.get("modelName")])
        ),
        "location": " ".join(filter(None, [item.get("idcEname"), item.get("rackName")])),
        "status": item.get("status") or "",
        "operation_status": item.get("operationStatus") or "",
        "device_type": item.get("modelType") or "",
        "loopback_ip": item.get("loopback0Ip") or "",
        "sn": item.get("sn") or "",
        "collected_at": collected_at,
    }


def collect_zabbix_hosts():
    """
    从 Zabbix API 拉取网络设备主机列表

    接口：POST {api_url}，JSON-RPC 2.0 host.get
    认证：Authorization: Bearer {Config.zabbix_config['api_token']}（Zabbix 5.4+ 方式）

    按 TASK_CONFIG["zabbix_group_names"] 过滤主机组——Zabbix 里混有台式机等非网络设备，
    不过滤会大量污染对账结果。只取启用的主机。
    """
    zabbix = Config.zabbix_config or {}
    api_url = zabbix.get("api_url")
    api_token = zabbix.get("api_token")
    if not api_url or not api_token:
        logger.error("Zabbix 配置缺失：Config.zabbix_config 需包含 api_url 与 api_token")
        return []

    group_names = TASK_CONFIG["zabbix_group_names"]
    if not group_names:
        logger.error("未配置 TASK_CONFIG['zabbix_group_names']，Zabbix 全量主机混有非网络设备，本次不采集")
        return []

    group_ids = _zabbix_group_ids(api_url, api_token, group_names)
    if not group_ids:
        logger.error(f"Zabbix 主机组未匹配到: {group_names}")
        return []

    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "host", "name", "status", "maintenance_status"],
            "selectInterfaces": ["ip", "dns", "useip", "port", "main", "type"],
            "selectParentTemplates": ["templateid", "name"],
            "groupids": group_ids,
            "filter": {"status": "0"},
        },
        "id": 2,
    }

    try:
        result = _zabbix_call(api_url, api_token, payload)
    except Exception as e:
        logger.error(f"Zabbix 主机拉取失败: {e}")
        return []

    collected_at = int(time.time())
    records = []
    seen_hostids = set()
    no_ip = 0
    ping_only = 0

    for host in result or []:
        hostid = str(host.get("hostid", ""))
        # 一台主机可能同时属于多个匹配组，按 hostid 去重，避免同 IP 重复记录
        if hostid in seen_hostids:
            continue
        seen_hostids.add(hostid)

        # 只挂了 ping 类模板的主机是 ping 监控条目，不是真实设备
        if _is_ping_only_host(host):
            ping_only += 1
            continue

        iface = _pick_zabbix_interface(host.get("interfaces") or [])
        ip = normalize_ip(iface.get("ip") if iface and iface.get("useip") == "1" else "")
        if not ip:
            no_ip += 1
        records.append({
            "source": SOURCE_ZABBIX,
            "key": hostid,
            "name": host.get("name") or host.get("host") or "",
            "ip": ip,
            "vendor_model": ", ".join(
                t.get("name", "") for t in (host.get("parentTemplates") or []) if t.get("name")
            ),
            "location": "",
            "status": "maintenance" if host.get("maintenance_status") == "1" else "enabled",
            "collected_at": collected_at,
        })

    if no_ip:
        logger.warning(f"Zabbix 主机中 {no_ip} 台未取到管理 IP（useip=0 或无接口），不参与 IP 匹配")
    if ping_only:
        logger.info(f"Zabbix 跳过仅挂 ping 模板的主机 {ping_only} 台")
    logger.info(f"Zabbix 拉取完成：组 {group_names} 共 {len(records)} 台")
    return records


def _is_ping_only_host(host):
    """主机所挂模板全部属于 ping 类模板时返回 True"""
    templates = {
        (t.get("name") or "").strip()
        for t in (host.get("parentTemplates") or [])
        if t.get("name")
    }
    if not templates:
        return False
    return templates.issubset(ZABBIX_SKIP_ONLY_TEMPLATES)


def _zabbix_call(api_url, api_token, payload):
    """执行一次 JSON-RPC 调用，返回 result，失败抛异常"""
    resp = requests.post(
        api_url,
        json=payload,
        headers={"Authorization": "Bearer {}".format(api_token)},
        timeout=TASK_CONFIG["http_timeout"],
    )
    result = resp.json()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result.get("result")


def _zabbix_group_ids(api_url, api_token, group_names):
    """把主机组名解析成 groupid 列表"""
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {
            "output": ["groupid", "name"],
            "filter": {"name": group_names},
        },
        "id": 1,
    }
    try:
        groups = _zabbix_call(api_url, api_token, payload)
    except Exception as e:
        logger.error(f"Zabbix 主机组查询失败: {e}")
        return []

    found = {g.get("name") for g in groups or []}
    missing = [name for name in group_names if name not in found]
    if missing:
        logger.warning(f"Zabbix 主机组不存在: {missing}")
    return [g.get("groupid") for g in groups or [] if g.get("groupid")]


def _pick_zabbix_interface(interfaces):
    """
    取主机的主接口，优先 SNMP 接口（type=2）

    Zabbix 一台主机可挂多个接口（agent/SNMP/JMX/IPMI），网络设备对账要的是 SNMP 那一组
    """
    if not interfaces:
        return None
    for iface in interfaces:
        if iface.get("type") == "2" and iface.get("main") == "1":
            return iface
    for iface in interfaces:
        if iface.get("type") == "2":
            return iface
    return interfaces[0]


def collect_platform_devices():
    """
    从 netops 平台数据库读取已纳管设备列表

    来源：CollectDB.get_device_list()，iplist LEFT JOIN devices，
    默认只取非屏蔽设备（admin_status <> '1'）
    """
    from tables.CollectDB import CollectDB

    try:
        devices = CollectDB().get_device_list()
    except Exception as e:
        logger.error(f"平台设备列表读取失败: {e}")
        return []

    collected_at = int(time.time())
    records = []

    for device in devices:
        records.append({
            "source": SOURCE_PLATFORM,
            "key": normalize_ip(device.get("ip")),
            "name": device.get("sysname") or "",
            "ip": normalize_ip(device.get("ip")),
            # devices 表采集失败时字段为空，只有 sys_type 的系统可能是老设备
            "vendor_model": " ".join(filter(None, [device.get("vendor"), device.get("sys_type")])),
            "location": "",
            "status": "collected" if device.get("sysname") else "no_snmp",
            "sysdesc": device.get("sysdesc") or "",
            "collected_at": collected_at,
        })

    no_snmp = sum(1 for r in records if r["status"] == "no_snmp")
    logger.info(f"平台设备拉取完成：共 {len(records)} 台，其中无 SNMP 信息 {no_snmp} 台")
    return records


def scan_managed_subnets():
    """
    扫描管理网段，探测存活设备（暂搁置，改用 collect_platform_devices）

    TODO: 网段清单来源待定（IPAM 管理网段 / Ocean 网段字段 / 管理 VLAN）
    TODO: 探测方式：ICMP + SNMP(sysName/sysDescr) + 端口
    TODO: 排除清单（打印机、终端、临时设备），控制并发避免设备 CPU 抖动
    """
    logger.warning("管理网段扫描未实现（PRD-01 3.3 / 3.4）")
    return []


# ============================================
# 二、匹配层
# ============================================

def normalize_ip(ip):
    """IP 归一化，作为首选匹配键"""
    return (ip or "").strip()


def normalize_name(name):
    """
    设备名归一化：去域名后缀、统一小写、去首尾 # 填充

    Ocean 的设备名会以 # 补齐宽度（如 sw-01####），直接比较会匹配不上
    """
    name = (name or "").strip().lower()
    for suffix in (".vdian.net", ".local"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip("#").strip()


# 参与匹配的来源；网段扫描接入后加 SOURCE_SCAN
MATCH_SOURCES = (SOURCE_OCEAN, SOURCE_ZABBIX, SOURCE_PLATFORM)


def build_device_index(records, source):
    """
    按归一化设备名建立索引

    三源的管理 IP 可能不一致（CMDB 管理 IP / Zabbix SNMP 接口 IP / 采集纳管 IP），
    不能作为匹配键。名称缺失的记录退回用 IP 作键。
    """
    index = {}
    conflicts = []

    for record in records:
        name_key = normalize_name(record.get("name"))

        if name_key:
            key = name_key
        else:
            key = normalize_ip(record.get("ip"))
            if not key:
                conflicts.append({
                    "source": source,
                    "key": "",
                    "reason": "缺少设备名和管理 IP",
                    "record": record,
                })
                continue

        if key in index:
            conflicts.append({
                "source": source,
                "key": key,
                "reason": "同一设备名多条记录",
                "record": record,
                "exist": index[key],
            })
            continue
        index[key] = record

    return index, conflicts


def match_sources(source_records):
    """
    按归一化设备名匹配各来源记录

    三源使用的管理 IP 可能不一致，匹配只认设备名，IP 仅作展示

    返回：
    - matched: {name_key: {source: rec|None}}
    - source_conflicts: 来源内部重复/缺标识的记录
    """
    indexes = {}
    conflicts = []
    for source in MATCH_SOURCES:
        index, source_conflicts = build_device_index(source_records.get(source) or [], source)
        indexes[source] = index
        conflicts.extend(source_conflicts)

    all_keys = set()
    for index in indexes.values():
        all_keys |= set(index)

    matched = {
        key: {source: indexes[source].get(key) for source in MATCH_SOURCES}
        for key in all_keys
    }

    return matched, conflicts


def _source_names(sources):
    """取各来源的非空设备名"""
    return {
        source: rec.get("name", "")
        for source, rec in sources.items()
        if rec and rec.get("name")
    }


def _source_ips(sources):
    """取各来源的非空管理 IP"""
    return {
        source: ip
        for source in MATCH_SOURCES
        if (ip := normalize_ip((sources.get(source) or {}).get("ip")))
    }


def _display_name(sources):
    """展示用设备名：优先取 Ocean 原名"""
    names = _source_names(sources)
    return names.get(SOURCE_OCEAN) or next(iter(names.values()), "")


# ============================================
# 三、分类层
# ============================================

def classify(matched):
    """
    按 PRD-01 第五章规则输出差异明细

    匹配键是归一化设备名，差异记录的 ip 取 Ocean 管理 IP（无则取其他来源的 IP）

    口径：Zabbix / 平台采集能拿到的设备，Ocean 的 operationStatus 不应为
    入库/待报废。因此"状态过期"（I）与"未登记"（E/F）都要反过来修正 CMDB，
    而不是反过来删监控。

    三源管理 IP 不一致属于正常现象，不做差异，仅在记录里展示各源 IP
    """
    diffs = []

    for key, sources in matched.items():
        ocean = sources[SOURCE_OCEAN]
        has_ocean = ocean is not None
        has_zabbix = sources[SOURCE_ZABBIX] is not None
        has_platform = sources[SOURCE_PLATFORM] is not None
        collected = has_zabbix or has_platform

        # CMDB 状态不在线的设备不参与分类：它已登记过，不能算「CMDB 未登记」
        if has_ocean and (ocean.get("operation_status") or "").strip() != OCEAN_STATUS_ONLINE:
            continue

        display_name = _display_name(sources)
        names = _source_names(sources)
        ips = _source_ips(sources)
        ip = ips.get(SOURCE_OCEAN) or next(iter(ips.values()), "")

        ocean_status = ocean.get("operation_status", "") if ocean else ""
        ocean_stale = ocean_status in OCEAN_STATUS_INVALID

        if collected and ocean_stale:
            # CMDB 登记了但状态过期：以采集结果为准，反向修正 CMDB
            diff_type = DIFF_I
            note = f"CMDB 状态为「{ocean_status}」但 {_source_desc(has_zabbix, has_platform)} 可采集，需修正 CMDB 为正常"
        elif collected and has_ocean:
            if has_zabbix and has_platform:
                diff_type, note = DIFF_A, "三方一致"
            elif has_zabbix:
                diff_type, note = DIFF_B, "监控在、平台未纳管，需加入平台采集"
            else:
                diff_type, note = DIFF_C, "平台有采集、Zabbix 无监控，需纳入 Zabbix"
        elif has_ocean and ocean_stale:
            # 采不到且 CMDB 状态为入库/待报废，两者一致，无需处理
            diff_type, note = DIFF_A, f"CMDB 状态为「{ocean_status}」且采不到，状态一致"
        elif has_ocean:
            diff_type, note = DIFF_D, "疑似僵尸资产，核实是否已下架"
        elif has_zabbix:
            diff_type, note = DIFF_E, "CMDB 未登记（有监控），需补登记"
        elif has_platform:
            diff_type, note = DIFF_F, "CMDB 未登记（平台已纳管），需补登记"
        else:
            # 三源都无记录的情况不应出现在 matched 中
            continue

        diffs.append({
            "key": key,
            "name": display_name,
            "ip": ip,
            "ips": ips,
            "names": names,
            "diff_type": diff_type,
            "ocean": ocean,
            "zabbix": sources[SOURCE_ZABBIX],
            "platform": sources[SOURCE_PLATFORM],
            "scan": sources.get(SOURCE_SCAN),
            "note": note,
            "handler_status": "待处理",
            "owner": "",
        })

    return diffs


def _source_desc(has_zabbix, has_platform):
    """描述一台设备被哪些采集来源看到，用于差异说明"""
    parts = []
    if has_zabbix:
        parts.append("Zabbix")
    if has_platform:
        parts.append("平台采集")
    return " + ".join(parts)


# ============================================
# 四、豁免与容差
# ============================================

def load_exemptions():
    """
    读取豁免清单

    TODO: 豁免清单需落库管理（审批人、原因、复核时间），当前先用本地 JSON 占位
    格式：[{"name": "设备名", "ip": "x.x.x.x", "reason": "原因", "owner": "负责人", "review_date": "2026-12-31"}]
    name 与 ip 至少填一个；同时填了两个键都会命中
    """
    path = Path(TASK_CONFIG["exempt_file"])
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception as e:
        logger.error(f"读取豁免清单失败: {e}")
        return {}

    exemptions = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name_key = normalize_name(item.get("name"))
        ip_key = normalize_ip(item.get("ip"))
        if name_key:
            exemptions[name_key] = item
        if ip_key:
            exemptions.setdefault(ip_key, item)
    return exemptions


def apply_exemptions(diffs, exemptions):
    """命中豁免清单的差异标记为 H，不参与告警；按设备名（归一化）或 IP 匹配"""
    for diff in diffs:
        exempt = exemptions.get(diff["key"]) or exemptions.get(diff["ip"])
        if exempt:
            diff["diff_type"] = DIFF_H
            diff["exempt_reason"] = exempt.get("reason", "")
            diff["owner"] = exempt.get("owner", "")
            diff["note"] = f"豁免：{diff['exempt_reason']}"
    return diffs


def apply_tolerance(diffs, batch_id):
    """
    容差规则：连续 N 次对账缺失才判定下线

    TODO: 需要读取最近 N 次快照的 recon_diff，判断该 IP 是否连续缺失。
          首次上线时无可比对历史，本次结果全部按首次出现处理。
    """
    rounds = TASK_CONFIG["offline_confirm_rounds"]
    for diff in diffs:
        diff["first_seen_batch"] = batch_id
        diff["missing_rounds"] = 0
        # 只有 D 是"除 CMDB 外三源皆无"的类型，其他类型设备本身仍在线，不适用下线容差
        if diff["diff_type"] == DIFF_D:
            if diff["missing_rounds"] < rounds:
                diff["note"] += f"（未达连续 {rounds} 次缺失阈值，暂不判定下线）"
    return diffs


# ============================================
# 五、持久化层
#
# 对应 PRD-01 6.5 数据模型：
#   recon_snapshot  批次 ID、采集时间、来源、设备总数
#   recon_device    批次 ID、来源、来源主键、设备名、IP、型号、位置、状态
#   recon_diff      批次 ID、匹配键、差异类型、三源状态、处理状态、负责人、动作、备注
#
# TODO: 建表 SQL 补进 scripts/db_create.sql，并在 tables/ 下新增 ReconDB.py
# TODO: 写入前先删同批次旧数据，保证重跑幂等
# ============================================

def persist_snapshot(batch_id, start_time, source_records):
    """落库本次对账快照（三源各自总数）"""
    summary = {source: len(records) for source, records in source_records.items()}
    logger.info(f"[TODO] 写入对账快照 batch={batch_id} time={start_time} summary={summary}")
    return summary


def persist_devices(batch_id, source_records):
    """落库三源设备明细"""
    total = sum(len(records) for records in source_records.values())
    logger.info(f"[TODO] 写入设备明细 batch={batch_id} 共 {total} 条")


def persist_diffs(batch_id, diffs):
    """落库差异明细，返回本次新建的差异（用于通知）"""
    counts = {}
    for diff in diffs:
        counts[diff["diff_type"]] = counts.get(diff["diff_type"], 0) + 1
    logger.info(f"[TODO] 写入差异明细 batch={batch_id} 分类统计={counts}")
    return diffs


# ============================================
# 六、通知
# ============================================

def notify_new_diffs(new_diffs):
    """
    推送本次新增差异

    TODO: 与上一次快照比对，只推"本次有、上次无"的差异（PRD 6.4）
    TODO: 接入平台已有消息/告警通道，不新增通道
    TODO: G/F 类型优先推送（冲突与野设备处置优先级最高）
    """
    pending = [d for d in new_diffs if d["diff_type"] not in (DIFF_A, DIFF_H)]
    logger.info(f"[TODO] 待推送新增差异 {len(pending)} 条")


# ============================================
# 主执行流程
# ============================================

def run(batch_id=None):
    """
    主执行函数

    Args:
        batch_id: 指定批次 ID（用于补跑），为空时按执行时间生成
    """
    if not TASK_CONFIG["enabled"]:
        logger.info("设备对账任务已禁用")
        return

    start_time = int(time.time())
    batch_id = batch_id or TASK_CONFIG["batch_id"] or time.strftime("%Y%m%d%H%M%S", time.localtime(start_time))

    logger.info("=" * 60)
    logger.info(f"开始执行设备对账任务 batch={batch_id}")
    logger.info("=" * 60)

    try:
        # 1. 采集各来源数据
        source_records = {
            SOURCE_OCEAN: collect_ocean_devices(),
            SOURCE_ZABBIX: collect_zabbix_hosts(),
            SOURCE_PLATFORM: collect_platform_devices(),
        }

        empty_sources = [source for source, records in source_records.items() if not records]
        if empty_sources:
            # 某源为空会导致大量假差异，直接终止，避免污染快照
            logger.error(f"以下数据源为空，本次对账终止: {', '.join(empty_sources)}")
            return

        persist_snapshot(batch_id, start_time, source_records)
        persist_devices(batch_id, source_records)

        # 2. 匹配
        matched, source_conflicts = match_sources(source_records)
        if source_conflicts:
            logger.warning(f"来源内部异常记录 {len(source_conflicts)} 条（缺标识或设备名重复）")
        logger.info(f"匹配完成：设备 {len(matched)} 台")

        # 3. 分类
        diffs = classify(matched)

        # 4. 豁免与容差
        diffs = apply_exemptions(diffs, load_exemptions())
        diffs = apply_tolerance(diffs, batch_id)

        # 5. 落库
        new_diffs = persist_diffs(batch_id, diffs)

        # 6. 通知
        notify_new_diffs(new_diffs)

        # 7. 汇总
        counts = {}
        for diff in diffs:
            counts[diff["diff_type"]] = counts.get(diff["diff_type"], 0) + 1
        aligned = counts.get(DIFF_A, 0)
        aligned_rate = round(aligned / len(diffs) * 100, 2) if diffs else 0

        logger.info("=" * 60)
        logger.info(f"设备对账任务完成 batch={batch_id}，耗时 {int(time.time()) - start_time} 秒")
        logger.info(f"设备总数: {len(diffs)}，对齐: {aligned}，对齐率: {aligned_rate}%")
        for diff_type in sorted(counts):
            logger.info(f"  类型 {diff_type}: {counts[diff_type]} 台  {DIFF_TYPE_DESC.get(diff_type, '')}")
        logger.info("=" * 60)

        summary = {
            "batch_id": batch_id,
            "total": len(diffs),
            "aligned_rate": aligned_rate,
            "counts": counts,
            "diffs": diffs,
            "source_conflicts": source_conflicts,
        }

        # 8. 展示
        print_report(summary)

        return summary

    except Exception as e:
        logger.error(f"设备对账任务执行失败: {e}")
        raise


def print_report(summary):
    """
    对账结果展示（人工核对用），每条差异逐行输出，不做取样

    只在 run() 里调用，注释掉 run() 末尾的 print_report 即可取消输出
    """
    print()
    print("=" * 70)
    print(f"批次 {summary['batch_id']}  设备 {summary['total']} 台  对齐率 {summary['aligned_rate']}%")
    for diff_type in sorted(summary["counts"]):
        print(f"  类型 {diff_type}: {summary['counts'][diff_type]} 台  {DIFF_TYPE_DESC.get(diff_type, '')}")
    print("=" * 70)

    by_type = {}
    for diff in summary["diffs"]:
        by_type.setdefault(diff["diff_type"], []).append(diff)

    for diff_type in sorted(by_type):
        if diff_type == DIFF_A:
            continue
        print()
        print(f"---- 类型 {diff_type}（{len(by_type[diff_type])} 台）{DIFF_TYPE_DESC.get(diff_type, '')} ----")
        for diff in by_type[diff_type]:
            ocean = diff.get("ocean") or {}
            zabbix = diff.get("zabbix") or {}
            platform = diff.get("platform") or {}
            print(
                "  {ip:<16} {name:<30} {note}".format(
                    ip=diff["ip"] or "-", name=diff["name"], note=diff["note"]
                )
            )
            print(
                "      ocean={o_status:<6} {o_model:<22} | zabbix={z_state:<10} {z_model:<22} | platform={p_state:<9} {p_model}".format(
                    o_status=ocean.get("operation_status", "-"),
                    o_model=ocean.get("vendor_model", "-") or "-",
                    z_state=zabbix.get("status", "-"),
                    z_model=zabbix.get("vendor_model", "-") or "-",
                    p_state=platform.get("status", "-"),
                    p_model=platform.get("vendor_model", "-") or "-",
                )
            )
            print("      管理IP  {}".format(
                " | ".join(f"{source}={ip}" for source, ip in diff["ips"].items()) or "-"
            ))

    if summary["source_conflicts"]:
        print()
        print(f"---- 来源内部异常（{len(summary['source_conflicts'])} 条）----")
        for item in summary["source_conflicts"]:
            record = item.get("record") or {}
            line = f"  {item['source']:<9} {item['reason']:<18} {record.get('ip', '-') or '-':<16} {record.get('name', '')}"
            if item["source"] == SOURCE_OCEAN:
                line += f"  sn={record.get('sn', '') or '-'}"
            print(line)
            exist = item.get("exist")
            if exist:
                exist_line = f"      已存在: {exist.get('ip', '-')} {exist.get('name', '')}"
                if item["source"] == SOURCE_OCEAN:
                    exist_line += f"  sn={exist.get('sn', '') or '-'}"
                print(exist_line)


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('../logs/recon_device_inventory.log')
        ]
    )

    logger.info("手动触发设备对账任务")

    try:
        run()
    except KeyboardInterrupt:
        logger.info("\n任务被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        sys.exit(1)

    # rds = collect_ocean_devices()
    # for rd in rds:
    #     if "rsw1_corp_wf_m04_1.21" == rd["name"]:
    #         print(rd)