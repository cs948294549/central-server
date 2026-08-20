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
-- 默认密码: 123456 (需要根据实际登录算法计算 identify)
-- 登录签名计算: md5(username + identify + "netops" + timestamp)
INSERT INTO users (username, identify, subname, phone, mail, rid, update_time, last_login) VALUES
('admin', 'b2fd3bace4778f19918ffbf7a42bb4b8', '系统管理员', '', 'admin@example.com', 'system', UNIX_TIMESTAMP(), '0');

-- 插入页面数据（分两步：先插入父级页面，再插入子页面）
-- 第一步：插入所有父级页面（parent_id = 0）
INSERT INTO pages (page_id, name, classify, sort_num, path, p_type, descr, hide, parent_id, icon) VALUES
(9, '用户配置', '系统管理', '900', '', '0', '系统管理', '0', 0, ''),
(12, '测试菜单', '分组1', '100', '', '0', '', '0', 0, ''),
(18, '系统基本接口权限', '系统管理', '901', '', '0', '', '1', 0, ''),
(19, '测试页面', '测试专用', '800', '', '0', '测试功能', '0', 0, ''),
(26, '文本工具', '实用工具', '800', '', '0', '', '0', 0, ''),
(33, '网工工具', '实用工具', '801', '', '0', '', '0', 0, ''),
(36, '图表工具', '实用工具', '802', '', '0', '', '0', 0, ''),
(39, '告警中心', '运维事务', '100', '', '0', '告警相关内容', '0', 0, ''),
(42, '主页', '', '0', 'pages/index', '1', '主页', '1', 0, '');

-- 第二步：插入所有子页面（parent_id != 0）
INSERT INTO pages (page_id, name, classify, sort_num, path, p_type, descr, hide, parent_id, icon) VALUES
-- 用户配置子页面
(10, '用户管理', '', '1', 'pages/systemManage/userManage', '1', '用户相关配置', '0', 9, ''),
(11, '页面管理', '', '5', 'pages/systemManage/pageManage', '1', '页面相关的配置', '0', 9, ''),
-- 测试菜单子页面
(13, '测试1', '', '1', 'pages/test2', '1', '', '0', 12, ''),
(14, '测试2', '', '2', 'pages/test3', '1', '', '0', 12, ''),
(15, '测试3', '', '3', 'pages/test4', '1', '', '1', 12, ''),
-- 测试页面子页面
(20, '拖动组件', '', '01', 'pages/demo/drag/dragParent', '1', '', '0', 19, ''),
(21, 'G6流程图', '', '04', 'pages/demo/workflow/g6_flow', '1', '', '0', 19, ''),
(22, '图片框选', '', '05', 'pages/demo/images/test6', '1', '', '0', 19, ''),
(23, 'WebSocket测试', '', '02', 'pages/demo/websocket/test1', '1', '', '0', 19, ''),
(24, '词云测试', '', '03', 'pages/demo/wordcloud/word_main', '1', '', '0', 19, ''),
(25, 'antv图测试', '', '06', 'pages/demo/antvg2/test2', '1', '', '0', 19, ''),
(35, '测试页面', '', '10', 'pages/demo/common_test', '1', '', '0', 19, ''),
-- 文本工具子页面
(27, 'Markdown表格转换', '', '1', 'pages/tools/markdownTable', '1', '', '0', 26, ''),
(28, '文本对比', '', '2', 'pages/tools/textDiff', '1', '', '0', 26, ''),
(29, 'JSON数据处理', '', '3', 'pages/tools/textJSON', '1', '', '0', 26, ''),
(32, '文本正则提取', '', '5', 'pages/tools/textRegExtract', '1', '', '0', 26, ''),
-- 网工工具子页面
(30, 'IP掩码计算', '', '4', 'pages/tools/ipmaskTranslate', '1', '', '0', 33, ''),
(31, 'IP前缀融合', '', '5', 'pages/tools/ipPrefixMerge', '1', '', '0', 33, ''),
(34, '交换机脚本', '', '1', 'pages/tools/switchConfig', '1', '', '0', 33, ''),
-- 图表工具子页面
(37, '地图工具', '', '1', 'pages/tools/map_tool', '1', '', '0', 36, ''),
(38, '词云工具', '', '2', 'pages/tools/wordcloud_tool', '1', '', '0', 36, ''),
-- 告警中心子页面
(40, '当前告警', '', '1', 'pages/alarms/current_alarm', '1', '当前告警', '0', 39, ''),
(41, '规则配置', '', '5', 'pages/alarms/alarm_config', '1', '规则配置，黑名单以及聚合规则', '0', 39, ''),
(43, '历史告警', '', '2', 'pages/alarms/history_alarm', '1', '历史告警页面', '0', 39, '');

