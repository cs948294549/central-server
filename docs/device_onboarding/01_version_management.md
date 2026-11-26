# 模块 1：版本管理设计

## 文档信息

- 所属：[交换机自动化上线整体框架](./README.md)
- 作用阶段：S2 开局引导（ZTP 装版本）；兼顾存量设备升级排期
- 设计范式：与 [前缀列表管理](../prefix_list_management_design.md) 一致 —— 基线定义期望状态，采集回读实际状态，差异驱动处理
- 核心模型：**`厂商 + 型号 + 版本 + 补丁` 四元组构成版本指纹，指纹不匹配基线即为待处理**

## 一、核心模型

### 1.1 版本指纹

```
设备实际指纹 = (vendor, model, version, patch)   ← 采集回读
基线期望指纹 = (vendor, model, version, patch)   ← 人工定义

前两项为匹配键（定位该设备适用哪条基线），后两项为比对值。
version 或 patch 任一不等 → 该设备待处理（待升级）
```

判定是**等值比较**，不做版本大小比较。这带来三个好处：

1. 不需要为各厂商实现版本号解析与排序（`9.3(7a)` 和 `10.2(3)` 的大小关系、H3C `Release 6318P01`、华为 `V200R011C10SPC600` 的格式差异全部绕开）。
2. 语义无歧义——"等于基线"就是合规，不存在"比基线新算不算合规"这类需要约定的边界。
3. 降级场景天然覆盖。某台设备版本高于基线同样算不匹配，这通常确实需要关注（可能是临时升级后未同步基线，或误装了版本）。

### 1.2 反向定位：改基线 → 出设备清单

这是本模块的主要用法。基线表里改一条记录的 `version`/`patch`，立刻能查出哪些设备需要动：

```
修改基线 (cisco_nx, N9K-C93180YC-FX, 9.3(7a), -) → (cisco_nx, N9K-C93180YC-FX, 10.5(5), -)
                            ↓
       该型号 14 台中，12 台指纹不再匹配 → 待升级清单
                            ↓
              按机房/MDU 分组，排期分批升级
```

与前缀列表的差别在于**不需要设备绑定表**。前缀列表要显式声明"哪台设备该装哪个策略"，而版本基线按 `(vendor, model)` 隐式绑定——设备型号是客观属性，采集即得，不需要人工分配。省掉一张表和一套绑定维护流程。

## 二、现网数据现状

### 2.1 指纹四元组已全部采集

`devices` 表由 `collector` 项目通过 SNMP 采集写入（`collector/Module/Device.py` 解析，`collector/utils/db_helper.py:save_device_info` 入库）。指纹四项**全部已有，本模块无需新增任何采集**：

| 指纹项 | 字段 | 示例（Cisco NX-OS） | 示例（H3C） | 示例（华为） |
|--------|------|-------------------|------------|-------------|
| 厂商 | `devices.vendor` | `cisco_nx` | `h3c` | `huawei` |
| 型号 | `devices.hardware` | `N9K-C93180YC-FX3` | `S5130S-52S-PWR-HI` | `S5720-56C-PWR-EI-AC` |
| 版本 | `devices.version` | `9.3(7a)` | `Release 6318P01` | `V200R011C10SPC600` |
| 补丁 | **`devices.features`** | 空 | 空 | `V200R011SPH012` |

> `features` 字段的 DDL 注释写的是"版本"，实际存的是补丁号。注释有误导性，建议顺手改成"补丁版本"。

### 2.2 补丁采集现状：按厂商分支实现

`collector/Module/Device.py` 中各厂商分支独立取补丁，均走 SNMP：

| 厂商 | 补丁来源 | 处理 |
|------|---------|------|
| huawei | OID `1.3.6.1.4.1.2011.5.25.19.1.8.5.1.1.4` | 取第一个值；回显 `None` 归一化为空串 |
| h3c | OID `1.3.6.1.4.1.25506.2.3.1.7.2.1.5/.7/.2` | 遍历补丁条目，取 status=1（active）的补丁名，正则 `-?([^-]+)\.BIN` 提取版本 |
| cisco_nx / cisco_ios / cisco ios-xr | — | 分支内未取补丁，`features` 恒为空 |
| dell / hillstone | — | 显式置空 |

