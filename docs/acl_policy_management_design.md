# ACL 管理：解析 JSON 结构与数据库存储

## 文档信息
- 创建时间: 2026-09-20
- 状态: 设计中
- 版本: v1.1

管理三个独立对象：**ACL**、**地址组（addrgroup）**、**端口组（portgroup）**。
ACL 规则通过组名引用地址组与端口组。

---

## 一、解析 JSON 结构

### 1.1 编码约定

| 约定 | 说明 |
|---|---|
| 字段名 | 与数据库列名一致（`acl_name` / `group_name` / `acl_type` / `entries`） |
| 必现键 | 所有键**始终存在**，不适用时写 `null`（不省略键，避免读取侧判空分支） |
| `options` | 始终为对象，**只写值为 true 的键**，无选项时为 `{}` |
| `entries` | 裸 JSON 数组，与前缀列表一致，不使用 `{"entries": [...]}` 包裹 |
| `entries` 顺序 | 按 `seq` 升序 |

JSON 中只保留设备配置内容本身。解析过程中出现的异常（无法识别的 token、
非连续掩码、缺少组成部分等）**记录到日志，不入库**，避免解析器调整引起指纹变化。

### 1.2 ACL

```json
{
  "acl_name": "acl_office_to_idc",
  "acl_number": null,
  "acl_type": "ipv4",
  "acl_kind": "advanced",
  "entries": [
    {
      "seq": 100,
      "action": "permit",
      "protocol": "tcp",
      "src": {"type": "any"},
      "src_port": null,
      "dst": {"type": "any"},
      "dst_port": null,
      "options": {"established": true}
    },
    {
      "seq": 120,
      "action": "permit",
      "protocol": "tcp",
      "src": {"type": "any"},
      "src_port": null,
      "dst": {"type": "addrgroup", "name": "og_ip_idcnet"},
      "dst_port": {"type": "portgroup", "name": "og_port_per"},
      "options": {}
    },
    {
      "seq": 910,
      "action": "deny",
      "protocol": "tcp",
      "src": {"type": "any"},
      "src_port": null,
      "dst": {"type": "addrgroup", "name": "og_ip_idcnet"},
      "dst_port": null,
      "options": {}
    },
    {
      "seq": 10000,
      "action": "deny",
      "protocol": "ip",
      "src": {"type": "any"},
      "src_port": null,
      "dst": {"type": "any"},
      "dst_port": null,
      "options": {}
    }
  ]
}
```

#### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `acl_name` | string | 是 | ACL 标识。命名 ACL 存名字，编号定义存编号字符串（如 `"2999"`） |
| `acl_number` | int \| null | 是 | 仅编号定义时有值；命名 ACL 为 `null`（不用 0） |
| `acl_type` | string | 是 | `ipv4` / `ipv6` |
| `acl_kind` | string \| null | 是 | `basic` / `advanced` / `l2` / `custom` / `named` |
| `entries` | array | 是 | 规则条目，按 `seq` 升序 |

`acl_name` 与 `acl_number` 的取值：

| 设备配置 | `acl_name` | `acl_number` | `acl_type` | `acl_kind` |
|---|---|---|---|---|
| `ip access-list 2999` | `"2999"` | `2999` | ipv4 | advanced |
| `ip access-list sec_list` | `"sec_list"` | `null` | ipv4 | named |
| `ip access-list standard X` | `"X"` | `null` | ipv4 | basic |
| `ipv6 access-list 3999` | `"3999"` | `3999` | ipv6 | advanced |
| `acl number 2999` | `"2999"` | `2999` | ipv4 | basic |
| `acl number 3999` | `"3999"` | `3999` | ipv4 | advanced |
| `acl ipv6 number 3999` | `"3999"` | `3999` | ipv6 | advanced |

- `acl_number = int(标识)` 当且仅当标识可转整数，否则 `null`
- `acl_kind`：H3C/Huawei 按编号段 2xxx=basic、3xxx=advanced、4xxx=l2、5xxx=custom；Cisco 按关键字

