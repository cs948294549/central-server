# 模块 2：配置基线设计

## 文档信息

- 所属：[交换机自动化上线整体框架](./README.md)
- 作用阶段：S2 开局引导（ZTP 下发的唯一配置）
- 配置内容：AAA/TACACS、SNMP、NTP、syslog、SSH 与登录安全、管理口与管理 VRF、banner
- 设计范式：**纯生成**。模板（带版本）+ 三级变量 → 渲染出开局配置

> **本模块不做配置比对。** 基线模板是"出厂设备开局时该下什么配置"，在网设备的 running-config 已累积大量业务配置与现场改动，与基线模板差异巨大，比对产出的全是噪音而非发现。配置合规巡检若有需要，是独立功能，不混进开局模板。

## 一、目标与边界

基线 = **让设备可被网管系统接管所需的最小配置集**，与业务无关、全网同构、不依赖任何上行业务链路。

| 属于基线 | 不属于基线 |
|---------|-----------|
| 管理口 IP、管理 VRF、管理默认路由 | 业务三层接口、Loopback |
| AAA/TACACS 认证授权计费 | BGP/OSPF/BFD |
| SNMP community 与 source-interface | M-LAG/peer-link、LACP |
| NTP server | VLAN、STP |
| syslog loghost + facility + source | 业务 ACL、路由策略 |
| SSH server、登录超时、密码策略 | 端口描述（业务侧定义） |
| hostname、banner/motd | 光模块告警阈值（型号相关，另议） |

分界线判据：**这条配置是否在设备没有任何业务上行时就必须生效**。是则属基线。

## 二、现网实际配置（2026-11-24 实测）

基线内容不能凭空设计，必须从现网提取。以下为三厂商各取一台代表设备的实际配置，**密钥/community/哈希已替换为占位符**。

### 2.1 Cisco NX-OS（`csw1_dc09_m01`，N9K-C9336C-FX2，9.3(7)）

```
! AAA / TACACS
feature tacacs+
tacacs-server host aaa1.vdian.net key 7 "<KEY>"
tacacs-server host aaa2.vdian.net key 7 "<KEY>"
aaa group server tacacs+ tacacs-server
    server aaa1.vdian.net
    server aaa2.vdian.net
    use-vrf management
    source-interface mgmt0
aaa authentication login default group tacacs-server none
aaa authentication login console local
aaa authorization config-commands default group tacacs-server local
aaa authorization commands default group tacacs-server local
aaa accounting default group tacacs-server
aaa authentication login error-enable

! SNMP
snmp-server source-interface traps mgmt0
snmp-server community <COMMUNITY> group network-operator
snmp-server user admin network-admin auth md5 <HASH> priv <HASH> localizedkey

! NTP
ntp server ntp.vdian.net use-vrf management
ntp source-interface mgmt0

! Syslog
logging server net-syslog1.vdian.net 7 use-vrf management facility local0
logging server net-syslog2.vdian.net 7 use-vrf management facility local0
logging source-interface mgmt0
logging timestamp milliseconds
logging message interface type ethernet description
```

### 2.2 H3C Comware 9（`new_csw1_dc19_m01`，S9825-64D，Release 9326）

```
# 管理口
interface M-GigabitEthernet0/0/0
 ip binding vpn-instance management
 ip address 10.26.252.13 255.255.255.0

# AAA / HWTACACS
hwtacacs scheme tacacs-server
 primary   authentication aaa1.vdian.net vpn-instance management
 primary   authorization  aaa1.vdian.net vpn-instance management
 primary   accounting     aaa1.vdian.net vpn-instance management
 secondary authentication aaa2.vdian.net vpn-instance management
 secondary authorization  aaa2.vdian.net vpn-instance management
 secondary accounting     aaa2.vdian.net vpn-instance management
 key authentication cipher <KEY>
 key authorization  cipher <KEY>
 key accounting     cipher <KEY>
 user-name-format without-domain
 nas-ip 10.26.252.13
domain name hwtacacs
 authentication login hwtacacs-scheme tacacs-server local
 authorization  login hwtacacs-scheme tacacs-server local
 accounting     login hwtacacs-scheme tacacs-server local
 authorization  command hwtacacs-scheme tacacs-server local
 domain default enable hwtacacs

# SNMP
snmp-agent
snmp-agent local-engineid <ENGINEID>
snmp-agent community read <COMMUNITY>
snmp-agent sys-info version all

# NTP
ntp-service enable
ntp-service unicast-server 10.1.1.9 vpn-instance management source M-GigabitEthernet0/0/0

# Syslog
info-center timestamp loghost iso
info-center loghost source M-GigabitEthernet0/0/0
info-center loghost vpn-instance management net-syslog1.vdian.net facility local4
info-center loghost vpn-instance management net-syslog2.vdian.net facility local4

# SSH / 用户
ssh server enable
local-user admin class manage
 service-type ssh terminal
header motd %
```