现网实测覆盖率（`rsw` 角色 248 台，2026-11-24）：

| 厂商 | 台数 | `features` |
|------|------|-----------|
| huawei | 27 | **全部非空**，6 种取值：`V200R011SPH012`(3) / `V200R011SPH008`(4) / `V200R011SPH005`(1) / `V200R019HP3b02`(1) / `V600R023SPH150`(16) / `V600R025SPH120`(2) |
| cisco_nx | 200 | 空 |
| cisco_ios | 8 | 空 |
| h3c | 11 | 空（采集逻辑存在，这批确实未装补丁） |
| unknown（飞塔） | 2 | 空 |

华为补丁号与主版本号对应关系清晰（`V200R011C10SPC600` 配 `V200R011SPH012`），指纹比对直接可用。

### 2.3 补丁维度的两个已知局限

不阻塞本模块落地，但要明确：

1. **Cisco 补丁（SMU）未采集**。NX-OS 的 SMU 需 CLI `show install active` 才能取到，SNMP 无对应 OID。现网 cisco_nx 占绝大多数（rsw 里 200/248），这批设备的 `patch` 恒为空。
   - 影响：如果某台 Cisco 装了 SMU，系统看不见，指纹仍显示匹配。属**漏报**，不会误报。
   - 处理：基线里 Cisco 型号的 `patch` 一律填 `-`，与采集值一致，不产生噪音。确有 SMU 管理需求时再按 2.4 补 CLI 采集。
2. **H3C 多补丁场景取最后一条**。采集逻辑 `patch_names[-1]` 只取最后一个 active 补丁，装了多个补丁时信息不全。现网 H3C 均无补丁，暂不影响。

### 2.4 若需补齐 Cisco 补丁（可选，非本期）

真机已验证取法（`csw1_dc09_m01`，N9K-C9336C-FX2，9.3(7)）：

```
show install active
  Boot Image:
          NXOS Image: bootflash:///nxos.9.3.7.bin
  Active Packages:                                    ← 此段为空 = 未装 SMU
  Active Base Packages:
          bfd-2.0.0.0-9.3.7.lib32_n9000
          bgp-2.0.0.0-9.3.7.lib32_n9000
          ...（全部为 9.3.7 基础包，版本号与主版本一致）
```

判定规则：`Active Packages` 段非空则取其中包名作为补丁；为空则补丁为 `-`。

要做的话，在版本统计页加"刷新补丁状态"按钮，用 `lib_ssh` 对选中设备按需采集即可——补丁只在人工打补丁后变化，不需要定时轮询。结果可直接 UPDATE 回 `devices.features`，保持单一数据源，不另建表。

### 2.5 补丁空值的归一化

采集层存空串，基线层填 `-`，比对时统一归一：

```sql
COALESCE(NULLIF(d.features, ''), '-')
```

**不在比对逻辑里直接用空串或 NULL**，避免 `NULL != NULL` 的三值逻辑踩坑。H3C/华为采集到 `None` 时已在采集层转空串，这里一并归一为 `-`。

## 三、数据库设计

**只新增一张表** `version_baseline`。版本统计页纯粹从 `devices` 表聚合得出，不落任何表。

### 3.1 版本基线表（唯一新增表）

