USE netops;
-- ============================================
-- 初始数据
-- ============================================

-- 插入默认角色
INSERT INTO roles (rid, name, descr) VALUES
('system', '系统管理员', '系统最高权限，拥有所有功能的完全访问权限'),
('admin', '管理员', '管理员权限，拥有大部分功能的访问权限'),
('default', '普通用户', '普通用户权限，需要分配具体页面权限');

-- 插入默认管理员用户
-- 默认密码: 123456 (b2fd3bace4778f19918ffbf7a42bb4b8 前端包含hash计算得出的结果，不要修改，这个对应的123456)
INSERT INTO users (username, identify, subname, phone, mail, rid, update_time, last_login) VALUES
('admin', 'b2fd3bace4778f19918ffbf7a42bb4b8', '系统管理员', '', 'admin@example.com', 'system', UNIX_TIMESTAMP(), '0');


-- 查看创建的表
SHOW TABLES;

-- 验证数据
SELECT 'Roles:' as info;
SELECT * FROM roles;

SELECT 'Users:' as info;
SELECT username, subname, rid FROM users;