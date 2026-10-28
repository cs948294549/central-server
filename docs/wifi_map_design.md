# Wi-Fi 地图功能设计

## 文档信息
- 创建时间: 2026-10-27
- 状态: 设计中
- 版本: v1.11
- 修订: v1.11 SNMP 采集拆到 `projects/collector`（`Module/Wlan*.py`），central-server 只提供接口、只读快照；前端去掉 mock，统一走 `wifi_interface.js` 真实接口；新增 `/wifi/map/info` 维护地图属性与底图，`/wifi/map/detail` 直接返回 data URI 底图，去掉 `/wifi/map/upload` 与 `/wifi/map/image`；SQL 全部参数化；`/wifi/ac/collect` 改为连通探测并回写 `last_status`；`map_name` 全局唯一；v1.10 地图属性「所属建筑」改为可选可输的输入框（下拉只作建议），明确建筑无独立维护入口、手输新名称保存即创建；v1.9 `wifi_ap` 补齐型号 `model`（`.13.3.3.1.3`）与软件版本 `sw_version`（`.13.3.3.1.7`）的 OID；v1.8 `wifi_ap` 增加 `sn`（AP 序列号，`.13.3.3.1.2`），详情抽屉基础信息展示 SN；v1.7 终端信号强度与上下行速率改为随快照入库（`wifi_client` 加 `up_rate / down_rate / rssi`），去掉 `/wifi/ap/client_stats` 实时查询；community 改为明文存库；v1.6 地图组件缩放策略改回"图标与底图同在舞台 + `scale(1/z)` 反向缩放"，去掉舞台 `will-change` 避免图标发虚；v1.5 `image_width / image_height` 改为底图实际显示尺寸，编辑器可按缩放"设为实际尺寸"并随保存布局提交，展示页按该尺寸展示（只缩小不放大）；v1.4 按最终表结构同步页面字段（去 SNMP 端口/版本、采集间隔、朝向角、图标缩放；终端速率改为实时查询）；v1.3 去掉历史表（不做趋势图）；v1.2 明确底图只用于大致定位、删除 AC 级联删除 AP 数据、MIB 的 OID 后续补充（先出框架）；v1.1 采集方式改为 SNMP、取消实时推送、确认一图一楼层、终端不关联 CMDB、AC 采集层按厂商 profile 抽象

在平面图上呈现 AP 位置、射频状态与接入终端，解决"哪个位置信号差、哪个 AP 用户多、哪个射频拥塞"的观察需求。交付 1 个地图组件 + 3 个页面（AC 管理、地图编辑、地图展示），后端沿用 central-server 的 Flask + MySQL（只提供接口），SNMP 采集由 `projects/collector` 负责入库，前端沿用 chen_vue 的 Vue 2 + Element UI。

---

## 一、页面与路由

| 编号 | 页面 | 路由 | 作用 |
|---|---|---|---|
| P1 | AC 管理 | `/wifi/ac` | 新增 / 删除 / 编辑 AC，测试连通性，立即探测 |
| P2 | 地图编辑 | `/wifi/map-edit` | 上传底图、拖拽摆放 AP、调整显示名 |
| P3 | 地图展示 | `/wifi/map` | 只读浏览 + AP 详情抽屉 |

页面权限沿用 `pages` / `pages_uri`，三个页面分别建记录。

**不在本期范围：** AP 配置下发、终端准入、信道自动调优、漫游分析、历史趋势图表（不建历史表）、实时推送。

---

## 二、地图组件设计

组件 `WifiMap.vue`，编辑态与展示态共用，通过 `mode` 切换。

**缩放策略：底图与图标同在一个舞台，图标反向缩放。**

- 舞台内放底图和全部图标，整体用 `transform: translate(tx, ty) scale(z)`（`transform-origin: 0 0`）缩放平移，外层为可拖拽视口；
- 图标在舞台坐标系内定位：`left = x_ratio × imgW`，`top = y_ratio × imgH`，缩放平移由舞台统一完成，**图标位置天然跟着底图走**；
- 图标外包一层 `scale(1/z)` 反向缩放，抵消舞台的放大缩小，**视觉大小恒定，锚点（图标底部尖端）始终钉在图上同一位置**；
- 舞台**不加 `will-change: transform`**，否则浏览器会把整层栅格化后按位图缩放，图标会发虚。

其他约定：