### 2.3 华为 VRP（`rsw1_poe_corp_bj_m01_10.15`，S5720-56C-PWR-EI-AC，V200R011C10SPC600）

```
# SNMP
snmp-agent
snmp-agent local-engineid <ENGINEID>
snmp-agent community read cipher <COMMUNITY>
snmp-agent community complexity-check disable
snmp-agent sys-info version v2c
undo snmp-agent sys-info version v3

# NTP
ntp-service unicast-server 10.1.1.9 vpn-instance mgmt
ntp-service source-interface MEth0/0/1 vpn-instance mgmt
ntp-service ipv6 server disable

# AAA / HWTACACS
hwtacacs-server template weidian
 hwtacacs-server authentication 10.32.100.243 vpn-instance mgmt
 hwtacacs-server authentication 10.129.23.14 vpn-instance mgmt secondary
 hwtacacs-server authorization  10.32.100.243 vpn-instance mgmt
 hwtacacs-server authorization  10.129.23.14 vpn-instance mgmt secondary
 hwtacacs-server accounting     10.32.100.243 vpn-instance mgmt
 hwtacacs-server accounting     10.129.23.14 vpn-instance mgmt secondary
 hwtacacs-server source-ip 172.24.250.15
 hwtacacs-server shared-key cipher <KEY>
 undo hwtacacs-server user-name domain-included
authentication-scheme hwtacacs
 authentication-mode hwtacacs local
authorization-scheme hwtacacs
 authorization-mode hwtacacs local
accounting-scheme hwtacacs
 accounting-mode hwtacacs

# Syslog —— 无配置
```

## 三、现网配置不一致（模板设计的输入）

三台设备横向对比，差异不只是厂商语法差异，还有**实质性的策略不一致**。这些不一致决定了模板里哪些值该统一、哪些该按厂商区分：

| 维度 | Cisco NX-OS | H3C Comware 9 | 华为 VRP | 性质 |
|------|-------------|---------------|---------|------|
| 管理 VRF 名 | `management` | `management` | **`mgmt`** | 实质不一致 |
| 管理口 | `mgmt0` | `M-GigabitEthernet0/0/0` | `MEth0/0/1` | 厂商差异，正常 |
| NTP 服务器 | `ntp.vdian.net` | **`10.1.1.9`** | **`10.1.1.9`** | 实质不一致（域名 vs IP） |
| syslog facility | `local0` | **`local4`** | — | 实质不一致 |
| syslog 服务器 | net-syslog1/2 | net-syslog1/2 | **无配置** | **缺失** |
| TACACS 服务器 | aaa1/aaa2.vdian.net | aaa1/aaa2.vdian.net | **10.32.100.243 / 10.129.23.14** | 实质不一致（域名 vs IP） |
| TACACS 方案名 | `tacacs-server` | `tacacs-server` | **`weidian`** | 命名不一致 |
| SNMP 版本 | v1/v2c/v3 | `version all` | **仅 v2c，显式关 v3** | 待确认是否有意 |

### 3.1 一个佐证：华为设备 syslog 完全缺失

`rsw1_poe_corp_bj_m01_10.15` 执行 `display info-center`：

```
Information Center:enabled
Log host:                      ← 空，未配置任何 loghost
Log buffer:
    ... overwritten messages 4602
```

`Log host` 为空，syslog 一条都没往外送，日志只在本地缓冲区循环覆盖（已覆盖 4602 条）。这台设备在 syslog 系统里完全静默，查它的历史日志什么都查不到。

