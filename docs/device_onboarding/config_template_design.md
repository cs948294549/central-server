# 配置模板设计

## 一、定位与职责

配置模板是**业务架构模板**（S4 业务配置）的实现载体，负责把"组网形态的抽象描述"渲染成"可下发的设备配置文本"。

**输入**：业务架构模板（arch_template）+ 实例参数（填写的表单数据）  
**输出**：可下发的配置文本，按厂商、按 A/Z 端分别产出  
**约束**：模板语法严格限制为三种 Jinja 写法，不允许逻辑外露、不允许隐藏派生参数

### 1.1 与基线配置的区别

| 维度 | 基线配置（S2） | 业务配置模板（S4） |
|------|---------------|-------------------|
| 作用域 | 全局单设备 | 按组网形态（如 400G-BGP、200G-OSPF） |
| 参数量 | 少（~10 个：管理 IP、主机名、机房、AS） | 多（~30-50 个：互联地址、路由协议、冗余参数） |
| 厂商差异 | 小（主要是语法差异：system-view vs configure terminal） | 大（NX-OS vpc、H3C IRF、华为 CSS 配置各不相同） |
| 下发时机 | 开局引导（带外 ZTP/POAP） | 纳管后（SSH 变更工单） |
| 可重入性 | 单次生效，后续不再碰 | 可反复重算、增量下发 |

**基线配置不用模板**：它足够短、全网同构，直接按厂商维护几份文本即可。  
**业务配置必须模板化**：形态多、参数多、A/Z 端配置耦合，不模板化管不过来。

---

## 二、Jinja 语法限制

模板用 Jinja2 渲染，但**只允许三种语法**，不允许任何超出此范围的写法。

### 2.1 允许的三种语法

| 语法 | 作用 | 示例 |
|------|------|------|
| `{{ 变量 }}` | 取值，支持 `对象.字段` 和过滤器 | `{{ hostname }}` <br> `{{ link.a_ip \| ip_only }}` |
| `{% for x in 集合 %}…{% endfor %}` | 遍历，可嵌套 | `{% for link in links %}` <br> `{% for port in link.a_ports %}` |
| `{% if 变量 %}…{% else %}…{% endif %}` | 条件取舍 | `{% if is_z %}…{% endif %}` |

**嵌套层次限制**：

- **参数取值**：最多二层，`{{ 对象.字段 }}` 或 `{{ 对象.子对象.字段 }}`
- **for 循环**：最多二层嵌套，外层遍历集合、内层遍历集合元素的子集合
- **典型模式**：
  ```jinja
  {% for link in links %}               ← 一层：遍历互联链路
    {% for port in link.a_ports %}      ← 二层：遍历链路的成员口
      interface {{ port }}
      description {{ link.z_host }}     ← 二层取值：link.z_host
    {% endfor %}
  {% endfor %}
  ```
- **不允许三层**：`{% for x in coll1 %}{% for y in x.coll2 %}{% for z in y.coll3 %}` 拒绝

**设计意图**：

- 一层参数（`{{ hostname }}`）对应表单里的单值字段
- 二层参数（`{{ link.a_ip }}`）对应表格里的某一列
- 超过二层（`{{ batch.group.device.field }}`）会让参数清单与表单结构对不上，前端难以生成嵌套三层的编辑界面

**不允许的语法**（校验阶段直接拒绝）：

- `{% set %}` / `{% macro %}` / `{% call %}`：不允许中间变量和函数
- `{% include %}` / `{% extends %}` / `{% block %}`：不允许模板继承和复用
- `{% with %}` / `{% filter %}`：不允许作用域嵌套
- 函数调用（如 `{{ get_peer_ip(link) }}`）：不允许任何函数调用

### 2.2 设计意图

**可读性**：模板里出现的名字就是表单里要填的参数，一眼能对上。

```jinja
{% for link in links %}
interface port-channel{{ link.a_agg }}
  description uT:{{ link.z_host }}:RAGG{{ link.z_agg }}
  ip address {{ link.a_ip | dotted }}
{% endfor %}
```