- 坐标只存**比例值**（0~1，6 位小数），不存像素。换底图只要宽高比例一致，位置不漂移；不一致时编辑器提示"底图比例已变化，请重新校准"。
- 缩放范围 0.2x ~ 5x，以鼠标位置为中心缩放（Ctrl + 滚轮 / 双指捏合），双击适应窗口，空白处拖拽平移。
- **一图一楼层**：每张图对应一个楼层，楼层名写在 `wifi_map.map_name`（如 `3F-A区`）。多楼层建多张图，展示页顶部按"建筑 → 楼层"两级切换，同一建筑内按 `sort_num` 排序。
- **底图类型**：建筑平面图和机房俯视图都要支持，底图只用于**大致定位**，不追求与真实平面图的精确对齐。因此不做比例尺、不做坐标系校准，摆放以"看得懂这个 AP 在哪个区域"为准；编辑器不提供吸附对齐网格（仅提供批量对齐按钮），避免为了精度牺牲编辑效率。
- 底图以 **base64 存库**（服务端运行在 Docker 中，没有文件存储）。上传限制 2MB，存库时去掉 `data:` 前缀；地图详情接口拼回 data URI 一并返回，列表接口不带图片字段。

### 2.1 标签分级

图标大小不随缩放变化，信息密度按缩放级别决定：

| 缩放 | 显示内容 |
|---|---|
| < 0.6x | 仅状态点 |
| 0.6x ~ 1.2x | 状态点 + AP 名称 + 用户数 |
| ≥ 1.2x | 名称 + 射频数 / 信道 / 利用率 / 功率 / 用户数（五项全量） |

全量标签两行：第一行名称，第二行 `2射频 · CH6/36 · 62% · 20dBm · 38人`。

多射频取值规则：利用率取所有射频**最大值**，功率取最大值，用户数取该 AP 下终端总数（射频明细进详情页）。利用率着色：< 40% 绿，40%~70% 黄，> 70% 红，图标外圈描边同色。

### 2.2 AP 状态

| 状态 | 图标表现 | 标签 |
|---|---|---|
| 在线 | 正常色 | 按分级显示指标 |
| 离线 | 灰 + 红色虚线框 | 只显示名称 + "离线"，指标显示 `--` |
| 未知（未采集过） | 虚线灰框 | 名称 + `--` |

离线 AP 的详情页终端表清空，提示"AP 离线，终端数据不可用"。

### 2.3 其他交互

悬停显示完整 tooltip；单击打开右侧详情抽屉；右上角提供建筑 / 楼层切换、状态筛选（全部 / 仅在线 / 仅告警）、搜索框（按 AP 名或 MAC 定位并居中）、**数据时间标识**（显示当前快照的采集时间，如"数据时间 10:35"）。

**刷新方式：** 不做实时推送。展示页提供自动刷新开关（关闭 / 30 秒 / 1 分钟，默认 1 分钟，仅重新拉取快照接口），以及手动刷新按钮。页面标题旁显示距上次刷新的时间。

---

## 三、页面功能

### 3.1 AC 管理（P1）

列表列：AC 名称、厂商、型号、管理 IP、采集状态、AP 数。

操作：新增、编辑、删除、测试连通、立即探测（只做 SNMP 连通探测并回写 `last_status`，不触发采集；快照由 collector 按周期写入）。

- AC 通过 **SNMP** 采集，不做 SSH 登录，因此不需要用户名密码，只配 SNMP 参数。
- 表单字段：AC 名称、厂商（华为 / H3C / 锐捷）、管理 IP、型号、Community。SNMP 版本固定 v2c、端口固定 161，不在页面暴露。
- Community 明文存库，列表与详情回显一律 `******`，编辑时留空表示不修改。
- **测试连通**：执行 `snmpget sysDescr` + `sysName`，回显设备型号与版本，用于确认 vendor 选得对不对。报错只在弹窗里提示，不入库。
- **删除 AC 二次确认**，提示会连带删除该 AC 下所有 AP、射频、SSID、终端数据及地图上的图标。没有"仅停用"选项。
- 采集间隔固定 5 分钟，页面不提供配置。
- 采集失败（超时、认证失败、OID 无返回）只更新 `last_status` 为 offline，具体原因看服务端日志。

### 3.2 地图编辑（P2）

左侧地图列表（按建筑 / 楼层分组，支持新建 / 复制 / 删除），右侧画布：

