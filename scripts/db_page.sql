-- MySQL dump 10.13  Distrib 8.0.46, for Linux (x86_64)
--
-- Host: 10.37.96.129    Database: netops
-- ------------------------------------------------------
-- Server version	8.0.33-25-20230707

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;
SET @@SESSION.SQL_LOG_BIN= 0;

--
-- GTID state at the beginning of the backup
--

SET @@GLOBAL.GTID_PURGED=/*!80000 '+'*/ 'ef0116fc-960f-11f1-9a44-02429149f30f:1-720121';

--
-- Table structure for table `pages`
--

DROP TABLE IF EXISTS `pages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pages` (
  `page_id` bigint NOT NULL AUTO_INCREMENT COMMENT '页面或目录ID',
  `name` varchar(40) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL COMMENT '页面名称',
  `classify` varchar(40) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '' COMMENT '页面分类',
  `sort_num` varchar(10) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '' COMMENT '同层排序',
  `path` varchar(100) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '' COMMENT '路径',
  `p_type` varchar(1) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '0' COMMENT '类型 0=目录 1=路由',
  `descr` varchar(300) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '' COMMENT '页面描述',
  `hide` varchar(1) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '0' COMMENT '是否隐藏 0=显示 1=隐藏',
  `parent_id` bigint NOT NULL DEFAULT '0' COMMENT '父级ID',
  `icon` varchar(40) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL COMMENT '图标',
  PRIMARY KEY (`page_id`),
  KEY `idx_parent_id` (`parent_id`)
) ENGINE=InnoDB AUTO_INCREMENT=48 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='页面表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pages`
--