```sql
-- 版本基线：(vendor, model) → 期望的 (version, patch) + 镜像位置
CREATE TABLE IF NOT EXISTS version_baseline (
    bid             BIGINT       NOT NULL AUTO_INCREMENT         COMMENT '基线ID',
    vendor          VARCHAR(20)  COLLATE utf8_bin NOT NULL       COMMENT '厂商代号，同lib_ssh：cisco_nx/cisco_ios/h3c/huawei/arista',
    model           VARCHAR(100) COLLATE utf8_bin NOT NULL       COMMENT '型号，精确对应devices.hardware采集值',
    version         VARCHAR(100) COLLATE utf8_bin NOT NULL       COMMENT '期望版本，精确对应devices.version采集值格式',
    patch           VARCHAR(100) COLLATE utf8_bin NOT NULL DEFAULT '-' COMMENT '期望补丁，无补丁填-',
    -- 镜像位置
    image_proto     VARCHAR(10)  COLLATE utf8_bin NOT NULL DEFAULT 'http' COMMENT '获取协议：http/ftp/tftp/scp',
    image_host      VARCHAR(128) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '镜像服务器地址[:端口]',
    system_image_path VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '主镜像路径含文件名',
    system_image_md5  VARCHAR(64) COLLATE utf8_bin NULL           COMMENT '主镜像MD5，下载后校验',
    boot_image_path VARCHAR(300) COLLATE utf8_bin NULL           COMMENT '引导镜像路径。H3C的BOOT包、N3K的kickstart填此项，单镜像平台留空',
    boot_image_md5  VARCHAR(64)  COLLATE utf8_bin NULL           COMMENT '引导镜像MD5',
    patch_path      VARCHAR(300) COLLATE utf8_bin NULL           COMMENT '补丁文件路径，patch为-时留空',
    image_size      BIGINT       NULL                            COMMENT '镜像字节数合计，升级前空间预检',
    -- 辅助
    eval_date       VARCHAR(10)  COLLATE utf8_bin NULL           COMMENT '评估时间YYYY-MM-DD，该版本通过测试定为标准的日期',
    eval_result     VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '评估结论：测试范围、已知缺陷、规避方法',
    descr           VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '说明：选版原因、升级注意事项',
    eos_date        VARCHAR(10)  COLLATE utf8_bin NULL           COMMENT '型号EOS日期YYYY-MM-DD，仅提示',
    operator        VARCHAR(40)  COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '最近修改人',
    created_at      VARCHAR(15)  COLLATE utf8_bin NOT NULL       COMMENT '创建时间(时间戳)',
    updated_at      VARCHAR(15)  COLLATE utf8_bin NOT NULL       COMMENT '更新时间(时间戳)',
    PRIMARY KEY(bid),
    UNIQUE KEY uk_vendor_model (vendor, model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备版本基线（期望指纹）';
```

`eval_date` + `eval_result` 是定标准这件事的凭据：这个版本什么时候评估的、测了什么、有什么已知问题。半年前定的基线和上周定的基线，可信度不同，页面上按 `eval_date` 排序能直接看出哪些基线该重新评估了。

### 3.2 不需要的表

| 曾考虑 | 为何不要 |
|--------|---------|
| 补丁采集表 | 补丁已在 `devices.features`（见 2.1），直接 JOIN |
| 设备绑定表 | 按 `(vendor, model)` 隐式绑定，型号是采集得到的客观属性，不需人工分配 |
| 基线变更历史表 | 改基线的影响是实时算出来的，不需要历史快照。`updated_at` + `operator` 够用 |
| 版本统计结果表 | 统计从 `devices` 实时聚合，数据量（千级）完全够快，落表反而引入同步问题 |

### 3.3 为什么型号/版本必须精确匹配采集值

基线与 `devices` 靠字符串等值 JOIN，差一个字符整条基线静默失效——不报错，只是那批设备永远显示"无基线"。所以基线维护表单必须约束输入，见 4.1。

## 四、功能设计：两个页面

对齐前缀列表已有的页面划分（`chen_vue/src/view/pages/policy_manage/prefix_manage/` 下 `prefix_rule.vue` + `prefix_log.vue`）：

| 页面 | 对应前缀列表 | 数据来源 | 职责 |
|------|-------------|---------|------|
| **版本管理** | `prefix_rule.vue`（规则） | `version_baseline` 表 | 定标准：维护期望指纹 + 镜像路径 + 评估信息，按指纹比对拉出各分类设备列表 |
| **版本统计** | `prefix_log.vue`（记录） | `devices` 表聚合 | 看现状：厂商/型号/版本/补丁的分布数量，下钻到设备列表 |

