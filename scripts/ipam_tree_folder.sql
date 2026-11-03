-- ============================================
-- IPAM 网段树自定义文件夹（仅用于树形展示，不影响 ipam_net）
-- 验证无误后再合并到 db_create.sql / db_page.sql
-- ============================================

-- 文件夹
CREATE TABLE IF NOT EXISTS ipam_tree_folder(
    id int NOT NULL AUTO_INCREMENT COMMENT '文件夹ID',
    name varchar(64) COLLATE utf8_bin NOT NULL COMMENT '文件夹名称',
    sort int NOT NULL DEFAULT 0 COMMENT '排序，越小越靠前',
    comment varchar(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '描述',
    create_time varchar(15) COLLATE utf8_bin NULL COMMENT '创建时间',
    update_time varchar(15) COLLATE utf8_bin NULL COMMENT '更新时间',
    primary key(id),
    unique key uk_name(name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IP网段树文件夹';

-- 文件夹成员（一个网段只能属于一个文件夹，仅最外层网段生效）
CREATE TABLE IF NOT EXISTS ipam_tree_folder_member(
    ip varchar(128) COLLATE utf8_bin NOT NULL COMMENT '网络地址，对应 ipam_net.ip',
    mask varchar(4) COLLATE utf8_bin NOT NULL COMMENT '掩码，对应 ipam_net.mask',
    folder_id int NOT NULL COMMENT '文件夹ID',
    update_time varchar(15) COLLATE utf8_bin NULL COMMENT '更新时间',
    primary key(ip, mask),
    key idx_folder(folder_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IP网段树文件夹成员';

-- 接口权限（page_id=47 为 IP地址管理页面，uri_id 走自增）
INSERT INTO pages_uri (page_id, uri, descr, privilege) VALUES
(47, '/ipam/folder/list', '查询网段文件夹', '0'),
(47, '/ipam/folder/add', '新增网段文件夹', '1'),
(47, '/ipam/folder/update', '修改网段文件夹', '1'),
(47, '/ipam/folder/delete', '删除网段文件夹', '1'),
(47, '/ipam/folder/move', '网段移入/移出文件夹', '1');