#### 规则条目字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `seq` | int | 是 | 规则序号。配置未写时按 10 递增自动分配 |
| `action` | string | 是 | `permit` / `deny` |
| `protocol` | string | 是 | `ip` / `tcp` / `udp` / `icmp` / `igmp` / `ospf` / `esp` / `ahp` / `pim` / 数字协议号。配置省略时补 `ip` |
| `src` | object | 是 | 源地址，见 1.5 AddressSpec |
| `src_port` | object \| null | 是 | 源端口，见 1.5 PortSpec。`null` = 不限制 |
| `dst` | object | 是 | 目的地址，见 1.5 AddressSpec |
| `dst_port` | object \| null | 是 | 目的端口，见 1.5 PortSpec。`null` = 不限制 |
| `options` | object | 是 | 规则选项，见下方 |

`options` 键（只写 true）：

| 键 | 说明 |
|---|---|
| `established` | `established` 关键字，仅 `tcp` 适用 |

`remark` **不纳入模型**：它是注释文本，改动时不应触发配置漂移告警。

### 1.3 地址组

```json
{
  "group_name": "og_ip_idcnet",
  "acl_type": "ipv4",
  "entries": [
    {"type": "network", "address": "10.32.0.0/14"},
    {"type": "network", "address": "10.36.0.0/16"},
    {"type": "host", "address": "10.35.112.170/32"},
    {"type": "range", "start": "10.26.0.1", "end": "10.26.0.100"},
    {"type": "ref", "name": "og_ip_inner"}
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `group_name` | string | 是 | 组名，如 `og_ip_idcnet` |
| `acl_type` | string | 是 | `ipv4` / `ipv6` |
| `entries` | array | 是 | 条目列表 |

条目按 `type` 区分：

| `type` | 字段 | 说明 |
|---|---|---|
| `network` | `address` | CIDR，如 `10.32.0.0/14` |
| `host` | `address` | 归一为 `/32`（v6 为 `/128`） |
| `range` | `start`, `end` | 地址区间 |
| `ref` | `name` | 引用另一个地址组（不展开） |

### 1.4 端口组

```json
{
  "group_name": "og_port_per",
  "acl_type": "ipv4",
  "entries": [
    {"protocol": "tcp", "op": "eq", "ports": [80]},
    {"protocol": "tcp", "op": "eq", "ports": [443, 8080, 9090]},
    {"protocol": "tcp", "op": "range", "ports": [49, 49]},
    {"type": "ref", "name": "og_port_common"}
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `group_name` | string | 是 | 组名，如 `og_port_per` |
| `acl_type` | string | 是 | `ipv4` / `ipv6` |
| `entries` | array | 是 | 条目列表 |

条目两种形态：

| 形态 | 字段 | 说明 |
|---|---|---|
| 端口条目 | `protocol`, `op`, `ports` | `ports` **始终为数组**：`eq` 单元素，`range` 两元素 `[起, 止]` |
| 引用条目 | `type: "ref"`, `name` | 引用另一个端口组（不展开） |

`protocol`：`tcp` / `udp` / 数字协议号。
`op`：`eq` / `gt` / `lt` / `neq` / `range`。

### 1.5 公共子结构

**AddressSpec**（`src` / `dst`）

| `type` | 字段 | 示例 |
|---|---|---|
| `any` | — | `{"type": "any"}` |
| `network` | `address` | `{"type": "network", "address": "10.143.170.0/24"}` |
| `host` | `address` | `{"type": "host", "address": "10.33.103.136/32"}` |
| `addrgroup` | `name` | `{"type": "addrgroup", "name": "og_ip_idcnet"}` |

`range` **不出现**在 ACL 规则中，仅存在于地址组条目。

**PortSpec**（`src_port` / `dst_port`）

| `type` | 字段 | 示例 |
|---|---|---|
| `direct` | `op`, `ports` | `{"type": "direct", "op": "eq", "ports": [8081]}` |
| `portgroup` | `name` | `{"type": "portgroup", "name": "og_port_per"}` |

不限制端口时整个字段为 `null`，不使用 `{"type": "any"}`。

**端口值**：数字端口存**整数**，服务名别名存**字符串**。见 1.6.3。

```json
{"type": "direct", "op": "eq", "ports": [53]}
{"type": "direct", "op": "eq", "ports": ["domain"]}
{"type": "direct", "op": "range", "ports": [5900, 5930]}
```

### 1.6 解析规则

#### 1.6.1 块内非规则行必须跳过

ACL 块内**并非每行都是规则**。真实配置里出现：

```
ip access-list acl_office_to_idc
  statistics per-entry                  ← 统计开关，不是规则
  100 permit tcp any any established
```

按首 token 匹配跳过清单：

| 首 token | 说明 |
|---|---|
| `statistics` / `no` | 统计开关，`statistics per-entry` / `no statistics` |
| `remark` | 块级描述（非规则描述） |
| `description` | 同上，H3C 用 `description` |
| `counters` | 计数开关 |
| `evaluate` | NX-OS 模板引用 |

不跳过会被当成规则解析并产生垃圾条目。**解析单位是"行"，但生效单位是"匹配到规则语法正则的行"** —— 块头的两条三要素正则先做匹配，匹配不上的行记录日志后丢弃。

#### 1.6.2 协议端口能力表

决定某个地址位置后面**是否可以跟端口表达式**。这是解析器的必要条件：
没有这张表，`permit ip any any` 后面的任何 token 都会被当作端口运算符试探。

| protocol | 允许端口 |
|---|---|
| `tcp` | 是 |
| `udp` | 是 |
| `ip` | 否 |
| `icmp` | 否（后跟关键字是 ICMP type，不是端口） |
| `igmp` | 否 |
| `ospf` | 否 |
| `esp` / `ahp` | 否 |
| `pim` | 否 |
| 数字协议号 | 否（保守处理） |

判定流程：解析完一个地址后，**仅当 `protocol` 在允许列表内**，才调用端口探测；
否则直接进入下一个地址的解析。

#### 1.6.3 端口值：数字存整数，别名存字符串

端口既可以写数字也可以写服务名别名：

```
550 permit udp any addrgroup og_ip_dns_24h eq domain     ← 别名
560 permit tcp any 10.18.24.12/32 eq 443                 ← 数字
```

**不做别名到数字的映射，按值本身决定类型**：

```json
{"type": "direct", "op": "eq", "ports": [443]}       // 数字 → int
{"type": "direct", "op": "eq", "ports": ["domain"]}  // 别名 → string
```

解析时对每个 port token 尝试转整数，成功存 `int`，失败存原字符串。
`op` 与参数个数的关系是固定的，不需要额外区分：

| `op` | `ports` 元素个数 |
|---|---|
| `eq` / `gt` / `lt` / `neq` | 恒为 1 |
| `range` | 恒为 2（起、止） |

不做映射的理由：映射表需要维护（内部服务名随环境变化），映射错误比不映射更危险。
代价是 `eq domain` 与 `eq 53` 会被判为不同配置 —— 这个差异交由后续的**配置规范**统一
（标准规则里统一写数字），而不是在解析层猜。

### 1.7 归一化字段对照

以下差异归一后为**同一 JSON**（不产生漂移）：

| 差异 | 归一动作 |
|---|---|
| `0.0.0.255` vs `/24` | 反掩码 → CIDR |
| `10.33.103.136 0` vs `host 10.33.103.136` vs `10.33.103.136/32` | 统一 `host` + `/32` |
| 协议省略 vs 显式 `ip` | 补 `ip` |
| 目的地址省略 vs `any` | 补 `any` |
| 端口运算符大小写 | 统一小写 |

以下视为**不同 JSON**：

| 差异 | 原因 |
|---|---|
| `seq` 不同 / 规则顺序不同 | 序号决定匹配顺序，是配置内容 |
| `portgroup X` vs 内联 `eq 80` | 不展开组比对，保留为不同 |
| 地址组内条目顺序不同 | 当前参与指纹，顺序敏感 |

---

## 二、数据库存储

### 2.1 表清单

| 对象 | 标准规则表 | 设备实际配置表 |
|---|---|---|
| ACL | `acl_standards` | `acl_records` |
| 地址组 | `addrgroup_standards` | `addrgroup_records` |
| 端口组 | `portgroup_standards` | `portgroup_records` |

问题处理表三对象共用：`acl_issue_records`。

设备实际配置表写入策略与前缀列表一致：每次采集先按 `device_ip` 删除再批量插入，
库中只保留最新一次。不保留历史版本，需要历史时查设备备份配置。

### 2.2 acl_records

```sql
DROP TABLE IF EXISTS acl_records;
CREATE TABLE acl_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    device_ip VARCHAR(15) NOT NULL COMMENT '设备IP地址',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称/hostname',
    vendor VARCHAR(32) NOT NULL COMMENT 'cisco_nx, cisco_ios, cisco_xr, h3c, huawei',
    acl_name VARCHAR(64) NOT NULL COMMENT 'ACL标识名：有名字用名字，纯编号时存编号字符串',
    acl_number INT DEFAULT NULL COMMENT 'ACL编号（仅编号定义时有值，命名ACL为NULL）',
    acl_type VARCHAR(16) NOT NULL DEFAULT 'ipv4' COMMENT '地址族：ipv4, ipv6',
    acl_kind VARCHAR(16) DEFAULT NULL COMMENT '类别：basic, advanced, l2, custom, named',
    rule_count INT NOT NULL DEFAULT 0 COMMENT '规则条数（冗余，列表页免解析JSON）',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256，组引用保留组名不展开）',
    dangling_count INT NOT NULL DEFAULT 0 COMMENT '引用了未定义组的规则数',
    entries JSON NOT NULL COMMENT '标准化规则内容，裸数组',
    collected_at VARCHAR(10) NOT NULL COMMENT '采集时间（10位时间戳）',

    UNIQUE KEY uk_device_acl_collected (device_ip, acl_name, acl_type, collected_at),
    INDEX idx_acl_number (acl_number, acl_type),
    INDEX idx_acl_fingerprint (acl_name, acl_type, fingerprint),
    INDEX idx_device_ip (device_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='ACL-设备实际配置表';
```

约束说明：

- **`acl_type` 必须进唯一键**。`ip access-list 3999` 与 `ipv6 access-list 3999` 是两个独立 ACL，编号空间不重叠，不加此字段会互相覆盖
- **`acl_name` 总是有值**，编号定义也存编号字符串，使两种情况共用同一条读取路径
- **`acl_number` 不进唯一键**，它由 `acl_name` 推导，不独立；进唯一键会因推导差异产生重复记录
- `acl_number` 用 `INT` 而非字符串，避免 `"2999"` 与 `"02999"` 被当成两个 ACL

### 2.3 addrgroup_records

```sql
DROP TABLE IF EXISTS addrgroup_records;
CREATE TABLE addrgroup_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    device_ip VARCHAR(15) NOT NULL COMMENT '设备IP地址',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称/hostname',
    vendor VARCHAR(32) NOT NULL COMMENT '设备厂商',
    group_name VARCHAR(64) NOT NULL COMMENT '地址组名称，如 og_ip_idcnet',
    acl_type VARCHAR(16) NOT NULL DEFAULT 'ipv4' COMMENT '地址族：ipv4, ipv6',
    entry_count INT NOT NULL DEFAULT 0 COMMENT '条目数',
    ref_count INT NOT NULL DEFAULT 0 COMMENT '被ACL规则引用次数（采集时统计）',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256）',
    entries JSON NOT NULL COMMENT '结构化条目，裸数组',
    collected_at VARCHAR(10) NOT NULL COMMENT '采集时间（10位时间戳）',

    UNIQUE KEY uk_device_group_collected (device_ip, group_name, acl_type, collected_at),
    INDEX idx_group_fingerprint (group_name, fingerprint),
    INDEX idx_device_ip (device_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='地址组-设备实际配置表';
```

### 2.4 portgroup_records

```sql
DROP TABLE IF EXISTS portgroup_records;
CREATE TABLE portgroup_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    device_ip VARCHAR(15) NOT NULL COMMENT '设备IP地址',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称/hostname',
    vendor VARCHAR(32) NOT NULL COMMENT '设备厂商',
    group_name VARCHAR(64) NOT NULL COMMENT '端口组名称，如 og_port_per',
    acl_type VARCHAR(16) NOT NULL DEFAULT 'ipv4' COMMENT '地址族：ipv4, ipv6',
    entry_count INT NOT NULL DEFAULT 0 COMMENT '条目数',
    ref_count INT NOT NULL DEFAULT 0 COMMENT '被ACL规则引用次数（采集时统计）',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256）',
    entries JSON NOT NULL COMMENT '结构化条目，裸数组',
    collected_at VARCHAR(10) NOT NULL COMMENT '采集时间（10位时间戳）',

    UNIQUE KEY uk_device_group_collected (device_ip, group_name, acl_type, collected_at),
    INDEX idx_group_fingerprint (group_name, fingerprint),
    INDEX idx_device_ip (device_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='端口组-设备实际配置表';
```

### 2.5 标准规则表

三张表结构一致，与 `prefix_list_standards` 对齐：

```sql
DROP TABLE IF EXISTS acl_standards;
CREATE TABLE acl_standards (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    name VARCHAR(64) NOT NULL COMMENT 'ACL标识名：有名字用名字，纯编号时存编号字符串',
    acl_number INT DEFAULT NULL COMMENT 'ACL编号（仅编号定义时有值，命名ACL为NULL）',
    acl_type VARCHAR(16) NOT NULL DEFAULT 'ipv4' COMMENT '地址族：ipv4, ipv6',
    acl_kind VARCHAR(16) DEFAULT NULL COMMENT '类别：basic, advanced, l2, custom, named',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256）',
    entries JSON NOT NULL COMMENT '标准配置内容，裸数组',
    description TEXT COMMENT '规则说明',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用：1-启用，0-禁用',
    created_at VARCHAR(10) NOT NULL COMMENT '创建时间（10位时间戳）',
    updated_at VARCHAR(10) NOT NULL COMMENT '更新时间（10位时间戳）',
    created_by VARCHAR(64) COMMENT '创建人',

    UNIQUE KEY uk_name_type_fingerprint (name, acl_type, fingerprint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='ACL-标准规则表';

DROP TABLE IF EXISTS addrgroup_standards;
CREATE TABLE addrgroup_standards (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    name VARCHAR(64) NOT NULL COMMENT '地址组名称',
    acl_type VARCHAR(16) NOT NULL DEFAULT 'ipv4' COMMENT '地址族：ipv4, ipv6',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256）',
    entries JSON NOT NULL COMMENT '标准配置内容，裸数组',
    description TEXT COMMENT '规则说明',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用：1-启用，0-禁用',
    created_at VARCHAR(10) NOT NULL COMMENT '创建时间（10位时间戳）',
    updated_at VARCHAR(10) NOT NULL COMMENT '更新时间（10位时间戳）',
    created_by VARCHAR(64) COMMENT '创建人',

    UNIQUE KEY uk_name_type_fingerprint (name, acl_type, fingerprint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='地址组-标准规则表';

DROP TABLE IF EXISTS portgroup_standards;
CREATE TABLE portgroup_standards (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    name VARCHAR(64) NOT NULL COMMENT '端口组名称',
    acl_type VARCHAR(16) NOT NULL DEFAULT 'ipv4' COMMENT '地址族：ipv4, ipv6',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256）',
    entries JSON NOT NULL COMMENT '标准配置内容，裸数组',
    description TEXT COMMENT '规则说明',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用：1-启用，0-禁用',
    created_at VARCHAR(10) NOT NULL COMMENT '创建时间（10位时间戳）',
    updated_at VARCHAR(10) NOT NULL COMMENT '更新时间（10位时间戳）',
    created_by VARCHAR(64) COMMENT '创建人',

    UNIQUE KEY uk_name_type_fingerprint (name, acl_type, fingerprint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='端口组-标准规则表';
```

> 标准表统一使用列名 `name`（对应 JSON 中的 `acl_name` / `group_name`），
> 与前缀列表 `prefix_list_standards` 保持一致。

### 2.6 acl_issue_records

```sql
DROP TABLE IF EXISTS acl_issue_records;
CREATE TABLE acl_issue_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',

    object_type ENUM('acl', 'addrgroup', 'portgroup') NOT NULL DEFAULT 'acl'
        COMMENT '问题所属对象类型',

    standard_id BIGINT NOT NULL COMMENT '标准规则ID',
    standard_name VARCHAR(64) NOT NULL COMMENT '标准规则名称',

    device_ip VARCHAR(15) NOT NULL COMMENT '设备IP',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称',
    device_vendor VARCHAR(32) NOT NULL COMMENT '设备厂商',

    issue_type ENUM('drifted', 'missing', 'dangling') NOT NULL DEFAULT 'drifted'
        COMMENT '问题类型：drifted=配置漂移, missing=缺失配置, dangling=引用了未定义的组',
    dangling_refs JSON DEFAULT NULL COMMENT '悬空引用明细：[{seq, position, group_name}]',

    standard_entries JSON NOT NULL COMMENT '标准配置条目',
    device_entries JSON NOT NULL COMMENT '设备配置条目',

    status ENUM('pending', 'processing', 'completed', 'ignored') NOT NULL DEFAULT 'pending'
        COMMENT '处理状态：pending=待处理, processing=处理中, completed=已完成, ignored=已忽略',

    change_ticket_id VARCHAR(64) DEFAULT NULL COMMENT '变更工单ID',

    created_by VARCHAR(64) DEFAULT NULL COMMENT '创建人',
    created_at VARCHAR(10) NOT NULL COMMENT '创建时间（10位时间戳）',
    processed_at VARCHAR(10) DEFAULT NULL COMMENT '处理完成时间（10位时间戳）',
    remark TEXT DEFAULT NULL COMMENT '备注信息',

    INDEX idx_standard_id (standard_id),
    INDEX idx_device_ip (device_ip),
    INDEX idx_status (status),
    INDEX idx_object_type (object_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='ACL 问题处理记录表';
```

`dangling_refs` 明细格式：

```json
[
  {"seq": 390, "position": "dst", "group_name": "og_ip_IT"},
  {"seq": 120, "position": "dst_port", "group_name": "og_port_xxx"}
]
```

`position` 取值：`src` / `dst` / `src_port` / `dst_port`。

### 2.7 字段与 JSON 对应关系

| JSON 字段 | acl_records 列 | 说明 |
|---|---|---|
| `acl_name` | `acl_name` | 直接对应 |
| `acl_number` | `acl_number` | 直接对应 |
| `acl_type` | `acl_type` | 直接对应 |
| `acl_kind` | `acl_kind` | 直接对应 |
| `entries` | `entries` | `json.dumps()` 存入 |
| — | `fingerprint` | 由前四个字段 + `entries` 计算，不存于 JSON |
| — | `rule_count` | `len(entries)`，冗余列 |
| — | `dangling_count` | 采集时统计，不存于 JSON |

| JSON 字段 | addrgroup_records 列 | 说明 |
|---|---|---|
| `group_name` | `group_name` | 直接对应 |
| `acl_type` | `acl_type` | 直接对应 |
| `entries` | `entries` | `json.dumps()` 存入 |
| — | `entry_count` | `len(entries)`，冗余列 |
| — | `fingerprint` | 由 `group_name` + `entries` 计算 |
| — | `ref_count` | 采集时统计 |

`portgroup_records` 与 `addrgroup_records` 对应关系一致。

---

## 附录：真实配置样本

| 厂商 | 文件 |
|---|---|
| H3C | `IDC/DC19割接相关/配置文件/割接前/new_csw1_dc19_m01.log` |
| Cisco NX-OS | `IDC/DC19割接相关/配置文件/割接前/rsw2_mdu1_prod_dc19_m01.log` |
| Cisco NX-OS（对象组用法） | `docs/network/办公网到IDC拦截机制分析.md` |
| 变更操作记录 | `config_b300_service_acl.txt` |

## 附录：解析回归用例

`acl_office_to_idc`（44 条规则）作为解析器回归测试的输入，覆盖了当前所有语法形态：

```
ip access-list acl_office_to_idc
  statistics per-entry
  100 permit tcp any any established
  110 permit icmp any any
  200 permit tcp any addrgroup og_ip_idcnet portgroup og_port_per
  210 permit ip any addrgroup og_ip_ad_idc
  230 permit tcp any 10.37.0.0/16 eq 2181
  240 permit tcp any addrgroup op_ip_oa_zhiyuan portgroup og_port_oa_zhiyuan
  260 permit tcp any addrgroup og_ip_relay eq 22
  280 permit tcp any addrgroup og_ip_git eq 60022
  281 permit tcp any 10.19.46.19/32 eq 8099
  290 permit tcp any 10.8.83.96/32 portgroup og_port_payftp
  320 permit ip addrgroup og_ip_ad_office addrgroup og_ip_ad_idc
  330 permit tcp addrgroup og_ip_ob_relay addrgroup og_ip_idcnet eq 3389
  340 permit tcp any addrgroup og_ip_bigdata_proxy portgroup og_port_bigdata_proxy
  370 permit tcp any addrgroup og_ip_jindie portgroup og_port_jindie
  380 permit tcp any addrgroup og_ip_oa portgroup og_port_oa
  400 permit tcp addrgroup og_ip_ob_relay addrgroup og_ip_idcnet range 5900 5930
  420 permit tcp any addrgroup og_ip_vdds eq 3308
  430 permit tcp addrgroup og_ip_ob_relay addrgroup og_ip_jindie eq 139
  440 permit tcp addrgroup og_ip_ob_relay addrgroup og_ip_jindie eq 445
  450 permit ip any 10.32.226.210/32
  500 permit ip any 10.18.24.12/32
  510 permit ip any 10.32.192.148/32
  520 permit ip 172.24.12.14/32 any
  550 permit udp any addrgroup og_ip_dns_24h eq domain
  560 permit tcp any addrgroup og_ip_dns_24h eq domain
  600 permit tcp addrgroup og_ip_ob_relay 10.18.8.8/32 eq 1433
  610 permit tcp addrgroup og_ip_ob_relay 10.18.8.3/32 eq 1433
  615 permit tcp any 10.18.24.49/32 eq 27017
  620 permit tcp any 10.32.113.34/32 eq 4430
  630 permit ip any 172.31.3.100/32
  640 permit tcp any 10.19.47.6/32 eq 56666
  645 permit tcp any 10.32.88.201/32 eq 9210
  655 permit tcp any 10.19.19.73/32 eq 9092
  660 permit ip any 10.37.2.106/32
  661 permit ip any 10.37.12.84/32
  675 permit tcp any 10.34.131.176/32 range 60001 60099
  720 permit tcp any 10.19.46.53/32 eq 3389
  725 permit tcp any 10.33.160.148/32 eq 222
  730 permit tcp any 10.26.0.128/28 range 18000 19000
  900 deny tcp any any portgroup og_port_deny
  910 deny tcp any addrgroup og_ip_idcnet
  1000 permit ip any any
```

该样本覆盖的形态：

| 形态 | 出现位置 |
|---|---|
| 块内非规则行（`statistics per-entry`） | 第 2 行，须跳过 |
| 规则选项 `established` | 100 |
| `icmp` 协议（无端口） | 110 |
| 源 any + 目的地址组 + 端口组 | 200 |
| `ip` 协议 + 目的地址组（无端口） | 210 |
| 目的 CIDR + 内联端口 | 230 |
| 源地址组 + 目的地址组（双组） | 320、330、400、430、440、600、610 |
| 目的地址组 + `eq` 数字端口 | 260、280、420 |
| 目的地址组 + 端口组 | 340、370、380 |
| 目的 host/32 + `eq` | 281、615、620、640、645、655、720、725 |
| 目的 host/32 + 端口组 | 290 |
| 目的 CIDR + `range` | 400、675、730 |
| 源 host/32 + 目的 any | 520 |
| `udp` + 端口别名 `domain` | 550 |
| `tcp` + 端口别名 `domain` | 560 |
| 目的地址组、**无端口**（游标耗尽收尾） | 910 |
| 目的 any + 端口组 | 900 |
| 兜底 `permit ip any any` | 1000 |

**未覆盖**的形态（v1 无需支持，留作已知缺口）：源端口内联、源端口组、
`gt`/`lt`/`neq` 运算符、ICMP type 关键字、命名端口的 `range`。
