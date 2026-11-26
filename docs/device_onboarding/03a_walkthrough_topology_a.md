# 拓扑 A 配置生成流程预演（核心—汇聚—接入，传统三层）

## 文档信息

- 所属：[模块 3 业务架构](./03_business_architecture.md)
- 目的：用具体数字走通一次三级结构上线，验证片段+意图模型是否够用，并暴露设计约束
- 结构：结构一（传统二层，网关在核心层）
- 厂商：Cisco NX-OS + vPC

> **重要更正（2026-11-24 实测后）**：本预演最初以 DC09 为场景，但实测证明 **DC09 实际是结构二（全三层 BGP，网关在接入层）**，不是结构一。详见[附录 A](#附录-adc09-实测结构二形态)。本文档保留结构一的预演逻辑（三级结构的流程推导仍然有效），但场景中的机房/网段/VLAN 均应视为**假设值**，不代表 DC09 现网。结构二的预演见模块 3 文档。

## 一、场景设定

DC09 新建 MDU5，业务类型 Normal，接入层 2 台成对。汇聚层、核心层已在网。

```
        csw1_dc09_m01 ══════ csw2_dc09_m01        已在网，vPC domain 1
              ╲                    ╱               网关：SVI + HSRP
          Po50 ╲                  ╱ Po50           下行到汇聚对
                ╲                ╱
       asw1_mdu5_dc09_m01 ══ asw2_mdu5_dc09_m01    已在网，vPC domain 50
              ╲                    ╱               纯二层透传
         Po105 ╲                  ╱ Po105          下行到接入对（本次新增）
                ╲                ╱
    rsw1_mdu5_prod_dc09_m01 ══ rsw2_...            ← 本次新上线，vPC domain 105
              ║            ║
           服务器 ×40（双网卡 bond）
```

关键点：**本次上线不只是配 2 台新设备**。汇聚层和核心层都要增量修改（加 VLAN、放通 trunk、建网关）。这是三级结构相比二级结构最实质的差别。

## 二、阶段 0：人工输入

### 2.1 输入模型（通用形式）

输入以 **MDU 组**为单位组织，而不是平铺设备列表。这是为了适配任意规模——2 台是一个组，8 台是四个组（或两个 Vdos-X 组），模型不变：

```yaml
idc: DC09
architecture: l2_gw_core          # 结构一；结构二填 l3_bgp
groups:                           # 列表，一个元素 = 一个 MDU 组 = 一套冗余单元
  - mdu: MDU5
    business_type: Normal         # 查 docs/idc/MDU分类.md 得规格
    redundancy: vpc               # vpc / mlag / irf / none
    devices:
      - { sn: FDO24110ABC, model: N9K-C93180YC-FX3, position: MDU5A.N1.net.DC09, member_id: 1 }
      - { sn: FDO24110DEF, model: N9K-C93180YC-FX3, position: MDU5B.N2.net.DC09, member_id: 2 }
    uplink_to:
      pair: [asw1_mdu5_dc09_m01, asw2_mdu5_dc09_m01]
      ports: [Ethernet1/5, Ethernet1/6]
    server_count: 40
```

`member_id` 决定成对设备中谁是 1 号谁是 2 号，影响 vPC role priority、HSRP priority、IP 末位等所有"镜像差异"。

### 2.2 为什么以组为单位

[规范定义](../../../../docs/idc/规范定义.md)明确：**一个 MDU = 2 台 Rack Switch + 2~4 个机柜 + 约 40 台服务器**。现网实测验证了这一点——62 个 MDU 组全部是 2 台 rsw，无例外：

```
单 MDU 组内 rsw 台数分布: {1: 1, 2: 62}
```

所以"8 台设备"不会是一个 MDU，只可能是两种情况：

| 情况 | 构成 | 说明 |
|------|------|------|
| **四个 Normal MDU 一批上线** | 4 组 × 2 台 | 最常见。整 POD 交付时的典型规模 |
| **两个 Vdos-X MDU** | 2 组 × 4 台 | Vdos-X 是唯一打破"2 台"的业务类型，见 2.3 |

两种情况都由 `groups` 列表自然表达，不需要为"8 台"设计特殊结构。

### 2.3 Vdos-X 是 2 台规则的例外

`docs/idc/MDU配置规格.md` 中 Vdos-X 规格：

```
1U 服务器 — Vdos-X
  机柜：2 个 20A
  服务器：38 台（单机柜 19 台）
  接入交换机：四台 48 口万兆，4 * 40G 上行     ← 4 台，不是 2 台
```

服务器四个万兆口（超融合架构）需要四台接入交换机。这种组的冗余形态需要确认：4 台是"两个 vPC 对"还是"一个 4 成员 IRF"，配置差别很大，见待确认第 5 条。

### 2.4 `uplink_to.ports` 的扩展

`uplink_to` 是唯一无法推导的信息——系统不知道现场把线接到了汇聚层哪个口。多组场景下每组的汇聚侧端口不同，所以 `uplink_to` 必须在组内，不能是全局字段。

端口可以两种写法：

```yaml
# 写法一：显式列出（组少时清晰）
uplink_to:
  pair: [asw1_mdu5_dc09_m01, asw2_mdu5_dc09_m01]
  ports: [Ethernet1/5, Ethernet1/6]

# 写法二：声明起始口，按组顺序自动递增（组多时省事）
uplink_allocation:
  pair: [asw1_mdu5_dc09_m01, asw2_mdu5_dc09_m01]
  port_prefix: Ethernet1/
  start_port: 5
  ports_per_group: 2
```

写法二下 MDU5 占 e1/5-6、MDU6 占 e1/7-8、MDU7 占 e1/9-10、MDU8 占 e1/11-12。**但这要求现场接线严格按顺序**，否则配置与实际接线错位。建议：渲染后用 LLDP 实际邻居核对（`tables/TopologyDB.py` 已有数据），对不上就报错而不是硬下发。

### 2.5 八台设备的完整输入示例

四个 Normal MDU 共用一对汇聚：

```yaml
idc: DC09
architecture: l2_gw_core
uplink_allocation:                # 组间共享的端口分配规则
  pair: [asw1_mdu5_dc09_m01, asw2_mdu5_dc09_m01]
  port_prefix: Ethernet1/
  start_port: 5
  ports_per_group: 2
groups:
  - { mdu: MDU5, business_type: Normal, redundancy: vpc, server_count: 40,
      devices: [{sn: FDO24110ABC, model: N9K-C93180YC-FX3, position: MDU5A.N1.net.DC09, member_id: 1},
                {sn: FDO24110DEF, model: N9K-C93180YC-FX3, position: MDU5B.N2.net.DC09, member_id: 2}] }
  - { mdu: MDU6, business_type: Normal, redundancy: vpc, server_count: 40,
      devices: [{sn: FDO24110GHI, model: N9K-C93180YC-FX3, position: MDU6A.N3.net.DC09, member_id: 1},
                {sn: FDO24110JKL, model: N9K-C93180YC-FX3, position: MDU6B.N4.net.DC09, member_id: 2}] }
  - { mdu: MDU7, business_type: Normal, redundancy: vpc, server_count: 40,
      devices: [{sn: FDO24110MNO, model: N9K-C93180YC-FX3, position: MDU7A.N5.net.DC09, member_id: 1},
                {sn: FDO24110PQR, model: N9K-C93180YC-FX3, position: MDU7B.N6.net.DC09, member_id: 2}] }
  - { mdu: MDU8, business_type: Normal, redundancy: vpc, server_count: 40,
      devices: [{sn: FDO24110STU, model: N9K-C93180YC-FX3, position: MDU8A.N7.net.DC09, member_id: 1},
                {sn: FDO24110VWX, model: N9K-C93180YC-FX3, position: MDU8B.N8.net.DC09, member_id: 2}] }
```

推导结果：

| 组 | 主机名 | VLAN | 网段 | vPC domain | 上行 Po（rsw侧） | 汇聚侧端口 | 汇聚侧 Po |
|----|--------|------|------|-----------|----------------|-----------|----------|
| MDU5 | `rsw1/2_mdu5_prod_dc09_m01` | 1005 | 10.143.5.0/24 | 105 | Po100 | e1/5-6 | Po105 |
| MDU6 | `rsw1/2_mdu6_prod_dc09_m01` | 1006 | 10.143.6.0/24 | 106 | Po100 | e1/7-8 | Po106 |
| MDU7 | `rsw1/2_mdu7_prod_dc09_m01` | 1007 | 10.143.7.0/24 | 107 | Po100 | e1/9-10 | Po107 |
| MDU8 | `rsw1/2_mdu8_prod_dc09_m01` | 1008 | 10.143.8.0/24 | 108 | Po100 | e1/11-12 | Po108 |

注意两点：

- **各组 rsw 侧上行 Po 号都是 Po100**，不冲突——Po 号只要求设备内唯一，不同 MDU 的 rsw 是不同设备。
- **汇聚侧 Po 号必须各不相同**（Po105-108），因为它们在同一台 asw 上。这是 8.4 节编号冲突检测要防的主要场景。

### 2.6 规模扩大带来的三个新问题

单组扩到多组，不是简单重复，有三处必须新增处理：

**① 汇聚层端口容量校验**

4 组 × 每组 2 口 = 每台 asw 消耗 8 个下行口。加上已有 MDU 和上行口，必须校验 asw 剩余端口是否够。这需要查 `ports` 表的实际占用情况，或 `model_port_layout` 的下行区容量。端口不够应在输入阶段报错。

**② 汇聚层 trunk VLAN 一次性并入 4 个**

第五节的 VLAN 收敛要算的是并集，4 组一起上线时汇聚侧上行 trunk 从 `1,1001-1004` 变成 `1,1001-1008`，一次改动涉及 4 个新 VLAN。用 `add` 语法则是 `switchport trunk allowed vlan add 1005-1008`。

**③ 变更批次从 3 批变成 1+N 批**

```
批次 1：汇聚层增量（4 个 Po + 4 个 VLAN）+ 核心层增量（4 个 SVI + trunk）
批次 2：MDU5 接入对
批次 3：MDU6 接入对
批次 4：MDU7 接入对
批次 5：MDU8 接入对
```

接入层分组分批而不是一批下完——单组出问题不影响其他组。汇聚/核心的增量可以合并成一批，因为它们是同一对设备上的配置。

## 三、阶段 1：资源推导

| 资源 | 推导规则 | 结果 |
|------|---------|------|
| 主机名 | 层级+序号+MDU+用途+机房+楼层（[命名规范](../../../../docs/network/设备命名规范.md)） | `rsw1_mdu5_prod_dc09_m01`、`rsw2_...` |
| 业务 VLAN | **固定 `1000`**，不按 MDU 变（见下方说明） | `1000` |
| 业务网段 | IPAM 申领（`function_collector/func_ipam.py`），按 MDU 区分 | `10.143.5.0/24`（假设值） |
| 网关地址 | 网段首个可用，结构一下落在核心层 | `10.143.5.1`（HSRP VIP） |
| VLAN 名 | `业务类型::网段`（[端口与VLAN规范](../../../../docs/network/端口与VLAN描述规范.md)） | `Internal-MDU5::10.143.5.0/24` |
| 管理 IP | 模块 2 已分配 | `10.143.232.45`、`.46` |
| 接入层规格 | 查 `docs/idc/MDU配置规格.md`：Normal = 两台 48 口千兆 + 4×10G 上行 | 校验型号是否匹配规格 |

规格校验这步有实际价值：填的型号如果和业务类型对应的规格不符（比如 Normal 却填了万兆接入），直接在输入阶段报错，不等配到一半才发现。

### 3.1 VLAN 规则更正：VLAN ID 固定，网段区分 MDU

初稿写的 `VLAN = 1000 + MDU编号` 是错的。现网实测：

```
rsw1_mdu9_prod_dc09_m01:   vlan 1000  Internal-Server::10.129.0.0/19
rsw1_mdu10_prod_dc09_m01:  vlan 1000  Internal-Server::10.129.32.0/19
```

**每个 MDU 都用 `vlan 1000`，只有网段不同。** VLAN ID 是本地标识，不跨 MDU 延伸，MDU 之间靠 BGP 路由互通（结构二）。这意味着：

| 维度 | 正确规则 |
|------|---------|
| VLAN ID | 固定值（现网 1000），不随 MDU 变化 |
| VLAN 名 | `Internal-Server::<本 MDU 网段>`，网段部分区分 |
| 网段 | 从 IPAM 按 MDU 申领，这才是区分 MDU 的维度 |
| 另有 `vlan 10` | `RSW::Internelconnect`，成对 rsw 之间的互联 VLAN，承载 iBGP |

结构一（二层延伸到核心）才需要每 MDU 一个唯一 VLAN ID，因为同一个二层域不能有 ID 冲突。结构二下 VLAN 不跨设备，复用同一个 ID 反而是对的——配置统一，无需为每个 MDU 算 VLAN 号。

本预演后文仍按结构一逻辑（每组一个唯一 VLAN ID）推导，因为结构一确实需要如此；但若实际采用结构二，VLAN 一项应改为固定值。

## 四、阶段 2：互联图构建

这是三级结构的核心难点。**互联是双端对象，不能挂在单台设备上。**

### 4.1 为什么必须有"互联"这个实体

一条链路的两端必须在 Po 号、vPC ID、VLAN 列表、端口描述上互相对应。如果让每台设备的意图各自声明自己的上行/下行，两边对不上的风险极高（一端 trunk 放通 1005 另一端忘了，链路通但业务不通）。

所以渲染的输入不是 6 份独立的设备意图，而是**互联列表 + 设备属性**，设备意图是从互联图展开出来的。

### 4.2 本次涉及的互联

| 互联 | 两端 | 类型 | 物理链路 |
|------|------|------|---------|
| IC-1 | rsw1 ←→ rsw2 | peer-link | rsw1:e1/51-52 ←→ rsw2:e1/51-52 |
| IC-2 | rsw 对 ←→ asw 对 | L2 trunk（双边 vPC） | 4 条，见下 |
| IC-3 | rsw1 ←→ 服务器 ×40 | L2 access | 每台服务器一条腿 |

IC-2 展开成 4 条物理链路（双边 vPC 的方形拓扑）：

```
rsw1:e1/49 ──→ asw1:e1/5
rsw1:e1/50 ──→ asw2:e1/5
rsw2:e1/49 ──→ asw1:e1/6
rsw2:e1/50 ──→ asw2:e1/6
```

两侧各自聚合成一个逻辑 LAG：

- rsw 侧：`Po100`，成员 e1/49+e1/50，`vpc 100`。rsw1 和 rsw2 **必须用同一个 Po 号和同一个 vPC ID**。
- asw 侧：`Po105`，成员 e1/5+e1/6，`vpc 105`。asw1 和 asw2 同理。

### 4.3 编号规则与约束

双边 vPC 有三条硬约束，编号规则必须满足：

| 约束 | 规则 |
|------|------|
| 相邻两对设备的 vPC domain 必须不同 | csw 对 = 1，asw 对 = 50，rsw 对 = `100 + MDU号` = 105 |
| 同一台设备上 Po 号唯一 | 服务器口 Po1-48（=端口号）；上行 Po100；peer-link Po4000 |
| 同一 vPC domain 内 vPC ID 唯一 | rsw 对：服务器 vPC 1-48，上行 vPC 100；asw 对：下行 vPC `100+MDU号`，上行 vPC 1 |

推导出的编号：

```
rsw 对：domain 105，peer-link Po4000(e1/51-52)
        服务器 Po1-48  vpc 1-48
        上行   Po100   vpc 100   → 对端 asw 对的 Po105
asw 对：domain 50，peer-link Po4000
        下行   Po105   vpc 105   → 对端 rsw 对的 Po100（本次新增）
        上行   Po1     vpc 1     → 对端 csw 对的 Po50（本次只改 VLAN）
csw 对：domain 1
        下行   Po50    vpc 50               （本次只改 VLAN）
        SVI Vlan1005 + HSRP                 （本次新增）
```

注意 `Po100`（rsw 侧）与 `Po105`（asw 侧）是同一条互联的两端，号不同。两端 Po 号不要求相同，只要求各自设备内唯一——但描述里必须互相指向，这由端口描述规范保证。

## 五、阶段 3：VLAN 自底向上收敛

结构一下汇聚层是纯二层透传，它上行 trunk 要放通的 VLAN 是**其下所有接入对 VLAN 的并集**。这个值不是某台设备自己的属性，必须全局算。

```
① 接入层声明需求：rsw 对(MDU5) 需要 vlan 1005
       ↓
② 汇聚层取并集：asw 对(MDU5) 下挂 MDU5~MDU8 的接入对
       已有 vlan 1001,1002,1003,1004 → 并入 1005 → 上行 trunk = 1,1001-1005
       ↓
③ 核心层建网关：csw 对为 vlan 1005 建 SVI + HSRP
       下行到 asw 对的 trunk = 1,1001-1005
```

**这条链决定了渲染单元是"一次上线批次"而不是单台设备。** 要算出汇聚层的 VLAN 并集，必须先知道这个汇聚对下所有接入对的 VLAN——包括已在网的。所以渲染时要查现有意图库（`device_intent`），不能只看本次新增的设备。

## 六、阶段 4：逐设备意图展开

从互联图 + 资源推导结果，展开出每台设备的意图。注意新建设备和存量设备的意图性质不同：

| 设备 | 意图性质 | 需要的片段 |
|------|---------|-----------|
| rsw1 / rsw2 | **全新**，产出完整业务配置 | `base.vlan` + `redundancy.vpc` + `uplink.l2po` + `downlink.l2po` + `base.stp` |
| asw1 / asw2 | **增量**，只产出新增部分 | `base.vlan` + `downlink.l2po`（新增 Po105）+ 上行 trunk VLAN 修改 |
| csw1 / csw2 | **增量** | `base.vlan` + `gateway.svi_hsrp`（新增 Vlan1005）+ 下行 trunk VLAN 修改 |

rsw1 的意图（节选）：

```json
{
  "hostname": "rsw1_mdu5_prod_dc09_m01",
  "vendor": "cisco_nx", "model": "N9K-C93180YC-FX3",
  "layer": "rsw", "architecture": "l2_gw_core",
  "idc": "DC09", "mdu": "MDU5",
  "redundancy": {
    "mode": "vpc", "domain": 105, "role_priority": 1,
    "peer_hostname": "rsw2_mdu5_prod_dc09_m01",
    "peer_link": { "agg_id": 4000, "ports": ["Ethernet1/51", "Ethernet1/52"] },
    "keepalive": { "local": "10.143.232.45", "peer": "10.143.232.46", "vrf": "management" }
  },
  "vlans": [{ "id": 1005, "name": "Internal-MDU5::10.143.5.0/24" }],
  "uplinks": [{
    "agg_id": 100, "vpc_id": 100, "type": "l2_trunk", "allowed_vlan": "1,1005",
    "peer_desc": "asw_pair_mdu5_dc09_m01::Po105",
    "members": [
      { "port": "Ethernet1/49", "peer": "asw1_mdu5_dc09_m01", "peer_port": "e1/5" },
      { "port": "Ethernet1/50", "peer": "asw2_mdu5_dc09_m01", "peer_port": "e1/5" }
    ]
  }],
  "server_ports": { "range": "1-40", "mode": "access", "vlan": 1005, "agg_per_port": true }
}
```

注意 `gateways` 为空——结构一下接入层不是网关。这就是结构一与结构二在意图层面的唯一差别，片段选择随之不同。

## 七、阶段 5：渲染输出

### 7.1 rsw1（全新配置）

```
vlan 1005
  name Internal-MDU5::10.143.5.0/24

! ── redundancy.vpc ──
vpc domain 105
  peer-switch
  role priority 1
  peer-keepalive destination 10.143.232.46 source 10.143.232.45 vrf management
  peer-gateway
  ip arp synchronize

interface port-channel4000
  description rsw2_mdu5_prod_dc09_m01::Po4000::L2
  switchport mode trunk
  switchport trunk allowed vlan 1,1005
  spanning-tree port type network
  vpc peer-link

interface Ethernet1/51-52
  description rsw2_mdu5_prod_dc09_m01::e1/51-52::L2
  switchport mode trunk
  switchport trunk allowed vlan 1,1005
  channel-group 4000 mode active
  no shutdown

! ── uplink.l2po ──
interface port-channel100
  description asw_pair_mdu5_dc09_m01::Po105::L2
  switchport mode trunk
  switchport trunk allowed vlan 1,1005
  spanning-tree port type network
  vpc 100

interface Ethernet1/49
  description asw1_mdu5_dc09_m01::e1/5::L2
  switchport mode trunk
  switchport trunk allowed vlan 1,1005
  channel-group 100 mode active
  no shutdown

interface Ethernet1/50
  description asw2_mdu5_dc09_m01::e1/5::L2
  switchport mode trunk
  switchport trunk allowed vlan 1,1005
  channel-group 100 mode active
  no shutdown

! ── downlink.l2po ×40（循环生成，此处示意前两个）──
interface port-channel1
  description Server::MDU5-R01-U01::bond0
  switchport mode access
  switchport access vlan 1005
  spanning-tree port type edge
  vpc 1

interface Ethernet1/1
  description Server::MDU5-R01-U01::eth0
  switchport mode access
  switchport access vlan 1005
  channel-group 1 mode active
  no shutdown
...（Po2-Po40 同构）
```

### 7.2 asw1（增量配置）

```
vlan 1005
  name Internal-MDU5::10.143.5.0/24

! 新增下行到 MDU5 接入对
interface port-channel105
  description rsw_pair_mdu5_prod_dc09_m01::Po100::L2
  switchport mode trunk
  switchport trunk allowed vlan 1,1005
  spanning-tree port type network
  vpc 105

interface Ethernet1/5
  description rsw1_mdu5_prod_dc09_m01::e1/49::L2
  switchport mode trunk
  switchport trunk allowed vlan 1,1005
  channel-group 105 mode active
  no shutdown

interface Ethernet1/6
  description rsw2_mdu5_prod_dc09_m01::e1/49::L2
  switchport mode trunk
  switchport trunk allowed vlan 1,1005
  channel-group 105 mode active
  no shutdown

! 修改上行 trunk 放通范围（原 1,1001-1004）
interface port-channel1
  switchport trunk allowed vlan 1,1001-1005
```

### 7.3 csw1（增量配置）

```
vlan 1005
  name Internal-MDU5::10.143.5.0/24

! ── gateway.svi_hsrp ──
interface Vlan1005
  description Gateway::MDU5::10.143.5.0/24
  no shutdown
  no ip redirects
  ip address 10.143.5.2/24
  hsrp version 2
  hsrp 1005
    ip 10.143.5.1
    priority 150
    preempt

! 修改下行 trunk 放通范围
interface port-channel50
  switchport trunk allowed vlan 1,1001-1005
```

csw2 对应段只有两处不同：`ip address 10.143.5.3/24`、`priority 140`（不抢占）。这种"成对设备的镜像差异"由片段里的 `member_id` 变量控制，不需要两套模板。

## 八、本流程暴露的设计约束

预演下来，有五条必须落到实现里：

### 8.1 渲染单元是上线批次，不是单台设备

VLAN 并集（第五节）要求知道同一汇聚对下所有接入对的 VLAN。单台设备独立渲染算不出来。所以 API 应是 `POST /api/arch/render/batch`，输入一个批次，输出该批次涉及的**所有设备**（含存量设备的增量）的配置。

### 8.2 必须区分全新配置与增量配置

本次上线产出三类配置：

| 类型 | 设备 | 下发方式 | 风险 |
|------|------|---------|------|
| 全新完整配置 | rsw1/rsw2 | 可整段下发 | 低，设备未承载业务 |
| 新增片段 | asw1/asw2 的 Po105 | 追加命令 | 低，不影响现有 Po |
| **修改现有配置** | asw/csw 的 trunk VLAN 列表 | 覆盖写入 | **中，写错会断现有业务** |

第三类最危险。`switchport trunk allowed vlan` 是覆盖语义，漏写一个已有 VLAN 就断那个 MDU。两种防护：

- 渲染时 VLAN 列表从意图库现有数据算出，不依赖人工填写
- 用 `switchport trunk allowed vlan add 1005` 增量语法而非全量覆盖（NX-OS 支持），把覆盖风险降为零

**倾向用 `add` 语法**。虽然导致配置行与"期望的完整列表"不是同一形式，但对在网设备安全得多。

### 8.3 互联必须是独立实体，不能挂在设备上

第四节已说明。数据库要加一张互联表，不能只有 `device_intent`：

```sql
CREATE TABLE IF NOT EXISTS arch_interconnect (
    icid        BIGINT      NOT NULL AUTO_INCREMENT COMMENT '互联ID',
    ic_type     VARCHAR(20) NOT NULL COMMENT 'peerlink/l2_trunk/l3_p2p/server',
    a_side      VARCHAR(100) NOT NULL COMMENT 'A端：设备名或"对"标识',
    a_agg_id    INT         NULL     COMMENT 'A端聚合口号',
    a_vpc_id    INT         NULL     COMMENT 'A端vPC/M-LAG组号',
    b_side      VARCHAR(100) NOT NULL COMMENT 'B端',
    b_agg_id    INT         NULL     COMMENT 'B端聚合口号',
    b_vpc_id    INT         NULL     COMMENT 'B端vPC/M-LAG组号',
    allowed_vlan VARCHAR(200) NOT NULL DEFAULT '' COMMENT '二层互联的VLAN列表',
    members     TEXT        NOT NULL COMMENT '物理链路映射JSON：[{a_port,b_port}]',
    idc         VARCHAR(20) NOT NULL COMMENT '机房',
    status      VARCHAR(20) NOT NULL DEFAULT 'planned' COMMENT 'planned/deployed',
    created_at  VARCHAR(15) NOT NULL,
    PRIMARY KEY(icid),
    INDEX idx_a (a_side),
    INDEX idx_b (b_side)
) COMMENT='设备互联';
```

端口描述、trunk VLAN、Po 号的两端一致性由这张表天然保证——两端配置从同一条记录渲染。

### 8.4 编号分配需要集中管理

vPC domain、Po 号、vPC ID 都有唯一性约束（4.3）。规则可算，但必须有冲突检测：渲染前校验算出的编号在该设备/该 domain 上没被占用。建议把编号规则做成可配置而非硬编码，不同机房的存量编号习惯可能不同（DC09 实测 peer-link 是 Po4000，别的机房未必）。

### 8.5 三级结构的上线顺序约束

```
① 汇聚层增量（Po + VLAN）+ 核心层增量（SVI + trunk VLAN）   ← 必须先于接入层
② 接入层全新配置，按 MDU 组分批                              ← 上行对端就位才能起来
```

接入层配完如果汇聚侧还没配，上行 Po 起不来，设备在业务上是孤岛（管理口已通，不影响纳管）。变更工单分批，`op_devs.batch` 字段正好用于此。

多组场景下接入层按组分批（见 2.6 ③），单组失败不牵连其他组。

### 8.6 规模相关的校验必须前置

2.6 节三个问题里，①汇聚层端口容量和 `uplink_allocation` 的接线顺序假设，都应在**输入阶段**校验，不能等渲染完才发现：

| 校验 | 数据来源 | 失败处理 |
|------|---------|---------|
| 汇聚层下行口是否够 | `ports` 表实际占用 + `model_port_layout` 容量 | 输入阶段报错 |
| 汇聚侧 Po 号/vPC ID 是否冲突 | `arch_interconnect` 已有记录 | 输入阶段报错 |
| 型号是否符合业务类型规格 | `docs/idc/MDU配置规格.md` | 输入阶段警告 |
| 实际接线是否与 `uplink_allocation` 一致 | LLDP（`tables/TopologyDB.py`） | **渲染后、下发前**核对，不一致报错 |

最后一条只能在设备已纳管、LLDP 已上报之后做，所以是下发前的闸门而非输入阶段校验。

## 九、与二级结构的差异总结

| 维度 | 三级（拓扑 A） | 二级（拓扑 B） |
|------|---------------|---------------|
| 涉及设备（单组） | 6 台（2 新建 + 4 增量） | 4 台（2 新建 + 2 增量） |
| 涉及设备（4 组 8 台） | 12 台（8 新建 + 4 增量） | 10 台（8 新建 + 2 增量） |
| VLAN 收敛 | 两跳并集（接入→汇聚→核心） | 一跳（接入→核心） |
| 双边 vPC | 2 处（rsw-asw、asw-csw） | 1 处（rsw-csw） |
| 接入层模板 | **完全相同** | **完全相同** |
| 上线批次（4 组） | 1 + 4 批 | 1 + 4 批 |

增量设备数不随组数增长（始终是那一对汇聚、那一对核心），这是三级结构在批量上线时的优势——组数越多，增量改动的边际成本越低。

接入层模板在两种拓扑下完全一致，这验证了模块 3 第四节的核心判断：**设备配置只取决于自身属性和邻接关系，不取决于整体拓扑深度**。

## 十、同一模型覆盖日常变更

分组意图模型不只用于上线。**上线是意图从无到有，日常变更是意图 diff，两者走同一条流水线。**

### 10.1 变更类型映射

| 日常变更 | 改意图哪里 | 渲染产出 | 涉及设备 |
|---------|-----------|---------|---------|
| 新增业务网段 | `gateways[]` 加一项 | SVI + HSRP（结构一在核心）或 SVI + BGP network（结构二在接入） | 结构一：核心+汇聚+接入；结构二：仅接入对 |
| 扩服务器端口 | `server_ports.range` 改范围 | 新增 Po + 成员口配置 | 仅本组接入对 |
| 扩上行带宽 | `uplinks[].members` 加成员口 | 新增成员口加入现有 Po，或新建 Po + BGP 邻居 | 本组接入对 + 上游一对 |
| 换故障设备 | 改 `devices[].sn` | 该设备整份配置重渲染 | 仅故障设备 |
| 整组下线 | 删除该 `group` | 反向生成清理命令（含上游增量回收） | 本组 + 上游一对 |
| 改 trunk 放通 | `uplinks[].allowed_vlan` | trunk VLAN 修改 | 链路两端 |

**结构二的变更影响面显著小于结构一**：新增网段只需改接入对（SVI + BGP 宣告），上游靠路由自动学习；结构一则要逐层放通 VLAN + 核心建网关。这是结构二在运维成本上的优势，也佐证了[模块 3](./03_business_architecture.md) 待确认第 4 条——新建机房应优先结构二。

### 10.2 变更流程

```
改意图 → 重渲染 → 与当前 running-config 做 diff → 人工确认 diff → 推变更工单 → 执行 → 更新意图状态
```

与上线流程的唯一差别是 diff 这步有真实对照物（设备已在网）。注意这**不是**模块 2 那种"模板 vs 在网设备"的无意义比对——这里比的是"即将下发的变更内容"，对照明确、噪音为零。

### 10.3 三条边界

**① 存量设备意图缺失，这是最大前提**

现网 248 台 rsw 没有任何意图记录。要用这套模型管日常变更，必须先把存量设备的意图从现网反推补齐。而这不是机械转换——3.1 节那个 VLAN 规则就是例子：按"1000+MDU号"推是错的，实际是固定 1000 + 网段区分。反推必须逐项用现网数据核对规则，不能靠假设。

建议做法：先只对**新上线的设备**维护意图，存量设备的日常变更继续走普通工单。等新设备积累到一定比例、规则在实践中校准准确后，再分批反推存量。不要一开始就追求全量覆盖。

**② 有些变更不该进模型**

临时抓包口、一次性放通、排障残留——这些硬塞进意图会污染模型（意图应该表达"稳定的设计",不是"临时的操作"）。这类继续走普通变更工单，与整体框架第四节"其他配置域不在自动化范围内"一致。

**③ 人工绕过会导致意图与现网脱节**

有人直接登录改了配置，意图库不会知道。模型没有强制力。两条路：

- 接受偏移，把意图当"设计记录"而非"事实记录"，下发前的 diff 自然会暴露偏移
- 要求所有变更走意图，现实中很难，尤其故障处置时

倾向前者。下发前 diff 本身就是偏移检测点，比强制流程更务实。

## 附录 A：DC09 实测结构二形态

本预演设定的场景是结构一，但实测发现 DC09 实际跑的是结构二。记录在此，作为结构二预演的素材。

`rsw1_mdu10_prod_dc09_m01`（10.143.232.29，N9K-C93180YC-EX）：

```
router bgp 4200091010
  router-id 172.21.34.19
  log-neighbor-changes
  address-family ipv4 unicast
    network 10.129.32.0/19          ← 本 MDU 业务网段
    network 172.21.34.19/32         ← Loopback
    maximum-paths 32
  neighbor 172.21.36.2              ← iBGP 到同组对端 rsw
    remote-as 4200091010            （AS 相同）
    password 3 <HASH>
    update-source Vlan10            （走 vlan 10 互联 VLAN）
    address-family ipv4 unicast
      next-hop-self
      soft-reconfiguration inbound always
  neighbor 172.21.48.145            ← eBGP 到 csw1
    bfd
    remote-as 4200090011
    password 3 <HASH>
    address-family ipv4 unicast
      soft-reconfiguration inbound always
  neighbor 172.21.48.153            ← eBGP 到 csw2
    bfd
    remote-as 4200090011
    ...

interface port-channel1001
  description uT:csw1_dc09_m01:RAGG69
  ip address 172.21.48.146/30       ← P2P /30 三层互联

interface Vlan1000
  description Internal::Server
  ip address 10.129.32.2/19
  hsrp version 2
  hsrp 1000
    preempt
    priority 120
    timers msec 250 msec 750
    ip 10.129.32.1                  ← 网关在接入层
  ip dhcp relay address 10.33.160.148
  ip dhcp relay information trusted
```

结构二的三个实测细节，是设计模板时初稿漏掉的：

1. **成对 rsw 之间有 iBGP**，走 `vlan 10`（`RSW::Internelconnect`）互联，`update-source Vlan10` + `next-hop-self`。这个 iBGP 片段初稿的片段清单里没有，需补。
2. **网关用 HSRP 而非 anycast**，带 `timers msec 250 msec 750` 快速切换。回答了待确认第 1 条——现网用 HSRP。
3. **带 DHCP relay**，服务器靠 DHCP 获址。这是业务配置的一部分，片段清单需补 `gateway.dhcp_relay`。

另有端口细节：服务器口带 `spanning-tree bpdufilter enable`，初稿模板只写了 `spanning-tree port type edge`，需补。

## 十一、待确认

1. ~~结构一的网关冗余用 HSRP 还是 vPC anycast~~ —— **已确认用 HSRP**（附录 A 实测，带 `timers msec 250 msec 750`）。
2. **trunk VLAN 修改用 `add` 增量语法还是全量覆盖**（8.2）？倾向 `add`。
3. **汇聚层在现网是否真实存在**？本预演的汇聚层是按需求设计的，DC09 实测为核心—接入二级。若三级结构仅为规划，本预演的汇聚层部分可延后实现。
4. **服务器端口是否真需要逐口建 Po**？DC09 实测 48 个单成员 Po（每个 Po 一个口），这是为了支持服务器双网卡跨设备 bond。若有单网卡服务器，需要混合模式。
5. **Vdos-X 的 4 台接入交换机是什么冗余形态**（2.3 节）？两个独立 vPC 对、一个 4 成员 IRF、还是 4 台独立？配置差异很大。现网未找到 Vdos-X 样本，需确认是否已部署。
6. **`uplink_allocation` 的顺序递增假设是否可接受**（2.4 节）？它要求现场接线严格按 MDU 顺序。若现场接线随意，必须逐组显式填端口。建议无论哪种都加 LLDP 核对闸门。
7. **多组上线时 VLAN 是否一组一个**？本预演按 `1000+MDU号` 一组一个 VLAN（故障域隔离在 MDU 级）。若多个 MDU 共用一个大 VLAN，网段和 SVI 的推导规则要改。

返回：[模块 3 业务架构](./03_business_architecture.md) ｜ [整体框架](./README.md)
