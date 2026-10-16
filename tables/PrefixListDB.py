from daos.database import mysqldb_netops
from utils.utils import waf
import time
import json
import logging

logger = logging.getLogger(__name__)

'''
地址前缀列表管理相关表操作
对应表：prefix_list_standards, prefix_list_records
说明：问题处理记录已合并到通用的 policy_issue_records 表，见 tables/PolicyIssueDB.py
'''


class PrefixListDB(mysqldb_netops):
    """地址前缀列表数据库操作类"""

    # ==================== 标准规则表操作 ====================

    def getStandardsList(self, data):
        """
        获取标准规则列表
        :param data: 查询条件 {name, is_active}
        :return: 列表数据或"failed"
        """
        data = waf(data)
        try:
            conditions = []

            # 按名称搜索
            if "name" in data.keys() and data["name"]:
                search_value = str(data["name"])
                conditions.append("name LIKE '%" + search_value + "%'")

            # 按状态筛选
            if "is_active" in data.keys():
                conditions.append("is_active=" + str(data["is_active"]))

            # 构建SQL
            sql = """SELECT id, name, fingerprint, entries, description,
                     is_active, created_at, updated_at, created_by
                     FROM prefix_list_standards"""

            if len(conditions) > 0:
                sql = sql + " WHERE " + " AND ".join(conditions)

            sql = sql + " ORDER BY created_at DESC"

            # 执行查询
            proper = ["id", "name", "fingerprint", "entries", "description",
                     "is_active", "created_at", "updated_at", "created_by"]
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []

            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        if proper[num] == "entries":
                            # JSON 字段解析
                            result[proper[num]] = json.loads(i[num]) if i[num] else {"entries": []}
                        else:
                            result[proper[num]] = i[num] if i[num] is not None else ""
                    results.append(result)

            return results

        except Exception as err:
            logger.error("======PrefixListDB getStandardsList error========\n{}".format(str(err)))
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

            sql = """SELECT id, name, fingerprint, entries, description,
                     is_active, created_at, updated_at, created_by
                     FROM prefix_list_standards WHERE id=%s"""

            self.cursor.execute(sql, (data["id"],))
            result = self.cursor.fetchone()

            if result:
                proper = ["id", "name", "fingerprint", "entries", "description",
                         "is_active", "created_at", "updated_at", "created_by"]
                detail = {}
                for num in range(len(proper)):
                    if proper[num] == "entries":
                        detail[proper[num]] = json.loads(result[num]) if result[num] else {"entries": []}
                    else:
                        detail[proper[num]] = result[num] if result[num] is not None else ""
                return detail
            else:
                return "failed"

        except Exception as err:
            logger.error("======PrefixListDB getStandardDetail error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def createStandard(self, data):
        """
        创建标准规则
        :param data: {name, fingerprint, entries, description, is_active, created_by}
        :return: lastrowid或"failed"
        """
        try:
            check_params = ["name", "fingerprint", "entries"]
            for i in check_params:
                if i not in data.keys():
                    logger.error("参数不足: {}".format(i))
                    return "failed"

            data = waf(data)

            sql = """INSERT INTO prefix_list_standards
                     (name, fingerprint, entries, description, is_active, created_by, created_at, updated_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""

            entries_json = json.dumps(data["entries"], ensure_ascii=False)
            timestamp = str(int(time.time()))

            sqlParam = (
                data["name"],
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
            logger.error("======PrefixListDB createStandard error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateStandard(self, data):
        """
        更新标准规则
        :param data: {id, name, fingerprint, entries, description, is_active}
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

            sql = "UPDATE prefix_list_standards SET " + ", ".join(update_fields) + " WHERE id=%s"

            self.cursor.execute(sql, tuple(params))
            self.conn.commit()

            return self.cursor.rowcount

        except Exception as err:
            logger.error("======PrefixListDB updateStandard error========\n{}".format(str(err)))
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

            sql = "DELETE FROM prefix_list_standards WHERE id=%s"

            self.cursor.execute(sql, (data["id"],))
            self.conn.commit()

            return self.cursor.rowcount

        except Exception as err:
            logger.error("======PrefixListDB deleteStandard error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 设备配置记录表操作 ====================

    def getRecordsList(self, data):
        """
        获取设备配置记录列表
        :param data: 查询条件 {device_ip, pl_name, fingerprint}
        :return: 列表数据或"failed"
        """
        data = waf(data)
        try:
            conditions = []

            # 按设备IP搜索
            if "device_ip" in data.keys() and data["device_ip"]:
                conditions.append("device_ip='" + str(data["device_ip"]) + "'")

            # 按前缀列表名称搜索
            if "pl_name" in data.keys() and data["pl_name"]:
                conditions.append("pl_name='" + str(data["pl_name"]) + "'")

            # 按指纹搜索
            if "fingerprint" in data.keys() and data["fingerprint"]:
                conditions.append("fingerprint='" + str(data["fingerprint"]) + "'")

            # 构建SQL
            sql = """SELECT id, device_ip, device_name, vendor, pl_name,
                     fingerprint, entries, collected_at
                     FROM prefix_list_records"""

            if len(conditions) > 0:
                sql = sql + " WHERE " + " AND ".join(conditions)

            sql = sql + " ORDER BY collected_at DESC"

            # 执行查询
            proper = ["id", "device_ip", "device_name", "vendor", "pl_name",
                     "fingerprint", "entries", "collected_at"]
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
            logger.error("======PrefixListDB getRecordsList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def addRecord(self, data):
        """
        添加设备配置记录
        :param data: {device_ip, device_name, vendor, pl_name, fingerprint, entries}
        :return: lastrowid或"failed"
        """
        try:
            check_params = ["device_ip", "device_name", "vendor", "pl_name", "fingerprint", "entries"]
            for i in check_params:
                if i not in data.keys():
                    logger.error("参数不足: {}".format(i))
                    return "failed"

            data = waf(data)

            sql = """INSERT INTO prefix_list_records
                     (device_ip, device_name, vendor, pl_name, fingerprint, entries, collected_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""

            entries_json = json.dumps(data["entries"], ensure_ascii=False)
            collected_at = str(int(time.time()))

            sqlParam = (
                data["device_ip"],
                data["device_name"],
                data["vendor"],
                data["pl_name"],
                data["fingerprint"],
                entries_json,
                collected_at
            )

            self.cursor.execute(sql, sqlParam)
            self.conn.commit()

            return self.cursor.lastrowid

        except Exception as err:
            logger.error("======PrefixListDB addRecord error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def addRecordsList(self, records):
        """
        批量添加设备配置记录
        :param records: [{device_ip, device_name, vendor, pl_name, fingerprint, entries}, ...]
        :return: {"success": 成功数量, "failed": 失败数量, "failed_items": [失败项]}
        """
        try:
            if not records or len(records) == 0:
                return {"success": 0, "failed": 0, "failed_items": []}

            check_params = ["device_ip", "device_name", "vendor", "pl_name", "fingerprint", "entries"]

            sql = """INSERT INTO prefix_list_records
                     (device_ip, device_name, vendor, pl_name, fingerprint, entries, collected_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""

            success_count = 0
            failed_count = 0
            failed_items = []
            collected_at = str(int(time.time()))

            for record in records:
                try:
                    # 参数检查
                    for param in check_params:
                        if param not in record.keys():
                            failed_items.append({
                                "pl_name": record.get("pl_name", "unknown"),
                                "reason": f"参数不足: {param}"
                            })
                            failed_count += 1
                            continue

                    record = waf(record)
                    entries_json = json.dumps(record["entries"], ensure_ascii=False)

                    sqlParam = (
                        record["device_ip"],
                        record["device_name"],
                        record["vendor"],
                        record["pl_name"],
                        record["fingerprint"],
                        entries_json,
                        collected_at
                    )

                    self.cursor.execute(sql, sqlParam)
                    success_count += 1

                except Exception as err:
                    logger.error(f"批量插入单条记录失败: {err}")
                    failed_items.append({
                        "pl_name": record.get("pl_name", "unknown"),
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
            logger.error("======PrefixListDB addRecordsList error========\n{}".format(str(err)))
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

            sql = "DELETE FROM prefix_list_records WHERE device_ip=%s"

            self.cursor.execute(sql, (device_ip,))
            self.conn.commit()

            return True

        except Exception as err:
            logger.error("======PrefixListDB deleteRecordsByIP error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

