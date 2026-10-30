# Wi-Fi 采集厂商适配设计（华为 / 飞塔）

## 文档信息
- 创建时间: 2026-10-29
- 状态: collector 飞塔采集已实现，待线上测试（映射已在实机 `172.19.2.8` 核对）
- 版本: v0.4
- 关联文档: [wifi_map_design.md](./wifi_map_design.md)（页面、接口、表结构总设计）
- 修订: v0.4 collector 四个模块实现飞塔采集，解析函数写在各 `__getFortinetXxx` 方法内、不新增公共模块（6.3）；终端 SSID 以 Wlan `.1` 为准、Sta `.2`（VAP 接口名）兜底，Online 列缺失时不丢终端（6.4.4）；v0.3 实测确认 `fgWcStaBandwidthTx/Rx` 是 Gauge32 瞬时带宽而非累计计数（会回落，不能相减），速率改为原值直取；补 walk 列 OID 写法（`表.列号`，多一层 entry 无响应）；v0.2 按实机核对结果修正飞塔映射（终端索引无长度前缀、`fgWcStaRadioType` 恒为 0、终端 VLAN 恒为 0 需回退 WLAN、AP 名与 profile 名相同、monitor 射频必须过滤），补充核对结果表；v0.1 补齐华为采集现状说明（此前只有代码没有文档）；新增飞塔 FortiGate 无线控制器适配方案，字段映射基于 `FORTINET-FORTIGATE-MIB`（LAST-UPDATED 2025-04-04）

说明 `projects/collector/Module/Wlan*.py` 四个采集模块的统一输出结构、华为实现现状，以及在**不改表结构、不改输出结构、不改 central-server 接口**的前提下接入飞塔的方案。

---

## 一、约束

1. **表结构不动**：`wifi_ap / wifi_radio / wifi_ssid / wifi_client` 字段、主键保持现状（DDL 见 `central-server/scripts/db_create.sql`）。
2. **输出结构不动**：每个模块按厂商分派到私有方法，返回的 dict 字段与现有华为方法完全一致，`collect_wifi.py` 与 `db_helper.replace_wifi_snapshot` 不改。
3. **采不到的字段按"空"处理**：字符串给 `""`，数值给 `None`（计数类给 `0`），前端已统一显示 `--`。
4. 只用 SNMP v2c、只读，不登录设备。

---

## 二、统一输出结构

四个模块各自独立 walk，互不传参；任一模块返回 `None` 视为该模块失败（AP 模块失败则整台 AC 判失败，保留旧快照）。

### 2.1 WlanAP.getAPs() → wifi_ap

| 字段 | 类型 | 口径 |
|---|---|---|
| ap_mac | str | 主键，小写冒号格式 `aa:bb:cc:dd:ee:ff` |
| ap_name | str | AP 名称 |
| sn | str | 序列号 |
| ap_group | str | 分组 |
| online_status | str | `online` / `offline` / `unknown` |
| ap_ip | str | AP 自身 IP，点分十进制 |
| model | str | 型号 |
| sw_version | str | 软件版本 |
| client_count | int | AP 下终端数，缺省 0 |
| lldp_name / lldp_port | str | 上级交换机 / 端口，取不到为空 |
| ac_id | int | 所属 AC |
| last_seen_at | str | 采集时间 `YYYY-mm-dd HH:MM:SS` |

### 2.2 WlanRadio.getRadios() → wifi_radio

| 字段 | 类型 | 口径 |
|---|---|---|
| ap_mac + radio_id | str + int | 联合主键，radio_id 取厂商原始编号 |
| wlan_type | str | 射频协议类型 |
| band | str | `2.4G` / `5G` / `6G`（前端按这三个值上色，空值按信道号推断） |
| channel_status | str | `up` / `down`，**down 不入库** |
| channel | int | 当前信道 |
| bandwidth | int | 信道带宽 MHz |
| utilization / interference_rate | float | 百分比，2 位小数 |
| client_count | int | 射频下终端数 |
| tx_power / max_power | int | dBm |

### 2.3 WlanSSID.getSSIDs() → wifi_ssid

| 字段 | 类型 | 口径 |
|---|---|---|
| ap_mac + radio_id + seq | str + int + int | 联合主键，seq 为该射频下 SSID 的序号，需在多次采集间稳定 |
| ssid | str | SSID 名称 |
| client_count | int | 该射频该 SSID 下终端数 |
| ssid_status | str | `up` / `down` |

### 2.4 WlanClient.getClients() → wifi_client

| 字段 | 类型 | 口径 |
|---|---|---|
| client_mac | str | 主键，小写冒号格式 |
| username | str | AC 上报的用户名，取不到为空（前端显示 MAC） |
| ap_mac / ap_name | str | 所属 AP，`ap_mac` 必须能关联到 `wifi_ap.ap_mac` |
| radio_id | int | 必须与 `wifi_radio.radio_id` 编号一致（详情抽屉按它取信道） |
| band | str | 同 2.2 |
| channel | int | 信道 |
| ssid | str | SSID 名称（不是接口名） |
| status | str | `online` / `offline` |
| vlan_id | int | VLAN |
| ip | str | 终端 IP |
| up_rate / down_rate | int | bps，上行 = AP 收、下行 = AP 发 |
| rssi | int | dBm |

---

## 三、华为实现现状（AC6508，HUAWEI-WLAN-*-MIB）

