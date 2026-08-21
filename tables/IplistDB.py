from daos.database import mysqldb_netops
from utils.utils import waf
import time
import logging

logger = logging.getLogger(__name__)

'''
-- 设备IP清单表
CREATE TABLE IF NOT EXISTS iplist (
    ip VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT 'IP地址',
    sysname VARCHAR(300) COLLATE utf8_bin NOT NULL COMMENT '设备名称',
    community VARCHAR(100) COLLATE utf8_bin NOT NULL DEFAULT 'public' COMMENT 'SNMP Community',
    admin_status VARCHAR(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '管理状态 0=正常 1=屏蔽',
    timestamp VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '更新时间',
    PRIMARY KEY(ip),
    INDEX idx_admin_status (admin_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备IP清单表';
'''


class IplistDB(mysqldb_netops):
    """设备IP清单数据库操作类"""

    def getIpList(self, data):
        """
        获取设备IP清单列表
        :param data: 查询条件 {search, admin_status}
        :return: 列表数据或"failed"
        """
        data = waf(data)
        try:
            # 构建查询条件
            conditions = []

            # 搜索条件（IP或设备名称）
            if "search" in data.keys() and data["search"]:
                search_value = str(data["search"])
                conditions.append("(ip like '%" + search_value + "%' or sysname like '%" + search_value + "%')")

            # 管理状态筛选
            if "admin_status" in data.keys():
                conditions.append("admin_status='" + str(data["admin_status"]) + "'")

            # 构建SQL
            sql = "SELECT ip, sysname, community, admin_status, timestamp FROM iplist"
            if len(conditions) > 0:
                sql = sql + " WHERE " + " AND ".join(conditions)

            sql = sql + " ORDER BY ip ASC"

            # 执行查询
            proper = ["ip", "sysname", "community", "admin_status", "timestamp"]
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

        except Exception as err:
            logger.error("======IplistDB getIpList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def addIp(self, data):
        """
        添加设备IP（如果已存在则更新）
        :param data: 设备数据 {ip, sysname, community, admin_status, timestamp}
        :return: lastrowid或"failed"
        """
        try:
            check_params = ["ip", "sysname"]
            for i in check_params:
                if i not in data.keys():
                    logger.error("参数不足: {}".format(i))
                    return "failed"

            data = waf(data)
            sqlParam = []
            sqlParam.append((
                data["ip"],
                data["sysname"],
                data.get("community", "public"),
                data.get("admin_status", "0"),
                data.get("timestamp", str(int(time.time())))
            ))

            sql = """INSERT INTO iplist (ip, sysname, community, admin_status, timestamp)
                     VALUES (%s, %s, %s, %s, %s)
                     ON DUPLICATE KEY UPDATE
                     sysname = VALUES(sysname),
                     community = VALUES(community),
                     admin_status = VALUES(admin_status),
                     timestamp = VALUES(timestamp)"""

            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid

        except Exception as err:
            self.conn.rollback()
            logger.error("======IplistDB addIp error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateIp(self, data):
        """
        更新设备IP信息
        :param data: 设备数据 {ip, sysname, community, admin_status, timestamp}
        :return: "success"或"failed"
        """
        data = waf(data)
        if "ip" in data.keys():
            conditions = []
            params = []

            update_key = ["sysname", "community", "admin_status", "timestamp"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])

            if len(conditions) > 0:
                sql = "UPDATE iplist SET " + ",".join(conditions) + " WHERE ip='{}'".format(str(data["ip"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======IplistDB updateIp error========\n{}".format(str(err)))
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"

    def delIp(self, data):
        """
        删除设备IP
        :param data: {ip}
        :return: "success"或"failed"
        """
        data = waf(data)
        if "ip" in data.keys():
            sql = "DELETE FROM iplist WHERE ip='{}'".format(str(data["ip"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======IplistDB delIp error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def batchDelIp(self, data):
        """
        批量删除设备IP
        :param data: {ip_list: [ip1, ip2, ...]}
        :return: "success"或"failed"
        """
        data = waf(data)
        if "ip_list" in data.keys() and isinstance(data["ip_list"], list) and len(data["ip_list"]) > 0:
            ip_list = data["ip_list"]
            # 构建占位符
            placeholders = ",".join(["'{}'".format(str(ip)) for ip in ip_list])
            sql = "DELETE FROM iplist WHERE ip IN ({})".format(placeholders)
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======IplistDB batchDelIp error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def getIpByIp(self, data):
        """
        根据IP地址查询设备信息
        :param data: {ip}
        :return: 设备信息字典或"failed"
        """
        data = waf(data)
        if "ip" not in data.keys():
            return "failed"

        sql = "SELECT ip, sysname, community, admin_status, timestamp FROM iplist WHERE ip='{}'".format(str(data["ip"]))
        proper = ["ip", "sysname", "community", "admin_status", "timestamp"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchone()

            if result1:
                result = {}
                for num in range(len(proper)):
                    result[proper[num]] = result1[num] if result1[num] != None else ""
                return result
            else:
                return None

        except Exception as err:
            logger.error("======IplistDB getIpByIp error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def batchAddOrUpdateIp(self, data_list):
        """
        批量添加或更新设备IP（如果已存在则更新）
        :param data_list: 设备数据列表
        :return: "success"或"failed"
        """
        try:
            if not data_list or not isinstance(data_list, list):
                return "failed"

            sqlParam = []
            for data in data_list:
                data = waf(data)
                sqlParam.append((
                    data["ip"],
                    data["sysname"],
                    data.get("community", "vdiannet"),
                    data.get("admin_status", "0"),
                    data.get("timestamp", str(int(time.time())))
                ))

            sql = """INSERT INTO iplist (ip, sysname, community, admin_status, timestamp)
                     VALUES (%s, %s, %s, %s, %s)
                     ON DUPLICATE KEY UPDATE
                     sysname = VALUES(sysname),
                     community = VALUES(community),
                     admin_status = VALUES(admin_status),
                     timestamp = VALUES(timestamp)"""

            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return "success"

        except Exception as err:
            self.conn.rollback()
            logger.error("======IplistDB batchAddOrUpdateIp error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

        """
        获取所有状态为正常的设备IP列表
        :return: IP列表或"failed"
        """
        sql = "SELECT ip, sysname, community FROM iplist WHERE admin_status='0' ORDER BY ip"
        proper = ["ip", "sysname", "community"]
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

        except Exception as err:
            logger.error("======IplistDB getAllActiveIps error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