这段模板对应的参数清单就是 `links` 集合的四个字段：`a_agg`、`z_host`、`z_agg`、`a_ip`。删掉这段配置，参数清单自动少这四个，不会留下死参数。

**可维护性**：派生值由后端过滤器提供（见 2.3），不散落在模板里做字符串切割。模板文本与参数清单始终一一对应，改了哪段配置，参数表就跟着变。

**可校验性**：Jinja AST 遍历能精确识别语法违规，不需要靠代码评审拦。上传模板时后端返回语法错误的位置（厂商、A/Z 端、行号、错误原因），修正后再保存。

### 2.3 过滤器白名单

地址换算类操作不允许写在模板里（如 `{{ link.a_ip.split('/')[0] }}`），必须用过滤器。

**自定义过滤器**（`function_poap/jinja_filters.py`）：

| 过滤器 | 输入 | 输出 | 用途 |
|--------|------|------|------|
| `ip_only` | `10.0.0.1/30` | `10.0.0.1` | BGP 邻居地址 |
| `prefix_len` | `10.0.0.1/30` | `30` | 子网掩码长度 |
| `netmask` | `10.0.0.1/30` | `255.255.255.252` | 点分掩码 |
| `wildcard` | `10.0.0.0/24` | `0.0.0.255` | Cisco ACL 反掩码 |
| `network` | `10.0.0.1/30` | `10.0.0.0` | 网络地址 |
| `dotted` | `10.0.0.1/30` | `10.0.0.1 255.255.255.252` | H3C/华为写法 |

**开放的 Jinja 内置过滤器**：

- `default`、`join`、`length`、`count`：集合操作
- `lower`、`upper`、`trim`、`replace`：字符串格式化
- `int`、`string`、`first`、`last`：类型转换与取首尾

**开放的 Jinja 测试**（配合 `if` 用）：

- `defined`、`undefined`、`none`：判断变量是否存在
- `eq`、`ne`、`in`、`sameas`：值比较
- `number`、`string`、`even`、`odd`：类型与奇偶判断

未在白名单里的过滤器/测试在校验阶段报错，提示可用列表。

### 2.4 参数提取机制

参数清单由后端从模板文本提取（`POST /poap/template/params`），走 Jinja AST，不用正则。

**提取结果示例**：

```json
{
  "ok": true,
  "variables": ["hostname", "mgmt_ip", "mdu_as", "router_id"],
  "collections": {
    "links": ["a_agg", "a_ip", "a_ports", "z_host", "z_agg", "z_ip"],
    "links.port_pairs": ["a_port", "z_port"],
    "server_ports": ["agg_id", "port", "vlan"]
  },
  "paths": ["hostname", "links.a_agg", "links.port_pairs.a_port", "..."],
  "loop_vars": ["link", "pp", "sp"],
  "filters": ["ip_only", "dotted"],
  "blocks": {"for": 5, "if": 1}
}
```

**前端职责**：把提取结果映射成界面参数行，补 `label`、`type`（int/string/port-list/…）、`scope`（batch/group/device）。`links` 集合按作用端拆成 12 个 `link.*` 字段，各自带 A/Z 标签。

**删配置自动少参数**：删掉模板里的 eBGP 段，`collections.links` 里不再出现 `z_as`、`z_router_id`，参数清单跟着少两个字段。四个标了 `always` 的结构字段（`a_member`、`z_host`、`z_mgmt_ip`、`z_vendor`）无论模板引不引用都保留，因为推导要靠它们把链路挂到设备、定位对端。

---

## 三、A/Z 端独立模板

互联场景下，配置分两端产出：

- **A 端**：本 MDU 单元内的设备（如 rsw01、rsw02）
- **Z 端**：互联的对侧设备（上行 cbs、横联对等 MDU 的 rsw）