| 模块 | MIB 表 | 索引 | 状态映射 |
|---|---|---|---|
| AP | `2011.6.139.13.3.3.1.*` | AP MAC（6 段） | 运行状态 `8(normal)` = online，其余 offline |
| 射频 | `2011.6.139.16.1.2.1.*` | AP MAC + 射频 ID | 频段 `1/2/3` → `2.4G/5G/6G`；信道状态 `1=up 2=down`（取值待实机确认） |
| SSID | `2011.6.139.17.1.1.1.*` | AP MAC + 射频 ID + 序号 | `1(normal)` = up |
| 终端 | `2011.6.139.18.1.2.1.*` | 终端 MAC（6 段） | `3(normal)` = online |
| LLDP | `2011.6.139.13.3.6.1.8` | AP MAC | 只取了上级设备名，端口 OID 待补 |

各列 OID 见 DDL 列注释。华为的特点是**所有表都以 MAC 做索引**，AP、射频、SSID、终端天然按 MAC 关联，表里直接就有利用率、干扰率、最大功率等运行指标，和我们的表结构几乎一一对应。

> 遗留：华为终端 `band`（`.18.1.2.1.7`）目前按原值 `toStr` 入库，没有像射频表那样映射成 `2.4G/5G`，如果实机返回的是枚举数字，前端会显示成数字，后续核对时一并处理。

---

## 四、飞塔与华为的差异

飞塔的 AC 就是 FortiGate 自带的无线控制器（`fgWc`，`1.3.6.1.4.1.12356.101.14`），设计上与华为有几处根本不同：

| # | 差异 | 华为 | 飞塔 | 对实现的影响 |
|---|---|---|---|---|
| 1 | AP 标识 | 索引即 AP MAC | 索引是 `vdom + WTP ID`，WTP ID 就是 AP 序列号（变长字符串）；MAC 只是 Session 表里的一列 `BaseMacAddress` | 必须先建 **WTP ID → ap_mac** 映射，射频、SSID、终端都靠它转换主键 |
| 2 | 配置与运行态 | 一张 AP 表 | AP 名称、管理状态在 **Config 表**；IP、型号、版本、在线状态在 **Session 表** | AP 字段要两张表拼 |
| 3 | 射频能力 | 射频表直接给频段、带宽 | Session Radio 表只有模式、运行信道、运行功率、用户数；**频段、信道宽度在 wtp-profile 的射频配置里** | 射频要按 AP 的 profile 名去 Profile Radio 表取频段 / 带宽（配置值，非运行值） |
| 4 | SSID | 按 AP+射频+序号的 VAP 表 | SSID 是全局 VAP 接口（有 ifIndex），Session VAP 表索引 `vdom + WTP ID + 射频 + VAP ifIndex` | `seq` 直接用 VAP 的 ifIndex，天然稳定 |
| 5 | 终端 | 索引终端 MAC，所属 AP 给 MAC | 索引 `vdom + VAP ifIndex + 终端 MAC`，所属 AP 给的是 **WTP ID**，WLAN 给的是 **VAP 接口名** | ap_mac / ap_name 走映射；SSID 用索引里的 ifIndex 查 `fgWcWlanSsid` |
| 6 | 运行指标 | 有利用率、干扰率、最大功率 | MIB 里**没有**信道利用率、干扰率、最大功率 | 三个字段固定为 `None`，地图不着色、显示 `--` |
| 7 | LLDP | AP 上报上级设备名 | MIB 无 LLDP 信息 | `lldp_name / lldp_port` 为空 |
| 8 | 射频编号 | 0 起（0/1/2） | 1 起（radio-1/2/3，与 FortiGate 界面一致） | 原值入库，前端显示 R1/R2/R3 |
| 9 | 终端速率 | 速率（bps） | `BandwidthTx/Rx`，**Gauge32 瞬时带宽，单位 kbps**，空闲归 0，会上下浮动 | ×1000 转 bps，原值直取；**不能相减**（实测会回落，见七.2） |
| 10 | 终端频段 / VLAN | 终端表直接给 | `fgWcStaRadioType` **全为 0（other）**，`fgWcStaVlanId` **全为 0** | 都只能推算：频段按 `(wtpId, radioId)` 查射频表，VLAN 按 ifIndex 查 WLAN 表 |

---

## 五、飞塔字段映射

以下 OID 均在 `1.3.6.1.4.1.12356.101.14` 之下，简写为 `14.x`。表名后括号为 INDEX。

涉及的表：

| 简称 | OID | 表 | INDEX |
|---|---|---|---|
| Wlan | `14.3.1` | fgWcWlanTable | vdom, ifIndex(VAP) |
| ProfRadio | `14.4.2.1` | fgWcWtpProfileRadioTable | vdom, profileName(变长串), radioId |
| Config | `14.4.3.1` | fgWcWtpConfigTable | vdom, wtpId(变长串) |
| Session | `14.4.4.1` | fgWcWtpSessionTable | vdom, wtpId(变长串) |
| SessRadio | `14.4.5.1` | fgWcWtpSessionRadioTable | vdom, wtpId, radioId |
| SessVap | `14.4.6.1` | fgWcWtpSessionVapTable | vdom, wtpId, radioId, ifIndex(VAP) |
| Sta | `14.5.1` | fgWcStaTable | vdom, ifIndex(VAP), staMac |

### 5.1 wifi_ap

主循环以 **Session 表** 为准（有 MAC 才能落主键），Config 表只补名称与管理状态。

