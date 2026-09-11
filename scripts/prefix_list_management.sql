-- 地址前缀列表管理相关表
-- 用途：策略管理 -> 地址前缀管理
-- 创建时间：2026-09-10

-- 1. 标准规则表（规则制定）
-- 用于定义和存储标准的地址前缀列表配置模板
CREATE TABLE IF NOT EXISTS prefix_list_standards (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    name VARCHAR(64) NOT NULL COMMENT '前缀列表名称，如 pl_global',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256）',
    entries JSON NOT NULL COMMENT '标准配置内容，包含完整的entries列表',
    description TEXT COMMENT '规则说明',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用：1-启用，0-禁用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by VARCHAR(64) COMMENT '创建人',

    UNIQUE KEY uk_name_fingerprint (name, fingerprint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='地址前缀列表-标准规则表';

-- 2. 设备实际配置表（规则记录）
-- 用于存储从设备采集的实际地址前缀列表配置
CREATE TABLE IF NOT EXISTS prefix_list_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    device_ip VARCHAR(15) NOT NULL COMMENT '设备IP地址',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称/hostname',
    vendor VARCHAR(32) NOT NULL COMMENT '设备厂商：cisco_nx, cisco_ios, cisco_xr, h3c, huawei',
    pl_name VARCHAR(64) NOT NULL COMMENT '前缀列表名称',
    fingerprint CHAR(64) NOT NULL COMMENT '配置指纹（SHA256）',
    entries JSON NOT NULL COMMENT '实际配置内容',
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '采集时间',

    UNIQUE KEY uk_device_pl_collected (device_ip, pl_name, collected_at),
    INDEX idx_pl_name_fingerprint (pl_name, fingerprint),
    INDEX idx_device_ip (device_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='地址前缀列表-设备实际配置表';

-- 3. 地址前缀问题处理记录表
-- 用于记录配置漂移和缺失问题的处理流程
CREATE TABLE IF NOT EXISTS prefix_list_issue_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',

    -- 标准规则信息
    standard_id BIGINT NOT NULL COMMENT '标准规则ID',
    standard_name VARCHAR(64) NOT NULL COMMENT '标准规则名称',

    -- 设备信息
    device_ip VARCHAR(15) NOT NULL COMMENT '设备IP',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称',
    device_vendor VARCHAR(32) NOT NULL COMMENT '设备厂商：cisco_nx, cisco_ios, cisco_xr, h3c, huawei',

    -- 问题类型
    issue_type ENUM('drifted', 'missing') NOT NULL DEFAULT 'drifted'
        COMMENT '问题类型：drifted=配置漂移, missing=缺失配置',

    -- 配置数据（JSON格式，用于对比展示）
    standard_entries JSON NOT NULL COMMENT '标准配置条目',
    device_entries JSON NOT NULL COMMENT '设备配置条目',

    -- 处理状态
    status ENUM('pending', 'processing', 'completed', 'ignored') NOT NULL DEFAULT 'pending'
        COMMENT '处理状态：pending=待处理, processing=处理中, completed=已完成, ignored=已忽略',

    -- 工单信息
    change_ticket_id VARCHAR(64) DEFAULT NULL COMMENT '变更工单ID',

    -- 操作信息
    created_by VARCHAR(64) DEFAULT NULL COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    processed_at TIMESTAMP NULL DEFAULT NULL COMMENT '处理完成时间',
    remark TEXT DEFAULT NULL COMMENT '备注信息',

    -- 索引
    INDEX idx_standard_id (standard_id),
    INDEX idx_device_ip (device_ip),
    INDEX idx_status (status)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='地址前缀问题处理记录表';

-- 示例数据说明：
-- 1. 规则制定：在 prefix_list_standards 插入标准配置，系统生成 fingerprint
-- 2. 规则记录：定期采集设备配置并插入 prefix_list_records
-- 3. 问题处理：从 test2 管理配置创建问题记录到 prefix_list_issue_records，在 test4 进行流程跟踪和工单管理
