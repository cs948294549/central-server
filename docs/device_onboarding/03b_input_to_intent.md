# 输入模型 → 意图 JSON 转换过程详细推演

## 文档信息

- 所属：[模块 3 业务架构](./03_business_architecture.md)
- 目的：逐字段推演转换过程，并回答"每个功能是否都需要单独方法适配"
- 结论预告：**不需要。8 类字段归并为 5 种机制，其中 3 种是配置驱动的通用机制，只有 2 种需要专用逻辑**

## 一、字段级推演表

输入（[拓扑 A 预演](./03a_walkthrough_topology_a.md) 2.1 节）15 行 YAML，输出 rsw1 一台的意图。逐字段追踪：

| # | 输出字段 | 值 | 从哪来 | 机制 |
|---|---------|----|--------|------|
| 1 | `hostname` | `rsw1_mdu5_prod_dc09_m01` | `layer`+`member_id`+`mdu`+`business_type`+`idc`+楼层 | M1 模板拼接 |
| 2 | `vendor` | `cisco_nx` | `model` 查型号库 | M2 查表 |
| 3 | `model` | `N9K-C93180YC-FX3` | 输入直给 | M0 直传 |
| 4 | `layer` | `rsw` | 输入组的设备层级（接入组固定 rsw） | M0 直传 |
| 5 | `architecture` | `l2_gw_core` | 输入直给 | M0 直传 |
| 6 | `idc` / `mdu` | `DC09` / `MDU5` | 输入直给 | M0 直传 |
| 7 | `redundancy.mode` | `vpc` | 输入直给 | M0 直传 |
| 8 | `redundancy.domain` | `105` | `100 + MDU号`，校验未占用 | **M3 编号分配** |
| 9 | `redundancy.role_priority` | `1` | `member_id` 查镜像规则表 | M2 查表 |
| 10 | `redundancy.peer_hostname` | `rsw2_mdu5_prod_dc09_m01` | 同组另一 `member_id` 走 #1 | M1 模板拼接 |
| 11 | `peer_link.agg_id` | `4000` | 编号规则常量 | M3 编号分配 |
| 12 | `peer_link.ports` | `[Eth1/51, Eth1/52]` | 型号端口布局 peerlink 区 | **M4 端口布局** |
| 13 | `keepalive.local/peer` | `10.143.232.45/.46` | 模块 2 已分配的管理 IP | M2 查表 |
| 14 | `keepalive.vrf` | `management` | 厂商级变量（复用模块 2 的 `baseline_variable`） | M2 查表 |
| 15 | `vlans[].id` | `1005`（结构一）/ `1000`（结构二） | 规则按 architecture 分支 | M1 模板拼接 |
| 16 | `vlans[].name` | `Internal-MDU5::10.143.5.0/24` | 模板 + #17 的结果 | M1 模板拼接 |
| 17 | 业务网段 | `10.143.5.0/24` | **IPAM 申领** | **M5 资源申领** |
| 18 | `uplinks[].agg_id` | `100` | 编号规则 + 冲突校验 | M3 编号分配 |
| 19 | `uplinks[].vpc_id` | `100` | 同 agg_id（Cisco 惯例） | M3 编号分配 |
| 20 | `uplinks[].type` | `l2_trunk` | `architecture` 映射：`l2_gw_core`→l2_trunk，`l3_bgp`→l3_p2p | M2 查表 |
| 21 | `uplinks[].allowed_vlan` | `1,1005` | 本组 VLAN + 管理 VLAN | M1 模板拼接 |
| 22 | `uplinks[].peer_desc` | `asw_pair_mdu5_dc09_m01::Po105` | **互联对端的 agg_id** | **M6 拓扑展开** |
| 23 | `uplinks[].members[]` | 2 条端口映射 | `uplink_to.ports` × 型号上行区 | M6 拓扑展开 |
| 24 | `server_ports.range` | `1-40` | `server_count` + 型号下行区容量校验 | M4 端口布局 |
| 25 | `server_ports.vlan` | `1005` | 同 #15 | M1 模板拼接 |

## 二、机制归并

25 个字段，看似要 25 套逻辑，实际归并为 **6 种机制**，其中前 4 种是通用的：