这台设备本身的修复不属本模块（需单独处理），但它说明了为什么要有标准化开局模板：**靠人工逐台配置，漏项不可避免**。模板化之后新设备不会再出现这类缺失。

### 3.2 对模板设计的三点要求

1. **模板必须允许厂商级参数覆盖**。管理 VRF 名（`management` vs `mgmt`）、管理口名（`mgmt0` / `M-GigabitEthernet0/0/0` / `MEth0/0/1`）是厂商固有差异，不能强求统一。
2. **应统一的策略必须在模板里定死一个值**。NTP/TACACS 用域名还是 IP、syslog facility 用哪个，现网混用是历史遗留，新设备开局必须只有一种写法。
3. **区分这两类是录模板时的核心判断**。第一类进厂商级变量，第二类进全局变量。判据：换个厂商这个值必须跟着变吗？必须变则是厂商差异，否则是该统一的策略。

## 四、数据模型

### 4.1 三层结构

```
基线模板（baseline_template）
    ├─ 适用范围：vendor × role（如 cisco_nx × rsw）
    ├─ 版本号：每次修改递增，历史可追溯
    └─ 配置项集合（baseline_item）
           ├─ 配置节（section）：mgmt / aaa / snmp / ntp / syslog / ssh / banner
           ├─ 渲染顺序（mgmt 必须最先）
           └─ 渲染模板（含变量占位）

变量（baseline_variable）三级作用域
    ├─ 全局级：ntp_server、syslog_host1/2、syslog_facility、tacacs_host1/2…
    ├─ 厂商级：mgmt_vrf（cisco_nx=management，huawei=mgmt）、mgmt_if
    └─ 设备级：hostname、mgmt_ip、mgmt_mask、mgmt_gw
```

变量三级覆盖（设备级 > 厂商级 > 全局级）是应对第三节那些差异的办法：**全局定策略，厂商级只覆盖固有差异**。厂商级/设备级覆盖要求填写理由，使"有意的厂商差异"在数据上可审计。

### 4.2 配置项只做渲染

每个配置项就是一段带变量占位的配置文本：

```json
{
  "section": "syslog",
  "vendor": "cisco_nx",
  "sort_num": 50,
  "render": [
    "logging server {{syslog_host1}} 7 use-vrf {{mgmt_vrf}} facility {{syslog_facility}}",
    "logging server {{syslog_host2}} 7 use-vrf {{mgmt_vrf}} facility {{syslog_facility}}",
    "logging source-interface {{mgmt_if}}",
    "logging timestamp milliseconds"
  ]
}
```

没有 match/required/ignore 这类比对字段——模板的职责到"产出正确的开局配置"为止。

### 4.3 设备上线后配置怎么管

基线模板只负责开局那一刻。之后设备的配置变化由现有机制承接：

| 场景 | 现有机制 |
|------|---------|
| 配置备份与历史留存 | `tasks/backup_device_config.py` + `tables/ConfigDB.py` |
| 配置变更 | `function_op/order_manage.py` 变更工单 |
| 业务配置下发 | 模块 3 业务架构（S4） |

本模块不介入这些，也不对在网设备做任何比对。

## 五、数据库设计

