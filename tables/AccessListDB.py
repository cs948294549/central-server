from daos.database import mysqldb_netops
from utils.utils import waf
import time
import json
import logging

logger = logging.getLogger(__name__)

'''
ACL 管理相关表操作
对应表：acl_standards, acl_records
说明：地址组/端口组表（addrgroup_*, portgroup_*）暂未纳入采集，本类只覆盖 ACL 本身
      问题处理记录已合并到通用的 policy_issue_records 表，见 tables/PolicyIssueDB.py
'''


class AccessListDB(mysqldb_netops):
    """ACL 数据库操作类"""

    # ==================== 标准规则表操作 ====================

    def getStandardsList(self, data):
        """
        获取标准规则列表
        :param data: 查询条件 {name, acl_type, is_active}
        :return: 列表数据或"failed"
        """
        data = waf(data)
        try:
            conditions = []

            # 按名称搜索
            if "name" in data.keys() and data["name"]:
                search_value = str(data["name"])
                conditions.append("name LIKE '%" + search_value + "%'")

            # 按地址族筛选
            if "acl_type" in data.keys() and data["acl_type"]:
                conditions.append("acl_type='" + str(data["acl_type"]) + "'")

            # 按状态筛选
            if "is_active" in data.keys():
                conditions.append("is_active=" + str(data["is_active"]))

            # 构建SQL
            sql = """SELECT id, name, acl_number, acl_type, acl_kind, fingerprint,
                     entries, description, is_active, created_at, updated_at, created_by
                     FROM acl_standards"""

            if len(conditions) > 0:
                sql = sql + " WHERE " + " AND ".join(conditions)

            sql = sql + " ORDER BY created_at DESC"

            # 执行查询
            proper = ["id", "name", "acl_number", "acl_type", "acl_kind", "fingerprint",
                      "entries", "description", "is_active", "created_at", "updated_at", "created_by"]
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []

            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        if proper[num] == "entries":
                            # JSON 字段解析
                            result[proper[num]] = json.loads(i[num]) if i[num] else []
                        else:
                            result[proper[num]] = i[num] if i[num] is not None else ""
                    # 列表页给出条目数，避免前端解析 entries
                    result["rule_count"] = len(result["entries"])
                    results.append(result)

            return results

        except Exception as err:
            logger.error("======AccessListDB getStandardsList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getStandardDetail(self, data):
        """
        获取标准规则详情
        :param data: {id}
        :return: 详情数据或"failed"
        """
        data = waf(data)
        try:
            if "id" not in data.keys():
                logger.error("参数不足: id")
                return "failed"

            sql = """SELECT id, name, acl_number, acl_type, acl_kind, fingerprint,
                     entries, description, is_active, created_at, updated_at, created_by
                     FROM acl_standards WHERE id=%s"""

            self.cursor.execute(sql, (data["id"],))
            result = self.cursor.fetchone()

            if result:
                proper = ["id", "name", "acl_number", "acl_type", "acl_kind", "fingerprint",
                          "entries", "description", "is_active", "created_at", "updated_at", "created_by"]
                detail = {}
                for num in range(len(proper)):
                    if proper[num] == "entries":
                        detail[proper[num]] = json.loads(result[num]) if result[num] else []
                    else:
                        detail[proper[num]] = result[num] if result[num] is not None else ""
                detail["rule_count"] = len(detail["entries"])
                return detail
            else:
                return "failed"

        except Exception as err:
            logger.error("======AccessListDB getStandardDetail error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def createStandard(self, data):
        """
        创建标准规则
        :param data: {name, acl_number, acl_type, acl_kind, fingerprint, entries, description, is_active, created_by}
        :return: lastrowid或"failed"
        """
        try:
            check_params = ["name", "acl_type", "fingerprint", "entries"]
            for i in check_params:
                if i not in data.keys():
                    logger.error("参数不足: {}".format(i))
                    return "failed"

            data = waf(data)

            sql = """INSERT INTO acl_standards
                     (name, acl_number, acl_type, acl_kind, fingerprint, entries,
                      description, is_active, created_by, created_at, updated_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

            entries_json = json.dumps(data["entries"], ensure_ascii=False)
            timestamp = str(int(time.time()))

            sqlParam = (
                data["name"],
                data.get("acl_number"),
                data["acl_type"],
                data.get("acl_kind"),
                data["fingerprint"],
                entries_json,
                data.get("description", ""),
                data.get("is_active", 1),
                data.get("created_by", ""),
                timestamp,
                timestamp
            )

            self.cursor.execute(sql, sqlParam)
            self.conn.commit()

            return self.cursor.lastrowid

        except Exception as err:
            logger.error("======AccessListDB createStandard error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateStandard(self, data):
        """
        更新标准规则
        :param data: {id, name, acl_number, acl_type, acl_kind, fingerprint, entries, description, is_active}
        :return: affected rows或"failed"
        """
        try:
            if "id" not in data.keys():
                logger.error("参数不足: id")
                return "failed"

            data = waf(data)

            # 动态构建更新字段
            update_fields = []
            params = []

            if "name" in data.keys():
                update_fields.append("name=%s")
                params.append(data["name"])

            if "acl_number" in data.keys():
                update_fields.append("acl_number=%s")
                params.append(data["acl_number"])

            if "acl_type" in data.keys():
                update_fields.append("acl_type=%s")
                params.append(data["acl_type"])

            if "acl_kind" in data.keys():
                update_fields.append("acl_kind=%s")
                params.append(data["acl_kind"])

            if "fingerprint" in data.keys():
                update_fields.append("fingerprint=%s")
                params.append(data["fingerprint"])

            if "entries" in data.keys():
                update_fields.append("entries=%s")
                params.append(json.dumps(data["entries"], ensure_ascii=False))

            if "description" in data.keys():
                update_fields.append("description=%s")
                params.append(data["description"])

            if "is_active" in data.keys():
                update_fields.append("is_active=%s")
                params.append(data["is_active"])

            if len(update_fields) == 0:
                logger.error("没有需要更新的字段")
                return "failed"

            # 自动更新 updated_at
            update_fields.append("updated_at=%s")
            params.append(str(int(time.time())))

            params.append(data["id"])

            sql = "UPDATE acl_standards SET " + ", ".join(update_fields) + " WHERE id=%s"

            self.cursor.execute(sql, tuple(params))
            self.conn.commit()

            return self.cursor.rowcount

        except Exception as err:
            logger.error("======AccessListDB updateStandard error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def deleteStandard(self, data):
        """
        删除标准规则
        :param data: {id}
        :return: affected rows或"failed"
        """
        try:
            if "id" not in data.keys():
                logger.error("参数不足: id")
                return "failed"

            data = waf(data)

            sql = "DELETE FROM acl_standards WHERE id=%s"

            self.cursor.execute(sql, (data["id"],))
            self.conn.commit()

            return self.cursor.rowcount

        except Exception as err:
            logger.error("======AccessListDB deleteStandard error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 设备配置记录表操作 ====================

    def getRecordsList(self, data):
        """
        获取设备配置记录列表
        :param data: 查询条件 {device_ip, device, vendor, acl_name, acl_type, fingerprint}
                     device 同时匹配 IP 和设备名
        :return: 列表数据或"failed"
        """
        data = waf(data)
        try:
            conditions = []

            # 按设备IP搜索
            if "device_ip" in data.keys() and data["device_ip"]:
                conditions.append("device_ip='" + str(data["device_ip"]) + "'")

            # 按设备搜索（IP 或名称模糊匹配）
            if "device" in data.keys() and data["device"]:
                search_value = str(data["device"])
                conditions.append("(device_ip LIKE '%" + search_value + "%' OR device_name LIKE '%" + search_value + "%')")

            # 按厂商筛选
            if "vendor" in data.keys() and data["vendor"]:
                conditions.append("vendor='" + str(data["vendor"]) + "'")

            # 按ACL名称搜索
            if "acl_name" in data.keys() and data["acl_name"]:
                conditions.append("acl_name='" + str(data["acl_name"]) + "'")

            # 按地址族筛选
            if "acl_type" in data.keys() and data["acl_type"]:
                conditions.append("acl_type='" + str(data["acl_type"]) + "'")

            # 按指纹搜索
            if "fingerprint" in data.keys() and data["fingerprint"]:
                conditions.append("fingerprint='" + str(data["fingerprint"]) + "'")

            # 构建SQL
            sql = """SELECT id, device_ip, device_name, vendor, acl_name, acl_number,
                     acl_type, acl_kind, rule_count, fingerprint,
                     entries, collected_at
                     FROM acl_records"""

            if len(conditions) > 0:
                sql = sql + " WHERE " + " AND ".join(conditions)

            sql = sql + " ORDER BY collected_at DESC"

            # 执行查询
            proper = ["id", "device_ip", "device_name", "vendor", "acl_name", "acl_number",
                      "acl_type", "acl_kind", "rule_count", "fingerprint",
                      "entries", "collected_at"]
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []

            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        if proper[num] == "entries":
                            result[proper[num]] = json.loads(i[num]) if i[num] else []
                        else:
                            result[proper[num]] = i[num] if i[num] is not None else ""
                    results.append(result)

            return results

        except Exception as err:
            logger.error("======AccessListDB getRecordsList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def addRecord(self, data):
        """
        添加设备配置记录
        :param data: {device_ip, device_name, vendor, acl_name, fingerprint, entries}
        :return: lastrowid或"failed"
        """
        try:
            check_params = ["device_ip", "device_name", "vendor", "acl_name", "fingerprint", "entries"]
            for i in check_params:
                if i not in data.keys():
                    logger.error("参数不足: {}".format(i))
                    return "failed"

            data = waf(data)

            sql = """INSERT INTO acl_records
                     (device_ip, device_name, vendor, acl_name, acl_number, acl_type,
                      acl_kind, rule_count, fingerprint, entries, collected_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

            entries_json = json.dumps(data["entries"], ensure_ascii=False)
            collected_at = str(int(time.time()))

            sqlParam = (
                data["device_ip"],
                data["device_name"],
                data["vendor"],
                data["acl_name"],
                data.get("acl_number"),
                data.get("acl_type", "ipv4"),
                data.get("acl_kind"),
                len(data["entries"]),
                data["fingerprint"],
                entries_json,
                collected_at
            )

            self.cursor.execute(sql, sqlParam)
            self.conn.commit()

            return self.cursor.lastrowid

        except Exception as err:
            logger.error("======AccessListDB addRecord error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def addRecordsList(self, records):
        """
        批量添加设备配置记录
        :param records: [{device_ip, device_name, vendor, acl_name, acl_type, fingerprint, entries}, ...]
        :return: {"success": 成功数量, "failed": 失败数量, "failed_items": [失败项]}
        """
        try:
            if not records or len(records) == 0:
                return {"success": 0, "failed": 0, "failed_items": []}

            check_params = ["device_ip", "device_name", "vendor", "acl_name", "acl_type", "fingerprint", "entries"]

            sql = """INSERT INTO acl_records
                     (device_ip, device_name, vendor, acl_name, acl_number, acl_type,
                      acl_kind, rule_count, fingerprint, entries, collected_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

            success_count = 0
            failed_count = 0
            failed_items = []
            collected_at = str(int(time.time()))

            for record in records:
                try:
                    # 参数检查
                    missing = [p for p in check_params if p not in record.keys()]
                    if missing:
                        failed_items.append({
                            "acl_name": record.get("acl_name", "unknown"),
                            "reason": f"参数不足: {', '.join(missing)}"
                        })
                        failed_count += 1
                        continue

                    record = waf(record)
                    entries_json = json.dumps(record["entries"], ensure_ascii=False)

                    sqlParam = (
                        record["device_ip"],
                        record["device_name"],
                        record["vendor"],
                        record["acl_name"],
                        record.get("acl_number"),
                        record["acl_type"],
                        record.get("acl_kind"),
                        len(record["entries"]),
                        record["fingerprint"],
                        entries_json,
                        collected_at
                    )

                    self.cursor.execute(sql, sqlParam)
                    success_count += 1

                except Exception as err:
                    logger.error(f"批量插入单条记录失败: {err}")
                    failed_items.append({
                        "acl_name": record.get("acl_name", "unknown"),
                        "reason": str(err)
                    })
                    failed_count += 1

            self.conn.commit()

            return {
                "success": success_count,
                "failed": failed_count,
                "failed_items": failed_items
            }

        except Exception as err:
            logger.error("======AccessListDB addRecordsList error========\n{}".format(str(err)))
            self.conn.rollback()
            return {
                "success": 0,
                "failed": len(records) if records else 0,
                "failed_items": [{"reason": str(err)}]
            }
        finally:
            self.cursor.close()
            self.conn.close()

    def deleteRecordsByIP(self, device_ip):
        """
        删除指定设备IP的所有配置记录
        :param device_ip: 设备IP
        :return: True或"failed"
        """
        try:
            device_ip = waf({"ip": device_ip})["ip"]

            sql = "DELETE FROM acl_records WHERE device_ip=%s"

            self.cursor.execute(sql, (device_ip,))
            self.conn.commit()

            return True

        except Exception as err:
            logger.error("======AccessListDB deleteRecordsByIP error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