| 机制 | 字段数 | 性质 | 是否需要专用方法 |
|------|-------|------|----------------|
| **M0 直传** | 6 | 输入字段原样搬运 | 否，一行字典赋值 |
| **M1 模板拼接** | 7 | 按格式串拼接，纯函数 | **否，一个通用渲染器 + 配置表** |
| **M2 查表** | 6 | 查映射关系 | **否，一个通用查表器 + 映射表** |
| **M3 编号分配** | 4 | 算号 + 查占用 + 冲突检测 | **否，一个通用分配器 + 规则表** |
| **M4 端口布局** | 3 | 查型号端口区 + 算接口名 | 是，但只一个方法 |
| **M5 资源申领** | 1 | IPAM 有状态申领 | 是，专用 |
| **M6 拓扑展开** | 2 | 构建互联 + 两端映射 | 是，专用 |

**答案：不需要每个功能一个方法。** M1/M2/M3 覆盖 17 个字段（68%），全部由配置表驱动，加新字段只改表不改代码。真正需要写专用逻辑的只有 M4/M5/M6 三处。

## 三、四种通用机制的实现

### 3.1 M1 模板拼接 —— 一个渲染器 + 规则表

所有"按格式串拼接"的字段共用一个渲染器：

```python
def render_rule(rule: str, ctx: dict) -> str:
    """rule 中的 {{var}} 用 ctx 替换，支持简单函数如 {{mdu|num}}"""
```

规则存表，不写死在代码里：

```sql
CREATE TABLE IF NOT EXISTS arch_naming_rule (
    rule_key    VARCHAR(50)  NOT NULL COMMENT '规则标识：hostname/vlan_name/port_desc…',
    scope       VARCHAR(30)  NOT NULL DEFAULT '*' COMMENT '适用范围：architecture或layer，*通用',
    rule_tpl    VARCHAR(300) NOT NULL COMMENT '格式串，含{{变量}}',
    descr       VARCHAR(200) NOT NULL DEFAULT '',
    PRIMARY KEY(rule_key, scope)
) COMMENT='命名与格式规则';
```

实际规则：

| rule_key | scope | rule_tpl | 产出示例 |
|----------|-------|----------|---------|
| `hostname` | `rsw` | `{{layer}}{{member_id}}_{{mdu\|lower}}_{{env}}_{{idc\|lower}}_{{floor}}` | `rsw1_mdu5_prod_dc09_m01` |
| `hostname` | `asw` | `{{layer}}{{member_id}}_{{mdu\|lower}}_{{idc\|lower}}_{{floor}}` | `asw1_mdu5_dc09_m01` |
| `vlan_id` | `l2_gw_core` | `{{1000+mdu_num}}` | `1005` |
| `vlan_id` | `l3_bgp` | `1000` | `1000`（固定） |
| `vlan_name` | `*` | `Internal-{{mdu}}::{{cidr}}` | `Internal-MDU5::10.143.5.0/24` |
| `port_desc_l2` | `*` | `{{peer_host}}::{{peer_port}}::L2` | `asw1_mdu5_dc09_m01::e1/5::L2` |
| `local_as` | `*` | `42001{{dc_num\|pad3}}{{layer_code}}{{mdu_num\|pad2}}` | `4200051005` |
| `router_id` | `*` | `{{loopback0_ip}}` | `172.21.34.19` |

**结构一与结构二的 VLAN 规则差异（#15）就落在 `scope` 字段上**，不需要代码分支。这是把规则做成数据的直接收益——[拓扑 A 预演](./03a_walkthrough_topology_a.md) 3.1 节发现的"VLAN 规则搞错了"那类问题，改表即可修正。

### 3.2 M2 查表 —— 一个查表器 + 映射表

六个字段的共性是"A 值映射到 B 值"：

```sql
CREATE TABLE IF NOT EXISTS arch_mapping (
    map_type    VARCHAR(30)  NOT NULL COMMENT '映射类型',
    from_key    VARCHAR(100) NOT NULL COMMENT '源值',
    to_value    VARCHAR(300) NOT NULL COMMENT '目标值（可为JSON）',
    PRIMARY KEY(map_type, from_key)
) COMMENT='架构映射关系';
```

