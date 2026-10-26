from daos.database import mysqldb_netops
from utils.utils import waf, unwaf
import time
import logging
import hashlib

logger = logging.getLogger(__name__)

'''
-- 设备配置表
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
);
'''


class ConfigDB(mysqldb_netops):
    """设备配置数据库操作类"""

    def add_config(self, data):
        """添加配置记录"""
        try:
            data = waf(data)
            timestamp = str(int(time.time()))

            sql = '''INSERT INTO dev_config
                     (ip, sysname, dev_type, detail, created_at, updated_at, change_id)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)'''
            params = (
                data["ip"],
                data.get("sysname", ""),
                data.get("dev_type", ""),
                data["detail"],
                timestamp,
                timestamp,
                data.get("change_id")
            )
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"添加配置记录失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def update_config_time(self, log_id):
        """更新配置记录的更新时间"""
        try:
            timestamp = str(int(time.time()))
            sql = "UPDATE dev_config SET updated_at = %s WHERE log_id = %s"
            self.cursor.execute(sql, (timestamp, log_id))
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"更新配置时间失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_config(self, log_id):
        """删除配置记录"""
        try:
            sql = "DELETE FROM dev_config WHERE log_id = %s"
            self.cursor.execute(sql, (log_id,))
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"删除配置记录失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_latest_config(self, ip):
        """获取设备最新的配置记录"""
        try:
            sql = '''SELECT log_id, ip, sysname, dev_type, detail, created_at, updated_at, change_id
                     FROM dev_config
                     WHERE ip = %s
                     ORDER BY created_at DESC
                     LIMIT 1'''

            proper = ["log_id", "ip", "sysname", "dev_type", "detail", "created_at", "updated_at", "change_id"]
            self.cursor.execute(sql, (ip,))
            result1 = self.cursor.fetchone()

            if result1:
                result = {}
                for num in range(len(proper)):
                    result[proper[num]] = result1[num] if result1[num] != None else ""
                result["detail"] = unwaf(result["detail"])
                return result
            return None
        except Exception as err:
            logger.error("======ConfigDB get_latest_config error========\n{}".format(str(err)))
            return None
        finally:
            self.cursor.close()
            self.conn.close()

    def get_config_list(self, data):
        """查询配置记录列表"""
        try:
            data = waf(data)
            conditions = []
            params = []

            # 精确匹配
            if "ip" in data:
                conditions.append("ip = %s")
                params.append(data["ip"])
            if "change_id" in data:
                conditions.append("change_id = %s")
                params.append(data["change_id"])

            # 模糊匹配
            if "sysname" in data:
                conditions.append("sysname REGEXP %s")
                params.append(data["sysname"])

            # 时间范围
            if "start_time" in data:
                conditions.append("created_at >= %s")
                params.append(data["start_time"])
            if "end_time" in data:
                conditions.append("created_at <= %s")
                params.append(data["end_time"])

            sql = """SELECT log_id, ip, sysname, dev_type, created_at, updated_at, change_id
                     FROM dev_config"""
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY created_at DESC"

            proper = ["log_id", "ip", "sysname", "dev_type", "created_at", "updated_at", "change_id"]
            self.cursor.execute(sql, params)
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
            logger.error("======ConfigDB get_config_list error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_latest_changed_devices(self, days=None):
        """
        获取最近发生过配置变更的设备列表，返回字段与 CollectDB.getDeviceList 保持一致

        判定依据：每个IP只取最新一条配置记录，若该记录的 created_at 与 updated_at 相同，
        说明这条记录是新采集后插入的（配置有变化）；
        若不相同，说明配置无变化、只是对原记录执行了 update_config_time。

        :param days: 仅统计最近多少天内的变更，None 表示不限时间
        :return: list，失败返回 "failed"
        """
        try:
            sql = '''SELECT d.ip, d.sysname, d.sysdesc, d.syscontact, d.uptime, d.hardware,
                            d.features, d.version, d.sys_type, d.vendor, d.timestamp
                     FROM devices d
                     INNER JOIN dev_config c ON c.ip = d.ip
                     INNER JOIN (
                         SELECT ip, MAX(log_id) AS log_id
                         FROM dev_config
                         GROUP BY ip
                     ) t ON c.log_id = t.log_id
                     WHERE c.created_at = c.updated_at'''
            params = []

            if days:
                sql += " AND CAST(c.created_at AS UNSIGNED) >= %s"
                params.append(int(time.time()) - int(days) * 86400)

            sql += " ORDER BY CAST(c.created_at AS UNSIGNED) DESC"

            proper = ["ip", "sysname", "sysdesc", "syscontact", "uptime", "hardware",
                      "features", "version", "sys_type", "vendor", "timestamp"]
            self.cursor.execute(sql, params)
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
            logger.error("======ConfigDB get_latest_changed_devices error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_config_detail(self, log_id):
        """获取配置详情（包含完整配置内容）"""
        try:
            sql = '''SELECT log_id, ip, sysname, dev_type, detail, created_at, updated_at, change_id
                     FROM dev_config
                     WHERE log_id = %s'''

            proper = ["log_id", "ip", "sysname", "dev_type", "detail", "created_at", "updated_at", "change_id"]
            self.cursor.execute(sql, (log_id,))
            result1 = self.cursor.fetchone()

            if result1:
                result = {}
                for num in range(len(proper)):
                    result[proper[num]] = result1[num] if result1[num] != None else ""
                result["detail"] = unwaf(result["detail"])
                return result
            return None
        except Exception as err:
            logger.error("======ConfigDB get_config_detail error========\n{}".format(str(err)))
            return None
        finally:
            self.cursor.close()
            self.conn.close()

    @staticmethod
    def calculate_config_hash(config_content):
        """计算配置内容的MD5哈希值"""
        return hashlib.md5(config_content.encode('utf-8')).hexdigest()