| 字段 | 飞塔来源 | 转换 |
|---|---|---|
| ap_mac | Session `.6` WtpBaseMacAddress | 6 字节 bytes → 小写冒号；为空 / 全 0 的跳过（见七.1） |
| ap_name | Config `.3` WtpName | 为空时回退 wtpId |
| sn | 索引中的 wtpId | 直接用（16 位，与 AP 机身 SN 一致，如 `FP431FTF23034442`） |
| ap_group | Session `.11` WtpProfileName | 飞塔无 AP 组概念，用 wtp-profile 名代替（见七.3） |
| online_status | Session `.7` ConnectionState | `onLine(2)` = online，其余 offline |
| ap_ip | Session `.5` WtpLocalIpAddress，空则 `.3` WtpIpAddress | InetAddress 4 字节 → 点分；`.3` 是 CAPWAP 报文源 IP，过 NAT 时与 AP 真实 IP 不同，所以优先 `.5` |
| model | Session `.12` WtpModelNumber | 实机值 `FP431F` |
| sw_version | Session `.14` WtpSwVersion | 实机值 `FP431F-v7.6.5-build1105` |
| client_count | Session `.17` WtpStationCount | |
| lldp_name / lldp_port | 无 | `""` |

过滤：Config `.2` WtpAdmin 为 `discovered(1)`（发现但未授权）的 AP 不入库。实机 18 台全部为 `enable(3)`。

> 实机核对：Config 表与 Session 表的 wtpId 集合完全一致（18/18），两表的 wtpId 都可用于关联。

### 5.2 wifi_radio

| 字段 | 飞塔来源 | 转换 |
|---|---|---|
| ap_mac | 索引 wtpId → 映射 | 映射不到的跳过 |
| radio_id | 索引 radioId | 原值 1/2/3 |
| channel_status | SessRadio `.3` Mode | `ap(3)` = up；`disabled(2) / notExist(1)` = down（不入库）；`monitor(4) / sniffer(5)` 见七.4 |
| channel | SessRadio `.7` OperatingChannel | |
| tx_power | SessRadio `.8` OperatingPower | MIB 注明单位 dBm |
| client_count | SessRadio `.9` StationCount | |
| wlan_type | ProfRadio `.11` Band（按 AP 的 profile + radioId 查） | FgWcWtpRadioType 枚举 → 协议文字，如 `802.11ax` |
| band | 同上 | 枚举 → 频段：`2/3/5/7/8/9/13/16/17/18` = 2.4G，`1/4/6/10/11/12/14/19/20/21` = 5G，`15` = 6G；查不到时按信道兜底（≤14 记 2.4G，否则 5G，6G 信道号与 2.4G 重叠无法兜底） |
| bandwidth | ProfRadio `.20` ChannelWidth | `1/2/3/4` → 20/40/80/160；`0` 或查不到为 None |
| utilization / interference_rate / max_power | 无 | None |

> 该 MIB 版本的 FgWcWtpRadioType 只到 `21`（802.11ax），没有 802.11be，ChannelWidth 也只到 160MHz；Wi-Fi 7 AP 若返回枚举外的值，`wlan_type` 存原值、`band` 走信道兜底。
>
> 频段、带宽取的是 **profile 配置值**。若某台 AP 在 wtp 下单独 override 了射频配置，MIB 里拿不到 override 后的值（Config 表的射频列不带 radioId，只能代表 radio-1），这种情况以 profile 为准，见七.5。
>
> 实机核对：18 台 AP × 3 射频 = 54 行 SessRadio，54 行 ProfRadio，`(profile, radioId)` **全部命中**；profile 枚举值与运行信道无一处冲突（r1 全为 band=13/802.11ax-2G、信道 1/6/11；r2 全为 band=14/802.11ax-5G、信道 36/44/56/60/149/157）；r3 全为 `monitor(4)`、band=5、信道 0、功率 31。

### 5.3 wifi_ssid

| 字段 | 飞塔来源 | 转换 |
|---|---|---|
| ap_mac / radio_id | 索引 wtpId → 映射、radioId | |
| seq | 索引最后一段 VAP ifIndex | VAP 是全局接口，ifIndex 跨采集稳定 |
| ssid | SessVap `.3` VapSsid | |
| client_count | SessVap `.4` VapStationCount | |
| ssid_status | 无状态列 | 出现在 Session VAP 表即视为在播，固定 `up` |

> 实机核对：18 台 AP × 2 个业务射频 × 2 个 SSID = 72 行；VAP ifIndex 只有 37（WeiDian-Guest）和 39（WeiDian-Inc）两个值，`VapStationCount` 与终端表按 `(wtpId, radioId, ifIndex)` 聚合的结果 **72/72 完全一致**。

### 5.4 wifi_client

| 字段 | 飞塔来源 | 转换 |
|---|---|---|
| client_mac | 索引第 3~8 段（定长 6 段） | 小写冒号 |
| ap_mac / ap_name | Sta `.3` WtpId → 映射 | 映射不到时 ap_mac 为空、ap_name 回退 wtpId |
| radio_id | Sta `.4` RadioId | 与射频表同编号 |
| band | **不用 Sta `.18`**，改按 `(wtpId, radioId)` 查射频表的频段结果 | 见下方说明 |
| channel | Sta `.17` Channel | |
| ssid | 索引中的 VAP ifIndex → Wlan `14.3.1.1` WlanSsid；查不到时用 Sta `.2` | Sta `.2` 是 VAP 接口名（MIB：WLAN interface），只是本机恰好与 SSID 同名，只作兜底 |
| status | Sta `.21` Online | `yes(1)` = online，其余 offline |
| vlan_id | Sta `.5` VlanId，为 0 时回退 Wlan `14.3.1.9` WlanVlanId | 按索引 ifIndex 查 WLAN 表 |
| ip | Sta `.7` IpAddress | 4 字节 → 点分；16 字节按 IPv6 格式化 |
| username | Sta `.10` User | 见七.6 |
| up_rate | Sta `.16` BandwidthRx | 瞬时值 kbps × 1000 → bps，**不跨次相减**（七.2） |
| down_rate | Sta `.15` BandwidthTx | 同上 |
| rssi | Sta `.12` Signal | MIB 注明单位 dBm |

