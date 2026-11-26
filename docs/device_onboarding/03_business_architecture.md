# 模块 3：业务架构设计

## 文档信息

- 所属：[交换机自动化上线整体框架](./README.md)
- 作用阶段：S4 业务配置（设备已纳管、可 SSH 之后）
- 职责：除管理地址与网管配置（模块 2）之外的**全部配置**——冗余机制、互联接口、网关、路由协议
- 本文档形式：先用具体场景做完整预演，从预演中提炼模型

## 一、术语对齐（重要）

用户描述的 CSW/DSW/ASW 与仓库[设备命名规范](../../../../docs/network/设备命名规范.md)中的角色缩写不是一一对应，先对齐，后文统一用**层级名**：

| 本文层级名 | 用户用词 | 仓库角色缩写 | 说明 |
|-----------|---------|-------------|------|
| 核心层 | CSW | `csw` | 内网核心。传统架构下是网关 |
| 汇聚层 | DSW | `asw` | 仓库里 asw = Aggregation Switch。**注意不是用户说的 ASW** |
| 接入层 | ASW | `rsw` | 仓库里 rsw = Rack Switch（ToR）。全三层架构下是网关 |

> 仓库规范中 `asw` 是汇聚、`rsw` 是接入；用户口语里的 ASW 指接入。配置模板里的角色字段必须用仓库缩写（`csw`/`asw`/`rsw`），以便与 `devices.sysname` 解析结果对应。本文档为避免歧义，统一写「核心层/汇聚层/接入层」。

## 二、现网实测：冗余机制不统一

### 2.1 三种并存的冗余形态

| 设备 | 机房 | 型号 | 冗余机制 | 实测 |
|------|------|------|---------|------|
| `rsw1_mdu10_prod_dc09_m01` | DC09 | N9K-C93180YC-EX | **vPC** | domain 109，48 个 vPC Po，peer-link Po4000，`Peer status: adjacency formed ok` |
| `csw1_dc07_m01_new` | DC07 | N9K-C9508 | **无（独立双核心 + ECMP）** | `show feature \| include vpc` → `disabled`，上行 Po53/Po54 为 Routed，无 LACP |
| `new_csw1_dc19_m01` | DC19 | S9825-64D | **M-LAG** | peer-link BAGG100，21 个 M-LAG 组，system-mac `0000-dc19-0001` |

三种形态在现网同时存在，而且**对应不同的机房代际**：DC07 老核心是独立双核心，DC09 接入层用 vPC，DC19 新核心用 M-LAG（符合 `docs/network/bgp.md` 里"新部署核心采用 M-LAG"的规划）。

### 2.2 一个真实接入层样本（第一种结构）

`rsw1_mdu10_prod_dc09_m01`（10.143.232.29）的实际形态，这正是用户描述的「传统三层 + 链路聚合 + 网关在核心」：

```
vPC domain id          : 109
vPC role               : secondary
Number of vPCs         : 48
Peer Gateway           : Enabled
Peer-link              : Po4000 (Eth1/51 + Eth1/52, LACP)   active vlans 1,10,1000

下行：Po1 ~ Po48  每个 1 个成员口 (Eth1/1~1/48)，LACP，Switched，vlan 1000
      → 每个 Po 对应一台双网卡服务器的一条腿，另一条腿在对端 rsw2
上行：Po1001 (Eth1/49)  Routed，无 LACP
      Po1002 (Eth1/50)  Routed，无 LACP
      → 两条独立三层链路分别上两台核心，ECMP
```

三个可直接转成模板规则的事实：

1. **下行 Po 编号 = 端口号**（Eth1/1 → Po1，Eth1/48 → Po48），vPC ID 也等于 Po 号。编号可算，不需人工指定。
2. **peer-link 固定 Po4000**，成员口取设备最后两个上行口位（这里 Eth1/51-52）。
3. **上行用 Routed Po 且不跑 LACP**，每个 Po 单成员——这与 `docs/network/ospf.md` 的"不用 Port-Channel 承载 OSPF 邻居"一致：用 Po 封装但单成员，保留了后续扩容的余地，又不掩盖单链路故障。

### 2.3 现网发现的问题（非本模块职责，但需记录）

`new_csw1_dc19_m01` 的 M-LAG keepalive 链路状态异常：

```
Peer-link interface state (cause): UP
Keepalive link state (cause):      DOWN (Local Rx timeout)
m-lag keepalive ip destination 10.26.252.24 source 10.26.252.23 vpn-instance management
```

peer-link 正常但 keepalive 收不到对端报文。keepalive 走带外管理 VRF，这条链路挂着的后果是 peer-link 真故障时无法判断对端是否存活，双主风险（split-brain）失去保护。另有 12 个 M-LAG 组（BAGG21-32）处于 `DOWN (A)`——聚合口本身 down，可能是尚未接线的预配置。

建议单独排查 keepalive。本模块的相关设计含义：**M-LAG/vPC 的 keepalive 必须走带外**，这要作为模板硬规则，且上线校验（模块 5）必须检查 keepalive 状态，否则配完看起来是好的，实际保护没生效。

## 三、场景预演

用户给出 2 种结构 × 2 种拓扑深度，再乘以每层的冗余形态。先枚举清楚，再看怎么收敛。

### 3.1 结构一：传统三层（网关在核心层）

二层域从接入层一直透传到核心层，核心层做网关。