```sql
-- 基线模板：vendor × role 一份，带版本
CREATE TABLE IF NOT EXISTS baseline_template (
    tid         BIGINT       NOT NULL AUTO_INCREMENT         COMMENT '模板ID',
    name        VARCHAR(100) COLLATE utf8_bin NOT NULL       COMMENT '模板名，如 cisco_nx-rsw-基线',
    vendor      VARCHAR(20)  COLLATE utf8_bin NOT NULL       COMMENT '厂商代号，同lib_ssh',
    role        VARCHAR(20)  COLLATE utf8_bin NOT NULL       COMMENT '设备角色：csw/rsw/asw/pcs/cbs/oob，*表示该厂商通用',
    version     INT          NOT NULL DEFAULT 1              COMMENT '当前版本号',
    is_active   VARCHAR(1)   COLLATE utf8_bin NOT NULL DEFAULT '1' COMMENT '1启用 0停用',
    descr       VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '说明',
    operator    VARCHAR(40)  COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '最近修改人',
    created_at  VARCHAR(15)  COLLATE utf8_bin NOT NULL       COMMENT '创建时间(时间戳)',
    updated_at  VARCHAR(15)  COLLATE utf8_bin NOT NULL       COMMENT '更新时间(时间戳)',
    PRIMARY KEY(tid),
    UNIQUE KEY uk_vendor_role (vendor, role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置基线模板';

-- 配置项：模板下的配置节
CREATE TABLE IF NOT EXISTS baseline_item (
    iid         BIGINT       NOT NULL AUTO_INCREMENT         COMMENT '配置项ID',
    tid         BIGINT       NOT NULL                        COMMENT '模板ID',
    section     VARCHAR(30)  COLLATE utf8_bin NOT NULL       COMMENT '配置节：mgmt/aaa/snmp/ntp/syslog/ssh/banner',
    sort_num    INT          NOT NULL DEFAULT 0              COMMENT '渲染顺序，mgmt需最先',
    render      TEXT         COLLATE utf8_bin NOT NULL       COMMENT '渲染模板，多行，含{{变量}}占位',
    descr       VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '该配置节的作用说明',
    PRIMARY KEY(iid),
    INDEX idx_tid (tid),
    INDEX idx_section (section)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基线配置项';

-- 模板版本快照
CREATE TABLE IF NOT EXISTS baseline_version (
    vid         BIGINT       NOT NULL AUTO_INCREMENT         COMMENT '版本ID',
    tid         BIGINT       NOT NULL                        COMMENT '模板ID',
    version     INT          NOT NULL                        COMMENT '版本号',
    snapshot    LONGTEXT     COLLATE utf8_bin NOT NULL       COMMENT '该版本全部配置项的JSON快照',
    change_log  VARCHAR(500) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '变更说明',
    operator    VARCHAR(40)  COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '操作人',
    created_at  VARCHAR(15)  COLLATE utf8_bin NOT NULL       COMMENT '创建时间(时间戳)',
    PRIMARY KEY(vid),
    UNIQUE KEY uk_tid_version (tid, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基线模板版本快照';

-- 变量：三级作用域
CREATE TABLE IF NOT EXISTS baseline_variable (
    varid       BIGINT       NOT NULL AUTO_INCREMENT         COMMENT '变量ID',
    scope       VARCHAR(10)  COLLATE utf8_bin NOT NULL       COMMENT '作用域：global/vendor/device',
    scope_key   VARCHAR(64)  COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT 'global为空，vendor填厂商代号，device填设备IP',
    var_name    VARCHAR(50)  COLLATE utf8_bin NOT NULL       COMMENT '变量名，如 ntp_server/mgmt_vrf',
    var_value   VARCHAR(300) COLLATE utf8_bin NOT NULL       COMMENT '变量值',
    is_secret   VARCHAR(1)   COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '1敏感(密钥/community)，页面脱敏显示',
    override_reason VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '非global作用域必填：为何需要覆盖',
    updated_at  VARCHAR(15)  COLLATE utf8_bin NOT NULL       COMMENT '更新时间(时间戳)',
    PRIMARY KEY(varid),
    UNIQUE KEY uk_scope_name (scope, scope_key, var_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基线变量(三级作用域)';

-- 渲染记录：每次为设备生成开局配置时留档
CREATE TABLE IF NOT EXISTS baseline_render_log (
    rid         BIGINT       NOT NULL AUTO_INCREMENT         COMMENT '渲染记录ID',
    sn          VARCHAR(100) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '设备序列号，ZTP按SN取配置',
    hostname    VARCHAR(100) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '规划主机名',
    mgmt_ip     VARCHAR(64)  COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '规划管理IP',
    vendor      VARCHAR(20)  COLLATE utf8_bin NOT NULL       COMMENT '厂商',
    model       VARCHAR(100) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '型号',
    role        VARCHAR(20)  COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '角色',
    tid         BIGINT       NOT NULL                        COMMENT '使用的模板ID',
    tpl_version INT          NOT NULL                        COMMENT '使用的模板版本',
    config_text LONGTEXT     COLLATE utf8_bin NOT NULL       COMMENT '渲染产出的配置全文(敏感值已替换为真值的不入库，见5.2)',
    operator    VARCHAR(40)  COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '操作人',
    created_at  VARCHAR(15)  COLLATE utf8_bin NOT NULL       COMMENT '渲染时间(时间戳)',
    PRIMARY KEY(rid),
    INDEX idx_sn (sn),
    INDEX idx_mgmt_ip (mgmt_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基线配置渲染记录';
```