| map_type | from_key | to_value | 对应字段 |
|----------|----------|----------|---------|
| `model_vendor` | `N9K-C93180YC-FX3` | `cisco_nx` | #2 |
| `arch_uplink_type` | `l2_gw_core` | `l2_trunk` | #20 |
| `arch_uplink_type` | `l3_bgp` | `l3_p2p` | #20 |
| `mirror_rule` | `vpc:1` | `{"role_priority":1,"hsrp_priority":150,"ip_offset":2,"preempt":true}` | #9 |
| `mirror_rule` | `vpc:2` | `{"role_priority":2,"hsrp_priority":140,"ip_offset":3,"preempt":false}` | #9 |
| `layer_code` | `rsw` | `1` | AS 号计算用 |

`mirror_rule` 是这张表最有价值的用法——**成对设备的全部镜像差异集中在一处**。[模块 3](./03_business_architecture.md) 6C.4 提到"镜像差异要在意图阶段算好、不进 encoder"，这张表就是落点。新增一种镜像差异（比如 M-LAG 的 system-number）只加一个 JSON 键。

### 3.3 M3 编号分配 —— 一个分配器 + 规则表

四个编号字段的共性：**按规则算出候选号 → 查是否被占用 → 占用则按策略避让或报错**。

```sql
CREATE TABLE IF NOT EXISTS arch_numbering_rule (
    num_key     VARCHAR(50) NOT NULL COMMENT '编号类型：vpc_domain/peerlink_agg/uplink_agg/server_agg',
    scope       VARCHAR(30) NOT NULL DEFAULT '*' COMMENT '适用层级或厂商',
    formula     VARCHAR(200) NOT NULL COMMENT '计算式，如 100+{{mdu_num}} 或常量 4000',
    uniq_scope  VARCHAR(30) NOT NULL COMMENT '唯一性范围：device/domain/pair/idc',
    on_conflict VARCHAR(20) NOT NULL DEFAULT 'error' COMMENT 'error报错 / next取下一个可用',
    range_min   INT NULL COMMENT '取值下界',
    range_max   INT NULL COMMENT '取值上界',
    PRIMARY KEY(num_key, scope)
) COMMENT='编号分配规则';
```

实际规则：

| num_key | formula | uniq_scope | on_conflict | 说明 |
|---------|---------|-----------|-------------|------|
| `vpc_domain` | `100+{{mdu_num}}` | `idc` | `error` | 相邻对 domain 不能相同，冲突必须人工介入 |
| `peerlink_agg` | `4000` | `device` | `error` | 常量，冲突说明该设备已有 peer-link |
| `uplink_agg` | `100` | `device` | `next` | 本设备内唯一即可，占用则取 101 |
| `server_agg` | `{{port_num}}` | `device` | `error` | Po 号 = 端口号，冲突说明端口已被占 |
| `downlink_agg`（上游侧） | `100+{{mdu_num}}` | `device` | `next` | 同一台 asw 上各 MDU 必须不同 |

分配器本身是通用的：

```python
def allocate(num_key, scope_ctx, idc, device=None, domain=None) -> int:
    rule = get_numbering_rule(num_key, scope_ctx['layer'])
    candidate = eval_formula(rule.formula, scope_ctx)
    while is_occupied(candidate, rule.uniq_scope, idc, device, domain):
        if rule.on_conflict == 'error':
            raise NumberConflict(num_key, candidate, ...)
        candidate += 1
        if rule.range_max and candidate > rule.range_max:
            raise NumberExhausted(num_key)
    return candidate
```

`is_occupied()` 查 `arch_interconnect` 和 `device_intent`。**`on_conflict` 两种策略的区分很重要**：`vpc_domain` 冲突意味着编号规划有问题，自动避让会掩盖问题；`uplink_agg` 冲突是正常的扩容场景，自动取下一个即可。

### 3.4 M4 端口布局 —— 一个方法，查型号表

三个字段（#12 peer-link 端口、#23 上行端口、#24 服务器端口范围）共用一个方法：

```python
def resolve_ports(vendor, model, zone, count=None, start=None) -> List[str]:
    """按型号端口布局，返回指定区域的实际接口名列表
    zone: access / uplink / peerlink
    """
```

依赖 [模块 3](./03_business_architecture.md) 4.5 的 `model_port_layout` 表。N9K-C93180YC-FX3 的布局：

| zone | port_prefix | start | end | speed |
|------|-------------|-------|-----|-------|
| `access` | `Ethernet1/` | 1 | 48 | 25G |
| `uplink` | `Ethernet1/` | 49 | 50 | 100G |
| `peerlink` | `Ethernet1/` | 51 | 52 | 100G |