两端各自一份 Jinja 模板，共用一张互联表（`links`），模板里按 `link.a_*` / `link.z_*` 显式取用。

### 3.1 为什么要分 A/Z 端

**设备归属不同**：A 端设备是本次上线的目标设备，纳入本批次管理；Z 端设备可能早已在网，或者属于另一个上线批次。两者不能混在一个配��文件里下发。

**配置内容不同**：

- **A 端**配置包含：互联接口、BGP 对等、本端 vPC/IRF 配置、服务器下联口
- **Z 端**配置只包含：互联接口、BGP 对等（不含服务器口，Z 端通常是核心或对等接入）

**参数作用域不同**：

| 参数 | A 端用？ | Z 端用？ | 说明 |
|------|---------|---------|------|
| `hostname` | ✓ | — | A 端自己的主机名 |
| `link.a_agg` | ✓ | — | A 端的 port-channel 号 |
| `link.a_ip` | ✓ | ✓ | A 端互联地址：A 配在自己接口，Z 配在 BGP 邻居 |
| `link.z_host` | ✓ | — | Z 端设备名：A 端用来生成端口描述 |
| `link.z_agg` | ✓ | ✓ | Z 端的 port-channel 号：A 端写描述，Z 端配接口 |
| `link.z_ip` | ✓ | ✓ | Z 端互联地址：Z 配在自己接口，A 配在 BGP 邻居 |
| `mdu_as` | ✓ | — | 本 MDU 的 AS 号 |
| `link.z_as` | — | ✓ | Z 端自己的 AS 号（Z 端配 `router bgp {{ z_as }}`） |

### 3.2 模板存储结构

`arch_template.configs` 是一个二层嵌套对象：

```javascript
{
  "cisco_nx": {
    "a": "configure terminal\n{% for link in links %}...",
    "z": "configure terminal\n{% for link in links %}..."
  },
  "h3c": {
    "a": "system-view\n{% for link in links %}...",
    "z": "system-view\n{% for link in links %}..."
  }
}
```

**厂商 × A/Z** 四个象限各自独立。Z 端模板可以不写（对于只含 A 端配置的模板，如纯服务器接入），前端界面允许只填 `a` 一栏。

### 3.3 渲染时的作用端判定

渲染时根据 `intent.role` 决定取哪一端模板：

```javascript
const side = intent.role === 'z' ? 'z' : 'a'
const tplText = template.configs[intent.vendor][side]
```

`buildContext` 里不做 `self` / `far` 映射，参数原样传给后端。后端过滤器按名字取值：

- A 端模板里写 `{{ link.a_ip }}`，取到的是 `links[i].a_ip`
- Z 端模板里写 `{{ link.z_ip }}`，取到的是 `links[i].z_ip`

这样模板里出现的字段名就是互联表的真实列名，参数清单与表格列一一对应。

---

## 四、表结构设计

### 4.1 arch_template 表（业务架构模板）

| 字段 | 类型 | 说明 |
|------|------|------|
| `tid` | string | 模板 ID，UUID |
| `name` | string | 模板名称，如"400G-BGP 双归上联" |
| `arch_type` | string | 架构类型标识：`400g-bgp` / `200g-ospf` / `cbs-ebgp` |
| `description` | string | 用途与适用场景说明 |
| `version` | int | 版本号，每次保存自增 |
| `updated_at` | timestamp | 最后修改时间 |
| `configs` | json | 配置模板正文，结构见 4.1.1 |
| `params` | json | 参数定义清单，结构见 4.1.2 |
| `tags` | json | 标签：`["rsw", "cbs", "ebgp"]` |
| `is_active` | boolean | 是否启用，停用的模板不在选择列表里出现 |
| `has_z_side` | boolean | 是否包含 Z 端配置（决定界面是否显示 Z 端页签） |
| `min_expand_unit` | int | 最小扩张单元：每次扩容的最小设备台数，如双归为 2 |
| `created_by` | string | 创建人 |
| `updated_by` | string | 最后修改人 |