### 5.1 设备如何匹配模板

不建绑定表，按 `(vendor, role)` 匹配：

- **新设备（S2 开局）**：`vendor`/`role` 来自 S1 登记时填的规划信息，设备还没上线，`devices` 表里查不到。
- **存量设备（重新渲染参考配置）**：`vendor` 取 `devices.vendor`，`role` 从 `devices.sysname` 按[设备命名规范](../../../../docs/network/设备命名规范.md)解析（`rsw1_mdu3_prod_dc07_m01` → `rsw`）。
- 优先匹配 `(vendor, role)` 精确模板，无则回退 `(vendor, '*')`。

### 5.2 渲染记录为什么要留档

ZTP 按 SN 取 `<SN>.cfg`，需要知道"这台设备当初下的是哪个版本的模板、配置内容是什么"。设备开局失败排查时，这是唯一能回答"下进去的到底是什么"的依据。

`config_text` 入库时**敏感值保持占位符形态**，不存真值（见 5.3）。

### 5.3 敏感变量不入库明文

`is_secret=1` 的变量（TACACS key、SNMP community）有两种处理，需二选一：

| 方案 | 做法 | 取舍 |
|------|------|------|
| A. 占位符 | 库里只存 `{{TACACS_KEY}}` 字面量，渲染下发那一刻才从环境变量/密钥源取真值 | 库被拖走也不泄密；ZTP 渲染服务需能访问密钥源 |
| B. 加密入库 | 对称加密存库，渲染时解密 | 实现简单；密钥管理问题只是转移，未消除 |

**倾向 A**：`docs/credentials/README.md` 已明确"实际凭证存储在加密的密码管理器中"，基线表里不该出现第二份真值。`baseline_render_log.config_text` 同样只存占位符形态——留档是为了追溯"用了哪个模板版本、生成了什么结构"，不需要真密钥。

## 六、渲染流程

```
输入：SN + 规划信息（hostname、mgmt_ip/mask/gw、vendor、model、role）
  → 匹配 baseline_template（vendor, role），取当前版本的配置项
  → 按 sort_num 排序（mgmt 最先）
  → 逐项展开 render 模板
  → 变量解析：device 级 → vendor 级 → global 级，逐级回退
  → 敏感变量从密钥源取真值替换
  → 输出完整开局配置文本
  → 写 baseline_render_log（config_text 保留占位符形态）
```

`mgmt` 节必须 `sort_num` 最小——管理口没起来，后面所有配置都没意义。

渲染结果三个去向：

1. **ZTP**：作为 `<SN>.cfg` 全文，设备开局时加载（模块 4）。
2. **页面预览/下载**：人工核对，或供无法走 ZTP 的设备（oob 交换机、新机房首台核心，见[框架 3.3](./README.md)）手工粘贴。
3. **留档**：`baseline_render_log`，开局失败时追溯下进去的是什么。

### 6.1 变量缺失的处理

渲染时任一变量在三级作用域都取不到值，**直接报错中止，不输出半成品配置**。管理 IP 为空的配置下进设备等于设备失联，宁可不生成。

页面上新建渲染任务时先做变量完整性检查，列出缺哪些值，补齐才允许渲染。

### 6.2 下发给设备时的厂商注意事项

配置文本本身由模板决定，但 ZTP 加载与保存环节有厂商差异（模块 4 实现时需注意）：

- **H3C 保存配置用 `save force`**，裸 `save` 会弹交互确认导致流程卡住。开局配置结尾固定 `return` + `save force`。
- **Cisco NX-OS** 走 `copy <file> startup-config` 后 `reload`，现有 `scripts/poap_cisco_nxos.py` 已实现。

## 七、API 设计