这里有个容量校验：`server_count=40` 要校验 `access` 区容量（48）够用，不够则报错。400G/200G 的差异也在这张表——只是 `speed` 和 `breakout` 不同，`resolve_ports` 方法本身不变。

## 四、两种专用机制

### 4.1 M5 资源申领 —— IPAM 缺"申领"能力

**现状问题**：`function_collector/func_ipam.py` 只有 CRUD（`add_network_address`、`get_network_address_list`、`delete_network_address`…），**没有"申领下一个可用网段"的方法**。`tables/IpamDB.py` 同样只有增删改查。

所以这块必须新建，而且要考虑并发：

```python
def claim_network(idc, business_type, prefix_len, purpose) -> str:
    """从该机房的规划池中申领一个未使用的网段
    1. 查该机房的网段池（父网段）
    2. 列出已分配子网
    3. 找第一个空洞，长度匹配 prefix_len
    4. 写入 IPAM 标记已占用（事务）
    5. 返回 CIDR
    """
```

三个要点：

| 要点 | 说明 |
|------|------|
| **幂等** | 同一个 MDU 重复渲染不能领到两个网段。按 `(idc, mdu, purpose)` 做唯一键，已有则返回原值 |
| **事务** | 并发申领必须串行化，否则两个批次领到同一网段。用数据库唯一约束兜底 |
| **可释放** | MDU 下线时要能归还。但归还不应立即可复用（防止地址在 ARP/路由表残留期被重分配），建议标记 `pending_release` + 延迟 N 天 |

同类申领还有：P2P /30、Loopback /32、管理 IP（模块 2 已处理）。四种资源可共用一个 `claim_*` 骨架，只是池不同、长度不同。

### 4.2 M6 拓扑展开 —— 唯一需要跨设备推理的部分

两个字段（#22 `peer_desc`、#23 `members`），但这是整个转换里最复杂的一步，因为要产出 `arch_interconnect` 记录并保证两端对应。

输入：

```yaml
uplink_to:
  pair: [asw1_mdu5_dc09_m01, asw2_mdu5_dc09_m01]
  ports: [Ethernet1/5, Ethernet1/6]
```

展开过程：

```
① 本端（rsw 对）上行端口 ← M4 resolve_ports(zone='uplink') = [Eth1/49, Eth1/50]
② 对端（asw 对）端口 ← 输入直给 = [Eth1/5, Eth1/6]
③ 判定互联形态：
     本端成对(2台) × 对端成对(2台) → 双边 vPC，4 条物理链路
④ 物理链路配对规则（方形拓扑）：
     rsw1:Eth1/49 ←→ asw1:Eth1/5     ← 本端 member1 接对端 member1
     rsw1:Eth1/50 ←→ asw2:Eth1/5     ← 本端 member1 接对端 member2
     rsw2:Eth1/49 ←→ asw1:Eth1/6
     rsw2:Eth1/50 ←→ asw2:Eth1/6
⑤ 两端 agg_id：
     本端 ← M3 allocate('uplink_agg', device=rsw1) = 100
     对端 ← M3 allocate('downlink_agg', device=asw1) = 105
⑥ 写 arch_interconnect 一条记录，含两端 agg_id + members 映射
⑦ 反填两端意图：
     rsw1.uplinks[0] = {agg_id:100, peer_desc:'asw_pair...::Po105', members:[...]}
     asw1.downlinks[+1] = {agg_id:105, peer_desc:'rsw_pair...::Po100', members:[...]}
```

第④步的配对规则是硬逻辑，不同互联形态不同：

| 本端 × 对端 | 物理链路数 | 配对规则 |
|------------|-----------|---------|
| 成对 × 成对 | 4 | 方形：每台本端设备各接两台对端设备 |
| 成对 × 单台 | 2 | 两台本端都接同一台对端 |
| 单台 × 成对 | 2 | 一台本端接两台对端 |
| 单台 × 单台 | 1 | 直连 |

四种情况需要代码分支，但只有四种，枚举完即可，不会随场景增长。

**⑦ 反填对端意图是这步的关键价值**：对端 asw 的意图不是人工填的，是从本端的 `uplink_to` 反推出来的。这保证了两端一致——两边配置从同一条 `arch_interconnect` 记录渲染，不存在对不上的可能。