#### 4.1.1 configs 字段结构

```json
{
  "cisco_nx": {
    "a": "configure terminal\n{% for link in links %}interface port-channel{{ link.a_agg }}\n  description uT:{{ link.z_host }}:RAGG{{ link.z_agg }}\n  ip address {{ link.a_ip | dotted }}\n{% endfor %}",
    "z": "configure terminal\n{% for link in links %}interface port-channel{{ link.z_agg }}\n  description dT:{{ link.a_host }}:RAGG{{ link.a_agg }}\n  ip address {{ link.z_ip | dotted }}\n{% endfor %}"
  },
  "h3c": {
    "a": "system-view\n{% for link in links %}interface Route-Aggregation{{ link.a_agg }}\n description uT:{{ link.z_host }}:RAGG{{ link.z_agg }}\n ip address {{ link.a_ip | dotted }}\n{% endfor %}",
    "z": "system-view\n{% for link in links %}interface Route-Aggregation{{ link.z_agg }}\n description dT:{{ link.a_host }}:RAGG{{ link.a_agg }}\n ip address {{ link.z_ip | dotted }}\n{% endfor %}"
  }
}
```

**厂商代号** 与 `lib_ssh` 保持一致：`cisco_nx`、`cisco_ios`、`cisco_xr`、`h3c`、`huawei`。

**A/Z 可选**：`configs[vendor].z` 可以不存在（纯 A 端模板）；`configs[vendor]` 也可以是字符串（老版本兼容，视作只有 A 端）。

#### 4.1.2 params 字段结构

参数清单数组，每个参数对象包含：

```json
[
  {
    "key": "hostname",
    "label": "设备主机名",
    "type": "string",
    "scope": "device",
    "side": "a",
    "path": "hostname",
    "required": true,
    "placeholder": "rsw01-dc09-m01",
    "help": "设备唯一标识，用于生成配置文件名和日志"
  },
  {
    "key": "link.a_agg",
    "label": "A端 Po",
    "type": "int",
    "scope": "group",
    "side": "a",
    "path": "links",
    "link_field": "a_agg",
    "required": true,
    "help": "本端 port-channel 号"
  },
  {
    "key": "link.z_as",
    "label": "Z端 AS",
    "type": "string",
    "scope": "group",
    "side": "z",
    "path": "links",
    "link_field": "z_as",
    "required": false,
    "help": "Z 端的 BGP AS 号，仅 Z 端配置引用"
  }
]
```

**字段说明**：

- `key`：参数唯一标识，链路字段以 `link.` 开头
- `label`：界面显示名称
- `type`：控件类型，可选值见 4.2
- `scope`：作用域，`batch`（批次级）/ `group`（单元级）/ `device`（设备级）
- `side`：作用端，`a`（A 端用）/ `z`（Z 端用）/ `both`（两端都用）
- `path`：在意图对象里的取值路径，如 `hostname`、`links`、`batch.idc`
- `link_field`：链路字段时指明对应 `links` 数组里的哪一列（如 `a_agg`、`z_ip`）
- `required`：是否必填
- `placeholder` / `help` / `default` / `options`：界面辅助信息

**参数提取与更新**：

1. 创建模板时，`params` 初始为空数组
2. 点「重新扫描参数」时，前端调 `POST /poap/template/params`，后端返回提取结果
3. 前端把提取结果映射成参数行，合并到 `params` 里：已存在的参数保留 `label` / `type` / `help` 等人工调整，新参数按默认规则补齐
4. 保存模板前再扫一次，确保 `params` 与 `configs` 同步

### 4.2 参数类型（type）

