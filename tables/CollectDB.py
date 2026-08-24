from daos.database import mysqldb_netops
from utils.utils import waf
from utils.ipaddr import ip2decimalism
import time
import logging

'''
-- 1. 设备基础信息表
CREATE TABLE IF NOT EXISTS devices (
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT 'ip地址',
    sysname VARCHAR(300) COLLATE utf8_bin NULL COMMENT '系统名',
    sysdesc TEXT COLLATE utf8_bin NULL COMMENT '系统描述',
    syscontact VARCHAR(300) COLLATE utf8_bin NULL COMMENT '公司',
    uptime VARCHAR(100) COLLATE utf8_bin NULL COMMENT '启动时间',
    hardware VARCHAR(100) COLLATE utf8_bin NULL COMMENT '硬件',
    features VARCHAR(100) COLLATE utf8_bin NULL COMMENT '版本',
    version VARCHAR(100) COLLATE utf8_bin NULL COMMENT '软件版本',
    sys_type VARCHAR(50) COLLATE utf8_bin NULL COMMENT '设备类型',
    timestamp VARCHAR(100) COLLATE utf8_bin NULL COMMENT '采集时间',
    PRIMARY KEY(ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备基础信息表';

-- 2. 端口状态信息表
CREATE TABLE IF NOT EXISTS ports (
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT 'ip地址',
    port_id INT COLLATE utf8_bin NOT NULL COMMENT '端口snmp-id',
    if_name VARCHAR(300) COLLATE utf8_bin NULL COMMENT '端口名称',
    mac_address VARCHAR(30) COLLATE utf8_bin NULL COMMENT '端口mac地址',
    speed VARCHAR(30) COLLATE utf8_bin NULL COMMENT '端口速度',
    admin_statu VARCHAR(30) COLLATE utf8_bin NULL COMMENT '端口管理状态',
    oper_statu VARCHAR(30) COLLATE utf8_bin NULL COMMENT '端口物理状态',
    alias VARCHAR(300) COLLATE utf8_bin NULL COMMENT '端口描述',
    timestamp VARCHAR(100) COLLATE utf8_bin NULL COMMENT '采集时间',
    PRIMARY KEY(ip, port_id),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='端口状态信息表';

-- 3. ARP表
CREATE TABLE IF NOT EXISTS arps (
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT 'ip地址',
    arp_mac VARCHAR(30) COLLATE utf8_bin NOT NULL COMMENT 'arp-mac地址',
    arp_ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT '设备ip地址',
    port_id INT COLLATE utf8_bin NULL COMMENT '逻辑端口id',
    timestamp VARCHAR(100) COLLATE utf8_bin NULL COMMENT '采集时间',
    PRIMARY KEY(ip, arp_mac, arp_ip),
    INDEX idx_arp_ip (arp_ip),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ARP表';

-- 4. MAC地址表
CREATE TABLE IF NOT EXISTS macs (
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT 'ip地址',
    vlan_id INT COLLATE utf8_bin NOT NULL COMMENT 'vlan_id',
    mac_address VARCHAR(30) COLLATE utf8_bin NOT NULL COMMENT 'mac地址',
    port_id INT COLLATE utf8_bin NULL COMMENT '转发端口id',
    timestamp VARCHAR(100) COLLATE utf8_bin NULL COMMENT '采集时间',
    PRIMARY KEY(ip, vlan_id, mac_address),
    INDEX idx_mac (mac_address),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='MAC地址表';

-- 5. IPv4网关表
CREATE TABLE IF NOT EXISTS gates (
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT '设备ip地址',
    gateway VARCHAR(30) COLLATE utf8_bin NOT NULL COMMENT '网关ip地址',
    port_id INT COLLATE utf8_bin NULL COMMENT '端口id',
    mask VARCHAR(64) COLLATE utf8_bin NULL COMMENT '子网掩码',
    startip INT UNSIGNED COLLATE utf8_bin NULL COMMENT '开始ip',
    endip INT UNSIGNED COLLATE utf8_bin NULL COMMENT '结束ip',
    timestamp VARCHAR(100) COLLATE utf8_bin NULL COMMENT '采集时间',
    PRIMARY KEY(ip, gateway),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IPv4网关表';

-- 6. IPv6网关表
CREATE TABLE IF NOT EXISTS gates_ipv6 (
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT '设备ip地址',
    gateway VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT '网关ipv6地址',
    port_id INT COLLATE utf8_bin NULL COMMENT '端口id',
    mask INT COLLATE utf8_bin NULL COMMENT '掩码长度',
    timestamp VARCHAR(100) COLLATE utf8_bin NULL COMMENT '采集时间',
    PRIMARY KEY(ip, gateway),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IPv6网关表';

-- 7. LLDP邻居信息表
CREATE TABLE IF NOT EXISTS lldps (
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT 'ip地址',
    port_id VARCHAR(30) COLLATE utf8_bin NOT NULL COMMENT '接口序号',
    rem_name VARCHAR(300) COLLATE utf8_bin NULL COMMENT '系统名',
    rem_portname VARCHAR(300) COLLATE utf8_bin NULL COMMENT '端口名称',
    timestamp VARCHAR(100) COLLATE utf8_bin NULL COMMENT '采集时间',
    rem_portalias VARCHAR(300) COLLATE utf8_bin NULL COMMENT '端口描述',
    loc_portname VARCHAR(300) COLLATE utf8_bin NULL COMMENT '本端端口名称',
    loc_portalias VARCHAR(300) COLLATE utf8_bin NULL COMMENT '本端端口描述',
    PRIMARY KEY(ip, port_id),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLDP邻居信息表';

-- 8. 路由表
CREATE TABLE IF NOT EXISTS routes (
    ip VARCHAR(32) COLLATE utf8_bin NOT NULL COMMENT '设备ip地址',
    dest VARCHAR(32) COLLATE utf8_bin NOT NULL COMMENT '目的地址',
    mask VARCHAR(32) COLLATE utf8_bin NOT NULL COMMENT '目的地址掩码',
    nexthop VARCHAR(32) COLLATE utf8_bin NOT NULL COMMENT '下一跳地址',
    nextindex VARCHAR(20) COLLATE utf8_bin NOT NULL COMMENT '下一跳端口ID',
    p_type VARCHAR(1) COLLATE utf8_bin NULL COMMENT '路由类型',
    proto VARCHAR(2) COLLATE utf8_bin NULL COMMENT '协议类型',
    metric BIGINT COLLATE utf8_bin NULL COMMENT '度量值',
    start_ip BIGINT COLLATE utf8_bin NULL COMMENT '开始IP',
    end_ip BIGINT COLLATE utf8_bin NULL COMMENT '结束IP',
    pool_len BIGINT COLLATE utf8_bin NULL COMMENT '匹配长度',
    timestamp VARCHAR(20) COLLATE utf8_bin NOT NULL COMMENT '采集时间',
    PRIMARY KEY(ip, dest, mask, nexthop),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='路由表';

-- 9. 设备序列号信息表
CREATE TABLE IF NOT EXISTS dev_sn (
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT 'ip地址',
    sn_id INT COLLATE utf8_bin NOT NULL COMMENT 'snmp id',
    sn_name VARCHAR(300) COLLATE utf8_bin NULL COMMENT '硬件名称',
    sn_desc VARCHAR(300) COLLATE utf8_bin NULL COMMENT '硬件描述',
    sn_number VARCHAR(300) COLLATE utf8_bin NULL COMMENT '序列号',
    sn_type INT COLLATE utf8_bin NOT NULL DEFAULT 0 COMMENT '类型',
    sn_ex VARCHAR(300) COLLATE utf8_bin NULL COMMENT '硬件扩展名称',
    timestamp VARCHAR(100) COLLATE utf8_bin NULL COMMENT '采集时间',
    PRIMARY KEY(ip, sn_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备序列号信息表';
'''

