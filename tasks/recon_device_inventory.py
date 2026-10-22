"""
设备对账定时任务（PRD-01）

功能：对齐 Ocean（CMDB）、Zabbix、netops 平台采集三个来源的设备清单，
逐台输出差异类型与处理依据。

执行流程：
1. 采集三源数据（Ocean / Zabbix / 平台采集），统一为标准设备记录
2. 按归一化设备名匹配三源记录，识别同一台设备
3. 剔除命中豁免清单的设备（不参与分类）
4. 按 PRD-01 第五章规则分类 A~I
5. 应用容差规则
6. 落库快照、设备明细、差异明细
7. 推送本次新增的差异

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
    # 绝对路径：相对路径按进程工作目录解析，定时任务换目录启动会读到别的文件
    "exempt_file": str(project_root / "config" / "recon_exempt.json"),  # 豁免清单，命中的设备不参与分类与告警
    "ocean_page_size": 100,         # Ocean 分页大小
    "ocean_max_pages": 500,         # 分页上限，防止接口异常导致死循环
    "zabbix_group_names": [         # Zabbix 交换机/防火墙主机组（精确匹配），必填
        "bj-office", "cq-office", "dg-office", "hz-office", "sz-office",
        "ts-office", "ts-hengfeng-office", "wf-office",
        "dc03-switch", "dc05-switch", "dc07-switch", "dc09-switch", "dc19-switch",
    ],
    "http_timeout": 30,             # HTTP 请求超时（秒）
}

# 「wjf 1s ICMP Ping Alarm」是全网兜底的 ping 监控模板：
# 后续未加监控的设备统一补挂该模板，因此仅挂它的主机也是真实设备，纳入对账
# 此类主机打 ping_only 标记，供后续补充 SNMP 监控时筛选
ZABBIX_PING_TEMPLATES = ("wjf 1s ICMP Ping Alarm",)

# Ocean 接口地址
OCEAN_API_BASE = "http://api-o2.vdian.net/v1"

# Ocean 状态口径：status 只有「正常」算在线，其余（待报废/维修等）一律视为不在线
OCEAN_STATUS_ONLINE = "正常"

# Ocean operationStatus 口径：Zabbix / 平台采集得到的设备，状态应为「正常」
# 实际样本中还有 入库/待报废/报废/搬迁/待返修 等取值，统一按「非正常即为状态过期」判定
OCEAN_STATUS_ACTIVE = "正常"

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
DIFF_I = "I"  # Ocean 状态过期：采得到但 operationStatus 非「正常」

DIFF_TYPE_DESC = {
    DIFF_A: "三方一致",
    DIFF_B: "平台未纳管（Zabbix 有、平台无）",
    DIFF_C: "未纳入监控（平台有、Zabbix 无）",
    DIFF_D: "CMDB 独有，疑似僵尸资产",
    DIFF_E: "CMDB 未登记（仅 Zabbix 有）",
    DIFF_F: "CMDB 未登记（仅平台有）",
    DIFF_I: "CMDB 状态过期（采得到但状态非正常）",
}

# 分类时的剔除口径，用于保证「匹配数 = 差异数 + 豁免数 + 剔除数」
DROP_STALE_OFFLINE = "CMDB 状态非正常且采不到（状态一致，无需处理）"


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

    仅挂「wjf 1s ICMP Ping Alarm」的主机也计入：该模板是未加监控设备的兜底 ping 监控，
    有它说明已经纳入监控，对账时应视为 Zabbix 侧存在（否则会被误判为 C 类未纳监控）。
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

        # 仅挂 ping 模板的主机：真实设备，但只纳入了 ping 监控，打标便于后续补监控
        is_ping_only = _is_ping_only_host(host)
        if is_ping_only:
            ping_only += 1

        ip = _zabbix_host_ip(host.get("interfaces") or [])
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
            "ping_only": is_ping_only,
            "collected_at": collected_at,
        })

    if no_ip:
        logger.warning(f"Zabbix 主机中 {no_ip} 台未取到管理 IP（useip=0 或无接口），不参与 IP 匹配")
    logger.info(f"Zabbix 拉取完成：组 {group_names} 共 {len(records)} 台，其中仅 ping 监控 {ping_only} 台")
    return records


def _is_ping_only_host(host):
    """主机所挂模板全部属于 ping 类模板时返回 True（真实设备，只是未加深度监控）"""
    templates = {
        (t.get("name") or "").strip()
        for t in (host.get("parentTemplates") or [])
        if t.get("name")
    }
    if not templates:
        return False
    return templates.issubset(ZABBIX_PING_TEMPLATES)


def _zabbix_host_ip(interfaces):
    """
    取主机管理 IP

    主接口可能是 agent 接口（useip=1），但网络设备的地址在 SNMP 接口上；
    仅挂 ping 模板的主机则只有一个 ICMP 接口。按主接口 → SNMP → 任一 useip=1 的顺序兜底
    """
    candidates = []
    primary = _pick_zabbix_interface(interfaces)
    if primary:
        candidates.append(primary)
    candidates.extend(interfaces)
    for iface in candidates:
        if iface.get("useip") == "1":
            ip = normalize_ip(iface.get("ip"))
            if ip:
                return ip
    return ""


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

def classify(matched, exemptions=None):
    """
    按 PRD-01 第五章规则输出差异明细

    匹配键是归一化设备名，差异记录的 ip 取 Ocean 管理 IP（无则取其他来源的 IP）

    口径：Zabbix / 平台采集能拿到的设备，Ocean 的 operationStatus 不应为非「正常」。
    因此"状态过期"（I）与"未登记"（E/F）都要反过来修正 CMDB，而不是反过来删监控。
    Ocean 状态非正常且也采不到的设备两边一致，不产生差异，单独计入 dropped。

    三源管理 IP 不一致属于正常现象，不做差异，仅在记录里展示各源 IP

    Args:
        matched: match_sources() 的匹配结果
        exemptions: 豁免索引，见 load_exemptions()；命中者不参与分类

    Returns:
        (diffs, exempted, dropped)：
        diffs 差异明细；exempted 被豁免剔除的设备记录；
        dropped 为 {口径说明: [设备记录]}，是既不产生差异也不豁免的设备，
        用于核对 len(matched) == len(diffs) + len(exempted) + 剔除总数
    """
    exemptions = exemptions or {}
    diffs = []
    exempted = []
    dropped = {}

    def _drop(reason, key, sources):
        dropped.setdefault(reason, []).append(_build_drop_record(key, sources))

    for key, sources in matched.items():
        # 豁免优先于一切分类：命中设备不进入 A~I，也不产生告警
        exempt = find_exemption(exemptions, key, sources)
        if exempt:
            exempted.append(_build_exempt_record(key, sources, exempt))
            continue

        ocean = sources[SOURCE_OCEAN]
        has_ocean = ocean is not None
        has_zabbix = sources[SOURCE_ZABBIX] is not None
        has_platform = sources[SOURCE_PLATFORM] is not None
        collected = has_zabbix or has_platform

        display_name = _display_name(sources)
        names = _source_names(sources)
        ips = _source_ips(sources)
        ip = ips.get(SOURCE_OCEAN) or next(iter(ips.values()), "")

        ocean_status = (ocean.get("operation_status") or "").strip() if ocean else ""
        # 只要不是「正常」就算过期：样本里有 入库/待报废/报废/搬迁/待返修/维修 等多种取值
        ocean_stale = has_ocean and ocean_status != OCEAN_STATUS_ACTIVE

        if has_ocean and ocean_stale and not collected:
            # CMDB 状态非正常、三源也采不到：两边一致，无需处理，不计入差异
            _drop(DROP_STALE_OFFLINE, key, sources)
            continue

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

    return diffs, exempted, dropped


def _build_drop_record(key, sources):
    """未产生差异也未豁免的设备记录，仅用于核对数量"""
    return {
        "key": key,
        "name": _display_name(sources),
        "ip": next(iter(_source_ips(sources).values()), ""),
        "ocean_status": (sources.get(SOURCE_OCEAN) or {}).get("operation_status", ""),
        "sources": [source for source in MATCH_SOURCES if sources.get(source)],
    }


def _build_exempt_record(key, sources, exempt):
    """被豁免剔除的设备记录，仅用于日志与展示，不落库为差异"""
    names = _source_names(sources)
    ips = _source_ips(sources)
    return {
        "key": key,
        "name": _display_name(sources),
        "ip": ips.get(SOURCE_OCEAN) or next(iter(ips.values()), ""),
        "ips": ips,
        "names": names,
        "exempt_match": exempt.get("_match", ""),   # 命中的是设备名还是 IP
        "exempt_reason": exempt.get("reason", ""),
        "owner": exempt.get("owner", ""),
        "review_date": exempt.get("review_date", ""),
    }


def _source_desc(has_zabbix, has_platform):
    """描述一台设备被哪些采集来源看到，用于差异说明"""
    parts = []
    if has_zabbix:
        parts.append("Zabbix")
    if has_platform:
        parts.append("平台采集")
    return " + ".join(parts)


# ============================================
# 四、容差
# ============================================

def load_exemptions():
    """
    读取豁免清单

    命中的设备不参与分类：不进 A~I、不告警、不计入设备总数与对齐率。

    TODO: 豁免清单需落库管理（审批人、原因、复核时间），当前先用本地 JSON 占位
    格式：[{"name": "设备名", "ip": "x.x.x.x", "reason": "原因", "owner": "负责人", "review_date": "2026-12-31"}]
    name 与 ip 至少填一个；同时填了两个键都会被尝试匹配。
    设备名与 IP 分两个索引存放，避免同名 IP 串键。

    Returns:
        {"names": {归一化设备名: item}, "ips": {IP: item}}
    """
    path = Path(TASK_CONFIG["exempt_file"])
    empty = {"names": {}, "ips": {}}
    if not path.exists():
        logger.warning(f"豁免清单不存在，本次不豁免任何设备: {path}")
        return empty
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception as e:
        logger.error(f"读取豁免清单失败: {e}")
        return empty

    if not isinstance(items, list):
        logger.error(f"豁免清单格式错误，应为 JSON 数组: {path}")
        return empty

    exemptions = {"names": {}, "ips": {}}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        ip = item.get("ip")
        name_key = normalize_name(name) if isinstance(name, str) else ""
        ip_key = normalize_ip(ip) if isinstance(ip, str) else ""
        if name_key:
            if name_key in exemptions["names"]:
                logger.warning(f"豁免清单设备名重复，后一条覆盖前一条: {name}")
            exemptions["names"][name_key] = item
        if ip_key:
            if ip_key in exemptions["ips"]:
                logger.warning(f"豁免清单 IP 重复，后一条覆盖前一条: {ip}")
            exemptions["ips"][ip_key] = item
        if not name_key and not ip_key:
            logger.warning(f"豁免清单存在既无 name 也无 ip 的条目，已跳过: {item}")

    logger.info(
        f"豁免清单加载完成：设备名 {len(exemptions['names'])} 条，IP {len(exemptions['ips'])} 条"
    )
    return exemptions


def source_counts(source_records):
    """
    三源数量口径

    - Ocean：只算 operationStatus 为「正常」的记录（其余状态是已下线/待清理，不参与对账）
    - Zabbix：采集到的全部启用主机
    - 平台：采集到的全部纳管设备

    只输出这三个数，不做逐源拆解。豁免清单只用于记录处理不了的设备，不计入这里的任何分类口径。
    """
    ocean_records = source_records.get(SOURCE_OCEAN) or []
    counts = {
        SOURCE_OCEAN: sum(
            1 for r in ocean_records
            if (r.get("operation_status") or "").strip() == OCEAN_STATUS_ACTIVE
        ),
        SOURCE_ZABBIX: len(source_records.get(SOURCE_ZABBIX) or []),
        SOURCE_PLATFORM: len(source_records.get(SOURCE_PLATFORM) or []),
    }
    logger.info(
        f"三源数量：Ocean 正常 {counts[SOURCE_OCEAN]} 台，"
        f"Zabbix {counts[SOURCE_ZABBIX]} 台，平台 {counts[SOURCE_PLATFORM]} 台"
    )
    return counts


def explain_gap(source_records, matched, diffs, exempted, dropped, source_conflicts):
    """
    解释各来源采集数的构成，A 类只统计三方都有的设备

    三个来源口径不同（Ocean 建档全量 / Zabbix 监控主机 / 平台纳管设备），数量本来就不相等。
    按来源原始记录逐条分桶，保证「采集 = 各桶之和」：

        采集 = A + 其他差异 + Ocean 状态非正常 + 豁免 + 不参与对账 + 未参与匹配

    "Ocean 状态非正常"只对 Ocean 有意义：这些记录已被采集进来（非空设备名），
    只是 operationStatus 不是「正常」，不进 A。Zabbix / 平台没有这个分桶。
    "未参与匹配"是来源内部重名或缺标识、在 build_device_index 阶段就被丢弃的记录。
    """
    a_keys = set()
    other_keys = set()
    for diff in diffs:
        (a_keys if diff["diff_type"] == DIFF_A else other_keys).add(diff["key"])

    exempt_keys = {item["key"] for item in exempted or []}
    drop_keys = {item["key"] for items in (dropped or {}).values() for item in items}

    gap_notes = {}
    for source in MATCH_SOURCES:
        records = source_records.get(source) or []
        bucket = {"a": 0, "other": 0, "non_normal": 0, "exempt": 0, "dropped": 0}

        for record in records:
            # Ocean 状态非正常的记录直接归入该桶，不再看是否命中
            if source == SOURCE_OCEAN and (
                (record.get("operation_status") or "").strip() != OCEAN_STATUS_ACTIVE
            ):
                bucket["non_normal"] += 1
                continue

            key = normalize_name(record.get("name")) or normalize_ip(record.get("ip"))
            if key in exempt_keys:
                bucket["exempt"] += 1
            elif key in a_keys:
                bucket["a"] += 1
            elif key in drop_keys:
                bucket["dropped"] += 1
            elif key in other_keys:
                bucket["other"] += 1

        pulled = len(records)
        accounted = sum(bucket.values())
        unmatched = pulled - accounted
        conflicts = sum(1 for item in (source_conflicts or []) if item["source"] == source)

        # 只列非零分桶：结果为 0 的类别不带出来，避免结论区噪音
        parts = [f"A {bucket['a']}"]
        if bucket["other"]:
            parts.append(f"其他差异 {bucket['other']}")
        if bucket["non_normal"]:
            parts.append(f"{bucket['non_normal']}（状态非正常）")
        if bucket["exempt"]:
            parts.append(f"豁免 {bucket['exempt']}")
        if bucket["dropped"]:
            parts.append(f"不参与对账 {bucket['dropped']}")
        if unmatched:
            parts.append(f"未参与匹配 {unmatched}（重名/缺标识 {conflicts}）")

        line = f"{source:<8} 采集 {pulled} = " + " + ".join(parts)
        gap_notes[source] = dict(bucket, pulled=pulled, unmatched=unmatched, conflicts=conflicts, line=line)
        logger.info(f"差额说明 {line}")
    return gap_notes


def find_exemption(exemptions, key, sources):
    """
    判断一台匹配后的设备是否命中豁免清单

    先按匹配键（归一化设备名）匹配，再按三个来源各自的管理 IP 匹配。
    命中返回豁免条目（带 _match 标识命中方式），未命中返回 None。
    """
    if not exemptions:
        return None

    name_item = exemptions["names"].get(key)
    if name_item:
        return dict(name_item, _match="name")

    for source in MATCH_SOURCES:
        ip = normalize_ip((sources.get(source) or {}).get("ip"))
        if not ip:
            continue
        ip_item = exemptions["ips"].get(ip)
        if ip_item:
            return dict(ip_item, _match="ip")

    return None


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
    pending = [d for d in new_diffs if d["diff_type"] != DIFF_A]
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

        # 3. 豁免：先于分类执行，命中的设备不进入 A~I
        exemptions = load_exemptions()

        # 4. 分类（豁免设备已剔除）
        diffs, exempted, dropped = classify(matched, exemptions)
        dropped_total = sum(len(items) for items in dropped.values())
        if exempted or dropped_total:
            logger.info(f"豁免 {len(exempted)} 台、不参与对账（CMDB 非正常且采不到）{dropped_total} 台")
        # 数量必须闭合，否则说明分类里有分支静默丢设备
        if len(matched) != len(diffs) + len(exempted) + dropped_total:
            logger.error(
                f"对账数量不闭合：匹配 {len(matched)} ≠ 差异 {len(diffs)} + 豁免 {len(exempted)} "
                f"+ 不参与 {dropped_total}"
            )

        # 5. 三源数量口径 + 差额拆解
        counts_by_source = source_counts(source_records)
        gap_notes = explain_gap(
            source_records, matched, diffs, exempted, dropped, source_conflicts
        )

        # 6. 容差
        diffs = apply_tolerance(diffs, batch_id)

        # 7. 落库
        new_diffs = persist_diffs(batch_id, diffs)

        # 8. 通知
        notify_new_diffs(new_diffs)

        # 9. 汇总
        counts = {}
        for diff in diffs:
            counts[diff["diff_type"]] = counts.get(diff["diff_type"], 0) + 1
        aligned = counts.get(DIFF_A, 0)
        aligned_rate = round(aligned / len(diffs) * 100, 2) if diffs else 0

        logger.info("=" * 60)
        logger.info(f"设备对账任务完成 batch={batch_id}，耗时 {int(time.time()) - start_time} 秒")
        logger.info(
            f"设备总数: {len(diffs)}（另有豁免 {len(exempted)} 台未参与），"
            f"对齐: {aligned}，对齐率: {aligned_rate}%"
        )
        for diff_type in sorted(counts):
            logger.info(f"  类型 {diff_type}: {counts[diff_type]} 台  {DIFF_TYPE_DESC.get(diff_type, '')}")
        logger.info("=" * 60)

        summary = {
            "batch_id": batch_id,
            "total": len(diffs),
            "aligned_rate": aligned_rate,
            "counts": counts,
            "diffs": diffs,
            "exempted": exempted,
            "dropped": dropped,
            "counts_by_source": counts_by_source,
            "gap_notes": gap_notes,
            "source_conflicts": source_conflicts,
        }

        # 9. 展示
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
    print(
        f"批次 {summary['batch_id']}  设备 {summary['total']} 台  对齐率 {summary['aligned_rate']}%"
        f"  豁免 {len(summary.get('exempted') or [])} 台未参与"
    )
    for diff_type in sorted(summary["counts"]):
        print(f"  类型 {diff_type}: {summary['counts'][diff_type]} 台  {DIFF_TYPE_DESC.get(diff_type, '')}")

    counts_by_source = summary.get("counts_by_source") or {}
    if counts_by_source:
        print("-" * 70)
        print(
            "  三源数量：Ocean 正常 {} 台，Zabbix {} 台，平台 {} 台".format(
                counts_by_source.get(SOURCE_OCEAN, 0),
                counts_by_source.get(SOURCE_ZABBIX, 0),
                counts_by_source.get(SOURCE_PLATFORM, 0),
            )
        )
    gap_notes = summary.get("gap_notes") or {}
    if gap_notes:
        for source in MATCH_SOURCES:
            row = gap_notes.get(source)
            if row:
                print(f"  {row['line']}")
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