| 类型 | 界面控件 | 存储格式 | 示例 |
|------|---------|---------|------|
| `string` | 单行文本框 | 字符串 | `"rsw01-dc09-m01"` |
| `int` | 数字输入框 | 整数 | `100` |
| `select` | 下拉选择 | 字符串 | `"dc09"`（选项在 `options` 里） |
| `port-list` | 端口列表输入框 | 字符串数组 | `["Eth1/1", "Eth1/2"]` |
| `string-list` | 多行文本框 | 字符串数组 | `["10.0.0.0/8", "172.16.0.0/12"]` |
| `table` | 嵌套表格 | 对象数组 | `[{agg_id: 100, port: "Eth1/49", vlan: 10}]` |
| `device-table` | 设备表格 | 对象数组 | `[{member_id: 1, mgmt_ip: "10.1.1.1", ...}]` |

**类型推断**：后端提取参数时不带类型，前端按命名规则猜测：

- `/_ports$/` → `port-list`
- `/_permit$|_list$/` → `string-list`
- `/^(vlan_|stp_|.*_agg$|.*_count$)/` → `int`
- `idc` → `select`
- 其余 → `string`

人工可调，调完保存在 `params[i].type` 里，下次扫描不覆盖。

### 4.3 参数作用域（scope）

决定参数在哪一层填写、能否跨设备复用：

| 作用域 | 填写层级 | 复用范围 | 典型参数 |
|--------|---------|---------|---------|
| `batch` | 批次级表单（整个上线批次填一次） | 该批次所有设备 | `idc`、`room_tag`、`timezone`、`ntp_server`、`snmp_community` |
| `group` | 单元级表单（每个 MDU 单元填一次） | 该单元所有设备 | `mdu_as`、`router_id`、`links`、`server_ports` |
| `device` | 设备级表单（每台设备单独填） | 单台设备 | `hostname`、`mgmt_ip`、`member_id` |

**默认推断规则**（`guessScope`）：

```javascript
const batchParams = [
  'idc', 'room_tag', 'mgmt_vrf', 'timezone', 'admin_password',
  'dns_server', 'tacacs_host', 'ntp_server', 'syslog_host1',
  'snmp_community', 'snmp_acl_v4', 'snmp_acl_permit'
]
return batchParams.includes(key) ? 'batch' : 'group'
```

设备表（`devices`）本身是 `group` 级参数，但表里的每一行是 `device` 级。

---

## 五、渲染流程

### 5.1 页面预览渲染（strict=false）

规划页预览配置时，`renderConfig(intent, template, strict=false)`：

1. 前端从 `intent` 对象构造 `context`，调 `POST /poap/template/render`
2. 后端 `function_poap/jinja_template.py` 里：
   - 校验模板语法（只允许三种写法，拒绝 set/macro/函数调用）
   - 用受限 `Environment` 渲染（`undefined=_MarkerUndefined`）
   - 缺失的参数渲染成 `<<未填:参数名>>`，不报错
3. 返回 `{ok: true, text: "...", missing: ["link.z_as", ...]}`
4. 前端提示"有 N 个参数未填：xxx"，配置文本里直接显示占位标记

**意图**：让用户在填表过程中随时预览，看出哪些参数还没填，不会生成看着正常实则少值的配置。

### 5.2 正式下发渲染（strict=true）

导出配置或提交变更工单时，`renderConfig(intent, template, strict=true)`：

1. 同样调后端接口，但 `strict: true`
2. 后端用 `StrictUndefined`，缺任何一个参数直接报 `UndefinedError`
3. 返回 `{ok: false, errors: [{message: "参数 link.z_as 未定义"}]}`
4. 前端阻止导出，提示"有 N 台设备渲染失败，请检查参数是否填全"

**意图**：确保下发的配置是完整的，不会因为漏填参数生成半成品配置。

### 5.3 配置头尾拼接（前端）

后端只渲染模板正文，不管配置头尾。前端在 `renderConfig` 里拼接：

```javascript
// 配置头
lines.push('configure terminal')  // Cisco
lines.push('system-view')         // H3C/华为

// 模板渲染结果（来自后端）
lines.push(r.text.trim())

// 配置尾
lines.push('copy running-config startup-config')  // Cisco
lines.push('return\nsave force')                  // H3C/华为
```