class CollectDB(mysqldb_netops):

    def getfulltextDeviceList(self, searchKey):
        searchKey = waf(searchKey)
        conditions = []
        if "ip" in searchKey.keys():
            for key in searchKey["ip"]:
                conditions.append("ip regexp'" + key.replace(".", "[.]") + "'")
        if "sysname" in searchKey.keys():
            for key in searchKey["sysname"]:
                conditions.append("sysname regexp'" + key.replace(".", "[.]") + "'")
        if "sysdesc" in searchKey.keys():
            for key in searchKey["sysdesc"]:
                conditions.append("sysdesc regexp'" + str(key) + "'")
        if "syscontact" in searchKey.keys():
            for key in searchKey["syscontact"]:
                conditions.append("syscontact regexp'" + str(key) + "'")

        sql = 'select ip,sysname,sysdesc,syscontact,uptime,hardware,features,version,timestamp from devices '
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + " limit 5 "

        proper = ["ip", "sysname", "sysdesc", "syscontact", "uptime", "hardware", "features", "version",
                  "timestamp"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("get full device List error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # 全文索引查找设备网关
    def getfulltextDeviceGates(self, searchKeys):
        searchKeys = waf(searchKeys)
        # searchKeys={"ip":"正则","gate":"过滤"}
        conditions = []
        if "ip" in searchKeys.keys():
            conditions.append("gates.ip regexp '" + searchKeys["ip"].replace(".", "[.]") + "'")
        if "gate" in searchKeys.keys():
            ip_int = ip2decimalism(searchKeys["gate"])
            if ip_int != 0:
                conditions.append("gates.startip<=" + str(ip_int) + " and gates.endip>=" + str(ip_int))
        if "gatereg" in searchKeys.keys():
            conditions.append("gates.gateway regexp '" + searchKeys["gatereg"].replace(".", "[.]") + "'")
        if "port_status" in searchKeys.keys():
            conditions.append("(ports.oper_statu <> 2 or ports.oper_statu is NULL)")
        if "sysname" in searchKeys.keys():
            conditions.append("devices.sysname regexp '" + searchKeys["sysname"] + "'")

        conditions.append(
            " ( ports.if_name <> 'igb0.0' and ports.if_name <> 'jsrv.1' and ports.if_name <> 'em0.0') ")

        sql = 'SELECT gates.ip,gates.gateway,ports.if_name,gates.mask,gates.startip,gates.endip,gates.timestamp,' \
              'ports.oper_statu,ports.port_id,devices.sysname,ports.alias ' \
              ' FROM gates ' \
              'left JOIN ports ON gates.ip=ports.ip AND gates.port_id=ports.port_id ' \
              'left JOIN devices ON gates.ip=devices.ip'
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        if "unlimit" in searchKeys.keys():
            pass
        else:
            sql = sql + " limit 5 "

        print("sql:", sql)
        proper = ["ip", "gateway", "if_name", "mask", "startip", "endip", "timestamp", "oper_statu","port_id", "sysname",
                  "alias"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("get full gate list error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # 全文索引查找设备网关v6
    def getfulltextDeviceGatesIPv6(self, searchKeys):
        searchKeys = waf(searchKeys)
        #searchKeys={"ip":"正则","gate":"过滤"}
        conditions = []
        if "ip" in searchKeys.keys():
            conditions.append("gates_ipv6.ip regexp '" + searchKeys["ip"].replace(".", "[.]") + "'")
        if "gatereg" in searchKeys.keys():
            conditions.append("gates_ipv6.gateway regexp '" + searchKeys["gatereg"].replace(".", "[.]") + "'")
        if "port_status" in searchKeys.keys():
            conditions.append("(ports.oper_statu <> 2 or ports.oper_statu is NULL)")
        sql = 'SELECT gates_ipv6.ip,gates_ipv6.gateway,ports.if_name,gates_ipv6.mask,gates_ipv6.timestamp,' \
              'ports.oper_statu,ports.port_id,devices.sysname,ports.alias ' \
              ' FROM gates_ipv6 ' \
              'left JOIN ports ON gates_ipv6.ip=ports.ip AND gates_ipv6.port_id=ports.port_id ' \
              'left JOIN devices ON gates_ipv6.ip=devices.ip'
        if len(conditions) > 0:
            if "and" in searchKeys.keys():
                sql = sql + " where " + " and ".join(conditions)
            else:
                sql = sql + " where " + " or ".join(conditions)

        if "unlimit" in searchKeys.keys():
            pass
        else:
            sql = sql + " limit 5 "

        proper = ["ip", "gateway", "if_name", "mask", "timestamp", "oper_statu", "port_id", "sysname", "alias"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("get full gate ipv6 list error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # 查询设备硬件信息，包含SN
    def getDeviceSNS(self, searchKeys):
        searchKeys = waf(searchKeys)
        #searchKeys={"ip":"正则","gate":"过滤"}
        conditions = []
        if "ip" in searchKeys.keys():
            conditions.append("ip regexp '" + searchKeys["ip"].replace(".", "[.]") + "'")
        if "sn_name" in searchKeys.keys():
            conditions.append("sn_name regexp '" + searchKeys["sn_name"].replace(".", "[.]") + "'")
        if "sn_desc" in searchKeys.keys():
            conditions.append("sn_desc regexp '" + searchKeys["sn_desc"].replace(".", "[.]") + "'")
        if "sn_number" in searchKeys.keys():
            conditions.append("sn_number regexp '" + searchKeys["sn_number"].replace(".", "[.]") + "'")
        if "sn_type" in searchKeys.keys():
            conditions.append("sn_type = '" + str(searchKeys["sn_type"]) + "'")

        sql = 'select t_sn.ip,devices.sysname,sn_id,sn_name,sn_desc,sn_number,t_sn.timestamp,sn_type from ' \
              '(select ip,sn_id,sn_name,sn_desc,sn_number,sn_type,timestamp from dev_sn '
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + ') t_sn join devices on t_sn.ip = devices.ip '
        if "limit" in searchKeys.keys():
            sql = sql + " limit 10"

        proper = ["ip", "sysname", "sn_id", "sn_name", "sn_desc", "sn_number", "timestamp", "sn_type"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("getSN error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


    # 查询端口信息
    def getPortInfo(self, searchKey):
        searchKey = waf(searchKey)
        conditions = []
        sql = '''select devices.sysname,ports.ip,ports.port_id,ports.if_name,ports.speed,ports.admin_statu,
        ports.oper_statu,ports.alias,ports.timestamp from ports join devices on devices.ip=ports.ip '''
        if "sysname" in searchKey.keys():
            keys = searchKey["sysname"].split(" ")
            for key in keys:
                if key != "":
                    conditions.append("devices.sysname regexp '" + key + "'")
        if "ip" in searchKey.keys():
            conditions.append("ports.ip regexp '" + searchKey["ip"].replace(".", "[.]") + "'")
        if "if_name" in searchKey.keys():
            conditions.append("ports.if_name regexp '" + searchKey["if_name"].replace(".", "[.]") + "'")
        if "port_id" in searchKey.keys():
            conditions.append("ports.port_id ='" + searchKey["port_id"] + "'")
        if "admin_statu" in searchKey.keys():
            conditions.append("ports.admin_statu = '" + searchKey["admin_statu"] + "'")
        if "oper_statu" in searchKey.keys():
            conditions.append("ports.oper_statu = '" + searchKey["oper_statu"] + "'")
        if "oper_statu_ex" in searchKey.keys():
            conditions.append("ports.oper_statu <> '" + searchKey["oper_statu_ex"] + "'")
        if "admin_statu_ex" in searchKey.keys():
            conditions.append("ports.admin_statu <> '" + searchKey["admin_statu_ex"] + "'")
        if "oper_statu_ex" in searchKey.keys():
            conditions.append("ports.oper_statu <> '" + searchKey["oper_statu_ex"] + "'")
        if "speed" in searchKey.keys():
            conditions.append("ports.speed regexp '" + searchKey["speed"] + "'")
        if "speed_ex" in searchKey.keys():
            conditions.append("ports.speed <> '0'")
        if "alias" in searchKey.keys():
            conditions.append("ports.alias regexp '" + searchKey["alias"].replace(".", "[.]") + "'")
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        else:
            return "more"
        if "limit" in searchKey.keys():
            sql = sql + " limit 20"

        proper = ["sysname", "ip", "port_id", "if_name", "speed", "admin_statu", "oper_statu", "alias", "timestamp"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("get port info error", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()



    def getfulltextDeviceARP(self, searchKey):
        searchKey = waf(searchKey)
        conditions = []
        if "arp_ip" in searchKey.keys():
            conditions.append("arp_ip regexp'" + searchKey["arp_ip"].replace(".", "[.]") + "'")
        if "arp_mac" in searchKey.keys():
            conditions.append("arp_mac regexp'" + searchKey["arp_mac"] + "'")

        sql = 'select t1.ip,t1.arp_mac,t1.arp_ip,t1.port_id,t1.timestamp,ports.if_name,devices.sysname from (select ip,arp_mac,arp_ip,port_id,timestamp from arps '
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + " limit 10) t1 left join ports on t1.ip=ports.ip and t1.port_id=ports.port_id left join devices on t1.ip=devices.ip;"

        proper = ["ip", "arp_mac", "arp_ip", "port_id", "timestamp", "if_name", "sysname"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("get full arp List error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getfulltextDeviceMAC(self, searchKey):
        searchKey = waf(searchKey)

        conditions = []
        if "arp_ip" in searchKey.keys():
            conditions.append("arp_ip ='" + searchKey["arp_ip"] + "'")
        if "arp_mac" in searchKey.keys():
            conditions.append("arp_mac ='" + searchKey["arp_mac"] + "'")

        sql = 'select t_mac.arp_ip,t_mac.arp_mac,macs.ip,devices.sysname,macs.vlan_id,macs.port_id,ports.if_name,ports.alias,' \
              'macs.timestamp from (select distinct arp_ip,arp_mac from arps '
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + ' limit 10) t_mac ' \
              'join macs on macs.mac_address=t_mac.arp_mac ' \
              'left join ports on macs.ip=ports.ip and macs.port_id=ports.port_id ' \
              'left join devices on devices.ip=macs.ip limit 10;'

        proper = ["arp_ip", "arp_mac", "ip", "sysname", "vlan_id", "port_id", "if_name", "if_alias", "timestamp"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("get full mac List error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


    # 查询LLDP信息
    def getLLDPs(self, searchKey):
        searchKey = waf(searchKey)
        conditions = []
        if "ip" in searchKey.keys():
            conditions.append("lldps.ip ='" + searchKey["ip"] + "'")
        if "loc_ip" in searchKey.keys():
            conditions.append("lldps.ip regexp'" + searchKey["loc_ip"] + "'")
        if "loc_portname" in searchKey.keys():
            conditions.append("loc_portname regexp'" + searchKey["loc_portname"] + "'")
        if "loc_sysname" in searchKey.keys():
            conditions.append("d1.sysname = '" + searchKey["loc_sysname"] + "'")
        if "rem_sysname" in searchKey.keys():
            conditions.append("rem_name = '" + searchKey["rem_sysname"] + "'")
        if "loc_name" in searchKey.keys():
            keys = searchKey["loc_name"].split(" ")
            for key in keys:
                if key != "":
                    conditions.append("d1.sysname regexp '" + key + "'")
        if "loc_alias" in searchKey.keys():
            conditions.append("loc_portalias regexp'" + searchKey["loc_alias"] + "'")
        if "rem_ip" in searchKey.keys():
            conditions.append("d2.ip regexp'" + searchKey["rem_ip"].replace(".", "[.]") + "'")
        if "rem_name" in searchKey.keys():
            keys = searchKey["rem_name"].split(" ")
            for key in keys:
                conditions.append("rem_name regexp '" + key + "'")
        if "rem_alias" in searchKey.keys():
            conditions.append("rem_portalias regexp'" + searchKey["rem_alias"] + "'")

        if "rem_portname" in searchKey.keys():
            conditions.append("rem_portname regexp'" + searchKey["rem_portname"] + "'")


        sql = '''select lldps.ip,d1.sysname,
        p1.port_id,p1.oper_statu,loc_portname,loc_portalias,
        d2.ip,rem_name,p2.port_id,p2.oper_statu,rem_portname,rem_portalias,lldps.timestamp from lldps
        left join devices d1 on d1.ip=lldps.ip
        left join devices d2 on d2.sysname=lldps.rem_name
        left join ports p1 on p1.if_name=lldps.loc_portname and p1.ip=lldps.ip
        left join ports p2 on p2.if_name=lldps.rem_portname and p2.ip=d2.ip'''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        else:
            return []
        if "limit" in searchKey.keys():
            sql = sql + " limit 8;"

        proper = ["loc_ip", "loc_name", "loc_portid", "loc_portstatus", "loc_portname", "loc_portalias",
                  "rem_ip", "rem_name","rem_portid","rem_portstatus","rem_portname","rem_portalias","timestamp"
                  ]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("getLLDP error", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # 查询设备列表信息
    def getDeviceList(self,searchKey):
        searchKey = waf(searchKey)
        conditions = []

        serach_reg_key = ["sysdesc", "hardware", "features", "version", "syscontact"]
        for key in serach_reg_key:
            if key in searchKey.keys():
                conditions.append(key + " regexp'" + str(searchKey[key]) + "'")
        if "host" in searchKey.keys():
            conditions.append("ip ='" + searchKey["host"] + "'")
        if "ip" in searchKey.keys():
            conditions.append("ip regexp'" + searchKey["ip"].replace(".", "[.]") + "'")
        if "sysname" in searchKey.keys():
            keys = searchKey["sysname"].split(" ")
            for key in keys:
                if key != "":
                    condition = "sysname regexp '"+key+"'"
                    conditions.append(condition)
        if "sysdesc_reg" in searchKey.keys():
            keys = searchKey["sysdesc_reg"].split(" ")
            for key in keys:
                if key != "":
                    condition = "sysdesc regexp '"+key+"'"
                    conditions.append(condition)

        sql = 'select ip,sysname,sysdesc,syscontact,uptime,hardware,features,version,timestamp from devices '
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)

        proper = ["ip", "sysname", "sysdesc", "syscontact", "uptime", "hardware",
                  "features", "version", "timestamp"
                  ]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("getList error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # 仅查询ARP信息
    def getARPList(self, searchKeys):
        searchKeys = waf(searchKeys)
        #searchKeys={"ip":"正则","gate":"过滤"}
        conditions = []
        if "ip" in searchKeys.keys():
            conditions.append("ip regexp '" + searchKeys["ip"].replace(".", "[.]") + "'")
        if "arp_ip" in searchKeys.keys():
            conditions.append("arp_ip regexp '" + searchKeys["arp_ip"].replace(".", "[.]") + "'")

        conditions1 = []
        if "if_name" in searchKeys.keys():
            conditions1.append("ports.if_name regexp '" + searchKeys["if_name"] + "'")
        if "sysname" in searchKeys.keys():
            conditions1.append("devices.sysname regexp '" + searchKeys["sysname"] + "'")


        sql = 'select t_arp.ip,devices.sysname,t_arp.arp_ip,t_arp.arp_mac,t_arp.port_id,ports.if_name,t_arp.timestamp from (select ip,arp_ip,arp_mac,port_id,timestamp from arps where '
        if len(conditions) > 0:
            sql += " and ".join(conditions)
        else:
            return []
        sql += ') t_arp left join devices on t_arp.ip=devices.ip left join ports on ports.port_id=t_arp.port_id and ports.ip=t_arp.ip '

        if len(conditions1) > 0:
            sql = sql + " where " + " and ".join(conditions1)

        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    result["ip"] = i[0] if i[0] != None else ""
                    result["sysname"] = i[1] if i[1] != None else ""
                    result["arp_ip"] = i[2] if i[2] != None else ""
                    result["arp_mac"] = i[3] if i[3] != None else ""
                    result["port_id"] = i[4] if i[4] != None else ""
                    result["if_name"] = i[5] if i[5] != None else ""
                    result["timestamp"] = i[6] if i[6] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("getFailureType", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


    # 通过交换机查询下联设备ARP
    def getSwitchArpByDevIP(self, searchKey):
        searchKey = waf(searchKey)

        if "switch_ip" in searchKey.keys():
            sql = '''select t_mac.ip,devices.sysname,t_mac.vlan_id,t_mac.mac_address,arps.arp_ip,t_mac.port_id,ports.if_name,t_mac.timestamp from 
            (select ip,vlan_id,mac_address,port_id,timestamp from macs where ip="{}") t_mac 
            join arps on arps.arp_mac=t_mac.mac_address 
            join ports on ports.ip=t_mac.ip and ports.port_id=t_mac.port_id 
            left join devices on devices.ip=t_mac.ip ;
            '''.format(searchKey["switch_ip"])
        else:
            return "failed"
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    result["ip"] = i[0] if i[0] != None else ""
                    result["sysname"] = i[1] if i[1] != None else ""
                    result["vlan_id"] = i[2] if i[2] != None else ""
                    result["mac_address"] = i[3] if i[3] != None else ""
                    result["arp_ip"] = i[4] if i[4] != None else ""
                    result["port_id"] = i[5] if i[5] != None else ""
                    result["if_name"] = i[6] if i[6] != None else ""
                    result["timestamp"] = i[7] if i[7] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("get mac List error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_gate_v4_list(self, searchKey):
        """
        获取IPv4网关列表
        用于IPAM地址更新任务
        """
        searchKey = waf(searchKey)
        sql = 'SELECT ip, gateway, port_id, mask, startip, endip, timestamp FROM gates'

        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    result["ip"] = i[0] if i[0] != None else ""
                    result["gateway"] = i[1] if i[1] != None else ""
                    result["port_id"] = i[2] if i[2] != None else ""
                    result["mask"] = i[3] if i[3] != None else ""
                    result["startip"] = i[4] if i[4] != None else ""
                    result["endip"] = i[5] if i[5] != None else ""
                    result["timestamp"] = i[6] if i[6] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("get gate v4 list error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_arp_list(self, searchKey):
        """
        获取ARP列表
        用于IPAM地址更新任务
        """
        searchKey = waf(searchKey)
        sql = 'SELECT ip, arp_mac, arp_ip, port_id, timestamp FROM arps'

        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    result["ip"] = i[0] if i[0] != None else ""
                    result["arp_mac"] = i[1] if i[1] != None else ""
                    result["arp_ip"] = i[2] if i[2] != None else ""
                    result["port_id"] = i[3] if i[3] != None else ""
                    result["timestamp"] = i[4] if i[4] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as e:
            print("get arp list error=", e)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


if __name__ == '__main__':
    pass