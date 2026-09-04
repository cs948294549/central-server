from daos.database import mysqldb_netops
from utils.utils import waf
from utils.ipaddr import ip2decimalism, decimalism2ip, length2netmask, getstartend
import time
import logging

logger = logging.getLogger(__name__)

'''
-- IPAM 网络地址管理表
CREATE TABLE ipam_net(
    ip VARCHAR(128) COLLATE utf8_bin NOT NULL COMMENT '网络地址',
    mask VARCHAR(4) COLLATE utf8_bin NOT NULL COMMENT '掩码',
    start_ip VARCHAR(15) COLLATE utf8_bin NOT NULL COMMENT '开始IP',
    end_ip VARCHAR(15) COLLATE utf8_bin NOT NULL COMMENT '结束IP',
    status VARCHAR(2) COLLATE utf8_bin NOT NULL COMMENT '状态',
    location VARCHAR(128) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '位置',
    isp VARCHAR(20) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '运营商',
    role VARCHAR(20) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '角色用途',
    label VARCHAR(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '业务标签',
    comment VARCHAR(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '描述',
    manage_user VARCHAR(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '管理员',
    create_time VARCHAR(15) COLLATE utf8_bin NULL COMMENT '创建时间',
    update_time VARCHAR(15) COLLATE utf8_bin NULL COMMENT '更新时间',
    gateway VARCHAR(20) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '网关',
    used_per VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '使用率',
    PRIMARY KEY(ip, mask)
);

-- IPAM IP地址管理表
CREATE TABLE ipam_ipaddr(
    ip_deci VARCHAR(20) COLLATE utf8_bin NOT NULL COMMENT 'IP地址整型',
    ip_addr VARCHAR(128) COLLATE utf8_bin NOT NULL COMMENT 'IP地址字符串',
    collect_type VARCHAR(10) COLLATE utf8_bin NOT NULL COMMENT '采集来源/arp/ip/人工',
    admin_status VARCHAR(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '管理状态',
    comment VARCHAR(300) COLLATE utf8_bin NOT NULL COMMENT '描述',
    update_time VARCHAR(15) COLLATE utf8_bin NULL COMMENT '更新时间',
    PRIMARY KEY(ip_deci)
);
'''