**原因**：头尾是纯语法差异，不涉及参数，放前端拼更简单。后端只关心模板正文的语法校验和参数提取。

---

## 六、版本化策略

### 6.1 模板版本号

`arch_template.version` 每次保存自增，不支持回滚到历史版本（版本号只用于标识变更顺序）。

**变更追踪**：

- 保存时在 `updated_at` 记时间戳，`updated_by` 记操作人
- 配置内容变更记在 `ChangeOrder` 表里（模板 ID + 旧版本 + 新版本 + diff）
- 前端界面显示"模板已保存（v12）"，让用户知道当前版本

### 6.2 意图对象的模板绑定

规划页填写的"意图对象"（intent）不直接嵌入配置文本，而是绑定模板 ID：

```json
{
  "template_id": "uuid-of-400g-bgp",
  "template_version": 12,
  "vendor": "cisco_nx",
  "role": "a",
  "hostname": "rsw01-dc09-m01",
  "links": [...]
}
```

**渲染时版本处理**：

- 优先用 `template_version` 指定的历史版本（如果版本表里有存档）
- 未指定或版本不存在时，用当前最新版本
- 配置下发时记录实际使用的模板版本，便于后续 diff 时找到同一版本对比

**模板改版影响**：

- 模板新增参数：已保存的意图对象缺新参数，渲染时用 `<<未填:参数名>>` 占位，提示用户补填
- 模板删参数：意图对象里多余的参数不影响渲染，只是不再被引用
- 模板改逻辑：比如 OSPF 改 BGP，意图对象里填的 `ospf_area` 变成死参数，新参数 `bgp_as` 要补填

---

## 七、A/Z 端配置的推导与下发

### 7.1 A 端配置推导

A 端设备是本次上线的目标，配置在规划页填完表单后即可导出：

```
批次参数（batch）+ 单元参数（group）+ 设备表（devices）
  → 逐台设备构造 intent 对象
  → renderConfig(intent, template, strict=true)
  → 导出 N 台设备的配置文本
```

### 7.2 Z 端配置推导

Z 端设备可能早已在网，不归本批次管理。配置推导分两种场景：

**场景一**：Z 端设备也是本次上线的一部分（如对等 MDU 的横联）

- 两个 MDU 单元各自填表，互为对方的 Z 端
- MDU-A 的 `links[i]` 里填了 Z 端信息（`z_host`、`z_mgmt_ip`、`z_vendor`、`z_agg`、`z_ip`、`z_as`）
- 系统根据 `z_host` 匹配到 MDU-B 的某台设备，自动生成 Z 端配置意图：
  ```javascript
  {
    template_id: "...",
    role: "z",
    vendor: link.z_vendor,
    hostname: link.z_host,
    links: [翻转后的链路：a/z 互换]
  }
  ```
- Z 端配置一并导出，或生成独立的变更工单

**场景二**：Z 端设备已在网，只需增量配置

- 推导同上，但 `mode: "modify"`（增量模式）
- 渲染出的配置只含新增的互联接口和 BGP 配置，不含全量基线
- 下发前先采集 Z 端设备现有配置，做 diff，确认只新增不删改

### 7.3 Z 端配置的校验

Z 端配置推导依赖 `links` 表里的 Z 端字段（`z_host`、`z_mgmt_ip`、`z_vendor` 等）。校验规则：

| 字段 | 必填？ | 校验规则 |
|------|-------|---------|
| `z_host` | ✓ | 非空，且在 CMDB 里能查到设备 |
| `z_mgmt_ip` | ✓ | 非空，IP 格式合法，能 ping 通 |
| `z_vendor` | ✓ | 枚举：`cisco_nx` / `h3c` / `huawei` |
| `z_agg` | △ | Z 端模板引用时必填 |
| `z_ip` | △ | Z 端模板引用时必填 |
| `z_as` | △ | Z 端模板引用 BGP 时必填 |