**拓扑 A：核心 — 汇聚 — 接入（三级）** —— 完整生成流程见 [拓扑 A 预演](./03a_walkthrough_topology_a.md)

```
          csw1 ══════ csw2        冗余：vPC / M-LAG / IRF（核心对）
         ╱   ╲  peer   ╱  ╲       网关：SVI 在核心对
        ╱     ╲       ╱    ╲      下行：二层 Po，trunk 透传 vlan
   asw1 ═════ asw2  asw3 ═ asw4   冗余：汇聚对
      ╲       ╱                   上行：二层 Po 到核心对（跨设备聚合）
       ╲     ╱                    下行：二层 Po 到接入对
    rsw1 ══ rsw2                  冗余：接入对 or 单台
        ║  ║                      下行：服务器双上行
     服务器(双网卡)
```

**拓扑 B：核心 — 接入（二级）**

```
     csw1 ══════ csw2      网关：SVI 在核心对
        ╲       ╱          下行：二层 Po 直连接入
     rsw1 ══ rsw2          冗余：接入对 or 单台
         ║  ║
      服务器(双网卡)
```

每层设备需要的配置：

| 层级 | 配置内容 |
|------|---------|
| 核心层 | 冗余（peer-link + keepalive + domain/system-mac）、VLAN、**SVI 网关 + VRRP 或 vPC/M-LAG 的虚拟网关**、下行二层 Po（trunk）、上行到 bbs/pcs |
| 汇聚层 | 冗余、VLAN、上行二层 Po（trunk）、下行二层 Po（trunk）、STP 角色 |
| 接入层 | 冗余（成对时）、VLAN、上行二层 Po（trunk）、下行服务器 Po（access 或 trunk） |

### 3.2 结构二：全三层 BGP（网关在接入层）

每台接入层交换机是自己机柜的网关，层间跑 eBGP，无跨设备二层域。

**拓扑 C：核心 — 汇聚 — 接入（三级）**

```
          csw1 ══════ csw2        AS: 4200xx0001（核心对共用）
            ╲  eBGP  ╱           宣告：Loopback0 /32
         P2P /30 × N              冗余：M-LAG（仅用于接入侧，上行纯 ECMP）
            ╱       ╲
       asw1 ═══════ asw2          AS: 独立分配
            ╲  eBGP  ╱
         P2P /30 × N
            ╱       ╲
       rsw1 ═══════ rsw2          AS: 4200xx1001（按 MDU 分配）
            ║     ║               网关：SVI 在接入对，M-LAG 虚拟网关
         服务器(双网卡)
```

**拓扑 D：核心 — 接入（二级）**

```
     csw1 ══════ csw2       AS: 4200xx0001
        ╲ eBGP  ╱
     P2P /30 × 4
        ╱      ╲
   rsw1 ═════ rsw2          AS: 4200xx1001
       ║     ║
    服务器(双网卡)
```

每层配置：

| 层级 | 配置内容 |
|------|---------|
| 核心层 | 冗余、Loopback0、上下行 P2P /30 三层口、eBGP（对每个下游 AS 建邻居）、BFD、`maximum-paths 32` |
| 汇聚层 | 同上，承上启下 |
| 接入层 | 冗余、Loopback0、上行 P2P /30、**SVI 网关（机柜业务网段）**、eBGP 宣告业务网段 + Loopback、下行服务器口 |

规范依据（`docs/network/bgp.md`）需固化进模板：4 字节私有 AS、BFD 50/50×4、全邻居 MD5、`soft-reconfiguration inbound always`、`maximum-paths 32`、**仅 `network` 宣告 Loopback0 /32 不宣告 P2P 网段**。

### 3.3 组合数爆炸

```
结构（2：传统二层 / 全三层BGP）
  × 拓扑深度（2：三级 / 二级）
  × 层级（3：核心 / 汇聚 / 接入）
  × 冗余形态（4：vPC / M-LAG / IRF / 单台）
  × 厂商（3+：cisco_nx / h3c / huawei）
  = 100+ 种组合
```

**按"场景"做模板必然失控。** 每加一种厂商或冗余形态，模板数量乘一遍，而且大量模板内容高度重复。

## 四、核心设计：按设备角色分解，而非按场景枚举

### 4.1 关键洞察

一台设备需要什么配置，**不取决于整个机房是什么拓扑，只取决于它自己的四个属性 + 它的邻接关系**：

```
设备配置 = f(层级, 冗余形态, 上行邻接, 下行邻接)
```

拓扑是这些局部事实的涌现结果，不需要作为输入。举例：

- 结构一拓扑 A 的汇聚层设备：`层级=汇聚，冗余=vPC，上行=二层Po到核心对，下行=二层Po到接入对`
- 结构一拓扑 B 不存在汇聚层，接入层的上行邻接直接指向核心对——**接入层模板本身不变**，变的只是"上行对端是谁"这个参数

于是 100+ 种组合塌缩成：

```
配置片段（fragment）数量 = 层级角色(3) × 冗余形态(4) + 互联片段类型(4) + 协议片段(3)
                        ≈ 20 个片段 × 厂商数
```

片段可组合、可复用，新增一种拓扑不需要新模板，只需要新的邻接关系描述。

### 4.2 片段分类

