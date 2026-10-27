-- ============================================
-- Wi-Fi 地图功能表结构
-- 设计文档: docs/wifi_map_design.md
-- 说明:
--   1. 只保存当前快照,不做历史趋势
--   2. 所有 SNMP 采集表都以 MAC 作为主键/索引
--   3. 不使用外键约束,级联删除由业务层控制(与现有表保持一致)
-- ============================================

-- ============================================
-- 1. AC 管理表
-- ============================================
DROP TABLE IF EXISTS wifi_ac;
CREATE TABLE wifi_ac (
    ac_id       INT AUTO_INCREMENT PRIMARY KEY COMMENT 'AC ID',
    ac_name     VARCHAR(64)  NOT NULL COMMENT 'AC名称',
    vendor      VARCHAR(32)  NOT NULL DEFAULT 'huawei' COMMENT '厂商: huawei/h3c/ruijie',
    mgmt_ip     VARCHAR(64)  NOT NULL COMMENT '管理IP',
    model       VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '设备型号,如 AC6508',
    community   VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'SNMP Community(明文)',
    last_status VARCHAR(16)  NOT NULL DEFAULT 'unknown' COMMENT '最近采集状态: online/offline/unknown',
    UNIQUE KEY uk_ac_name (ac_name),
    UNIQUE KEY uk_mgmt_ip (mgmt_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Wi-Fi AC管理表';

-- ============================================
-- 2. AP 表
-- 主键: ap_mac
-- 说明: lldp 信息需要 AP 支持,不支持时留空;lldp_port 的 OID 待补
-- ============================================
DROP TABLE IF EXISTS wifi_ap;
CREATE TABLE wifi_ap (
    ap_mac        VARCHAR(32)  NOT NULL COMMENT 'AP MAC,主键,统一小写冒号格式',
    ap_name       VARCHAR(128) NOT NULL DEFAULT '' COMMENT 'AP名称 1.3.6.1.4.1.2011.6.139.13.3.3.1.4',
    sn            VARCHAR(64)  NOT NULL DEFAULT '' COMMENT 'AP序列号 1.3.6.1.4.1.2011.6.139.13.3.3.1.2',
    ap_group      VARCHAR(128) NOT NULL DEFAULT '' COMMENT '分组 1.3.6.1.4.1.2011.6.139.13.3.3.1.5',
    online_status VARCHAR(16)  NOT NULL DEFAULT 'unknown' COMMENT '运行状态 1.3.6.1.4.1.2011.6.139.13.3.3.1.6: 8(normal)=online,其余=offline,未采集=unknown',
    ap_ip         VARCHAR(64)  NOT NULL DEFAULT '' COMMENT 'AP IP 1.3.6.1.4.1.2011.6.139.13.3.3.1.13',
    model         VARCHAR(64)  NOT NULL DEFAULT '' COMMENT 'AP型号 1.3.6.1.4.1.2011.6.139.13.3.3.1.3',
    sw_version    VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '软件版本 1.3.6.1.4.1.2011.6.139.13.3.3.1.7',
    client_count  INT          NOT NULL DEFAULT 0  COMMENT '用户数量 1.3.6.1.4.1.2011.6.139.13.3.3.1.44',
    lldp_name     VARCHAR(128) NOT NULL DEFAULT '' COMMENT '上级设备名 1.3.6.1.4.1.2011.6.139.13.3.6.1.8(需AP支持)',
    lldp_port     VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '上级端口(OID待补,需AP支持)',
    ac_id         INT          NOT NULL DEFAULT 0  COMMENT '所属AC ID',
    last_seen_at  VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '最近采集时间',
    PRIMARY KEY (ap_mac),
    INDEX idx_ac_id (ac_id),
    INDEX idx_online_status (online_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Wi-Fi AP表';

-- ============================================
-- 3. 射频表
-- 主键: (ap_mac, radio_id)
-- 说明: 只存开启的射频,关闭的射频不入库
--       band 不枚举,2.4G/5G/6G 及后续新频段按 OID 原值存
--       一个 AP 可能有多个射频,也可能只有部分开启
-- ============================================
DROP TABLE IF EXISTS wifi_radio;
CREATE TABLE wifi_radio (
    ap_mac            VARCHAR(32)  NOT NULL COMMENT '所属AP MAC',
    radio_id          INT          NOT NULL COMMENT '射频ID(索引第二部分)',
    wlan_type         VARCHAR(32)  NOT NULL DEFAULT '' COMMENT 'WLAN类型 1.3.6.1.4.1.2011.6.139.16.1.2.1.4',
    band              VARCHAR(16)  NOT NULL DEFAULT '' COMMENT '频段 1.3.6.1.4.1.2011.6.139.16.1.2.1.5',
    channel_status    VARCHAR(16)  NOT NULL DEFAULT 'down' COMMENT '信道状态 1.3.6.1.4.1.2011.6.139.16.1.2.1.6',
    channel           INT          DEFAULT NULL COMMENT '信道 1.3.6.1.4.1.2011.6.139.16.1.2.1.7',
    bandwidth         INT          DEFAULT NULL COMMENT '带宽MHz 1.3.6.1.4.1.2011.6.139.16.1.2.1.19',
    utilization       DECIMAL(5,2) DEFAULT NULL COMMENT '信道利用率% 1.3.6.1.4.1.2011.6.139.16.1.2.1.25',
    interference_rate DECIMAL(5,2) DEFAULT NULL COMMENT '干扰率% 1.3.6.1.4.1.2011.6.139.16.1.2.1.29',
    client_count      INT          NOT NULL DEFAULT 0  COMMENT '射频在线数量 1.3.6.1.4.1.2011.6.139.16.1.2.1.40',
    tx_power          INT          DEFAULT NULL COMMENT '功率dBm 1.3.6.1.4.1.2011.6.139.16.1.2.1.45',
    max_power         INT          DEFAULT NULL COMMENT '最大功率dBm 1.3.6.1.4.1.2011.6.139.16.1.2.1.46',
    ac_id             INT          NOT NULL DEFAULT 0 COMMENT '所属AC ID',
    PRIMARY KEY (ap_mac, radio_id),
    INDEX idx_ac_id (ac_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Wi-Fi射频表';

-- ============================================
-- 4. SSID 表
-- 主键: (ap_mac, radio_id, seq)
-- 说明: 同一 SSID 出现在多个射频下时各存一行
-- ============================================
DROP TABLE IF EXISTS wifi_ssid;
CREATE TABLE wifi_ssid (
    ap_mac       VARCHAR(32) NOT NULL COMMENT '所属AP MAC',
    radio_id     INT         NOT NULL COMMENT '所属射频ID',
    seq          INT         NOT NULL COMMENT '序号(索引第三部分)',
    ssid         VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'SSID名称 1.3.6.1.4.1.2011.6.139.17.1.1.1.6',
    client_count INT         NOT NULL DEFAULT 0  COMMENT '在线数量 1.3.6.1.4.1.2011.6.139.17.1.1.1.9',
    ssid_status  VARCHAR(16) NOT NULL DEFAULT 'up' COMMENT 'SSID状态 1.3.6.1.4.1.2011.6.139.17.1.1.1.10: 1(normal)=up,其余=down',
    ac_id        INT         NOT NULL DEFAULT 0 COMMENT '所属AC ID',
    PRIMARY KEY (ap_mac, radio_id, seq),
    INDEX idx_ssid (ssid),
    INDEX idx_ac_id (ac_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Wi-Fi SSID表';

-- ============================================
-- 5. 终端表
-- 主键: client_mac
-- 说明: 只存在线终端的关联关系
--       信号强度和上下行速率随终端快照一起采集入库,不做实时查询
-- ============================================
DROP TABLE IF EXISTS wifi_client;
CREATE TABLE wifi_client (
    client_mac VARCHAR(32)  NOT NULL COMMENT '终端MAC,主键,统一小写冒号格式',
    username   VARCHAR(128) NOT NULL DEFAULT '' COMMENT '用户名 1.3.6.1.4.1.2011.6.139.18.1.2.1.2',
    ap_mac     VARCHAR(32)  NOT NULL DEFAULT '' COMMENT '所属AP MAC 1.3.6.1.4.1.2011.6.139.18.1.2.1.3',
    ap_name    VARCHAR(128) NOT NULL DEFAULT '' COMMENT '所属AP名称 1.3.6.1.4.1.2011.6.139.18.1.2.1.4',
    radio_id   INT          DEFAULT NULL COMMENT '所在射频ID 1.3.6.1.4.1.2011.6.139.18.1.2.1.6',
    band       VARCHAR(16)  NOT NULL DEFAULT '' COMMENT '用户频段 1.3.6.1.4.1.2011.6.139.18.1.2.1.7',
    channel    INT          DEFAULT NULL COMMENT '用户信道 1.3.6.1.4.1.2011.6.139.18.1.2.1.9',
    ssid       VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '所在SSID 1.3.6.1.4.1.2011.6.139.18.1.2.1.18',
    status     VARCHAR(16)  NOT NULL DEFAULT '' COMMENT '终端状态 1.3.6.1.4.1.2011.6.139.18.1.2.1.19: 3(normal)=online,其余=offline',
    vlan_id    INT          DEFAULT NULL COMMENT '用户VLAN 1.3.6.1.4.1.2011.6.139.18.1.2.1.24',
    ip         VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '用户IP 1.3.6.1.4.1.2011.6.139.18.1.2.1.25',
    up_rate    BIGINT       DEFAULT NULL COMMENT '用户速率收(上行bps) 1.3.6.1.4.1.2011.6.139.18.1.2.1.35',
    down_rate  BIGINT       DEFAULT NULL COMMENT '用户速率发(下行bps) 1.3.6.1.4.1.2011.6.139.18.1.2.1.38',
    rssi       INT          DEFAULT NULL COMMENT '用户信号强度dBm 1.3.6.1.4.1.2011.6.139.18.1.2.1.42',
    ac_id      INT          NOT NULL DEFAULT 0 COMMENT '所属AC ID',
    PRIMARY KEY (client_mac),
    INDEX idx_ap_mac (ap_mac),
    INDEX idx_ssid (ssid),
    INDEX idx_ac_id (ac_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Wi-Fi终端表(当前快照)';

-- ============================================
-- 6. 地图表
-- 说明: 一图一楼层,底图以 base64 存库(服务端无文件存储)
--       列表查询禁止带出 image_base64,图片单独走接口
--       上传限制 2MB,需保证 max_allowed_packet >= 8M
-- ============================================
DROP TABLE IF EXISTS wifi_map;
CREATE TABLE wifi_map (
    map_id       INT AUTO_INCREMENT PRIMARY KEY COMMENT '地图ID',
    map_name     VARCHAR(100) NOT NULL COMMENT '地图名称',
    building     VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '所属建筑',
    sort_num     INT          NOT NULL DEFAULT 0  COMMENT '同建筑内楼层排序,小的在前',
    image_base64 LONGTEXT     NOT NULL COMMENT '底图base64,不含data URI前缀',
    image_width  INT          NOT NULL DEFAULT 0  COMMENT '底图原始宽(px),展示页按宽高比定行高',
    image_height INT          NOT NULL DEFAULT 0  COMMENT '底图原始高(px)',
    version      INT          NOT NULL DEFAULT 1  COMMENT '版本号(乐观锁)',
    UNIQUE KEY uk_map_name (map_name),
    INDEX idx_building (building, sort_num)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Wi-Fi地图表';

-- ============================================
-- 7. 地图-AP 摆放表
-- 主键: (map_id, ap_mac)
-- 说明: 位置只存在这里,AP 表不存位置,同一 AP 可出现在多张地图
--       坐标用比例值(0~1),与底图分辨率解耦
-- ============================================
DROP TABLE IF EXISTS wifi_map_ap;
CREATE TABLE wifi_map_ap (
    map_id       INT          NOT NULL COMMENT '地图ID',
    ap_mac       VARCHAR(32)  NOT NULL COMMENT 'AP MAC',
    x_ratio      DECIMAL(9,6) NOT NULL DEFAULT 0 COMMENT '横坐标比例(0~1),相对底图宽度',
    y_ratio      DECIMAL(9,6) NOT NULL DEFAULT 0 COMMENT '纵坐标比例(0~1),相对底图高度',
    display_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '地图显示名,为空时取AP名称',
    PRIMARY KEY (map_id, ap_mac),
    INDEX idx_ap_mac (ap_mac)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Wi-Fi地图AP摆放表';
