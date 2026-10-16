-- Central-Server ACL 管理数据库表结构
-- 用途：策略管理 -> ACL 管理（ACL / 地址组 / 端口组）
-- 说明：三类对象各自独立采集，ACL 规则中以组名引用，采集时不展开
-- 测试通过后合并到 db_create.sql

USE netops;

-- ============================================
-- ACL 管理相关表
-- ============================================

-- ACL 设备实际配置表（规则记录）
DROP TABLE IF EXISTS acl_records;
CREATE TABLE acl_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    device_ip VARCHAR(15) NOT NULL COMMENT '设备IP地址',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称/hostname',
    vendor VARCHAR(32) NOT NULL COMMENT '设备厂商：cisco_nx, cisco_ios, cisco_xr, h3c, huawei',
    acl_name VARCHAR(64) NOT NULL COMMENT 'ACL标识名：有名字用名字，纯编号时存编号字符串',
    acl_number INT DEFAULT NULL COMMENT 'ACL编号（仅编号定义时有值，命名ACL为NULL）',
    acl_type VARCHAR(16) NOT NULL DEFAULT 'ipv4' COMMENT '地址族：ipv4, ipv6',
    acl_kind VARCHAR(16) DEFAULT NULL COMMENT '类别：basic, advanced, l2, custom, named',
    rule_count INT NOT NULL DEFAULT 0 COMMENT '规则条数（冗余，列表页免解析JSON）',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256，组引用保留组名不展开）',
    entries JSON NOT NULL COMMENT '标准化规则内容，裸数组',
    collected_at VARCHAR(10) NOT NULL COMMENT '采集时间（10位时间戳）',

    -- acl_type 必须进唯一键：ip access-list 3999 与 ipv6 access-list 3999 是独立 ACL
    -- acl_number 不进唯一键，它由 acl_name 推导，不独立
    UNIQUE KEY uk_device_acl_collected (device_ip, acl_name, acl_type),
    INDEX idx_acl_number (acl_number, acl_type),
    INDEX idx_acl_fingerprint (acl_name, acl_type, fingerprint),
    INDEX idx_device_ip (device_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ACL-设备实际配置表';

-- 地址组设备实际配置表（规则记录）
DROP TABLE IF EXISTS addrgroup_records;
CREATE TABLE addrgroup_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    device_ip VARCHAR(15) NOT NULL COMMENT '设备IP地址',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称/hostname',
    vendor VARCHAR(32) NOT NULL COMMENT '设备厂商：cisco_nx, cisco_ios, cisco_xr, h3c, huawei',
    group_name VARCHAR(64) NOT NULL COMMENT '地址组名称，如 og_ip_idcnet',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256）',
    entries JSON NOT NULL COMMENT '结构化条目，裸数组',
    collected_at VARCHAR(10) NOT NULL COMMENT '采集时间（10位时间戳）',

    UNIQUE KEY uk_device_group_collected (device_ip, group_name),
    INDEX idx_group_fingerprint (group_name, fingerprint),
    INDEX idx_device_ip (device_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='地址组-设备实际配置表';

-- 端口组设备实际配置表（规则记录）
DROP TABLE IF EXISTS portgroup_records;
CREATE TABLE portgroup_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    device_ip VARCHAR(15) NOT NULL COMMENT '设备IP地址',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称/hostname',
    vendor VARCHAR(32) NOT NULL COMMENT '设备厂商：cisco_nx, cisco_ios, cisco_xr, h3c, huawei',
    group_name VARCHAR(64) NOT NULL COMMENT '端口组名称，如 og_port_per',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256）',
    entries JSON NOT NULL COMMENT '结构化条目，裸数组',
    collected_at VARCHAR(10) NOT NULL COMMENT '采集时间（10位时间戳）',

    UNIQUE KEY uk_device_group_collected (device_ip, group_name),
    INDEX idx_group_fingerprint (group_name, fingerprint),
    INDEX idx_device_ip (device_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='端口组-设备实际配置表';

-- ACL 标准规则表（规则制定）
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ACL-标准规则表';

-- 地址组标准规则表（规则制定）
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='地址组-标准规则表';

-- 端口组标准规则表（规则制定）
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='端口组-标准规则表';

-- 问题处理记录：ACL / 地址组 / 端口组 与 前缀列表 共用 policy_issue_records 表
-- 表结构见 db_create.sql，用 object_type 区分对象类型（acl / addrgroup / portgroup）

-- 示例数据说明：
-- 1. 规则制定：在 acl_standards / addrgroup_standards / portgroup_standards 插入标准配置
-- 2. 规则记录：定期采集设备配置，按 device_ip 先删后插，库中只保留最新一次
-- 3. 问题处理：比对标准与设备配置生成问题记录写入 policy_issue_records，进行流程跟踪和工单管理