| 片段类 | 片段 | 决定因素 | 举例内容 |
|--------|------|---------|---------|
| **冗余** | `redundancy.vpc` | 冗余形态 + 厂商 | `feature vpc` / domain / peer-keepalive / peer-link / peer-gateway |
| | `redundancy.mlag` | 同上 | `m-lag system-mac/number/priority` / keepalive / peer-link |
| | `redundancy.irf` | 同上 | IRF member/domain/priority/port |
| | `redundancy.none` | 单台 | 空片段 |
| **互联** | `uplink.l2po` | 结构一 | 二层 Po + trunk + allowed vlan + description |
| | `uplink.l3p2p` | 结构二 | P2P /30 三层口 + BFD + description |
| | `downlink.l2po` | 结构一/二的服务器口 | 二层 Po + access/trunk |
| | `downlink.l3p2p` | 结构二层间 | P2P /30 三层口 |
| **网关** | `gateway.svi_hsrp` | 网关层（结构一在核心，结构二在接入） | VLAN + SVI + HSRP（现网实测用 HSRP，带 `timers msec 250 msec 750`） |
| | `gateway.dhcp_relay` | 服务器靠 DHCP 获址时 | `ip dhcp relay address` + `relay information trusted` |
| **协议** | `routing.bgp_ebgp` | 结构二，到上游 | eBGP 邻居 + BFD + MD5 + `soft-reconfiguration` + `maximum-paths 32` |
| | `routing.bgp_ibgp_pair` | 结构二，成对设备间 | iBGP 走互联 VLAN + `update-source Vlan10` + `next-hop-self` |
| | `routing.ospf` | 存量机房 | 接口 enable + cost + passive + MD5 |
| | `routing.static` | 简单场景 | 静态路由 + tag |
| **基础** | `base.vlan` | 所有 | VLAN 定义 + 命名 |
| | `base.stp` | 结构一 | STP 模式 + 根桥优先级 + edge port |

### 4.3 设备配置意图（Device Intent）

每台设备的输入不是"选哪个模板"，而是一份**意图声明**：

```json
{
  "sn": "FDO21120U8N",
  "hostname": "rsw1_mdu3_prod_dc19_m01",
  "vendor": "h3c",
  "model": "S6805-54HF",
  "layer": "rsw",
  "idc": "DC19",
  "mdu": "MDU3",
  "architecture": "l3_bgp",
  "redundancy": {
    "mode": "mlag",
    "peer_hostname": "rsw2_mdu3_prod_dc19_m01",
    "member_id": 1,
    "peer_link": { "ports": ["FortyGigE1/0/53", "FortyGigE1/0/54"], "agg_id": 100 },
    "keepalive": { "local": "10.26.253.21", "peer": "10.26.253.22", "vrf": "management" }
  },
  "loopback0": "10.26.255.21/32",
  "bgp": {
    "local_as": 4200191003,
    "peers": [
      { "peer_hostname": "csw1_dc19_m01", "peer_as": 4200190001,
        "local_ip": "10.26.254.9/30", "peer_ip": "10.26.254.10", "local_port": "HundredGigE1/0/49" },
      { "peer_hostname": "csw2_dc19_m01", "peer_as": 4200190001,
        "local_ip": "10.26.254.13/30", "peer_ip": "10.26.254.14", "local_port": "HundredGigE1/0/50" }
    ]
  },
  "gateways": [
    { "vlan": 1003, "name": "Internal-MDU3", "cidr": "10.26.3.0/24", "svi_ip": "10.26.3.1/24" }
  ],
  "server_ports": {
    "range": "1-48", "mode": "access", "vlan": 1003, "agg_per_port": true
  }
}
```

渲染流程：

```
意图声明
  → 按 architecture + layer 决定需要哪些片段
  → 按 redundancy.mode + vendor 选具体片段实现
  → 片段按固定顺序渲染（vlan → 冗余 → 接口 → 网关 → 协议）
  → 输出该设备的业务配置
```

### 4.4 意图从哪来

人工填这份 JSON 不现实。意图的各字段应尽量**从规划推导**：

| 字段 | 来源 |
|------|------|
| `hostname` | 按[命名规范](../../../../docs/network/设备命名规范.md)由 层级+序号+MDU+用途+机房+楼层 拼出 |
| `local_as` | 按[AS 号规划](../../../../docs/network/AS号规划.md)由 机房+层级+MDU 算出（`42001`+DC 编号+层级编号） |
| `loopback0`、P2P /30、业务网段 | 从 IPAM 申领（`function_collector/func_ipam.py`） |
| `peer_hostname`、`local_port`/`peer_ip` | **按端口映射规则推导**，见 4.5 |
| `vlan`、网段 | 按 MDU 编号规则推导（如 MDU3 → vlan 1003） |
| `redundancy.mode` | 按机房代际/型号的默认策略（新机房 M-LAG，Cisco 接入 vPC） |

真正需要人工输入的只有：**SN、机柜位置、MDU 编号、上行对端设备与端口**。其余可算。

### 4.5 端口映射规则

这是预演中发现最需要固化的部分。从 2.2 的实测样本提炼：