class IpamDB(mysqldb_netops):
    """IPAM 数据库操作类"""

    # ==================== 网络地址管理 ====================

    def add_network_item(self, data):
        """添加网络地址记录"""
        try:
            data = waf(data)

            # 计算起始和结束IP（仅对IPv4）
            if ":" not in data["ip"]:
                start_ip, end_ip = getstartend(data["ip"], length2netmask(int(data["mask"])))
                data["start_ip"] = str(start_ip)
                data["end_ip"] = str(end_ip)
                data["ip"] = decimalism2ip(start_ip)
            else:
                data["start_ip"] = "0"
                data["end_ip"] = "0"

            timestamp = str(int(time.time()))
            sql = '''INSERT INTO ipam_net
                     (ip, mask, start_ip, end_ip, status, location, isp, role, label,
                      comment, manage_user, create_time, update_time, gateway, used_per)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
            params = (
                data["ip"],
                data["mask"],
                data["start_ip"],
                data["end_ip"],
                data.get("status", "1"),
                data.get("location", ""),
                data.get("isp", ""),
                data.get("role", ""),
                data.get("label", ""),
                data.get("comment", ""),
                data.get("manage_user", ""),
                timestamp,
                timestamp,
                data.get("gateway", ""),
                data.get("used_per", "0")
            )
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"添加网络地址记录失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def add_network_batch(self, data_list):
        """批量添加网络地址记录（带事务支持，全部成功或全部失败）"""
        try:
            if not isinstance(data_list, list) or len(data_list) == 0:
                return {
                    "status": "failed",
                    "message": "数据列表为空或格式错误",
                    "success_count": 0,
                    "failed_count": 0,
                    "failed_items": []
                }

            timestamp = str(int(time.time()))
            sql = '''INSERT INTO ipam_net
                     (ip, mask, start_ip, end_ip, status, location, isp, role, label,
                      comment, manage_user, create_time, update_time, gateway, used_per)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''

            params_list = []
            failed_items = []

            # 预处理所有数据
            for item in data_list:
                try:
                    data = waf(item)

                    # 验证必需字段
                    if "ip" not in data or "mask" not in data:
                        failed_items.append({
                            "ip": data.get("ip", "未知"),
                            "mask": data.get("mask", "未知"),
                            "error": "缺少必需字段: ip 或 mask"
                        })
                        continue

                    # 计算起始和结束IP（仅对IPv4）
                    if ":" not in data["ip"]:
                        start_ip, end_ip = getstartend(data["ip"], length2netmask(int(data["mask"])))
                        data["start_ip"] = str(start_ip)
                        data["end_ip"] = str(end_ip)
                        data["ip"] = decimalism2ip(start_ip)
                    else:
                        data["start_ip"] = "0"
                        data["end_ip"] = "0"

                    params = (
                        data["ip"],
                        data["mask"],
                        data["start_ip"],
                        data["end_ip"],
                        data.get("status", "1"),
                        data.get("location", ""),
                        data.get("isp", ""),
                        data.get("role", ""),
                        data.get("label", ""),
                        data.get("comment", ""),
                        data.get("manage_user", ""),
                        timestamp,
                        timestamp,
                        data.get("gateway", ""),
                        data.get("used_per", "0")
                    )
                    params_list.append(params)

                except Exception as e:
                    failed_items.append({
                        "ip": item.get("ip", "未知"),
                        "mask": item.get("mask", "未知"),
                        "error": f"数据预处理失败: {str(e)}"
                    })
                    logger.error(f"批量添加网段预处理失败: {item.get('ip')}/{item.get('mask')}, 错误: {str(e)}")

            # 如果有预处理失败的，直接返回失败
            if len(failed_items) > 0:
                logger.error(f"批量添加网络地址预处理失败，共 {len(failed_items)} 条数据有误")
                return {
                    "status": "failed",
                    "message": f"数据验证失败，共 {len(failed_items)} 条数据有误",
                    "success_count": 0,
                    "failed_count": len(failed_items),
                    "failed_items": failed_items
                }

            # 批量执行插入（事务）
            if len(params_list) > 0:
                self.cursor.executemany(sql, params_list)
                self.conn.commit()
                success_count = len(params_list)
                logger.info(f"批量添加网络地址成功: {success_count} 个")

                return {
                    "status": "success",
                    "message": f"批量添加成功，共 {success_count} 个网段",
                    "success_count": success_count,
                    "failed_count": 0,
                    "failed_items": []
                }
            else:
                return {
                    "status": "failed",
                    "message": "没有有效的数据可以插入",
                    "success_count": 0,
                    "failed_count": len(data_list),
                    "failed_items": []
                }

        except Exception as e:
            self.conn.rollback()
            logger.error(f"批量添加网络地址异常: {e}")
            return {
                "status": "failed",
                "message": f"批量添加失败: {str(e)}",
                "success_count": 0,
                "failed_count": len(data_list) if isinstance(data_list, list) else 0,
                "failed_items": []
            }
        finally:
            self.cursor.close()
            self.conn.close()

    def update_network_item(self, data):
        """更新网络地址记录"""
        try:
            data = waf(data)
            if "ip" not in data or "mask" not in data:
                return "failed"

            fields = []
            params = []
            timestamp = str(int(time.time()))

            fields.append("update_time = %s")
            params.append(timestamp)

            update_keys = ["status", "location", "isp", "role", "label", "comment",
                          "manage_user", "gateway", "used_per"]
            for key in update_keys:
                if key in data:
                    fields.append(f"{key} = %s")
                    params.append(data[key])

            if len(fields) == 1:
                return "failed"

            params.extend([data["ip"], data["mask"]])
            sql = f"UPDATE ipam_net SET {', '.join(fields)} WHERE ip = %s AND mask = %s"
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"更新网络地址记录失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_network_item(self, data):
        """删除网络地址记录"""
        try:
            data = waf(data)
            if "ip" not in data or "mask" not in data:
                return "failed"

            sql = "DELETE FROM ipam_net WHERE ip = %s AND mask = %s"
            self.cursor.execute(sql, (data["ip"], data["mask"]))
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"删除网络地址记录失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_network_list(self, data):
        """查询网络地址记录"""
        try:
            data = waf(data)
            conditions = []
            params = []

            # 精确匹配
            if "ip" in data:
                conditions.append("ip = %s")
                params.append(data["ip"])
            if "mask" in data:
                conditions.append("mask = %s")
                params.append(data["mask"])
            if "status" in data:
                conditions.append("status = %s")
                params.append(data["status"])

            # 模糊匹配
            search_keys = ["location", "isp", "role", "label", "comment", "manage_user"]
            for key in search_keys:
                if key in data:
                    conditions.append(f"{key} REGEXP %s")
                    params.append(data[key])

            # IP范围查询
            if "ip_range" in data:
                ip_deci = str(ip2decimalism(data["ip_range"]))
                conditions.append("start_ip <= %s AND end_ip >= %s")
                params.extend([ip_deci, ip_deci])

            sql = """SELECT ip, mask, start_ip, end_ip, status, location, isp, role, label,
                     comment, manage_user, create_time, update_time, gateway, used_per
                     FROM ipam_net"""
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            proper = ["ip", "mask", "start_ip", "end_ip", "status", "location", "isp", "role", "label",
                     "comment", "manage_user", "create_time", "update_time", "gateway", "used_per"]
            self.cursor.execute(sql, params)
            result1 = self.cursor.fetchall()
            results = []

            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        if proper[num] == "used_per":
                            # used_per 字段如果为空则默认为 "0"
                            result[proper[num]] = i[num] if i[num] else "0"
                        else:
                            result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)

            return results
        except Exception as err:
            logger.error("======IpamDB get_network_list error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== IP地址管理 ====================

    def add_ipaddr_batch(self, data_list):
        """批量添加IP地址记录"""
        try:
            timestamp = str(int(time.time()))
            sql = '''INSERT INTO ipam_ipaddr (ip_deci, ip_addr, collect_type, comment, update_time)
                     VALUES (%s, %s, %s, %s, %s)
                     ON DUPLICATE KEY UPDATE
                     collect_type = VALUES(collect_type),
                     comment = VALUES(comment),
                     update_time = VALUES(update_time)'''

            params_list = []
            for item in data_list:
                params_list.append((
                    str(item["ip_deci"]),
                    item["ip_addr"],
                    item.get("collect_type", ""),
                    item.get("comment", ""),
                    timestamp
                ))

            self.cursor.executemany(sql, params_list)
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"批量添加IP地址记录失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_ipaddr_list(self, data):
        """查询IP地址记录"""
        try:
            data = waf(data)
            conditions = []
            params = []

            if "ip_addr" in data:
                conditions.append("ip_addr = %s")
                params.append(data["ip_addr"])
            if "ip_deci" in data:
                conditions.append("ip_deci = %s")
                params.append(str(data["ip_deci"]))
            if "collect_type" in data:
                conditions.append("collect_type REGEXP %s")
                params.append(data["collect_type"])
            if "start_ip" in data:
                conditions.append("ip_deci >= %s")
                params.append(str(data["start_ip"]))
            if "end_ip" in data:
                conditions.append("ip_deci <= %s")
                params.append(str(data["end_ip"]))

            sql = """SELECT ip_deci, ip_addr, collect_type, admin_status, comment, update_time
                     FROM ipam_ipaddr"""
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            proper = ["ip_deci", "ip_addr", "collect_type", "admin_status", "comment", "update_time"]
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
            logger.error("======IpamDB get_ipaddr_list error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_ipaddr_item(self, data):
        """删除IP地址记录"""
        try:
            data = waf(data)
            if "ip_deci" not in data:
                return "failed"

            sql = "DELETE FROM ipam_ipaddr WHERE ip_deci = %s"
            self.cursor.execute(sql, (str(data["ip_deci"]),))
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"删除IP地址记录失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()