- 上传底图（PNG / JPG，≤ 2MB），存 base64 入库；前端读取图片 `naturalWidth / naturalHeight` 作为初始尺寸，随保存一起提交 `image_width / image_height`。
- **实际尺寸**：`image_width / image_height` 是底图的实际显示尺寸，图片按它拉伸，不再以原始像素为准。编辑器工具栏显示"实际 W×H · 当前显示 W×H"，缩放到合适大小后点"设为实际尺寸"，按当前显示大小等比取整（短边 ≥ 100、长边 ≤ 10000），点"保存布局"时随图标一起提交。坐标是比例值，等比改尺寸不影响 AP 位置；尺寸缺失（为 0）时回退到图片原始像素。
- 展示页每张图独占一行，**按实际尺寸展示**：行高取 `image_height`（加少量留白），图片默认 100% 显示、只缩小不放大；比行宽还宽时按行宽等比缩小，比一屏还高时行高封顶到可视高度并等比缩小居中。双击回到该状态，Ctrl + 滚轮可再自由缩放。尺寸缺失（为 0）时按整行宽度 3:2 兜底，图片加载后再以真实尺寸校正。
- 地图属性：名称、所属建筑、同建筑内排序。**所属建筑为自由文本，没有独立的建筑维护入口**：表单里是「可选可输」的输入框，下拉只给出已有建筑作为建议，直接输入一个新名称保存即创建该建筑（该建筑下有了第一张图，左侧列表与下拉里就会带出来）。**没有楼层字段**，楼层名写进地图名称（如 `3F`、`B1`），一张图就是一个楼层。
- 右侧 AP 池按 AC 分组，支持搜索、隐藏已摆放项；拖拽到图上完成摆放。同一 AP 在同一张图只能出现一次，跨地图可复用（跨楼层复制地图时保留相对位置）。
- 选中图标后可编辑：显示名称（默认 AP 名称，可覆盖，存 `wifi_map_ap.display_name`）。**不支持朝向角和图标缩放**，图标随舞台反向缩放，大小天然统一。
- 支持批量选中、对齐、删除（只从地图移除，不删 AP 数据）。
- 保存使用 `version` 乐观锁，冲突提示"地图已被他人修改，请刷新"。
- 提供"临时预览"开关，编辑中切到展示态看效果，不落库。

### 3.3 地图展示 + 详情抽屉（P3）

地图铺满内容区，顶部工具栏同 2.3。点击 AP 打开右侧抽屉（约 720px），抽屉打开时地图仍可操作。

抽屉自上而下四段：

1. **基础信息**：AP 名称、MAC（主键）、SN、型号、软件版本、IP、所属 AC、分组、运行状态、上级设备 / 端口（lldp，AP 不支持时显示 `--`）、所在图 / 楼层、最近采集时间。
2. **射频信息**：一个射频一张卡片内联排列，含射频编号与 WLAN 类型、频段、信道、带宽、信道状态、信道利用率、干扰率、当前功率 / 最大功率、关联用户数。只显示已开启的射频。
3. **开放 SSID**：SSID 名、绑定射频、在线数量、SSID 状态。
4. **终端表格**：MAC、用户名、IP、关联射频、频段、信道、SSID、VLAN、状态，外加**信号强度与上下行速率**两列。支持按 MAC / IP 搜索、按信号强度 / 速率排序、分页（默认 20 条）。

**数据口径：** 四段数据全部来自最近一次采集的快照（5 分钟一次），表头显示"数据时间 HH:mm:ss"，配手动刷新按钮；页面级自动刷新打开时随页面一起更新。**信号强度与速率随终端快照一起入库**：RSSI（`.18.1.2.1.42`）、上行（`.35`）、下行（`.38`）与终端其它字段同批采集（AC 侧每分钟更新一次），不做实时查询。采不到时两列显示 `--`，表格其它数据照常展示。

---

## 四、数据模型

### 4.1 采集方式

全部数据通过 **SNMP** 从 AC 侧拉取，只读，不写设备。

- 快照表（AP / 射频 / SSID / 终端）**每 5 分钟全量刷新**，由 `projects/collector` 负责写入；刷新方式、并发与超时控制都在 collector 侧处理，central-server 只读。
- 单台 AC 采集失败不影响其他 AC；central-server 侧 `/wifi/ac/test`、`/wifi/ac/collect` 只做连通探测，后者回写 `last_status`。
- **只保留最新快照**，不做历史抽样、不建历史表（不做趋势图）。每张快照表在采集时全量替换。
- 终端表存关联关系（AP、射频、SSID、IP、VLAN、状态）以及信号强度、上下行速率，随快照一起采集入库，不做实时查询，见 3.3。

### 4.2 厂商适配层

SNMP 采集已拆到 `projects/collector`，central-server 不再包含采集代码。collector 按数据类型拆成四个模块：

```
projects/collector/Module/
  WlanAP.py          # wifi_ap
  WlanRadio.py       # wifi_radio
  WlanSSID.py        # wifi_ssid
  WlanClient.py      # wifi_client
```