| 规则 | 内容 | 依据 |
|------|------|------|
| 下行服务器口 | 端口 1~48 → Po1~Po48（Po 号 = 端口号），vPC ID 同号 | DC09 实测 |
| peer-link | 固定高位 Po 号（Cisco Po4000 / H3C BAGG100），成员取上行区最后两口 | DC09、DC19 实测 |
| 上行口 | 从上行区起始口依次分配，每个上行口单独一个 Po（单成员） | DC09 实测 Po1001/Po1002 |
| 端口描述 | `对端设备名::对端接口::L2或L3`（[端口与VLAN描述规范](../../../../docs/network/端口与VLAN描述规范.md)） | 规范 |

"上行区"与"下行区"的划分依型号而定（如 N9K-C93180YC-EX 是 48×25G 下行 + 6×100G 上行），这需要一张**型号端口布局表**：

```sql
CREATE TABLE IF NOT EXISTS model_port_layout (
    vendor      VARCHAR(20)  NOT NULL COMMENT '厂商',
    model       VARCHAR(100) NOT NULL COMMENT '型号',
    zone        VARCHAR(20)  NOT NULL COMMENT '端口区：access下行/uplink上行/peerlink',
    port_prefix VARCHAR(50)  NOT NULL COMMENT '接口名前缀，如 Ethernet1/ 或 HundredGigE1/0/',
    port_start  INT          NOT NULL COMMENT '起始端口号',
    port_end    INT          NOT NULL COMMENT '结束端口号',
    speed       VARCHAR(20)  NOT NULL COMMENT '速率：25G/40G/100G/200G/400G',
    breakout    VARCHAR(20)  NULL     COMMENT '拆分形态，如 4x100G，不拆为空',
    PRIMARY KEY(vendor, model, zone)
) COMMENT='型号端口布局';
```

有了这张表，"上行第 1 口是哪个接口名"就能算出来，不需要每台设备手填。400G/200G 的差异主要落在这张表的 `speed` 和 `breakout` 字段上——**这也回答了框架待确认的第 3 条：400G/200G 不需要独立模板，是同一套片段 + 不同端口布局**。

## 五、预演验证：用现网设备反推

检验模型是否够用的方法：**能否用意图 + 片段重新生成一台现网设备的实际配置**。

以 `rsw1_mdu10_prod_dc09_m01` 为例（结构一、拓扑 B、vPC、cisco_nx）：

| 实测配置 | 对应片段 | 意图字段 |
|---------|---------|---------|
| vPC domain 109、peer-link Po4000(Eth1/51-52)、peer-gateway | `redundancy.vpc` | `redundancy.mode=vpc, member_id, peer_link.ports` |
| Po1~Po48 + LACP + vlan 1000 + vPC 1~48 | `downlink.l2po` | `server_ports.range=1-48, vlan=1000` |
| Po1001(Eth1/49)、Po1002(Eth1/50) Routed | `uplink.l3p2p`（单成员 Po 封装） | `uplink.peers[]` 两个核心 |
| vlan 1,10,1000 | `base.vlan` | `gateways[]` / `server_ports.vlan` |

四个片段 + 一份意图能覆盖这台设备的业务配置，模型成立。

**待补充验证**：
- 结构二（全三层 BGP）在现网找一台已部署的接入层设备做同样反推。DC19 是新机房，`new_csw1_dc19_m01` 可验证核心层 M-LAG + BGP 片段。
- IRF 形态现网暂未找到样本，若确实在用需补一台。

## 六、数据库设计（初稿）

```sql
-- 配置片段库
CREATE TABLE IF NOT EXISTS arch_fragment (
    fid         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '片段ID',
    frag_key    VARCHAR(50)  NOT NULL COMMENT '片段标识，如 redundancy.vpc / uplink.l3p2p',
    vendor      VARCHAR(20)  NOT NULL COMMENT '厂商',
    layer       VARCHAR(20)  NOT NULL DEFAULT '*' COMMENT '适用层级：csw/asw/rsw，*通用',
    sort_num    INT          NOT NULL DEFAULT 0 COMMENT '渲染顺序',
    render      TEXT         NOT NULL COMMENT '渲染模板，含{{变量}}与循环语法',
    version     INT          NOT NULL DEFAULT 1 COMMENT '版本号',
    descr       VARCHAR(300) NOT NULL DEFAULT '' COMMENT '说明与规范依据',
    PRIMARY KEY(fid),
    UNIQUE KEY uk_frag (frag_key, vendor, layer, version)
) COMMENT='业务架构配置片段';

-- 设备意图声明
CREATE TABLE IF NOT EXISTS device_intent (
    iid          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '意图ID',
    sn           VARCHAR(100) NOT NULL DEFAULT '' COMMENT '序列号',
    hostname     VARCHAR(100) NOT NULL COMMENT '主机名',
    mgmt_ip      VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '管理IP',
    vendor       VARCHAR(20)  NOT NULL COMMENT '厂商',
    model        VARCHAR(100) NOT NULL COMMENT '型号',
    layer        VARCHAR(20)  NOT NULL COMMENT '层级：csw/asw/rsw',
    idc          VARCHAR(20)  NOT NULL COMMENT '机房',
    mdu          VARCHAR(20)  NOT NULL DEFAULT '' COMMENT 'MDU编号',
    architecture VARCHAR(20)  NOT NULL COMMENT '结构：l2_gw_core传统 / l3_bgp全三层',
    intent_json  LONGTEXT     NOT NULL COMMENT '完整意图JSON（冗余/BGP/网关/端口等）',
    status       VARCHAR(20)  NOT NULL DEFAULT 'draft' COMMENT 'draft/rendered/deployed',
    operator     VARCHAR(40)  NOT NULL DEFAULT '',
    created_at   VARCHAR(15)  NOT NULL,
    updated_at   VARCHAR(15)  NOT NULL,
    PRIMARY KEY(iid),
    UNIQUE KEY uk_hostname (hostname),
    INDEX idx_idc_mdu (idc, mdu)
) COMMENT='设备业务配置意图';
```