实机核对与两处关键修正：

1. **终端索引是定长 `vdom . ifIndex(VAP) . MAC(6 段)`，共 9 段，MAC 前没有长度前缀。** v0.1 里"MAC 前可能带长度前缀 6"的猜测作废。只有 WTP ID、profile 名这类非 IMPLIED 的变长字符串索引才带长度前缀。
2. **`fgWcStaRadioType` 在实机上 36 个终端全为 `0(other)`**，无法用来判断频段；`fgWcStaVlanId` 也全为 `0`。所以频段按 `(wtpId, radioId)` 取射频表结果（业务射频只有 2.4G / 5G 两种，取值可靠），VLAN 回退到 WLAN 表的 `WlanVlanId`（实机 136 / 128，与终端 IP 网段 `172.19.36.x / 172.19.39.x` 对不上，说明 VLAN 是无线侧业务 VLAN，终端 IP 由其它网关分配，属正常）。

其它核对结果：终端索引里的 VAP ifIndex 与 WLAN 表 100% 对得上（无孤立 ifIndex）；`Sta .3 WtpId` 是 DisplayString（16 字符可读文本），18 台 AP 全部映射成功，无残留；`Host` 有值 35/36、`User` 只有 7/36（正是 802.1X 认证的终端）；`RadioId` 只有 1/2，`Channel` 只有 1/6/11/36/44/56/149/157。

---

## 六、实现方案

### 6.1 改动点

| 位置 | 改动 |
|---|---|
| `collector/Module/WlanAP.py` / `WlanRadio.py` / `WlanSSID.py` / `WlanClient.py` | 分派处加 `elif self.vendor == "fortinet"`，各加一个 `__getFortinetXxx` 私有方法；OID 与解析写在方法内，风格同华为方法，不新增公共模块（见 6.3） |
| `central-server/function_wifi/func_ac.py` | 厂商白名单加 `fortinet`，提示文案同步 |
| `chen_vue/src/view/pages/wireless/ac_manage.vue` | `VENDORS` 加 `{ value: 'fortinet', label: '飞塔' }` |
| `central-server/scripts/db_create.sql` | 只改 `wifi_ac.vendor` 列注释，不改结构 |
| `central-server/docs/wifi_map_design.md` | 4.2、七.4 的厂商列表补飞塔，引用本文 |

不改：`collect_wifi.py`、`db_helper.py`、central-server 接口与 DAO、前端其它页面。

`lib_snmp.identify_device_vendor` 不认飞塔，"测试连通"回显的 `vendor_detect` 会是 `unknown`，只影响提示，本期不动这个公共库。

### 6.2 索引解析

飞塔各表的索引分两类，**必须分开处理**，不能统一"取末 6 段"：

**（1）含变长字符串的索引**——Config / Session / SessRadio / SessVap / ProfRadio，结构为

```
<列号> . <vdom> . <长度 n> . <n 个字符的 ASCII...> . <后续定长段...>
```

例如 vdom=1、wtpId=`FP231F0000000001`、radio=2 的射频行：

```
14.4.5.1.7.1.16.70.80.50.51.49.70.48.48.48.48.48.48.48.48.48.49.2
         │ │  │  └──────────── 16 个字符 ────────────────┘ └ radioId
         │ │  └ 长度 16
         │ └ vdom
         └ 列号
```

解析：先按表前缀（`14.4.3.1.` 等）剥掉，剩下的第一段是列号，第二段是 vdom，第三段是长度 n，`[3:3+n]` 还原字符串，`3+n` 之后是 radioId / VAP ifIndex。用**表前缀**剥离而不是数固定下标——各表前缀层数不同（`14.3.1` 是 3 层，`14.4.6.1` 是 4 层），数下标极易错位（两次踩过）。

**（2）纯定长索引**——Wlan `14.3.1` = `列号.vdom.ifIndex`，Sta `14.5.1` = `列号.vdom.ifIndex.MAC(6 段)`，共 9 段，**MAC 前没有长度前缀**。

值的转换：
- `PhysAddress` / `InetAddress` / `DisplayString` 在 aiosnmp 里都是 bytes。**MAC、IP 必须按字节格式化，不能 `decode`**：`80802c0d66a8` → `80:80:2c:0d:66:a8`，`ac130715` → `172.19.7.21`；
- 真正的 `DisplayString` 值（`Sta .3 WtpId`、`Sta .9 Host`、`Sta .10 User`、`Config .3 WtpName`、`SessVap .3 Ssid`）按 UTF-8 解码。用 `--hex` 抓包时是十六进制文本，代码里拿到的是 bytes，直接 `decode` 即可。

> 抓包核对时 `bin/sk snmp … --walk --hex` 输出的 MAC/IP 是十六进制串，看着像乱码（`80802c0d66a8`），这是正常的，不是设备返回错误。

### 6.3 方法内的解析工具

照现有结构写，**不新增公共模块**：和华为方法的 `macIndex / toStr / toInt` 一样，解析函数定义在各 `__getFortinetXxx` 方法内部，四个模块各自独立 walk、互不传参（不改 `collect_wifi.py` 的调用方式）。