前端在保存意图对象前调用 `validateIntent()`，检查：

1. A 端参数是否填全（对照 `params` 里 `side=a` 或 `side=both` 的必填参数）
2. 若模板包含 Z 端配置（`has_z_side=true`），检查 Z 端参数是否填全
3. `links` 表里每一行的 Z 端字段是否齐全

---

## 八、与其他模块的集成

### 8.1 与变更管理的集成

业务配置下发走变更工单（`ChangeOrder` 表）：

```json
{
  "order_id": "CO-20261105-001",
  "type": "device_config",
  "devices": [
    {
      "ip": "10.1.1.1",
      "vendor": "cisco_nx",
      "cmd_exec": "渲染后的配置文本",
      "cmd_roll": "回滚配置（no 版本）"
    }
  ],
  "metadata": {
    "template_id": "uuid-of-400g-bgp",
    "template_version": 12,
    "intent_snapshot": {...}
  }
}
```

**回滚配置生成**：

- Cisco：每条配置前加 `no`，如 `no interface port-channel100`
- H3C/华为：`undo` 版本
- 嵌套配置块（如 `interface` / `router bgp`）需要整块删除

### 8.2 与采集模块的集成

配置下发后，定期采集设备实际配置，做 diff：

```
期望配置（renderConfig 产出） vs 实际配置（采集回读）
  → 生成 diff HTML
  → 偏差大于阈值时告警
```

**配置域标记**（见整体框架 § 四）：

```
! ===== poap:business:400g-bgp:v12 begin =====
interface port-channel100
  description uT:cbs01:RAGG200
  ip address 10.0.0.1 255.255.255.252
! ===== poap:business:400g-bgp:v12 end =====
```

Diff 时只比对同一配置域内的配置节，避免跨域污染（如人工改了 SNMP community，不应该算作业务配置偏差）。

### 8.3 与 CMDB 的集成

Z 端设备信息（`z_host`、`z_mgmt_ip`）需要与 CMDB 对齐：

- 填写 `z_host` 时，前端自动补全（从 CMDB 查询设备列表）
- 保存意图对象前，校验 `z_host` 在 CMDB 里存在
- Z 端配置下发时，根据 `z_mgmt_ip` 定位设备，调 `lib_ssh` 执行

---

## 九、后续扩展方向

### 9.1 模板片段复用

当前设计不支持 `{% include %}`，每个模板都是独立的完整配置。未来可引入**片段库**：

```
common/vpc-peerlink.j2  → vPC peer-link 配置片段
common/hsrp.j2          → HSRP 配置片段
```

在模板编辑器里作为"插入片段"功能，而不是在渲染时动态 include，保持模板的自包含性。

### 9.2 配置合规校验

渲染产出的配置在下发前，先过合规引擎：

- 禁止规则：不允许 `ip http server`、不允许 `snmp-server community public`
- 强制规则：必须有 `ntp server`、必须开 `logging`
- 命名规范：接口描述必须符合 `^[ud]T:.*` 格式

合规不通过时阻止下发，或生成告警工单。

### 9.3 配置模拟与预检

在真实设备上下发前，先在虚拟设备（如 Cisco CML、EVE-NG）上验证：

1. 自动拉起对应厂商和版本的虚拟设备
2. 把渲染配置灌进去，检查语法是否通过、协议是否能起
3. 模拟通过后再下发到真实设备

---

## 附录：配置示例

### A.1 400G-BGP 双归上联（Cisco NX-OS A 端）