按 6.0 的输入契约决定，必需的表只有两张：

| 表 | 必需性 | 用途 |
|----|-------|------|
| `device_intent` | **必需** | 存意图 JSON（输入契约本身），兼作变更时的 diff 基准 |
| `arch_interconnect` | **必需** | 存互联声明，两端配置从同一记录渲染 |
| `arch_fragment` | 必需 | 片段渲染模板，按 `frag_key + vendor` 组织 |
| `model_port_layout` | **可选** | 仅推导工具需要（算接口名）。手写 JSON 时接口名直接给出 |
| `arch_naming_rule` / `arch_mapping` / `arch_numbering_rule` | **可选** | 仅推导工具需要，见 [03b](./03b_input_to_intent.md) |

四张可选表全部属于推导层。不做推导工具时，本模块只需三张表。

**互联必须独立成表**，不能挂在 `device_intent` 上——一条链路两端的 Po 号、vPC ID、trunk VLAN、端口描述必须互相对应，从同一条记录渲染才能保证一致。详见预演文档 8.3。

**不建"场景/拓扑"表**——拓扑不是输入，是意图+互联的涌现结果。想看拓扑图，从互联表渲染即可（现网已有 LLDP 数据可对照，见 `tables/TopologyDB.py`）。

## 六、输入契约：意图 JSON 直接作为输入

### 6.0 设计决定

**意图 JSON 就是输入模型，渲染器只认它。** 不强制经过"YAML 简化输入 → 推导 → 意图"这一层。

理由：推导逻辑天然绑定特定规则（命名规范、AS 分配、VLAN 方案、端口布局），这些规则各机房/各阶段都可能不同。把推导做成必经路径，等于把项目绑死在当前规则上。意图 JSON 作为契约则完全中立——任何拓扑、任何厂商、任何规则，都只是不同的 JSON 内容，渲染器不用改。

| 环节 | 定位 | 可否绕过 |
|------|------|---------|
| 推导（输入简化 → 意图） | **可选辅助工具** | 可。手写 JSON 或自行脚本生成皆可 |
| 校验（意图自洽性） | **强制** | 不可。见 6.2 |
| 渲染（意图 → 配置） | 核心 | 不可 |

### 6.1 输入结构：设备 + 互联

输入分两部分，**互联必须独立声明，不能只在设备里各写一半**：

```json
{
  "meta": { "idc": "DC09", "batch_name": "MDU5-8上线", "architecture": "l2_gw_core" },

  "devices": [
    {
      "hostname": "rsw1_mdu5_prod_dc09_m01",
      "sn": "FDO24110ABC",
      "vendor": "cisco_nx",
      "model": "N9K-C93180YC-FX3",
      "layer": "rsw",
      "mode": "create",
      "redundancy": {
        "mode": "vpc", "domain": 105, "member_id": 1, "role_priority": 1,
        "peer_hostname": "rsw2_mdu5_prod_dc09_m01",
        "peer_link": { "agg_id": 4000, "ports": ["Ethernet1/51", "Ethernet1/52"] },
        "keepalive": { "local": "10.143.232.45", "peer": "10.143.232.46", "vrf": "management" },
        "extras": { "peer_switch": true, "peer_gateway": true, "arp_synchronize": true }
      },
      "vlans": [ { "id": 1005, "name": "Internal-MDU5::10.143.5.0/24" } ],
      "server_ports": { "range": "1-40", "mode": "access", "vlan": 1005, "agg_per_port": true,
                        "stp_type": "edge", "bpdufilter": true }
    },
    { "hostname": "rsw2_mdu5_prod_dc09_m01", "...": "member_id=2，镜像字段相反" },
    { "hostname": "asw1_mdu5_dc09_m01", "mode": "modify", "vlans": [ { "id": 1005, "name": "..." } ] },
    { "hostname": "asw2_mdu5_dc09_m01", "mode": "modify", "...": "" }
  ],

  "interconnects": [
    {
      "type": "l2_trunk",
      "allowed_vlan": "1,1005",
      "a": { "pair": ["rsw1_mdu5_prod_dc09_m01", "rsw2_mdu5_prod_dc09_m01"],
             "agg_id": 100, "vpc_id": 100, "ports": ["Ethernet1/49", "Ethernet1/50"] },
      "b": { "pair": ["asw1_mdu5_dc09_m01", "asw2_mdu5_dc09_m01"],
             "agg_id": 105, "vpc_id": 105, "ports": ["Ethernet1/5", "Ethernet1/6"] }
    }
  ]
}
```

**为什么互联必须独立成数组**：一条链路两端的 Po 号、vPC ID、trunk VLAN、端口描述必须对应。如果让每台设备各自声明自己的上行/下行，两端对不上时 JSON 依然合法、渲染出的配置依然语法正确，只有下发后才发现链路 up 但业务不通。独立声明后两端从同一个对象渲染，结构上不可能对不上。

这是对输入格式的唯一结构性要求，成本是多一个数组，不是多写代码。

