-- Central-Server 数据库初始化脚本
-- 包含所有表结构定义和初始数据

-- 创建数据库
CREATE DATABASE IF NOT EXISTS netops DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE netops;

-- ============================================
-- 用户认证相关表
-- ============================================

-- 用户表
DROP TABLE IF EXISTS users;
CREATE TABLE users(
    username VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '用户名',
    identify VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT '密码hash或API认证凭证',
    subname VARCHAR(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '中文名',
    phone VARCHAR(20) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '电话',
    mail VARCHAR(50) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '邮箱',
    rid VARCHAR(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '角色ID',
    update_time VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '最近更新时间',
    last_login VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '最近登陆时间',
    PRIMARY KEY(username),
    INDEX idx_rid (rid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 角色表
DROP TABLE IF EXISTS roles;
CREATE TABLE roles(
    rid VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '角色ID',
    name VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '角色名',
    descr VARCHAR(64) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '角色描述',
    PRIMARY KEY(rid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色表';

-- 角色页面权限关联表
DROP TABLE IF EXISTS role_pages;
CREATE TABLE role_pages(
    rid VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '角色ID',
    page_id BIGINT COLLATE utf8_bin NOT NULL COMMENT '页面ID',
    privilege VARCHAR(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '页面权限 0=只读 1=读写',
    PRIMARY KEY(rid, page_id),
    INDEX idx_rid (rid),
    INDEX idx_page_id (page_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色页面权限表';

-- ============================================
-- 页面和权限管理表
-- ============================================

-- 页面表
DROP TABLE IF EXISTS pages;
CREATE TABLE pages(
    page_id BIGINT COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '页面或目录ID',
    name VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '页面名称',
    classify VARCHAR(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '页面分类',
    sort_num VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '同层排序',
    path VARCHAR(100) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '路径',
    p_type VARCHAR(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '类型 0=目录 1=路由',
    descr VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '页面描述',
    hide VARCHAR(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '是否隐藏 0=显示 1=隐藏',
    parent_id BIGINT COLLATE utf8_bin NOT NULL DEFAULT 0 COMMENT '父级ID',
    icon VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '图标',
    PRIMARY KEY(page_id),
    INDEX idx_parent_id (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='页面表';

-- 页面URI表
DROP TABLE IF EXISTS pages_uri;
CREATE TABLE pages_uri(
    uri_id BIGINT COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '页面接口ID',
    page_id BIGINT COLLATE utf8_bin NOT NULL COMMENT '页面ID',
    uri VARCHAR(60) COLLATE utf8_bin NOT NULL COMMENT '接口地址',
    descr VARCHAR(64) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '接口描述',
    privilege VARCHAR(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '权限级别 0=只读 1=读写',
    PRIMARY KEY(uri_id),
    INDEX idx_page_id (page_id),
    INDEX idx_uri (uri)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='页面URI表';

-- ============================================
-- Syslog 日志管理表
-- ============================================

-- Syslog 黑名单表
DROP TABLE IF EXISTS syslog_black_list;
CREATE TABLE syslog_black_list(
    rule_id BIGINT COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '规则ID',
    pattern VARCHAR(300) COLLATE utf8_bin NOT NULL COMMENT '规则正则表达式',
    descr VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '规则描述',
    update_time VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '最近更新时间',
    PRIMARY KEY(rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Syslog黑名单规则表';

-- Syslog 合并规则表
DROP TABLE IF EXISTS syslog_merge_list;
CREATE TABLE syslog_merge_list(
    rule_id BIGINT COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '规则ID',
    group_name VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '分组名称',
    pattern VARCHAR(300) COLLATE utf8_bin NOT NULL COMMENT '规则正则表达式',
    descr VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '规则描述',
    update_time VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '最近更新时间',
    PRIMARY KEY(rule_id),
    INDEX idx_group_name (group_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Syslog合并规则表';

-- ============================================
-- 告警管理表
-- ============================================

-- 告警列表
DROP TABLE IF EXISTS alarm_list;
CREATE TABLE alarm_list(
    alarm_id BIGINT COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '告警ID',
    ip VARCHAR(300) COLLATE utf8_bin NOT NULL COMMENT '设备IP',
    hostname VARCHAR(300) COLLATE utf8_bin NOT NULL COMMENT '设备名称',
    alarm_type VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '告警分类：日志、指标、其他',
    group_label VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '分组标签hash',
    msg VARCHAR(500) COLLATE utf8_bin NOT NULL COMMENT '原始信息',
    group_name VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '分组名称',
    alarm_object VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '告警对象',
    keyword VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '关键字',
    status VARCHAR(1) COLLATE utf8_bin NOT NULL COMMENT '状态 0=待处理 1=已确认 2=已处理 3=忽略 4=屏蔽',
    create_time VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '创建时间',
    PRIMARY KEY(alarm_id),
    INDEX idx_ip (ip),
    INDEX idx_group_label (group_label),
    INDEX idx_status (status),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警列表';

-- 告警处理日志
DROP TABLE IF EXISTS alarm_log;
CREATE TABLE alarm_log(
    log_id BIGINT COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    group_label VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '分组标签hash',
    handler VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '处理人',
    msg VARCHAR(300) COLLATE utf8_bin NOT NULL COMMENT '处理内容',
    create_time VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '创建时间',
    PRIMARY KEY(log_id),
    INDEX idx_group_label (group_label),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警处理日志';


-- ipam网段管理
DROP TABLE IF EXISTS ipam_net;
CREATE TABLE ipam_net(
    ip varchar(128) COLLATE utf8_bin NOT NULL COMMENT '网络地址',
    mask varchar(4) COLLATE utf8_bin NOT NULL COMMENT '掩码',
    start_ip varchar(15) COLLATE utf8_bin NOT NULL COMMENT '开始IP',
    end_ip varchar(15) COLLATE utf8_bin NOT NULL COMMENT '结束IP',
    status varchar(2) COLLATE utf8_bin NOT NULL COMMENT '状态',
    location varchar(128) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '位置',
    isp varchar(20) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '运营商',
    role varchar(20) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '角色用途',
    label varchar(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '业务标签',
    comment varchar(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '描述',
    manage_user varchar(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '管理员',
    create_time varchar(15) COLLATE utf8_bin NULL COMMENT '创建时间',
    update_time varchar(15) COLLATE utf8_bin NULL COMMENT '更新时间',
    gateway varchar(20) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '网关',
    used_per varchar(10) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '使用率',
    primary key(ip, mask)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IP网段分配';

-- ipam使用记录
DROP TABLE IF EXISTS ipam_ipaddr;
CREATE TABLE ipam_ipaddr(
    ip_deci varchar(20) COLLATE utf8_bin NOT NULL COMMENT 'IP地址整型',
    ip_addr varchar(128) COLLATE utf8_bin NOT NULL COMMENT 'IP地址字符串',
    collect_type varchar(10) COLLATE utf8_bin NOT NULL COMMENT '采集来源/arp/ip/人工',
    admin_status varchar(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '管理状态',
    comment varchar(300) COLLATE utf8_bin NOT NULL COMMENT '描述',
    update_time varchar(15) COLLATE utf8_bin NULL COMMENT '更新时间',
    primary key(ip_deci)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='网段内实际使用地址';

-- ============================================
-- 拓扑管理表
-- ============================================

-- 拓扑数据表
DROP TABLE IF EXISTS topology_data;
CREATE TABLE topology_data (
    topology_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '拓扑ID',
    topology_name VARCHAR(100) NOT NULL COMMENT '拓扑名称',
    category_types JSON COMMENT '分类标签数组，如["按机房","IDC-A","核心网络"]',
    description TEXT COMMENT '描述',
    topology_json LONGTEXT NOT NULL COMMENT '拓扑JSON数据',
    created_by VARCHAR(50) COMMENT '创建人',
    created_at VARCHAR(20) COMMENT '创建时间',
    updated_by VARCHAR(50) COMMENT '最后修改人',
    updated_at VARCHAR(20) COMMENT '更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    UNIQUE KEY uk_name (topology_name),
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='拓扑数据表';

-- ============================================
-- 流量看板表
-- ============================================

-- 流量看板数据表
DROP TABLE IF EXISTS flow_data;
CREATE TABLE flow_data (
    flow_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '看板ID',
    flow_name VARCHAR(100) NOT NULL COMMENT '看板名称',
    category_types JSON COMMENT '分类标签数组，如["按机房","IDC-A","核心网络"]',
    description TEXT COMMENT '描述',
    flow_json LONGTEXT NOT NULL COMMENT '面板配置',
    created_by VARCHAR(50) COMMENT '创建人',
    created_at VARCHAR(20) COMMENT '创建时间',
    updated_by VARCHAR(50) COMMENT '最后修改人',
    updated_at VARCHAR(20) COMMENT '更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    UNIQUE KEY uk_name (flow_name),
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流量看板数据表';

-- ============================================
-- 设备配置备份表
-- ============================================

-- 设备配置备份表
DROP TABLE IF EXISTS dev_config;
CREATE TABLE dev_config (
    log_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT 'IP地址',
    sysname VARCHAR(300) COLLATE utf8_bin NULL COMMENT '设备名',
    dev_type VARCHAR(20) COLLATE utf8_bin NULL COMMENT '设备类型',
    detail LONGTEXT COLLATE utf8_bin NOT NULL COMMENT '配置内容',
    created_at VARCHAR(15) COLLATE utf8_bin NOT NULL COMMENT '创建时间(时间戳)',
    updated_at VARCHAR(15) COLLATE utf8_bin NOT NULL COMMENT '更新时间(时间戳)',
    change_id VARCHAR(50) COLLATE utf8_bin NULL COMMENT '变更单号',

    PRIMARY KEY (log_id),
    INDEX idx_ip (ip),
    INDEX idx_sysname (sysname),
    INDEX idx_change_id (change_id),
    INDEX idx_created_at (created_at),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='设备配置备份表';

-- ============================================
-- 变更工单管理表
-- ============================================

-- 工单类型表
DROP TABLE IF EXISTS op_types;
CREATE TABLE op_types (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '类型ID',
    name VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '类型名称',
    op_group1 BIGINT COLLATE utf8_bin NULL COMMENT '审批组1',
    op_group2 BIGINT COLLATE utf8_bin NULL COMMENT '审批组2',
    op_group3 BIGINT COLLATE utf8_bin NULL COMMENT '审批组3',
    PRIMARY KEY (pid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='工单类型配置表';

-- 审批分组表
DROP TABLE IF EXISTS op_groups;
CREATE TABLE op_groups (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '分组ID',
    name VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '分组名称',
    op_list TEXT COLLATE utf8_bin NULL COMMENT '成员列表(逗号分隔)',
    PRIMARY KEY (pid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='审批分组表';

-- 工单列表表
DROP TABLE IF EXISTS op_lists;
CREATE TABLE op_lists (
    op_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '工单ID',
    op_type BIGINT COLLATE utf8_bin NOT NULL COMMENT '工单类型ID',
    title VARCHAR(200) COLLATE utf8_bin NOT NULL COMMENT '工单标题',
    descrip TEXT COLLATE utf8_bin NULL COMMENT '工单描述',
    status VARCHAR(2) COLLATE utf8_bin NOT NULL DEFAULT '00' COMMENT '工单状态',
    username VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '创建人',
    assigner VARCHAR(40) COLLATE utf8_bin NULL COMMENT '指定执行人',
    is_auto TINYINT NULL DEFAULT 0 COMMENT '是否自动执行',
    popo VARCHAR(100) COLLATE utf8_bin NULL COMMENT '通知群组',
    create_time VARCHAR(10) COLLATE utf8_bin NULL COMMENT '创建时间',
    update_time VARCHAR(10) COLLATE utf8_bin NULL COMMENT '更新时间',
    begin_time VARCHAR(10) COLLATE utf8_bin NULL COMMENT '变更开始时间',
    finish_time VARCHAR(10) COLLATE utf8_bin NULL COMMENT '变更结束时间',
    cur_group TEXT COLLATE utf8_bin NULL COMMENT '当前审批组成员列表',
    cur_user VARCHAR(40) COLLATE utf8_bin NULL COMMENT '当前处理人',
    step_name VARCHAR(50) COLLATE utf8_bin NULL COMMENT '当前步骤名称',
    step_id INT NULL COMMENT '当前步骤ID',
    node_info TEXT COLLATE utf8_bin NULL COMMENT '流程节点信息(JSON)',
    PRIMARY KEY (op_id),
    INDEX idx_status (status),
    INDEX idx_username (username),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='工单列表表';

-- 设备命令表
DROP TABLE IF EXISTS op_devs;
CREATE TABLE op_devs (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    op_id BIGINT COLLATE utf8_bin NOT NULL COMMENT '工单ID',
    batch INT COLLATE utf8_bin NULL DEFAULT 1 COMMENT '批次号',
    ip VARCHAR(50) COLLATE utf8_bin NOT NULL COMMENT '设备IP',
    sysname VARCHAR(100) COLLATE utf8_bin NULL COMMENT '设备名称',
    model VARCHAR(100) COLLATE utf8_bin NULL COMMENT '设备型号',
    asset_no VARCHAR(200) COLLATE utf8_bin NULL COMMENT '资产编号',
    status VARCHAR(2) COLLATE utf8_bin NULL COMMENT '执行状态',
    cmd_exec TEXT COLLATE utf8_bin NULL COMMENT '执行命令',
    cmd_roll TEXT COLLATE utf8_bin NULL COMMENT '回滚命令',
    result TEXT COLLATE utf8_bin NULL COMMENT '执行结果',
    tag VARCHAR(50) COLLATE utf8_bin NULL COMMENT '标签',
    is_auto TINYINT NULL DEFAULT 0 COMMENT '是否自动执行',
    pre_check TEXT COLLATE utf8_bin NULL COMMENT '预检查结果',
    timestamp VARCHAR(10) COLLATE utf8_bin NULL COMMENT '时间戳',
    PRIMARY KEY (pid),
    INDEX idx_op_id (op_id),
    INDEX idx_batch (op_id, batch)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='设备命令执行表';

-- 审批记录表
DROP TABLE IF EXISTS op_approve;
CREATE TABLE op_approve (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    op_id BIGINT COLLATE utf8_bin NOT NULL COMMENT '工单ID',
    op_group BIGINT COLLATE utf8_bin NOT NULL COMMENT '审批分组ID',
    username VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '审批人',
    status VARCHAR(2) COLLATE utf8_bin NULL COMMENT '审批状态',
    timestamp VARCHAR(10) COLLATE utf8_bin NULL COMMENT '审批时间',
    PRIMARY KEY (pid),
    INDEX idx_op_id (op_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='审批记录表';

-- 操作日志表
DROP TABLE IF EXISTS op_logs;
CREATE TABLE op_logs (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    op_id BIGINT COLLATE utf8_bin NOT NULL COMMENT '工单ID',
    tag VARCHAR(2) COLLATE utf8_bin NULL COMMENT '日志标签',
    msg LONGTEXT COLLATE utf8_bin NOT NULL COMMENT '日志内容',
    username VARCHAR(40) COLLATE utf8_bin NULL COMMENT '操作人',
    timestamp VARCHAR(10) COLLATE utf8_bin NULL COMMENT '操作时间',
    PRIMARY KEY (pid),
    INDEX idx_op_id (op_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='操作日志表';

-- 通知群组表
DROP TABLE IF EXISTS op_notify;
CREATE TABLE op_notify (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    name VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '群组名称',
    descrip VARCHAR(200) COLLATE utf8_bin NULL COMMENT '描述',
    target VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '群组号',
    PRIMARY KEY (pid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin COMMENT='通知群组表';

-- ============================================
-- 数据库初始化完成
-- ============================================