- 每个类按 `wifi_ac.vendor` 分派到 `__getHuaweiXxx` / `__getH3cXxx` / `__getRuijieXxx`，输出统一结构（与 4.4 的表字段一一对应）。
- OID 写在各厂商方法内部，统一使用 `utils.snmp_tool` 的异步 `snmpwalk`。
- **华为 OID 已落地；H3C、锐捷方法暂时返回 `None`，待实机 `snmpwalk` 核对后补齐**，补齐时只改对应方法，不动表结构和接口。
- 企业 OID 分支（华为 `1.3.6.1.4.1.2011.*`、H3C `1.3.6.1.4.1.25506.*`、锐捷 `1.3.6.1.4.1.4881.*`）**必须用实机核对后再固化**，不能凭文档照抄。

### 4.3 表间关系

- `wifi_ac` 1—N `wifi_ap`：AP 以 `ap_mac` 全局唯一，换 AC 时只更新 `ac_id`，AP 主键不变，地图与数据都跟着走。
- `wifi_ap` 1—N `wifi_radio`：按 `(ap_mac, radio_id)` 唯一；一个 AP 可能有多个射频，也可能只开部分，关闭的射频不入库。
- `wifi_radio` 1—N `wifi_ssid`：按 `(ap_mac, radio_id, seq)` 唯一，同名 SSID 出现在多个射频则各存一行。
- `wifi_ap` 1—N `wifi_client`：以 `client_mac` 为主键，`ap_mac` 建索引；只存在线终端，漫游时更新 `ap_mac`。
- `wifi_map` 1—N `wifi_map_ap`：位置与显示名只在 `wifi_map_ap`，**AP 表不存位置**，同一 AP 可出现在多张图（多楼层）且互不影响。

不做历史表和趋势分析，所有表都只保存当前状态。

### 4.4 字段速览

完整 DDL 见 `scripts/db_create.sql`（Wi-Fi 地图功能表结构一节）。**所有 SNMP 采集表统一以 MAC 作为主键或索引。**

| 表 | 主键 / 关键字段 | 说明 |
|---|---|---|
| wifi_ac | ac_id；ac_name, vendor, mgmt_ip, model, community, last_status | community 明文；ac_name、mgmt_ip 唯一 |
| wifi_ap | ap_mac；ap_name, sn, ap_group, online_status, ap_ip, model, sw_version, client_count, lldp_name, lldp_port, ac_id | 主键即 MAC，换 AC 只改 ac_id |
| wifi_radio | (ap_mac, radio_id)；band, channel_status, channel, bandwidth, utilization, interference_rate, client_count, tx_power, max_power | 只存开启的射频；地图标签数据源 |
| wifi_ssid | (ap_mac, radio_id, seq)；ssid, client_count, ssid_status | 同一 SSID 在多个射频各存一行 |
| wifi_client | client_mac；ap_mac, radio_id, band, channel, ssid, status, vlan_id, ip, up_rate, down_rate, rssi | 只存在线终端；含 RSSI 与上下行速率 |
| wifi_map | map_id；map_name, building, sort_num, image_base64, image_width, image_height, version | 一图一楼层；底图 base64 存库；宽高为底图实际显示尺寸（默认原始像素，可在编辑器按缩放调整），用于画布尺寸与展示页按实际尺寸展示 |
| wifi_map_ap | (map_id, ap_mac)；x_ratio, y_ratio, display_name | 坐标用比例值，与分辨率解耦 |

> `wifi_radio.band` 不做枚举，2.4G / 5G / 6G 及后续新频段按 OID 原值存。
> `wifi_client` 的信号强度（dBm）与上下行速率（bps）随终端快照一起入库（见 3.3）。

---

## 五、接口设计

沿用现有约定：Flask Blueprint `/wifi` + `APIResponse` 包装，前端 `src/api/mapis/wifi_interface.js`。

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | /wifi/ac/list | AC 列表 | 读 |
| POST | /wifi/ac/save | 新增或修改 AC | 写 |
| POST | /wifi/ac/delete | 删除 AC（连带数据） | 写 |
| POST | /wifi/ac/test | SNMP 连通性测试，返回 sysDescr / sysName | 写 |
| POST | /wifi/ac/collect | 立即探测：SNMP 连通探测并回写 `last_status`，不触发采集 | 写 |
| POST | /wifi/map/list | 地图列表（按建筑 / 楼层分组，不带底图） | 读 |
| POST | /wifi/map/detail | 地图 + 底图（data URI）+ 全部图标（含最新指标、数据时间、`image_width / image_height`） | 读 |
| POST | /wifi/map/info | 新增 / 修改地图属性与底图，带 `map_id` 为修改；`map_name` 全局唯一，底图 ≤ 2MB | 写 |
| POST | /wifi/map/save | 只保存布局：图标全量替换，`version` 乐观锁（冲突返回 409）；可选带 `image_width / image_height` 更新实际尺寸 | 写 |
| POST | /wifi/map/delete | 删除地图 | 写 |
| POST | /wifi/ap/detail | AP 详情（基础 + 射频 + SSID） | 读 |
| POST | /wifi/ap/clients | AP 下终端（前端搜索 / 排序 / 分页） | 读 |
| POST | /wifi/ap/pool | 可摆放 AP 池（按 AC 分组） | 读 |