`mode` 字段区分 `create`（全新完整配置）与 `modify`（增量），对应[拓扑 A 预演](./03a_walkthrough_topology_a.md) 8.2 节的三类配置。

### 6.2 强制校验（唯一不可绕过的逻辑）

校验不理解业务规则，只检查 JSON 内部自洽。它拦的是**静默失败**——格式合法、语法正确、下发才出问题的那类错误：

| 校验项 | 规则 | 不校验的后果 |
|--------|------|-------------|
| 成对设备镜像 | 同 `peer_hostname` 互指的两台，`domain`/`peer_link.agg_id` 必须相同，`member_id`/`role_priority` 必须不同 | peer 建不起来 |
| 互联两端引用有效 | `a.pair`/`b.pair` 中的 hostname 必须在 `devices` 中存在（或已在网） | 渲染出悬空配置 |
| 互联端口数匹配 | `a.ports` 与 `b.ports` 数量一致，且与 pair 规模匹配 | 物理链路映射错位 |
| 设备内 agg_id 唯一 | 同一 hostname 下所有 `agg_id`（含 peer_link、互联、server_ports 展开值）不重复 | 下发失败 |
| 同 domain 内 vpc_id 唯一 | 同 `domain` 下 `vpc_id` 不重复 | 下发失败 |
| 相邻互联 domain 不同 | 一条互联两端的 `domain` 不能相同（双边 vPC 要求） | peer 异常 |
| VLAN 引用一致 | 设备 `vlans` 必须覆盖其所有互联的 `allowed_vlan` 与 `server_ports.vlan` | 业务不通 |
| trunk VLAN 并集（结构一） | `modify` 模式设备的上行 `allowed_vlan` 必须包含其下所有互联的 VLAN | **覆盖下发断掉已有业务** |

最后一条是唯一能断现网业务的，必须有独立单测。

校验失败一律拒绝渲染，不输出半成品。

### 6.3 允许的压缩写法

为减少输入量，渲染器接受两处压缩，展开过程纯机械、不涉及跨设备推理：

| 压缩写法 | 展开结果 |
|---------|---------|
| `server_ports: {range: "1-40", mode: "access", vlan: 1005, agg_per_port: true}` | 40 个 Po + 40 个成员口配置 |
| `peer_link.ports: ["Ethernet1/51","Ethernet1/52"]` | 两个成员口加入同一 Po |

除此之外意图应是完全展开的事实。特别是**不接受"规则式"写法**（如 `vlan: "1000+mdu"`）——那会把推导逻辑塞回渲染器，失去通用性。

### 6.4 推导工具（可选层）

[输入模型→意图转换推演](./03b_input_to_intent.md)中的推导逻辑降级为可选工具：输入简化 YAML，输出符合 6.1 格式的意图 JSON。

它的四个方法（`resolve_ports`/`claim_network`/`expand_interconnect`/`converge_vlans`）与三张配置表（`arch_naming_rule`/`arch_mapping`/`arch_numbering_rule`）不再是必经路径。不用它时：手写 JSON、自己脚本生成、从现网反推、从 Excel 导出都可以。

**实施上建议先做渲染器 + 校验器，推导工具延后。** 这样系统立刻可用且通用，推导工具什么时候做、做到什么程度，取决于手写 JSON 的实际负担有多大。

### 6.5 这个选择的代价

通用性不是免费的，诚实记录代价：

| 维度 | 意图 JSON 直接输入 | 经推导层 |
|------|------------------|---------|
| 通用性 | 高，换规则/换厂商/换拓扑不改代码 | 低，规则变化要改表或改代码 |
| 输入量（4 组 8 台） | 大，12 份设备意图 + 4 条互联，需逐一填写 | 小，约 25 行 YAML |
| 出错位置 | 人工填写时 | 推导逻辑里 |
| 批量重复性工作 | 多，相似设备要重复填 | 少 |
| 对使用者要求 | 需理解 vPC/BGP 配置细节 | 只需知道机房/MDU/型号 |

**结论**：通用性优先，用强制校验兜住人工填写的错误。输入量的问题后续用推导工具或模板复制（填一个组、复制改 MDU 号）缓解，但不把推导做成必经路径。

## 六A、意图转配置的环节代价

确定输入契约后，链路变成：

```
① 意图 JSON（输入契约，见第六节）
      ↓  ← 强制校验，6.2
② 校验通过的意图
      ↓  ← 可复用 lib_config 骨架，见 6C
③ 厂商配置文本
      ↓
④ 变更工单下发

（可选）简化 YAML → 推导工具 → ① ，见 6.4
```

必经路径的工作量：

| 环节 | 代价 | 说明 |
|------|------|------|
| 校验器 | 小 | 8 条规则，纯结构检查，不含业务规则。见 6.2 |
| ① → ③ 意图转配置 | 中，框架可复用 | `lib_config` 注册/分发骨架直接用，模型和 encoder 方法要新写。见 6C |
| ③ → ④ 下发 | 小 | `function_op/order_manage.py` 现成 |
| （可选）推导工具 | 大 | 不在必经路径上，可延后或不做。见 [03b](./03b_input_to_intent.md) |

## 六B、推导层的内部结构（可选实现）