LOCK TABLES `pages` WRITE;
/*!40000 ALTER TABLE `pages` DISABLE KEYS */;
INSERT INTO `pages` VALUES (9,'用户配置','系统管理','900','','0','系统管理','0',0,''),(10,'用户管理','','1','pages/systemManage/userManage','1','用户相关配置','0',9,''),(11,'页面管理','','5','pages/systemManage/pageManage','1','页面相关的配置','0',9,''),(12,'测试菜单','测试','903','','0','','0',0,''),(13,'测试1','','1','pages/demo/test2','1','','0',12,''),(14,'测试2','','2','pages/demo/test3','1','','0',12,''),(15,'测试3','','3','pages/demo/test4','1','','1',12,''),(18,'系统基本接口权限','系统管理','901','','0','','1',0,''),(26,'文本工具','实用工具','800','','0','','0',0,''),(27,'Markdown表格转换','','1','pages/tools/markdownTable','1','','0',26,''),(28,'文本对比','','2','pages/tools/textDiff','1','','0',26,''),(29,'JSON数据处理','','3','pages/tools/textJSON','1','','0',26,''),(30,'IP掩码计算','','4','pages/tools/ipmaskTranslate','1','','0',33,''),(31,'IP前缀融合','','5','pages/tools/ipPrefixMerge','1','','0',33,''),(32,'文本正则提取','','5','pages/tools/textRegExtract','1','','0',26,''),(33,'网工工具','实用工具','801','','0','','0',0,''),(34,'交换机脚本','','1','pages/tools/switchConfig','1','','0',33,''),(36,'图表工具','实用工具','802','','0','','0',0,''),(37,'地图工具','','1','pages/tools/map_tool','1','','0',36,''),(38,'词云工具','','2','pages/tools/wordcloud_tool','1','','0',36,''),(39,'告警中心','运维事务','200','','0','告警相关内容','0',0,''),(40,'当前告警','','1','pages/alarms/current_alarm','1','当前告警','0',39,''),(41,'规则配置','','5','pages/alarms/alarm_config','1','规则配置，黑名单以及聚合规则','0',39,''),(42,'主页','','0','pages/index','1','主页','1',0,''),(43,'历史告警','','2','pages/alarms/history_alarm','1','历史告警页面','0',39,''),(44,'设备定位','运维数据','100','pages/device/fmManage','1','','0',0,''),(45,'设备详情页','运维数据','199','pages/device/device_detail','1','设备详情页，不需要导航','1',0,''),(46,'设备数据查询','运维数据','110','pages/ops_data/ops_data_views','1','采集的数据信息','0',0,''),(47,'IPAM','运维数据','120','pages/ipam/address_manage','1','ipam管理','0',0,'');
/*!40000 ALTER TABLE `pages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pages_uri`
--

DROP TABLE IF EXISTS `pages_uri`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pages_uri` (
  `uri_id` bigint NOT NULL AUTO_INCREMENT COMMENT '页面接口ID',
  `page_id` bigint NOT NULL COMMENT '页面ID',
  `uri` varchar(60) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL COMMENT '接口地址',
  `descr` varchar(64) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '' COMMENT '接口描述',
  `privilege` varchar(1) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '0' COMMENT '权限级别 0=只读 1=读写',
  PRIMARY KEY (`uri_id`),
  KEY `idx_page_id` (`page_id`),
  KEY `idx_uri` (`uri`)
) ENGINE=InnoDB AUTO_INCREMENT=81 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='页面URI表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pages_uri`
--

LOCK TABLES `pages_uri` WRITE;
/*!40000 ALTER TABLE `pages_uri` DISABLE KEYS */;
INSERT INTO `pages_uri` VALUES (6,18,'/system/change_passwd','修改密码','0'),(7,18,'/system/login','登陆','0'),(8,18,'/system/getuser','获取当前用户信息','0'),(9,10,'/system/add_role','新增角色','1'),(10,10,'/system/update_role','修改角色','1'),(11,10,'/system/delete_role','删除角色','1'),(12,10,'/system/get_role_list','查询角色列表','0'),(13,10,'/system/add_user','添加用户','1'),(14,10,'/system/update_user','修改用户','1'),(15,10,'/system/delete_user','删除用户','1'),(16,10,'/system/get_user_list','查看用户列表','0'),(17,10,'/system/add_role_page','添加权限','1'),(18,10,'/system/add_role_page_list','批量添加权限','1'),(19,10,'/system/update_role_page','修改权限','1'),(20,10,'/system/delete_role_page','删除权限','1'),(21,10,'/system/get_role_page_list','查询权限','0'),(22,18,'/system/get_route_list','查询角色菜单','0'),(23,11,'/system/add_page','新增页面','1'),(24,11,'/system/update_page','修改页面','1'),(25,11,'/system/delete_page','删除页面','1'),(26,11,'/system/get_page_list','查询页面','0'),(27,11,'/system/add_uri','页面接口新增','1'),(28,11,'/system/update_uri','修改接口','1'),(29,11,'/system/delete_uri','删除接口','1'),(30,11,'/system/get_uri_list','查询接口','0'),(31,31,'/tools/check_diff','对比配置','0'),(32,31,'/tools/network_merge','前缀融合','0'),(33,28,'/tools/check_diff','文本对比','0'),(34,40,'/alarm/get_current_alarm','当前告警列表','0'),(35,40,'/alarm/get_alarm_by_group','告警详情','0'),(36,40,'/alarm/handle_alarm_by_group','处理告警','1'),(37,41,'/alarm/check_blacklist','检查黑名单效果','0'),(38,41,'/alarm/check_mergelist','检查聚合效果','0'),(39,41,'/alarm/add_blacklist','新增黑名单','1'),(40,41,'/alarm/del_blacklist','删除黑名单','1'),(41,41,'/alarm/update_blacklist','更新黑名单','1'),(42,41,'/alarm/get_blacklist','查看黑名单','0'),(43,41,'/alarm/add_mergelist','新增聚合规则','1'),(44,41,'/alarm/del_mergelist','删除聚合规则','1'),(45,41,'/alarm/update_mergelist','更新聚合规则','1'),(46,41,'/alarm/get_mergelist','查看聚合规则','0'),(47,40,'/alarm/get_log_by_group','导出告警','0'),(48,43,'/alarm/get_history_alarm','查询历史告警','0'),(49,43,'/alarm/get_log_by_group','导出告警','0'),(50,44,'/collector/getfullsearch','全局搜索设备信息','0'),(51,46,'/collector/getdeviceslist','获取设备列表','0'),(52,46,'/collector/getports_ex','获取端口列表','0'),(53,46,'/collector/gates_v4','获取v4地址','0'),(54,46,'/collector/gates_v6','获取v6地址','0'),(55,46,'/collector/getlldps','查询lldp','0'),(56,46,'/collector/getdevice_sn','查询设备sn','0'),(57,46,'/collector/getarp_list','查询arp列表','0'),(58,46,'/collector/get_torarp','查询mac地址表','0'),(59,45,'/collector/getdeviceslist','获取设备列表','0'),(60,45,'/collector/getports_ex','获取端口列表','0'),(61,45,'/collector/getlldps','获取lldp信息','0'),(62,45,'/command/dis_cur_interface','查看接口配置','0'),(63,45,'/command/dis_interface','查看接口状态','0'),(64,45,'/command/dis_transceiver','光衰查询','0'),(65,45,'/command/dis_logging','看设备日志','0'),(66,45,'/command/dis_arp','arp表','0'),(67,45,'/command/dis_routes','查路由表','0'),(68,45,'/command/dis_common','通用命令查询-模版形式','0'),(69,45,'/command/exec_dev_cmds','执行自定义命令','1'),(70,45,'/webssh/create_session','webssh创建会话','1'),(71,45,'/webssh/send_command','webssh发送命令','1'),(72,45,'/webssh/close_session','webssh关闭会话','1'),(73,45,'/collector/snmp_get','图表的查询snmp方法','0'),(74,47,'/ipam/add_address','新增网段','1'),(75,47,'/ipam/update_address','修改网段','1'),(76,47,'/ipam/del_address','删除网段','1'),(77,47,'/ipam/get_address_tree','获取网段树','0'),(78,47,'/ipam/get_ipam_address','获取网段下的IP地址','0'),(79,47,'/ipam/batch_add_ipaddr','新增保留的地址','1'),(80,47,'/ipam/del_ipam_address','删除保留地址','1');
/*!40000 ALTER TABLE `pages_uri` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `roles`
--

DROP TABLE IF EXISTS `roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles` (
  `rid` varchar(40) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL COMMENT '角色ID',
  `name` varchar(40) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL COMMENT '角色名',
  `descr` varchar(64) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '' COMMENT '角色描述',
  PRIMARY KEY (`rid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='角色表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `roles`
--

LOCK TABLES `roles` WRITE;
/*!40000 ALTER TABLE `roles` DISABLE KEYS */;
INSERT INTO `roles` VALUES ('admin','管理员','管理员权限，拥有大部分功能的访问权限'),('default','普通用户','普通用户权限，需要分配具体页面权限'),('system','系统管理员','系统最高权限，拥有所有功能的完全访问权限');
/*!40000 ALTER TABLE `roles` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `role_pages`
--

DROP TABLE IF EXISTS `role_pages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `role_pages` (
  `rid` varchar(40) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL COMMENT '角色ID',
  `page_id` bigint NOT NULL COMMENT '页面ID',
  `privilege` varchar(1) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '0' COMMENT '页面权限 0=只读 1=读写',
  PRIMARY KEY (`rid`,`page_id`),
  KEY `idx_rid` (`rid`),
  KEY `idx_page_id` (`page_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='角色页面权限表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `role_pages`
--

LOCK TABLES `role_pages` WRITE;
/*!40000 ALTER TABLE `role_pages` DISABLE KEYS */;
INSERT INTO `role_pages` VALUES ('default',18,'0'),('default',26,'0'),('default',27,'0'),('default',28,'0'),('default',29,'0'),('default',30,'0'),('default',31,'0'),('default',32,'0'),('default',33,'0'),('default',34,'0'),('default',36,'0'),('default',37,'0'),('default',38,'0'),('default',42,'0');
/*!40000 ALTER TABLE `role_pages` ENABLE KEYS */;
UNLOCK TABLES;
SET @@SESSION.SQL_LOG_BIN = @MYSQLDUMP_TEMP_LOG_BIN;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-20 16:35:10