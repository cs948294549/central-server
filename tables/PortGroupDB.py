from daos.database import mysqldb_netops
from utils.utils import waf
import time
import json
import logging

logger = logging.getLogger(__name__)

'''
端口组数据库操作
对应表：portgroup_standards（标准规则）、portgroup_records（设备实际配置）

条目两种结构（设计文档 1.4）：{protocol, op, ports} 端口条目 / {type:"ref", name} 组引用。
问题处理记录已合并到通用的 policy_issue_records 表，见 tables/PolicyIssueDB.py
'''

# 表字段顺序，与 SELECT 保持一致
PORTGROUP_COLUMNS = ["id", "name", "acl_type", "fingerprint", "entries",
                     "description", "is_active", "created_at", "updated_at", "created_by"]

# portgroup_records 字段顺序，与 SELECT 保持一致
PORTGROUP_RECORD_COLUMNS = ["id", "device_ip", "device_name", "vendor", "group_name",
                            "fingerprint", "entries", "collected_at"]


class PortGroupDB(mysqldb_netops):
    """端口组数据库操作类"""

    def _decode_rows(self, rows):
        """把结果集解码成字典列表"""
        results = []
        for row in rows:
            result = {}
            for num in range(len(PORTGROUP_COLUMNS)):
                if PORTGROUP_COLUMNS[num] == "entries":
                    result[PORTGROUP_COLUMNS[num]] = json.loads(row[num]) if row[num] else []
                else:
                    result[PORTGROUP_COLUMNS[num]] = row[num] if row[num] is not None else ""
            # 列表页给出条目数，避免前端解析 entries
            result["entry_count"] = len(result["entries"])
            results.append(result)
        return results

    def getGroupsList(self, data):
        """
        获取端口组标准规则列表
        :param data: 查询条件 {name, acl_type, is_active}
        :return: 列表数据或"failed"
        """
        data = waf(data)
        try:
            conditions = []

            # 按名称搜索
            if "name" in data.keys() and data["name"]:
                conditions.append("name LIKE '%" + str(data["name"]) + "%'")

            # 按地址族筛选
            if "acl_type" in data.keys() and data["acl_type"]:
                conditions.append("acl_type='" + str(data["acl_type"]) + "'")

            # 按状态筛选
            if "is_active" in data.keys():
                conditions.append("is_active=" + str(data["is_active"]))

            sql = """SELECT id, name, acl_type, fingerprint, entries,
                     description, is_active, created_at, updated_at, created_by
                     FROM portgroup_standards"""

            if len(conditions) > 0:
                sql = sql + " WHERE " + " AND ".join(conditions)

            sql = sql + " ORDER BY created_at DESC"

            self.cursor.execute(sql)
            return self._decode_rows(self.cursor.fetchall())

        except Exception as err:
            logger.error("======PortGroupDB getGroupsList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getGroupDetail(self, data):
        """
        获取端口组标准规则详情
        :param data: {id}
        :return: 详情数据或"failed"
        """
        data = waf(data)
        try:
            if "id" not in data.keys():
                logger.error("参数不足: id")
                return "failed"

            sql = """SELECT id, name, acl_type, fingerprint, entries,
                     description, is_active, created_at, updated_at, created_by
                     FROM portgroup_standards WHERE id=%s"""

            self.cursor.execute(sql, (data["id"],))
            row = self.cursor.fetchone()

            if row:
                return self._decode_rows([row])[0]
            else:
                return "failed"

        except Exception as err:
            logger.error("======PortGroupDB getGroupDetail error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def createGroup(self, data):
        """
        创建端口组标准规则
        :param data: {name, acl_type, fingerprint, entries, description, is_active, created_by}
        :return: lastrowid或"failed"
        """
        try:
            check_params = ["name", "acl_type", "fingerprint", "entries"]
            for i in check_params:
                if i not in data.keys():
                    logger.error("参数不足: {}".format(i))
                    return "failed"

            data = waf(data)

            sql = """INSERT INTO portgroup_standards
                     (name, acl_type, fingerprint, entries, description,
                      is_active, created_by, created_at, updated_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""

            entries_json = json.dumps(data["entries"], ensure_ascii=False)
            timestamp = str(int(time.time()))

            sqlParam = (
                data["name"],
                data["acl_type"],
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
            logger.error("======PortGroupDB createGroup error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateGroup(self, data):
        """
        更新端口组标准规则
        :param data: {id, name, acl_type, fingerprint, entries, description, is_active}
        :return: affected rows或"failed"
        """
        try:
            if "id" not in data.keys():
                logger.error("参数不足: id")
                return "failed"

            data = waf(data)

            update_fields = []
            params = []

            if "name" in data.keys():
                update_fields.append("name=%s")
                params.append(data["name"])

            if "acl_type" in data.keys():
                update_fields.append("acl_type=%s")
                params.append(data["acl_type"])

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

            sql = "UPDATE portgroup_standards SET " + ", ".join(update_fields) + " WHERE id=%s"

            self.cursor.execute(sql, tuple(params))
            self.conn.commit()

            return self.cursor.rowcount

        except Exception as err:
            logger.error("======PortGroupDB updateGroup error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def deleteGroup(self, data):
        """
        删除端口组标准规则
        :param data: {id}
        :return: affected rows或"failed"
        """
        try:
            if "id" not in data.keys():
                logger.error("参数不足: id")
                return "failed"

            data = waf(data)

            sql = "DELETE FROM portgroup_standards WHERE id=%s"

            self.cursor.execute(sql, (data["id"],))
            self.conn.commit()

            return self.cursor.rowcount

        except Exception as err:
            logger.error("======PortGroupDB deleteGroup error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 设备配置记录表操作 ====================

    def getRecordsList(self, data):
        """
        获取端口组设备配置记录列表
        :param data: 查询条件 {device_ip, group_name, fingerprint}
        :return: 列表数据或"failed"
        """
        data = waf(data)
        try:
            conditions = []

            if "device_ip" in data.keys() and data["device_ip"]:
                conditions.append("device_ip='" + str(data["device_ip"]) + "'")

            if "group_name" in data.keys() and data["group_name"]:
                conditions.append("group_name='" + str(data["group_name"]) + "'")

            if "group_name_like" in data.keys() and data["group_name_like"]:
                conditions.append("group_name LIKE '%" + str(data["group_name_like"]) + "%'")

            if "fingerprint" in data.keys() and data["fingerprint"]:
                conditions.append("fingerprint='" + str(data["fingerprint"]) + "'")

            sql = """SELECT id, device_ip, device_name, vendor, group_name,
                     fingerprint, entries, collected_at
                     FROM portgroup_records"""

            if len(conditions) > 0:
                sql = sql + " WHERE " + " AND ".join(conditions)

            sql = sql + " ORDER BY collected_at DESC"

            self.cursor.execute(sql)
            rows = self.cursor.fetchall()
            results = []

            if len(rows) > 0:
                for row in rows:
                    result = {}
                    for num in range(len(PORTGROUP_RECORD_COLUMNS)):
                        if PORTGROUP_RECORD_COLUMNS[num] == "entries":
                            result[PORTGROUP_RECORD_COLUMNS[num]] = json.loads(row[num]) if row[num] else []
                        else:
                            result[PORTGROUP_RECORD_COLUMNS[num]] = row[num] if row[num] is not None else ""
                    results.append(result)

            return results

        except Exception as err:
            logger.error("======PortGroupDB getRecordsList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def addRecordsList(self, records):
        """
        批量添加端口组设备配置记录
        :param records: [{device_ip, device_name, vendor, group_name, fingerprint, entries}, ...]
        :return: {"success": 成功数量, "failed": 失败数量, "failed_items": [失败项]}
        """
        try:
            if not records or len(records) == 0:
                return {"success": 0, "failed": 0, "failed_items": []}

            check_params = ["device_ip", "device_name", "vendor", "group_name", "fingerprint", "entries"]

            sql = """INSERT INTO portgroup_records
                     (device_ip, device_name, vendor, group_name,
                      fingerprint, entries, collected_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""

            success_count = 0
            failed_count = 0
            failed_items = []
            collected_at = str(int(time.time()))

            for record in records:
                try:
                    missing = [p for p in check_params if p not in record.keys()]
                    if missing:
                        failed_items.append({
                            "group_name": record.get("group_name", "unknown"),
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
                        record["group_name"],
                        record["fingerprint"],
                        entries_json,
                        collected_at
                    )

                    self.cursor.execute(sql, sqlParam)
                    success_count += 1

                except Exception as err:
                    logger.error(f"批量插入单条端口组记录失败: {err}")
                    failed_items.append({
                        "group_name": record.get("group_name", "unknown"),
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
            logger.error("======PortGroupDB addRecordsList error========\n{}".format(str(err)))
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
        删除指定设备IP的所有端口组配置记录
        :param device_ip: 设备IP
        :return: True或"failed"
        """
        try:
            device_ip = waf({"ip": device_ip})["ip"]

            sql = "DELETE FROM portgroup_records WHERE device_ip=%s"

            self.cursor.execute(sql, (device_ip,))
            self.conn.commit()

            return True

        except Exception as err:
            logger.error("======PortGroupDB deleteRecordsByIP error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()