> 本节描述的是 6.4 的**可选推导工具**内部结构，不是必经路径。按 6.0 的决定，意图 JSON 直接作为输入，本节内容可延后实现或不实现。保留在此是因为：若后续手写 JSON 负担过大，这是最自然的补充方向。

这步不是字段映射，而是四类推导的叠加。以[拓扑 A 预演](./03a_walkthrough_topology_a.md)的输入为例，一份 15 行 YAML 要展开成 6 台设备的意图 + 3 条互联记录。

### 6B.1 四类推导

| 类型 | 输入 | 输出 | 依赖 |
|------|------|------|------|
| **纯函数推导** | `mdu: MDU5` + `idc: DC09` + `member_id: 1` | `hostname: rsw1_mdu5_prod_dc09_m01`、`local_as`、`vlan_name` | 命名规范、AS 号规划，无外部状态 |
| **资源申领** | 业务类型 + 机房 | 业务网段、P2P /30、Loopback | IPAM（有状态，需防重复分配） |
| **编号分配** | 组内设备 + 上游对端 | vPC domain、Po 号、vPC ID | **需查现网已占用**，有冲突风险 |
| **拓扑展开** | `uplink_to.pair` + `ports` | `arch_interconnect` 记录 + 两端 `members` 映射 | 型号端口布局表 |

纯函数推导那类最简单，写死规则即可。真正的难点是后三类——都需要查询外部状态，且都可能失败。

### 6B.2 跨设备约束是核心难点

单台设备的意图无法独立生成，有四处必须全局计算：

| 约束 | 说明 | 不满足的后果 |
|------|------|-------------|
| 成对设备的镜像一致性 | vPC domain 相同、Po 号相同、vPC ID 相同，但 role priority / IP 末位 / HSRP priority 相反 | peer 建不起来 |
| 互联两端对应 | 两端 Po 号各自唯一但描述互指，trunk VLAN 列表一致 | 链路 up 但业务不通 |
| VLAN 自底向上并集 | 汇聚层上行 trunk = 其下所有接入对 VLAN 的并集（仅结构一需要） | 新 MDU 业务不通，或误删已有 VLAN |
| 编号全局唯一 | 同设备内 Po 号唯一、同 domain 内 vPC ID 唯一、相邻对 domain 不同 | 配置下发失败或冲突 |

**这四条决定了转换器的输入必须是整个批次 + 现网已有状态，不能逐台独立转换。**

### 6B.3 转换器需要的外部数据

```
device_intent        已有设备的意图 → 算 VLAN 并集、查编号占用
arch_interconnect    已有互联 → 查 Po/vPC ID 占用
model_port_layout    型号端口布局 → 算上行区/下行区的实际接口名
ports 表             实际端口占用 → 校验上游端口容量
IPAM                 网段/P2P/Loopback 申领
docs/idc/MDU配置规格  业务类型 → 规格校验
LLDP（TopologyDB）    下发前核对实际接线与 uplink_to 是否一致
```

六个数据源加一个校验闸门。这也解释了为什么这步代价大——它是整个模块里唯一需要"理解现网全局状态"的环节。

### 6B.4 建议的实现分层

> 字段级完整推演、机制归并分析见 [输入模型→意图转换推演](./03b_input_to_intent.md)。结论：25 个字段归并为 6 种机制，只有 4 个方法需要专门写代码，其余由三张配置表驱动。

```
function_arch/
    input_parser.py       YAML 输入解析 + 格式校验
    derive_naming.py      纯函数推导：主机名、AS、VLAN 名
    derive_resource.py    资源申领：IPAM 对接
    derive_numbering.py   编号分配 + 冲突检测
    derive_topology.py    互联展开 + 端口映射
    vlan_converge.py      VLAN 并集计算（结构一）
    intent_builder.py     汇总上述结果，产出 intent + interconnect
    intent_render.py      调 lib_config 渲染
```

拆这么细是因为每一块的失败模式不同、测试方式不同。编号冲突检测和 VLAN 并集计算尤其需要独立单测——它们错了不会报错，只会生成看似正常但实际有问题的配置。

## 六C、意图转配置：lib_config 的复用边界

### 6C.1 现状

`lib_config` 当前只覆盖策略类对象：

```
encoders/encode_cisco.py 的 section：
    prefix_lists      encode_prefix_lists()
    access_lists      encode_access_lists()
    address_groups    encode_address_groups()
    port_groups       encode_port_groups()

models.py 的模型：
    PrefixListEntry/Config、AclEntry/Config、AddrGroupEntry/Config、PortGroupEntry/Config
```

**没有任何设备级模型**——接口、Port-Channel、VLAN、SVI、vPC/M-LAG、BGP、HSRP 全都不在。

### 6C.2 可复用的部分

| 复用项 | 位置 | 用途 |
|--------|------|------|
| `BaseEncoder.encode(data, sections, operation)` 签名 | `encoders/encode_base.py:66` | 片段标识直接当 section 用 |
| `@register_encoder` 厂商注册 + `get_encoder()` 分发 | `encoders/__init__.py` | 按 vendor 选 encoder，机制现成 |
| `_validate_sections()` + `_get_encode_method()` | `encode_base.py:47,147` | section 校验与方法路由 |
| `operation='add'/'del'` 语义 | 全局 | 正好对应新建配置 / 整组下线清理 |
| `_dict_to_models()` 反序列化 | `encode_base.py:125` | 意图 JSON → 模型对象 |