| 方法内函数 | 作用 | 用在 |
|---|---|---|
| `wtpIndex(oid, prefix)` / `strIndex(oid, prefix)` | 解析变长串索引；`strIndex` 返回 `(串, 后续段...)`，如 SessRadio 得 `(wtpId, radioId)`、SessVap 得 `(wtpId, radioId, ifIndex)` | AP 用前者，其余三个用后者 |
| `staIndex(oid, prefix)` | 解析 Sta 定长索引 → `(ifIndex, 终端 MAC)` | 终端 |
| `toMac` / `toIp` / `toStr` / `toInt` | 值转换，MAC、IP 按字节格式化（全 0 视为无效），DisplayString 才解码 | 全部 |
| `walkIndex(column_oid)` | walk 一列，返回 `{索引元组: 原始值}`，供按 wtpId / `(wtpId, radioId)` / `(profile, radioId)` 关联 | 射频、SSID、终端 |
| `fill` / `fillSta` | walk 一列并按索引填进 `oid_cache` | AP、终端 |

- prefix 一律传**列 OID**（`base + "4.5.1.7"` 这种），剥掉后剩下的第一段就是 vdom，不用再数列号所在下标；**中间不能再插一层 entry**（`14.5.1.1.15` 是错的，会返回空）。
- 索引段里出现非数字、长度越界时该行跳过，不抛异常拖垮整张表。
- WTP ID → MAC / profile / 名称这几张映射表是每 AP 一行的小表，各模块重复 walk 的开销可以忽略；换来的是模块间不传参、单模块可独立调试。

### 6.4 四张表的采集方式

每张表都是"walk 若干列 → 按索引拼行 → 换算字段"三步。列 OID 写作 `表.列`，实际前缀为 `1.3.6.1.4.1.12356.101.14.`。

#### 6.4.1 wifi_ap（`WlanAP.__getFortinetAPs`）

**walk 列（10 个）**

| 表 | 列 | OID | 用途 |
|---|---|---|---|
| Session | `.6` WtpBaseMacAddress | `14.4.4.1.6` | 主键；**没有 MAC 的行直接丢弃** |
| Session | `.5` WtpLocalIpAddress | `14.4.4.1.5` | `ap_ip` 首选 |
| Session | `.3` WtpIpAddress | `14.4.4.1.3` | `ap_ip` 兜底（CAPWAP 源 IP） |
| Session | `.7` ConnectionState | `14.4.4.1.7` | `online_status` |
| Session | `.11` WtpProfileName | `14.4.4.1.11` | `ap_group` |
| Session | `.12` WtpModelNumber | `14.4.4.1.12` | `model` |
| Session | `.14` WtpSwVersion | `14.4.4.1.14` | `sw_version` |
| Session | `.17` WtpStationCount | `14.4.4.1.17` | `client_count` |
| Config | `.2` WtpAdmin | `14.4.3.1.2` | 过滤未授权 AP |
| Config | `.3` WtpName | `14.4.3.1.3` | `ap_name` |

**组装**

1. 以 **Session 表**为行集（每行 = 一台 AP，索引里的 wtpId 就是 `sn`）；Config 表按同一个 wtpId 关联补名称、查管理状态。
2. 丢弃 `WtpAdmin == discovered(1)`（发现未授权）的行；Session 里 MAC 为空或全 0 的行也丢弃。
3. 字段换算：
   - `ap_mac` ← `.6` 6 字节 → 小写冒号；`sn` ← 索引 wtpId（16 字符，如 `FP431FTF23034442`）
   - `ap_name` ← Config `.3`，空则回退 wtpId
   - `ap_ip` ← `.5`，为空 / `0.0.0.0` 时用 `.3`
   - `online_status` ← `.7`：`onLine(2)` = `online`，其余（含 `offLine(1)`、`downloadingImage(3)`、`connectedImage(4)`）= `offline`
   - `client_count` ← `.17`，缺失补 0；`lldp_name / lldp_port` = `""`；`last_seen_at` = 本次采集时间

#### 6.4.2 wifi_radio（`WlanRadio.__getFortinetRadios`）

**walk 列（8 个）**

| 表 | 列 | OID | 用途 |
|---|---|---|---|
| Session | `.6` WtpBaseMacAddress | `14.4.4.1.6` | wtpId → ap_mac |
| Session | `.11` WtpProfileName | `14.4.4.1.11` | wtpId → profile，用于查 ProfRadio |
| SessRadio | `.3` Mode | `14.4.5.1.3` | 过滤 + `channel_status` |
| SessRadio | `.7` OperatingChannel | `14.4.5.1.7` | `channel` |
| SessRadio | `.8` OperatingPower | `14.4.5.1.8` | `tx_power` |
| SessRadio | `.9` StationCount | `14.4.5.1.9` | `client_count` |
| ProfRadio | `.11` Band | `14.4.2.1.11` | `wlan_type` + `band` |
| ProfRadio | `.20` ChannelWidth | `14.4.2.1.20` | `bandwidth` |

**组装**