```
# 模板管理
GET    /api/baseline/template                   模板列表
POST   /api/baseline/template                   新建模板
PUT    /api/baseline/template/<tid>             修改模板（版本号递增，写快照）
GET    /api/baseline/template/<tid>/items       模板的配置项
PUT    /api/baseline/template/<tid>/items       批量更新配置项
GET    /api/baseline/template/<tid>/versions    版本历史
GET    /api/baseline/template/<tid>/diff        两个模板版本间的差异

# 变量管理
GET    /api/baseline/variable                   变量列表，按作用域分组
PUT    /api/baseline/variable                   新增/修改变量
GET    /api/baseline/variable/overrides         所有非 global 覆盖项及理由（审计用）
GET    /api/baseline/variable/check             变量完整性检查，返回缺失项

# 渲染
POST   /api/baseline/render                     渲染配置，body 传规划信息（SN/hostname/mgmt_ip/vendor/role…）
POST   /api/baseline/render/batch               批量渲染，返回下载包
GET    /api/baseline/render/log                 渲染记录列表
GET    /api/baseline/render/log/<rid>           某次渲染的配置全文

# 供 ZTP 调用
GET    /api/baseline/config?sn=<SN>             按序列号返回开局配置全文（敏感值已填真值）
```

## 八、前端页面

两个页面：

- **基线模板**：模板列表（厂商/角色/版本/配置节数）→ 配置项编辑（按 section 分组，带变量占位的文本编辑器，右侧实时渲染预览）→ 版本历史与版本间 diff。
- **基线变量**：按作用域分组。厂商级/设备级覆盖项高亮并显示 `override_reason`，敏感变量只显示 `******`。顶部提示变量缺失项。

渲染入口放在模板页：填规划信息（SN/hostname/mgmt_ip/mask/gw）→ 选模板 → 预览 → 下载或推送给 ZTP。渲染记录单独一个抽屉查看。

模板编辑器的实时预览很关键——录模板时能立刻看到变量展开后的实际配置文本，比抽象的占位符好核对。

## 九、实施顺序

| 步骤 | 内容 | 依赖 | 价值 |
|------|------|------|------|
| 1 | 表结构 + 基线变量管理 | 无 | 先把全局参数（NTP/syslog/TACACS 地址、facility）集中定下来 |
| 2 | 模板 + 配置项 CRUD，录入三厂商基线 | 1 | 标准沉淀成数据，同时填上 `docs/config/README.md` 的空白 |
| 3 | 渲染引擎 + 变量完整性检查 + 预览 | 2 | **本模块核心产出**，能出配置就有价值 |
| 4 | 渲染记录留档 + 批量渲染下载 | 3 | 可用于手工开局场景 |
| 5 | `/api/baseline/config?sn=` 对接 ZTP | 3 | 等模块 4 开工 |

步骤 3 做完，即使 ZTP 还没有，也能用页面渲染出标准配置让现场粘贴——这已经消除了"人工逐台配置漏项"的问题（三节那台华为 syslog 缺失就是这么来的）。

## 十、待确认

决策项（会写进基线变量，需先定）：

1. **NTP/TACACS/syslog 服务器用域名还是 IP**？现网 Cisco 用域名、H3C/华为用 IP（见三节）。域名更灵活，但设备需能解析 DNS，DNS 本身成为开局依赖——而开局阶段 DNS 可达性未经验证，这点倾向用 IP。
2. **syslog facility 统一到哪个值**？现网 Cisco `local0`、H3C `local4`。需要和 `function_alarm/syslog_manage.py` 的现有分类规则一起看，改哪边取决于规则侧的成本。
3. **基线按 `(vendor, role)` 还是只按 `vendor`**？csw 和 rsw 的基线差异主要在管理口类型和 SNMP 权限。倾向先只做 `(vendor, '*')`，确有差异再拆角色。
4. **敏感变量选 A 占位符还是 B 加密入库**（5.3 节）？倾向 A。

事实确认项：

5. **华为管理 VRF 叫 `mgmt` 而非 `management`** —— 厂商限制还是历史配置？前者作为厂商级变量固化，后者应在新设备上统一。
6. **华为显式 `undo snmp-agent sys-info version v3`** —— 有意的安全策略还是遗留？影响模板里 SNMP 节怎么写。
7. **开局基线是否包含 SNMP v3 用户**？Cisco 现网有 `snmp-server user admin network-admin auth md5 ...`，H3C/华为没有。采集侧目前用 v2c community，v3 用户似乎没在用。

返回：[整体框架](./README.md)