```jinja
configure terminal

! vPC domain
vpc domain {{ vpc_domain }}
  peer-keepalive destination {{ peer_mgmt_ip }} source {{ mgmt_ip }} vrf {{ mgmt_vrf }}
  peer-gateway
  auto-recovery

! Peer-link
{% for port in peerlink_ports %}
interface {{ port }}
  description peer-link
  channel-group {{ peerlink_agg }} mode active
{% endfor %}

interface port-channel{{ peerlink_agg }}
  description peer-link
  switchport mode trunk
  vpc peer-link

! 上行互联
{% for link in links %}
{% for port in link.a_ports %}
interface {{ port }}
  description uT:{{ link.z_host }}:{{ link.z_ports[loop.index0] }}
  no switchport
  channel-group {{ link.a_agg }} mode active
{% endfor %}

interface port-channel{{ link.a_agg }}
  description uT:{{ link.z_host }}:RAGG{{ link.z_agg }}
  no switchport
  mtu 9216
  ip address {{ link.a_ip | ip_only }}/{{ link.a_ip | prefix_len }}
  no shutdown
  vpc {{ link.a_agg }}
{% endfor %}

! BGP 配置
router bgp {{ mdu_as }}
  router-id {{ router_id }}
  address-family ipv4 unicast
{% for link in links %}
  neighbor {{ link.z_ip | ip_only }} remote-as {{ link.z_as }}
  neighbor {{ link.z_ip | ip_only }} update-source port-channel{{ link.a_agg }}
  neighbor {{ link.z_ip | ip_only }} bfd
{% endfor %}

copy running-config startup-config
```

### A.2 400G-BGP 双归上联（H3C A 端）

```jinja
system-view

! IRF 配置
irf member {{ member_id }} priority {{ role_priority }}
irf-port {{ member_id }}/1
{% for port in peerlink_ports %}
  port group interface {{ port }}
{% endfor %}

! 上行互联
{% for link in links %}
{% for port in link.a_ports %}
interface {{ port }}
  description uT:{{ link.z_host }}:{{ link.z_ports[loop.index0] }}
  port link-aggregation group {{ link.a_agg }}
{% endfor %}

interface Route-Aggregation{{ link.a_agg }}
  description uT:{{ link.z_host }}:RAGG{{ link.z_agg }}
  ip address {{ link.a_ip | dotted }}
  undo shutdown
{% endfor %}

! BGP 配置
bgp {{ mdu_as }}
  router-id {{ router_id }}
{% for link in links %}
  peer {{ link.z_ip | ip_only }} as-number {{ link.z_as }}
  peer {{ link.z_ip | ip_only }} bfd enable
{% endfor %}
  address-family ipv4 unicast
{% for link in links %}
    peer {{ link.z_ip | ip_only }} enable
{% endfor %}
    balance 32

return
save force
```

### A.3 Z 端配置（Cisco NX-OS）

```jinja
configure terminal

! 下联 MDU-A
{% for link in links %}
{% for port in link.z_ports %}
interface {{ port }}
  description dT:{{ link.a_host }}:{{ link.a_ports[loop.index0] }}
  no switchport
  channel-group {{ link.z_agg }} mode active
{% endfor %}

interface port-channel{{ link.z_agg }}
  description dT:{{ link.a_host }}:RAGG{{ link.a_agg }}
  no switchport
  mtu 9216
  ip address {{ link.z_ip | ip_only }}/{{ link.z_ip | prefix_len }}
  no shutdown
{% endfor %}

! BGP 配置
router bgp {{ z_as }}
  router-id {{ z_router_id }}
  address-family ipv4 unicast
{% for link in links %}
  neighbor {{ link.a_ip | ip_only }} remote-as {{ mdu_as }}
  neighbor {{ link.a_ip | ip_only }} update-source port-channel{{ link.z_agg }}
  neighbor {{ link.a_ip | ip_only }} bfd
{% endfor %}

copy running-config startup-config
```

**说明**：

- Z 端配置不含 vPC/IRF（上游核心不需要成对冗余给下游看）
- `link.a_*` / `link.z_*` 字段在 A/Z 两端模板里显式取用，不做 `self` / `far` 映射
- 过滤器 `ip_only` / `prefix_len` / `dotted` 由后端提供，模板里不写字符串切割
- `loop.index0` 是 Jinja 内置的循环计数（从 0 起），用于按下标取对端口名