-- 插入页面 URI（API 接口权限配置）
-- privilege: 0=只读 1=读写
INSERT INTO pages_uri (uri_id, page_id, uri, descr, privilege) VALUES
-- 系统基本接口权限（page_id=18）
(6, 18, '/system/change_passwd', '修改密码', '0'),
(7, 18, '/system/login', '登陆', '0'),
(8, 18, '/system/getuser', '获取当前用户信息', '0'),
(22, 18, '/system/get_route_list', '查询角色菜单', '0'),
-- 用户管理（page_id=10）
(9, 10, '/system/add_role', '新增角色', '1'),
(10, 10, '/system/update_role', '修改角色', '1'),
(11, 10, '/system/delete_role', '删除角色', '1'),
(12, 10, '/system/get_role_list', '查询角色列表', '0'),
(13, 10, '/system/add_user', '添加用户', '1'),
(14, 10, '/system/update_user', '修改用户', '1'),
(15, 10, '/system/delete_user', '删除用户', '1'),
(16, 10, '/system/get_user_list', '查看用户列表', '0'),
(17, 10, '/system/add_role_page', '添加权限', '1'),
(18, 10, '/system/add_role_page_list', '批量添加权限', '1'),
(19, 10, '/system/update_role_page', '修改权限', '1'),
(20, 10, '/system/delete_role_page', '删除权限', '1'),
(21, 10, '/system/get_role_page_list', '查询权限', '0'),
-- 页面管理（page_id=11）
(23, 11, '/system/add_page', '新增页面', '1'),
(24, 11, '/system/update_page', '修改页面', '1'),
(25, 11, '/system/delete_page', '删除页面', '1'),
(26, 11, '/system/get_page_list', '查询页面', '0'),
(27, 11, '/system/add_uri', '页面接口新增', '1'),
(28, 11, '/system/update_uri', '修改接口', '1'),
(29, 11, '/system/delete_uri', '删除接口', '1'),
(30, 11, '/system/get_uri_list', '查询接口', '0'),
-- 文本对比（page_id=28）
(33, 28, '/tools/check_diff', '文本对比', '0'),
-- IP前缀融合（page_id=31）
(31, 31, '/tools/check_diff', '对比配置', '0'),
(32, 31, '/tools/network_merge', '前缀融合', '0'),
-- 当前告警（page_id=40）
(34, 40, '/alarm/get_current_alarm', '当前告警列表', '0'),
(35, 40, '/alarm/get_alarm_by_group', '告警详情', '0'),
(36, 40, '/alarm/handle_alarm_by_group', '处理告警', '1'),
(47, 40, '/alarm/get_log_by_group', '导出告警', '0'),
-- 规则配置（page_id=41）
(37, 41, '/alarm/check_blacklist', '检查黑名单效果', '0'),
(38, 41, '/alarm/check_mergelist', '检查聚合效果', '0'),
(39, 41, '/alarm/add_blacklist', '新增黑名单', '1'),
(40, 41, '/alarm/del_blacklist', '删除黑名单', '1'),
(41, 41, '/alarm/update_blacklist', '更新黑名单', '1'),
(42, 41, '/alarm/get_blacklist', '查看黑名单', '0'),
(43, 41, '/alarm/add_mergelist', '新增聚合规则', '1'),
(44, 41, '/alarm/del_mergelist', '删除聚合规则', '1'),
(45, 41, '/alarm/update_mergelist', '更新聚合规则', '1'),
(46, 41, '/alarm/get_mergelist', '查看聚合规则', '0'),
-- 历史告警（page_id=43）
(48, 43, '/alarm/get_history_alarm', '查询历史告警', '0'),
(49, 43, '/alarm/get_log_by_group', '导出告警', '0');

-- 注意：
-- 1. identify 字段说明：
--    - Web 用户：存储密码 hash（如上面的示例）
--    - API 用户：存储随机 secret 字符串
-- 2. API 用户示例（可选）：
--    INSERT INTO users (username, identify, subname, rid, update_time, last_login) VALUES
--    ('collector_service', 'random_secret_string_here', '数据采集服务', 'system', UNIX_TIMESTAMP(), '0');



-- 查看创建的表
SHOW TABLES;

-- 验证数据
SELECT 'Roles:' as info;
SELECT * FROM roles;

SELECT 'Users:' as info;
SELECT username, subname, rid FROM users;