无 WebSocket 接口。

---

## 六、落地拆分

### 6.1 数据库

1. `scripts/db_create.sql`：Wi-Fi 地图功能表结构已合并进这份初始化脚本的末尾（与现有脚本同风格：`DROP TABLE IF EXISTS` + 列注释 + `utf8mb4`）。
2. `scripts/db_page.sql` 追加三条页面记录及对应 `pages_uri` 权限。

### 6.2 前端（chen_vue）

```
src/view/pages/wireless/
  ac_manage.vue
  map_edit.vue
  map_view.vue
  wifi_components/
    WifiMap.vue            # 唯一地图组件，mode 区分编辑/展示
    WifiMapToolbar.vue     # 建筑/楼层切换、筛选、搜索、刷新
    ApDetailDrawer.vue
    ApIcon.vue             # 图标 + 标签 + 状态描边
    ClientTable.vue        # 快照表格，支持搜索/排序/分页
src/api/mapis/wifi_interface.js
```

`WifiMap` 通过 props 接收 `map`、`markers`、`mode`，向外抛 `marker-click`、`marker-move`、`marker-select`、`zoom-change`；拖拽逻辑封装在组件内部，页面只处理结果。

### 6.3 后端（central-server）

1. `api/api_wifi.py`：接口层，注册到 `core/app.py`。
2. `function_wifi/func_ac.py`、`func_map.py`、`func_ap.py`：业务层。
3. `tables/WifiDB.py`：DAO，继承 `mysqldb_netops`。
4. SNMP 采集不在 central-server：由 `projects/collector` 的 `Module/Wlan*.py` 周期采集并写入快照表（见 4.2），central-server 只读。

分层约定：api 只做参数校验与 `APIResponse` 封装，调用 function_wifi；function_wifi 调用 `WifiDB`，返回 `{success, data, message, code?}`；DAO 出错返回 `"failed"`，SQL 全部参数化。

**注意点：** SNMP 本期只用 v2c（community 参数），`wifi_ac` 没有 snmp 版本 / 端口字段；后续接 v3 需要 collector 侧增加 v3 封装并给 `wifi_ac` 加 `snmp_v3_*` 字段。非 system / admin 角色访问 `/wifi/*` 需要在 `pages_uri` 中有对应记录，否则返回 403。

---

## 七、已确认结论

1. **地图粒度**：一图一楼层，多楼层建多张图；地图表用 `building + sort_num` 排序，楼层名即 `map_name`，展示页两级切换。
2. **底图类型**：建筑平面图与机房俯视图都支持，只用于大致定位，不追求精度；不做比例尺、坐标系校准与吸附网格。底图 base64 存库，2MB 上限。
3. **终端归属**：不关联 CMDB / DHCP 租约，用户名取 AC 上报值，取不到显示 MAC。
4. **采集方式**：统一 SNMP，不做 SSH；采集由 `projects/collector` 负责，新增厂商只补 `Module/Wlan*.py` 中对应方法，不改表结构与接口。**华为 OID 已落地，H3C、锐捷待实机补齐。**
5. **实时性**：不做 WebSocket 推送；以 5 分钟快照为数据源，页面提供自动刷新（可关闭）与手动刷新。终端信号强度与速率随快照入库，不做实时查询。
6. **删除 AC**：级联删除该 AC 下所有 AP、射频、SSID、终端数据以及地图图标，不做软删除、不保留历史。
7. **不做趋势图**：不建历史表，所有表只保存当前状态；快照采集直接覆盖，无抽样与清理任务。

## 八、待确认

1. 各厂商无线 MIB 的 OID 需按实机 `snmpwalk` 核对（尤其是终端 RSSI `.18.1.2.1.42`、上下行速率 `.35/.38`、SSID-VLAN 绑定关系），核对前 DDL 与解析逻辑按本设计推进，不阻塞。
2. AP 的 lldp-port OID 待补（型号 `.13.3.3.1.3`、软件版本 `.13.3.3.1.7` 已补）；`channel_status`（`.16.1.2.1.6`）的实际取值含义待实机确认。