1. 以 **SessRadio 表**为行集，索引 `(wtpId, radioId)`；wtpId 映射不到的跳过。
2. 用 `(profile, radioId)` 去 ProfRadio 表取频段枚举与信道宽度；profile 来自该 AP 的 Session `.11`。
3. **只保留 `Mode == ap(3)`**。`disabled(2) / notExist(1) / monitor(4) / sniffer(5) / other(0)` 全部丢弃（实机 54 行保留 36 行，radio-3 全是 `monitor(4)`）。
4. 字段换算：
   - `wlan_type` ← Band 枚举 → 文字（`dot11ax2g` → `802.11ax`，去重后按频段补后缀可省，见 5.2）；枚举外的值存原值
   - `band` ← Band 枚举 → `2.4G/5G/6G`；查不到时按信道兜底：信道 ≤ 14 记 `2.4G`，否则 `5G`
   - `bandwidth` ← ChannelWidth `1/2/3/4` → `20/40/80/160`；`0` 或缺失为 `None`
   - `channel_status` 保留时固定 `up`（down 的已丢弃，不入库）
   - `utilization / interference_rate / max_power` 固定 `None`

#### 6.4.3 wifi_ssid（`WlanSSID.__getFortinetSSIDs`）

**walk 列（4 个）**

| 表 | 列 | OID | 用途 |
|---|---|---|---|
| Session | `.6` WtpBaseMacAddress | `14.4.4.1.6` | wtpId → ap_mac |
| SessRadio | `.3` Mode | `14.4.5.1.3` | 只在 ap 射频上出 SSID |
| SessVap | `.3` VapSsid | `14.4.6.1.3` | `ssid` |
| SessVap | `.4` VapStationCount | `14.4.6.1.4` | `client_count` |

**组装**

1. 以 **SessVap 表**为行集，索引 `(wtpId, radioId, ifIndex)`。
2. `seq` 用索引最后一段 **VAP ifIndex**——VAP 是全局接口，编号在多次采集间稳定，直接满足"seq 需稳定"的要求。
3. 按 `(wtpId, radioId)` 查 SessRadio 的 Mode，只保留 `ap(3)` 射频下的行（正常情况 monitor 射频不会出现在 VAP 表里，这一层是防御）。
4. `ssid` ← `.3` 解码；`client_count` ← `.4`；`ssid_status` 固定 `up`（表里没有状态列，出现在 Session VAP 表即视为在播）。

#### 6.4.4 wifi_client（`WlanClient.__getFortinetClients`）

**walk 列（18 个）**

| 表 | 列 | OID | 用途 |
|---|---|---|---|
| Session | `.6` WtpBaseMacAddress | `14.4.4.1.6` | wtpId → ap_mac |
| Session | `.11` WtpProfileName | `14.4.4.1.11` | wtpId → profile |
| Config | `.3` WtpName | `14.4.3.1.3` | wtpId → ap_name |
| SessRadio | `.3` Mode | `14.4.5.1.3` | 终端所在射频须是 ap |
| ProfRadio | `.11` Band | `14.4.2.1.11` | `band`（`(profile, radioId)` 查） |
| Wlan | `.1` WlanSsid | `14.3.1.1` | `ssid` 首选（按 ifIndex 查） |
| Wlan | `.9` WlanVlanId | `14.3.1.9` | `vlan_id` 兜底（按 ifIndex 查） |
| Sta | `.2` Wlan | `14.5.1.2` | `ssid` 兜底（VAP 接口名，本机与 SSID 同名，但接口名 ≤15 字符、SSID ≤32 字符，不保证一致） |
| Sta | `.3` WtpId | `14.5.1.3` | 所属 AP |
| Sta | `.4` RadioId | `14.5.1.4` | `radio_id` |
| Sta | `.5` VlanId | `14.5.1.5` | `vlan_id` 首选（实机恒 0） |
| Sta | `.7` IpAddress | `14.5.1.7` | `ip` |
| Sta | `.10` User | `14.5.1.10` | `username` |
| Sta | `.12` Signal | `14.5.1.12` | `rssi` |
| Sta | `.15` BandwidthTx | `14.5.1.15` | `down_rate` |
| Sta | `.16` BandwidthRx | `14.5.1.16` | `up_rate` |
| Sta | `.17` Channel | `14.5.1.17` | `channel` |
| Sta | `.21` Online | `14.5.1.21` | `status` |

**组装**

1. 以 **Sta 表**为行集，索引是定长 9 段 `列号.vdom.ifIndex(VAP).MAC(6 段)`，`client_mac` 取第 3~8 段。
2. 同一 MAC 若出现多行（多个 VAP 索引），以 `Online == yes(1)` 的那行优先，其次取后出现的一行——`wifi_client` 主键是 MAC，只能留一行。
3. `Online == no(2)` 的终端丢弃；Online 列整列没采到时不丢，`status` 置空（避免一列失败清空整张终端表）。
4. 关联：
   - `wtpId`（Sta `.3`，DisplayString 明文）→ `ap_mac`、`ap_name`（Config `.3`，缺失回退 wtpId）
   - `(wtpId, radioId)` → 该射频的 SessRadio Mode 与 ProfRadio Band：Mode 查得到且不是 `ap(3)` 的丢弃；`band` 取 Band 枚举映射结果，查不到按 Sta `.17` 信道兜底
   - 索引里的 `ifIndex` → Wlan `.1` 得 `ssid`、`.9` 得 `vlan_id` 兜底值
5. 字段换算：
   - `ssid` ← Wlan `.1`，查不到时用 Sta `.2`
   - `vlan_id` ← Sta `.5`，为 0 时用 Wlan `.9`
   - `ip` ← `.7` 4 字节 → 点分，16 字节按 IPv6 格式化；全 0 → `""`
   - `username` ← `.10` 解码，不回退主机名（七.6）
   - `rssi` ← `.12`；`channel` ← `.17`
   - `up_rate` ← `.16` × 1000，`down_rate` ← `.15` × 1000，**原值直取、不相减**（七.2）
   - `status` ← `.21`：`yes(1)` = `online`