关键区别：**版本统计页不依赖基线表**。没录任何基线时它就能用，直接回答"现网在跑哪些版本、各多少台"。基线录入后，统计页可叠加一列标注是否匹配基线，但那是增强不是前提。

### 4.1 基线维护（强约束输入）

CRUD 之外，三个必须有的约束：

- **型号从现网候选中选**：下拉数据源 `SELECT DISTINCT vendor, hardware FROM devices WHERE hardware != ''`，不允许手工输入型号。
- **版本从现网在跑版本中选，或从镜像文件名反推**：下拉列出该型号现网所有在跑版本及台数（如 `9.3(7a) — 13台`）。若要升到现网尚无的新版本，提供"手动输入"兜底，但弹窗提示"该版本现网无设备在跑，请确认格式与采集值一致"。
- **保存前预览影响**：提交时先算出"此改动将使 N 台设备变为待升级"，列出设备清单，确认后才写库。

第三点是 1.2 那个主要用法的入口——改基线和看影响在同一个动作里完成。影响实时算，不存快照。

### 4.2 指纹匹配与状态判定

```sql
SELECT
    d.ip, d.sysname, d.vendor, d.hardware, d.version,
    COALESCE(NULLIF(d.features,''), '-')  AS cur_patch,
    b.version                             AS exp_version,
    b.patch                               AS exp_patch,
    CASE
        WHEN d.version = b.version
         AND COALESCE(NULLIF(d.features,''),'-') = b.patch
                                             THEN 'matched'       -- 指纹匹配
        WHEN d.version = b.version           THEN 'patch_diff'    -- 仅补丁不符
        ELSE                                      'version_diff'  -- 版本不符
    END                                   AS fp_status
FROM devices d
JOIN version_baseline b
     ON b.vendor = d.vendor AND b.model = d.hardware
LEFT JOIN iplist i ON i.ip = d.ip
WHERE i.admin_status <> '1';
```

用 `JOIN` 而非 `LEFT JOIN` 关联基线：**在 `devices` 表里就是纳管设备，每个型号都必须有基线**。若某型号 JOIN 不上，说明基线漏录，这由 4.3 的覆盖率检查单独暴露，不作为设备状态分类。

补丁维度只对华为（及未来装补丁的 H3C）真正生效；Cisco 的 `features` 恒为空，基线填 `-` 即可匹配，不产生噪音。

三种分类，**版本管理页的核心交互就是点分类数字拉出对应设备列表**：

| 分类 | 含义 | 处理 |
|------|------|------|
| `matched` | 指纹完全一致 | 无需处理 |
| `version_diff` | 版本不符 | 待升级，需排期停机 |
| `patch_diff` | 版本对、补丁不符 | 待打补丁，部分平台可热打不重启 |

`version_diff` 与 `patch_diff` 分开，因为处理方式和风险等级不同——补丁往往支持热打，不需要重启。

基线列表每行展示该型号的三个分类计数（类似 `prefix_rule.vue` 的「应用统计」列 `20✓ 3⚠ 2✗`），点任一数字弹出设备列表，这就是 1.2 反向定位的落地入口。

**待退役型号怎么处理**：不设"不纳管"开关，直接把基线的 `version`/`patch` 填成该型号当前在跑的版本，状态自然为 `matched`，不产生噪音。配合 `eos_date` 和 `descr` 注明"待替换，不再升级"即可。这比加一个 `managed` 字段更简单，语义也更准确——基线就是"这个型号应该跑什么"，待退役型号应该跑的就是它现在跑的。

### 4.3 版本统计页（纯聚合，不依赖基线）

从 `devices` 表直接聚合，一条 SQL 搞定主视图：

```sql
SELECT
    d.vendor,
    d.hardware                              AS model,
    d.version,
    COALESCE(NULLIF(d.features,''), '-')    AS patch,
    COUNT(*)                                AS dev_count
FROM devices d
LEFT JOIN iplist i ON i.ip = d.ip
WHERE i.admin_status <> '1'
  AND d.hardware != ''
GROUP BY d.vendor, d.hardware, d.version, COALESCE(NULLIF(d.features,''), '-')
ORDER BY d.vendor, dev_count DESC;
```