这套骨架与片段模型高度契合：**一个片段 = 一个 section，一个厂商 = 一个 encoder 子类**。架构不用改。

### 6C.3 需要新建的部分

`models.py` 新增设备级模型：

```python
@dataclass
class InterfaceConfig:        # 物理口/逻辑口通用
    name: str                 # Ethernet1/49 / port-channel100 / Vlan1000
    description: str
    mode: str                 # access / trunk / routed
    access_vlan: Optional[int] = None
    allowed_vlan: Optional[str] = None
    ip_address: Optional[str] = None
    agg_id: Optional[int] = None      # channel-group 号
    agg_mode: str = 'active'          # LACP 模式
    vpc_id: Optional[int] = None
    stp_type: Optional[str] = None    # edge / network
    bpdufilter: bool = False
    bfd: bool = False
    shutdown: bool = False

@dataclass
class VlanConfig:
    vlan_id: int
    name: str

@dataclass
class RedundancyConfig:
    mode: str                 # vpc / mlag / irf / none
    domain: Optional[int]
    member_id: int
    peer_link: Dict[str, Any]         # {agg_id, ports}
    keepalive: Dict[str, Any]         # {local, peer, vrf}
    system_mac: Optional[str] = None  # M-LAG 用
    extras: Dict[str, Any] = field(default_factory=dict)  # peer-gateway 等厂商特性

@dataclass
class SviGatewayConfig:
    vlan_id: int
    description: str
    ip_address: str                   # 本机地址
    vip: Optional[str] = None         # HSRP VIP
    hsrp_group: Optional[int] = None
    hsrp_priority: Optional[int] = None
    hsrp_timers: Optional[str] = None
    dhcp_relay: List[str] = field(default_factory=list)

@dataclass
class BgpNeighborConfig:
    peer_ip: str
    remote_as: int
    description: str = ''
    bfd: bool = False
    password: Optional[str] = None
    update_source: Optional[str] = None
    next_hop_self: bool = False
    soft_reconfiguration: bool = True

@dataclass
class BgpConfig:
    local_as: int
    router_id: str
    networks: List[str]
    neighbors: List[BgpNeighborConfig]
    maximum_paths: int = 32
```

各 encoder 新增方法（以 Cisco 为例，H3C/华为同构但语法不同）：

```
encode_vlans()          → vlan 1000 / name xxx
encode_interfaces()     → interface + switchport/ip address + channel-group + vpc
encode_redundancy()     → vpc domain / peer-keepalive / peer-link（M-LAG/IRF 各自实现）
encode_svi_gateway()    → interface Vlan + hsrp + dhcp relay
encode_bgp()            → router bgp + address-family + neighbor
encode_stp()            → spanning-tree 模式与优先级
```

约 6 个方法 × 3 个厂商 = 18 个新方法，加 6 个新模型。工作量不小但结构清晰、可逐个交付。

### 6C.4 三个实现注意点

1. **成对设备的镜像差异放在模型里，不在 encoder 里**。`member_id` 决定的 role priority、IP 末位、HSRP priority 应由 6B 的意图构建阶段算好，encoder 只负责把模型翻译成文本。否则每个厂商的 encoder 都要重复一遍镜像逻辑。
2. **循环生成的端口要在意图里展开**。40 个服务器口应在意图里就是 40 个 `InterfaceConfig`，不要让 encoder 去解析 `range: 1-40`。意图应该是完全展开的事实，不含待解释的规则。
3. **`operation='del'` 要注意 H3C 的 undo 语法限制**。H3C 的 `undo` 比配置形式窄，不能机械加前缀（多带参数报 `Too many parameters`）。整组下线的清理命令需要 H3C encoder 单独处理，不能复用 add 路径取反。

## 七、渲染与下发

```
意图 → 片段选择 → 渲染 → 预览 diff → 推送变更工单 → 人工审批 → 工单执行
```

与模块 2 的区别：**业务配置下发时设备已纳管可 SSH**，所以能做下发前 diff 预览（拿当前 running-config 与渲染结果比），这不是基线那种"模板 vs 在网设备"的无意义比对，而是"即将下发的变更内容"预览。

一律走变更工单（`function_op/order_manage.py`），不自动下发。BGP/M-LAG 配错会导致全机柜断网。

## 八、待确认

1. **汇聚层（仓库 `asw`）现网是否真实存在**？2.2 实测的 DC09 是核心—接入二级结构，没看到汇聚层。如果三级结构只存在于规划中而非现网，拓扑 A/C 可以降低优先级。
2. **IRF 是否在用**？现网实测只找到 vPC（DC09 接入）、M-LAG（DC19 核心）、独立双核心（DC07）。IRF 若无存量，片段可以先不做。
3. **结构一的网关冗余用 VRRP 还是 vPC/M-LAG 的 anycast 网关**？两者配置差异大，需要定一种。
4. **新建机房是否只用结构二（全三层 BGP）**？`docs/network/bgp.md` 说"新建 IDC 使用 eBGP 作为标准"，若结构一只用于存量机房扩容，那么自动化上线的主路径应该是结构二，结构一按"兼容存量"对待。这个定位会显著影响实施优先级。
5. **型号端口布局表的数据从哪来**？手工录入还是从 `devices`/`ports` 表的实际接口名反推？现网 14+ 型号，手工录一次可接受。

返回：[整体框架](./README.md)
