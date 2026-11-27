-- 业务架构模板主表
-- 存储模板的元信息，配置文本和参数定义按厂商拆分到 arch_template_config 表
CREATE TABLE IF NOT EXISTS `arch_template` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `tid` VARCHAR(64) NOT NULL COMMENT '模板 ID（UUID），业务主键',
  `name` VARCHAR(200) NOT NULL COMMENT '模板名称，如"400G-BGP 双归上联"',
  `arch_type` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '架构类型标识：400g-bgp / 200g-ospf / cbs-ebgp',
  `description` TEXT COMMENT '用途与适用场景说明',
  `tags` JSON COMMENT '标签，如 ["rsw", "cbs", "ebgp"]',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用（0=停用，1=启用）',
  `min_expand_unit` INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '最小扩张单元：每次扩容的最小设备台数，如双归为 2',
  `created_by` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '创建人',
  `updated_by` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '最后修改人',
  `created_at` VARCHAR(10) NOT NULL DEFAULT '' COMMENT '创建时间（Unix 时间戳）',
  `updated_at` VARCHAR(10) NOT NULL DEFAULT '' COMMENT '最后修改时间（Unix 时间戳）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tid` (`tid`),
  KEY `idx_name` (`name`),
  KEY `idx_arch_type` (`arch_type`),
  KEY `idx_active` (`is_active`),
  KEY `idx_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='业务架构模板主表';


-- 业务架构模板配置表（按厂商分行存储）
-- 每个模板 × 每个厂商一行，只存该厂商自身（A 端）的配置文本与参数定义
-- 版本号按厂商独立管理，修改某个厂商的配置时该厂商的版本号 +1
CREATE TABLE IF NOT EXISTS `arch_template_config` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `tid` VARCHAR(64) NOT NULL COMMENT '模板 ID，关联 arch_template.tid',
  `vendor` VARCHAR(50) NOT NULL COMMENT '厂商代号：cisco_nx / cisco_ios / cisco_xr / h3c / huawei',
  `version` INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '该厂商配置的版本号，每次修改自增',
  `config_a` MEDIUMTEXT COMMENT '配置文本（Jinja 格式）',
  `params` JSON NOT NULL COMMENT '该厂商的参数定义清单，数组格式',
  `created_at` VARCHAR(10) NOT NULL DEFAULT '' COMMENT '创建时间（Unix 时间戳）',
  `updated_at` VARCHAR(10) NOT NULL DEFAULT '' COMMENT '最后修改时间（Unix 时间戳）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tid_vendor` (`tid`, `vendor`),
  KEY `idx_tid` (`tid`),
  KEY `idx_vendor` (`vendor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='业务架构模板配置表';


-- 配置模板版本快照表
-- 按 tid + vendor + version 存储每个厂商配置的历史版本
-- 每次修改某个厂商的配置时，插入一条快照记录
CREATE TABLE IF NOT EXISTS `arch_template_snapshot` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `tid` VARCHAR(64) NOT NULL COMMENT '模板 ID',
  `vendor` VARCHAR(50) NOT NULL COMMENT '厂商代号',
  `version` INT UNSIGNED NOT NULL COMMENT '版本号',
  `config_a` MEDIUMTEXT COMMENT '配置文本快照',
  `params` JSON NOT NULL COMMENT '参数定义清单快照',
  `updated_by` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '修改人',
  `updated_at` VARCHAR(10) NOT NULL DEFAULT '' COMMENT '修改时间（Unix 时间戳）',
  `change_summary` VARCHAR(500) COMMENT '变更摘要',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tid_vendor_version` (`tid`, `vendor`, `version`),
  KEY `idx_tid` (`tid`),
  KEY `idx_tid_version` (`tid`, `version`),
  KEY `idx_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置模板版本快照表';


-- 示例数据（可选）
INSERT INTO `arch_template`
  (`tid`, `name`, `arch_type`, `description`, `tags`, `min_expand_unit`, `created_by`, `updated_by`)
VALUES
  (
    '00000000-0000-0000-0000-000000000001',
    '400G-BGP 双归上联（示例）',
    '400g-bgp',
    '适用于 400G 单模 MDU，双归上联到核心，使用 BGP 协议',
    '["rsw", "bgp", "400g"]',
    2,
    'system',
    'system'
  );

INSERT INTO `arch_template_config`
  (`tid`, `vendor`, `version`, `config_a`, `params`)
VALUES
  (
    '00000000-0000-0000-0000-000000000001',
    'cisco_nx',
    1,
    'configure terminal\n! vPC domain {{ vpc_domain }}\n! 配置示例\ncopy running-config startup-config',
    '[{"key":"vpc_domain","label":"vPC Domain","type":"int","scope":"group","required":true}]'
  ),
  (
    '00000000-0000-0000-0000-000000000001',
    'h3c',
    1,
    'system-view\n# irf member {{ member_id }}\n# 配置示例\nreturn\nsave force',
    '[{"key":"member_id","label":"IRF Member ID","type":"int","scope":"device","required":true}]'
  );