三层下钻，与 `prefix_log.vue` 的「按指纹分组 / 按设备展示」切换同构：

1. **厂商汇总**：厂商 / 型号数 / 设备总数 / 指纹种类数。
2. **型号-指纹分布**（主视图）：厂商 / 型号 / 版本 / 补丁 / 台数 / 占比。按型号折叠，同型号内按台数降序。附一列「该型号指纹种类数」，降序排在前面的就是分化最严重、最该收敛的型号。
3. **设备列表**：点击某个 `(型号, 版本, 补丁)` 组合，展开该组合下的设备——IP / 设备名 / 机房 / 采集时间。可勾选导出。

基线录入后叠加一列「基线状态」（`matched` / `version_diff` / `patch_diff`），用颜色标注。该列是增强项，统计页本身不依赖基线即可工作。

**基线覆盖率检查**：统计页顺带能暴露基线漏录——聚合出的 `(vendor, model)` 若在 `version_baseline` 中查不到，页面标注"该型号未录基线"。这是基线维护的 TODO 提示，不是设备状态：

```sql
SELECT DISTINCT d.vendor, d.hardware, COUNT(*) AS dev_count
FROM devices d
LEFT JOIN version_baseline b ON b.vendor = d.vendor AND b.model = d.hardware
LEFT JOIN iplist i ON i.ip = d.ip
WHERE i.admin_status <> '1' AND d.hardware != '' AND b.bid IS NULL
GROUP BY d.vendor, d.hardware
ORDER BY dev_count DESC;
```

现网实测（2026-11-24，仅 `rsw` 角色 248 台）：**14 个型号、31 种型号-版本组合**。分化最严重的几个：

| 型号 | 台数 | 在跑版本数 |
|------|------|-----------|
| N9K-C93180YC-FX | 14 | 5 |
| N3K-C3048TP-1GE | 95 | 4 |
| N9K-C92160YC-X | 26 | 3 |
| N9K-C93180YC-EX | 22 | 3 |
| N9K-C93180YC-FX3 | 19 | 3 |

指纹模型下这些全部算待处理。这是符合预期的——现实就是不一致，页面的作用是把工作量如实摊开，由人决定收敛节奏，而不是用"可接受区间"把问题藏起来。

### 4.4 双机版本一致性检查

独立检查项，不依赖基线表，优先级高于基线匹配。

配对规则按 [设备命名规范](../../../../docs/network/设备命名规范.md)：取 `sysname` 中角色后的序号 1/2 构成冗余对。

```
配对键：正则 ^(oob_)?(csw|rsw|asw|pcs|cbs|bbr|bbs|edr|esw)([12])_(.*)$
        → 键 = \1\2_\4，序号 = \3
同键且序号分别为 1、2 的两台设备构成冗余对
```

同对内 `hardware` 或 `version`+`patch` 不一致即告警。型号不一致比版本不一致更严重，单独标记。

现网已存在的不一致（实测）：

| 设备对 | 差异 |
|--------|------|
| `csw1_corp_ts_m21` / `csw2_corp_ts_m21` | 10.1(1) vs **10.4(2)** |
| `csw1_dc07_m01_new` / `csw2_dc07_m01_new` | 10.2(3) vs **10.2(5)** |

M-LAG/vPC 双机版本不一致有实际风险（特性行为差异、peer-link 兼容性），比"是否等于基线"更该优先处理。建议先上这项。

### 4.5 升级清单导出

把 `version_diff` / `patch_diff` 设备按「机房 + 型号 + 目标指纹」分组导出，每组含：设备列表、当前指纹、目标指纹、镜像 URL + MD5、是否需重启。

仅导出清单，不建变更工单、不下发升级命令。存量设备升级由人工排期执行。

## 五、API 设计