#### 6.4.5 调用次数与耗时

| 模块 | walk 次数 | 说明 |
|---|---|---|
| AP | 10 | 全部是小表（18 行级） |
| 射频 | 8 | SessRadio 54 行、ProfRadio 54 行 |
| SSID | 4 | SessVap 72 行 |
| 终端 | 18 | Sta 36 行，单次全表约 1 秒内 |

四个模块由 `collect_wifi.py` **串行**调用，按实机规模总计约十来次完整表读取，远在单 AC 超时 180 秒之内。真正耗时的是重复 walk 的往返延迟（每次 walk 一次请求），可按需在本模块内缓存同一列的结果，不做跨模块共享。

#### 6.4.6 边界与失败处理

- **任一 walk 返回空**：该列按缺失处理（`""` / `None` / `0`），不抛异常；只有整体异常（超时、认证失败）才 `return None`，与华为方法一致。
- **映射不到 AP 的终端 / 射频 / SSID**：射频、SSID 丢弃（没有 `ap_mac` 就没法落主键）；终端保留，`ap_mac` 空、`ap_name` 回退 wtpId，避免因为 AP 表异常丢掉整个终端列表。
- **索引解析失败**（段数不足、长度越界）：跳过该行并 `print` 一次，不让一行坏数据拖垮整张表。
- **重复索引**：同一 `(wtpId, radioId)`、同一终端 MAC 只保留一条，见各表组装步骤。

### 6.5 前提条件（由运维在设备上配置）

- `config system snmp community` 里放通 collector 所在主机 IP，v2c；
- 被采集的接口 `allowaccess` 含 `snmp`；
- HA 集群填主设备或集群管理 IP。

---

## 七、待确认

实机核对（`172.19.2.8`，FortiGate 管 18 台 FortiAP FP431F / v7.6.5-build1105，单 VDOM，36 个在线终端）已结掉大部分问题，剩余两条需要在**下一台设备**或**故障态**上确认。

### 7.1 离线 AP 在 Session 表里是否还有 MAC（影响 AP 离线显示）— 未验证

主键是 MAC，而离线 AP 的 MAC 只能从 Session 表拿。本次核对期间 18 台全部在线，没有样本。如果离线 AP 在 Session 表里没有行、或 BaseMacAddress 为空：

- **方案 A（当前默认）**：跳过，该 AP 从快照消失，地图上显示为"未知"（虚线灰框），而不是"离线"。
- 方案 B：`collect_wifi.py` 里按 sn 从上一次 `wifi_ap` 快照找回 MAC，补一行 offline。能和华为表现一致，但要改 collector 主流程。

代码先按方案 A 实现；上线后第一次遇到离线 AP 时看一眼 Session 表，再决定要不要做方案 B。

### 7.2 终端速率口径 — 已确认：原值直取，不做差值计算

原始设想是"飞塔两列需要隔一段时间相减才能得出速率"，**实机实测否定了这个做法**：

| 观测 | 数据（60 秒两次采样，以及 10 秒间隔重复采样） |
|---|---|
| 数值会回落 | `27:e4:fd:45:3c:bb` 的 tx 4316 → 0，rx 221 → 0；`25:be:83:5b:71:a0` 的 rx 7 → 0 |
| 数值会暴涨 | `27:4c:d5:77:2b:6e` 的 tx 26 → 8951 |
| 增量方向 | 37 个终端里升 5、降 4、平 28，多次出现负增量 |

累计计数器只增不减，而这两列能降到 0、能回落，说明它们是 **Gauge32 的瞬时（滑动窗口）带宽**，MIB 的描述就是字面意思"单位 kbps 的实时带宽"。对瞬时值做 `(S2 − S1) / Δt` 会得到负数，速率算错。

结论：**按原值取，与华为口径一致**——`down_rate = BandwidthTx × 1000`、`up_rate = BandwidthRx × 1000`，方向沿用 FortiGate 界面 Tx = AP 发（下行）/ Rx = AP 收（上行）。

一个遗留判断：若前端要求"一段时间内的平均速率"，正确做法是**多点采样取均值**（如 30 秒内每 5 秒采一次、6 次求平均），而不是相减；这会让终端模块额外耗时约 30 秒（单 AC 超时 180 秒，仍有余量）。本期不做，按单次快照入库。

### 7.3 `ap_group` 用什么 — 已确认

用 wtp-profile 名（Session `.11`）。**注意：本套环境的 AP 是"一 AP 一 profile"**（profile 名 `4F-APnn`，与 AP 名完全相同，18/18），此时 `ap_group` 会和 `ap_name` 重复显示。这是本环境的配置习惯，不是映射错误；换成多 AP 共享 profile 的环境就是正常的分组。仍然按原字段映射，不做特殊处理。

### 7.4 monitor / sniffer 模式的射频是否入库 — 已确认

**不入库。** 实机 18 台 AP 的 radio-3 全部是 `monitor(4)`：`channel` 为 0、`stationCount` 为 0、`tx_power` 为 31、profile 的 band 是 `dot11n2g(5)`，典型扫描射频。若入库，每个 AP 都会多出一个"2.4G / 信道 0 / 0 用户"的假射频，地图标签和射频卡片都会被污染。

过滤规则：SessRadio `.3` Mode 只保留 `ap(3)`，`disabled(2)` / `notExist(1)` / `monitor(4)` / `sniffer(5)` / `other(0)` 全部丢弃。实机 54 行 → 保留 36 行。