## 五、完整调用链

```python
def build_intents(input_yaml) -> Tuple[List[Intent], List[Interconnect]]:
    inp = parse_and_validate(input_yaml)           # 格式校验
    pre_check(inp)                                  # 规格校验、上游端口容量校验

    intents, ics = [], []
    for group in inp.groups:
        # 1. 组级资源（整组共享）
        cidr = claim_network(inp.idc, group.business_type, 24, 'server')   # M5
        vlan_id = render_rule('vlan_id', {**ctx, 'arch': inp.architecture}) # M1
        domain = allocate('vpc_domain', ctx, inp.idc)                       # M3

        # 2. 逐设备意图骨架
        for dev in group.devices:
            ctx = build_context(inp, group, dev)
            intent = {
                **direct_fields(inp, group, dev),                           # M0
                'hostname': render_rule('hostname', ctx),                   # M1
                'vendor':   lookup('model_vendor', dev.model),              # M2
                'redundancy': {
                    'mode': group.redundancy,
                    'domain': domain,
                    **lookup('mirror_rule', f'{group.redundancy}:{dev.member_id}'),  # M2
                    'peer_link': {
                        'agg_id': allocate('peerlink_agg', ctx, ...),       # M3
                        'ports':  resolve_ports(vendor, dev.model, 'peerlink'),  # M4
                    },
                },
                'vlans': [{'id': vlan_id, 'name': render_rule('vlan_name', ctx)}],  # M1
            }
            intents.append(intent)

        # 3. 互联展开 + 两端反填
        ic = expand_interconnect(group, intents, inp)                       # M6
        ics.append(ic)

        # 4. 服务器端口展开（意图里完全展开，不留 range）
        expand_server_ports(intents, group.server_count, vlan_id)           # M4

    # 5. 跨组全局计算
    if inp.architecture == 'l2_gw_core':
        converge_vlans(intents, ics, inp.idc)      # VLAN 并集，改上游 trunk
    build_upstream_increments(intents, ics, inp)    # 产出上游设备的增量意图

    validate_consistency(intents, ics)              # 最终一致性校验
    return intents, ics
```

## 六、必须有独立单测的三处

这三处错了不会抛异常，只会生成"看起来正常但实际有问题"的配置：

| 位置 | 错误表现 | 测试方法 |
|------|---------|---------|
| `allocate()` 冲突检测 | 两台设备分到同一 vPC domain，下发时才失败 | 构造已占用场景，断言抛 `NumberConflict` |
| `converge_vlans()` | VLAN 并集漏算，覆盖式下发断掉已有 MDU 业务 | 构造已有 4 个 MDU 场景，断言并集含全部 |
| `expand_interconnect()` 两端对应 | 两端 Po 号/VLAN 对不上，链路 up 但不通 | 断言两端 `peer_desc` 互指、`allowed_vlan` 相同 |

`converge_vlans()` 的测试尤其重要——这是唯一能断掉现有业务的环节。

## 七、小结：要不要每个功能单独适配

| 问题 | 答案 |
|------|------|
| 25 个字段要 25 个方法吗？ | 不要。归并为 6 种机制 |
| 加一个新字段要改代码吗？ | 多数不用。若属 M1/M2/M3，只加一行配置表记录 |
| 加一种新厂商要改转换器吗？ | 不用。厂商差异在 `model_port_layout` 和 encoder 层，转换器无感 |
| 加一种新拓扑（如四级结构）要改吗？ | 要改 M6 的配对规则，其余不变 |
| 加一种新冗余形态（IRF）要改吗？ | 加 `mirror_rule` 记录 + encoder 的 `encode_redundancy` 分支，转换器主体不变 |

**真正需要写代码的只有四个方法**：`resolve_ports`（M4）、`claim_network`（M5）、`expand_interconnect`（M6）、`converge_vlans`（跨组）。其余靠三张配置表（`arch_naming_rule`、`arch_mapping`、`arch_numbering_rule`）驱动。

这也意味着**规则调整不需要改代码**。[拓扑 A 预演](./03a_walkthrough_topology_a.md) 3.1 节那个 VLAN 规则错误（`1000+MDU号` 实际应为固定 1000），在这个设计下就是改一条 `arch_naming_rule` 记录。

返回：[模块 3 业务架构](./03_business_architecture.md) ｜ [整体框架](./README.md)