```
# 版本管理页（基线）
GET    /api/version/baseline                基线列表，含每行三分类计数
POST   /api/version/baseline                新增基线
PUT    /api/version/baseline/<bid>          修改基线
DELETE /api/version/baseline/<bid>          删除基线
GET    /api/version/baseline/<bid>/devices  按分类拉设备列表，?status=version_diff|patch_diff|matched
GET    /api/version/baseline/impact         保存前影响预览，参数为待保存的 vendor/model/version/patch
GET    /api/version/baseline/uncovered      未录基线的型号及台数（覆盖率缺口）
GET    /api/version/candidates              现网型号候选 + 各型号在跑版本及台数（供 4.1 下拉）

# 版本统计页（聚合）
GET    /api/version/stats                   厂商-型号-版本-补丁 分布，支持 vendor/model/idc 过滤
GET    /api/version/stats/devices           某指纹组合下的设备列表，参数 vendor/model/version/patch

# 独立检查
GET    /api/version/pair-check              双机一致性检查
GET    /api/version/upgrade-list            升级清单导出

# 供 ZTP 调用
GET    /api/version/image?vendor=&model=    返回该型号期望指纹与镜像 URL/MD5
```

### 5.1 `/api/version/image` 响应

ZTP 引导脚本唯一依赖的接口，字段扁平，便于设备端 Python 解析：

```json
{
  "code": 0,
  "data": {
    "vendor": "cisco_nx",
    "model": "N9K-C93180YC-FX3",
    "version": "10.4(3)",
    "patch": "-",
    "system_image_url": "http://10.143.225.1:8888/images/nxos64-cs.10.4.3.F.bin",
    "system_image_md5": "a1b2c3...",
    "boot_image_url": null,
    "patch_url": null,
    "image_size": 2147483648
  }
}
```

## 六、文件结构

```
tables/VersionDB.py              基线表/历史表 CRUD + 指纹统计查询
function_op/version_manage.py    基线维护、指纹判定、双机检查、升级清单
api/api_version.py               API 路由
```

沿用现有命名风格（`tables/XxxDB.py` + `function_*/` + `api/api_*.py`）。

两个不需要的东西：

- **不需要 `utils/version_compare.py`** —— 指纹等值比较不涉及版本大小判断。
- **不需要补丁采集模块** —— 补丁已在 `devices.features`，采集器已覆盖华为/H3C。

## 七、前端页面

两个页面，与 `chen_vue/src/view/pages/policy_manage/prefix_manage/` 的 `prefix_rule.vue` / `prefix_log.vue` 同构：

```
chen_vue/src/view/pages/.../version_manage/
    version_rule.vue    版本管理（标准）
    version_stat.vue    版本统计（现状）
chen_vue/src/api/mapis/version_interface.js
```

### 7.1 版本管理页（version_rule.vue）

```
┌──────────────────────────────────────────────────────────────────────┐
│  版本管理                                    [+ 新建基线]  [导出]    │
├──────────────────────────────────────────────────────────────────────┤
│ 厂商      型号               版本/补丁          设备统计      评估   │
│ cisco_nx  N9K-C93180YC-FX   10.5(5) / -      2✓ 12⚠ 0◐   2026-11 │
│ cisco_nx  N9K-C93180YC-FX3  9.3(7a) / -     16✓  3⚠ 0◐   2026-08 │
│ cisco_nx  N3K-C3048TP-1GE   7.0(3)I4(6) / - 74✓ 21⚠ 0◐   2025-03 │
│ huawei    S5720-56C-PWR-EI  V200R011C10SPC600 / V200R011SPH012     │
│                                               3✓  0⚠ 4◐   2026-09 │
└──────────────────────────────────────────────────────────────────────┘
   ✓ matched   ⚠ version_diff   ◐ patch_diff   ← 点数字弹出设备列表

点「12⚠」：
┌──────────────────────────────────────────────────────────────────────┐
│ N9K-C93180YC-FX — 待升级 (12台)        目标：10.5(5) / -   [导出]   │
├──────────────────────────────────────────────────────────────────────┤
│ 设备名                   IP            当前版本   当前补丁  机房     │
│ rsw1_mdu3_prod_dc07_m01  10.39.x.x     9.3(3)    -        DC07     │
│ rsw2_mdu3_prod_dc07_m01  10.39.x.x     9.3(3)    -        DC07     │
│ ...                                                                  │
│ [全选] [导出升级清单]                                                │
└──────────────────────────────────────────────────────────────────────┘
```