### 7.5 是否有 AP 单独 override 射频配置 — 未验证

本环境没有 override。若有，这些 AP 的 `band / bandwidth` 会按 profile 显示，可能不准。MIB 里 Config 表的射频列（`.6~.12`）不带 radioId，只能代表 radio-1，不能用来纠正 override，这个限制接受。

### 7.6 `username` 是否回退到主机名 — 已确认

**不回退。** 实测 36 个终端中 `fgWcStaUser` 只有 7 个有值（正是 802.1X 认证的终端，如 `yangjie02`），其余为 PSK 网络的终端，`username` 存 `""`，前端按设计显示 MAC。`fgWcStaHost` 有值 35/36（如 `vivo-X30`、`MiTV-MTSU0`），但主机名不是用户名，混用会让 802.1X 终端和 PSK 终端的"用户名"列口径不一。

### 7.7 VDOM — 部分确认

本套环境为单 VDOM，所有表的 vdom 索引段均为 `1`。代码仍按"vdom 解析后丢弃"实现，多 VDOM 环境下如果同一 community 可见多个 VDOM、且同一 wtpId 名字不同，理论上会撞键——`wtpId` 用的是 AP 序列号，全局唯一，实际不会撞。多 VDOM 场景留待有设备时再验证。

### 7.8 厂商标识 — 已确认

`wifi_ac.vendor` 取值定为 `fortinet`，界面显示"飞塔"。注意 `lib_snmp.identify_device_vendor` 不认飞塔，"测试连通"回显的 `vendor_detect` 是 `unknown`，只影响提示，本期不动这个公共库。

---

## 八、实机核对结果

核对对象：`172.19.2.8`（`fw1_corp_wf_m04`），FortiOS 自带无线控制器，18 台 FortiAP **FP431F**（固件 `FP431F-v7.6.5-build1105`），单 VDOM，2 个业务 SSID（WeiDian-Guest / WeiDian-Inc），36 个在线终端（23 个在 2.4G、13 个在 5G）。采集方式 `bin/sk snmp 172.19.2.8 -O <列> --walk --hex`。

| 核对项 | 结论 |
|---|---|
| 变长串索引编码 | 与 6.2 一致：`列号.vdom.长度.ASCII...`，wtpId 固定 16 字符，profile 名如 `4F-AP01` |
| 终端索引 | **定长 9 段** `列号.vdom.ifIndex.MAC(6)`，MAC 前无长度前缀（v0.1 的猜测作废） |
| Config 与 Session 的 wtpId | 集合完全一致（18/18），两表都可作为 AP 主表 |
| `WtpAdmin` 分布 | 全部 `enable(3)`，无 `discovered(1)` |
| AP 名与 profile 名 | 18/18 相同（一 AP 一 profile 的部署习惯） |
| `WtpIpAddress` vs `WtpLocalIpAddress` | 18/18 相同，取 `.5` 安全 |
| `ConnectionState` | 全部 `onLine(2)` |
| `fgWcInfo` | `wtpCapacity=128`、`wtpManaged=18`、`wtpSessions=18`、`stationCount=37`（与 STA 表的 36 行差 1，属统计口径差异，不用它做数据源） |
| ProfRadio 表 | 54 行，18 个 profile × 3 射频，按 `(profile, radioId)` **全部命中** |
| 频段枚举 | r1 = `dot11ax2g(13)`，r2 = `dot11ax5g(14)`，与运行信道（1/6/11 与 36~157）**无一处冲突** |
| 信道带宽 | r1 = 20MHz（枚举 1），r2 = 40MHz（枚举 2），映射正确 |
| `OperatingPower` | 2.4G 9 dBm，5G 11/19/20 dBm，数值合理，确认单位是 dBm 而非百分比 |
| `fgWcWtpProfileRadioChannel` | 是**信道列表**（如 `36;40`），不是运行信道；运行信道取 SessRadio `.7` |
| monitor 射频 | 18 台 AP 的 radio-3 全部 `monitor(4)`，信道 0、0 用户，必须过滤 |
| `VapStationCount` | 与终端表按 `(wtpId, radioId, ifIndex)` 聚合的结果 **72/72 一致** |
| WLAN 表 | 只有 2 个 VAP 接口：ifIndex 37 = WeiDian-Guest（VLAN 136），39 = WeiDian-Inc（VLAN 128） |
| `fgWcStaRadioType` | **36 个终端全为 `other(0)`**，不能用，频段改从射频表取 |
| `fgWcStaVlanId` | **36 个终端全为 0**，VLAN 改从 WLAN 表取 |
| 终端 `WtpId` | DisplayString 明文（16 字符），18 台 AP 全部映射成功，无残留 |
| 终端 `User` / `Host` | `User` 7/36（802.1X），`Host` 35/36 |
| 终端 `Online` | 36/36 为 `yes(1)` |
| 终端 ifIndex | 36 个终端的 ifIndex 全部能在 WLAN 表里找到，无孤立值 |

核对时踩到的两个坑，写代码时注意：
1. **按表前缀剥索引，不要数固定下标**——`14.3.1` 是 3 层、`14.4.6.1` 是 4 层，混用会让整个表的键错位，表现为"只解析出 1 台 AP"。
2. **MAC / IP 不能 `decode`**——按字节格式化，否则 `80:80:2c:0d:66:a8` 会变成乱码字符串，写进 `wifi_ap.ap_mac` 后与地图、终端全部关联不上。