编辑弹窗字段：厂商、型号（现网候选下拉）、版本（现网在跑版本下拉 + 手动输入）、补丁、镜像协议/主机/路径/MD5、引导镜像、补丁文件、评估时间、评估结论、说明、EOS 日期。保存前弹影响预览。

顶部提示条展示基线覆盖率缺口："3 个型号未录基线（共 28 台）[查看]"。

### 7.2 版本统计页（version_stat.vue）

```
┌──────────────────────────────────────────────────────────────────────┐
│ 筛选：厂商 [全部▾]  型号 [全部▾]  机房 [全部▾]                       │
│ 分组：(•) 按指纹分组   ( ) 按设备展示          ← 同 prefix_log.vue   │
├──────────────────────────────────────────────────────────────────────┤
│ 厂商      型号               版本          补丁             台数 占比│
│ ▼ cisco_nx  N3K-C3048TP-1GE                          指纹数:4       │
│     │                       7.0(3)I4(6)   -            74   77.9%  │
│     │                       6.0(2)U5(1)   -            13   13.7%  │
│     │                       6.0(2)U3(7)   -             7    7.4%  │
│     │                       7.0(3)I2(2)   -             1    1.1%  │
│ ▼ huawei    S5700                                    指纹数:3       │
│     │                       V600R023C00SPC500  V600R023SPH150  16  │
│     │                       V600R025C00SPC500  V600R025SPH120   2  │
└──────────────────────────────────────────────────────────────────────┘
   型号按「指纹种类数」降序 —— 分化最严重的排最前
```

点任一指纹行展开该组合的设备列表（IP / 设备名 / 机房 / 采集时间）。基线已录时每行附「基线状态」色标。

厂商标签颜色按 `vendor` 字段哈希生成，不硬编码映射。

## 八、实施顺序

| 步骤 | 内容 | 依赖 | 价值 |
|------|------|------|------|
| 1 | **版本统计页**（4.3）—— 纯 SQL 聚合 + 下钻 | 无 | 零依赖，立刻能看清现网版本分布 |
| 2 | 4.4 双机一致性检查 | 无 | 现网已有 2 对不一致，立即有结果 |
| 3 | `version_baseline` 表 + **版本管理页** CRUD + 受约束下拉 | 无 | 标准可录入 |
| 4 | 4.2 指纹判定 + 按分类拉设备列表 + 影响预览 | 3 | 1.2 反向定位闭环，核心功能到位 |
| 5 | 4.5 升级清单导出 + 基线覆盖率提示 | 4 | 排期落地 |
| 6 | `/api/version/image` | 3 | 等模块 4 ZTP 开工再接 |

补丁已采集，无前置采集工作。步骤 1 和 2 都不依赖新表，可以先上——统计页只是一条 `GROUP BY`，投入最小而现网分化情况立刻可见，也能为步骤 3 录基线提供依据。

## 九、待确认

1. **N3K-C3048TP（95 台，占 rsw 近四成）基线定在哪个版本**？若不再升级只待替换，基线填当前主流版本 `7.0(3)I4(6)`（74 台在跑），则剩余 21 台跑旧版本的仍会显示待升级——这可能正是期望（至少收敛到同一版本），也可能想完全忽略。前者保持现状，后者需要补一个忽略机制。
2. **镜像服务器**：复用 POAP 脚本里的 `10.143.225.1:8888`，还是各机房独立镜像源？后者需要 `image_host` 支持按机房覆盖，表结构要加一层。
3. **Cisco SMU 是否需要纳入**？当前采集器未取 Cisco 补丁（见 2.3），基线填 `-` 即可无噪音运行。若有 SMU 管理需求，按 2.4 补 CLI 按需采集，结果回写 `devices.features`。
4. **`version_diff` 是否要区分升级/降级**？指纹模型下两者都是"不匹配"。若需区分（降级通常是异常），仍需最小限度的版本比较，但只用于打标签不用于判定。

返回：[整体框架](./README.md)
