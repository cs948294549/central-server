"""
策略配置问题处理记录（通用）

对应表：policy_issue_records

前缀列表 / ACL / 地址组 / 端口组 四类对象共用同一张问题表，
用 object_type 区分。四类对象的问题都是「标准配置 vs 设备配置」的比对结果，
字段结构一致，因此合并到一张表，按类型分流处理。

前缀列表与 ACL 的差异只在 entries 的字段结构上，库层不感知具体结构，
只负责原样存取 JSON。
"""
from daos.database import mysqldb_netops
from utils.utils import waf
import json
import time
import logging

logger = logging.getLogger(__name__)

class PolicyIssueDB(mysqldb_netops):
    """策略配置问题处理记录通用库层"""

    # 四类对象共用的 JSON 字段
    JSON_FIELDS = ["dangling_refs", "standard_entries", "device_entries"]

    def _decode_row(self, names, row):
        """按字段名列表把一行结果解码成字典"""
        result = {}
        for num in range(len(names)):
            name = names[num]
            if name in self.JSON_FIELDS:
                # dangling_refs 无值时为 None，其余 JSON 字段无值时为 []
                result[name] = json.loads(row[num]) if row[num] else (None if name == "dangling_refs" else [])
            else:
                result[name] = row[num] if row[num] is not None else ""
        return result

    def getIssueRecordsList(self, data):
        """
        获取问题处理记录列表
        :param data: 查询条件 {id, object_type, standard_id, device_ip, device_name,
                                status, issue_type, start_date, end_date}
        :return: 列表数据或"failed"
        """
        data = waf(data)
        try:
            conditions = []

            if "id" in data.keys() and data["id"]:
                conditions.append("id=" + str(data["id"]))

            # 按对象类型筛选：acl / prefix_list / addrgroup / portgroup
            if "object_type" in data.keys() and data["object_type"]:
                conditions.append("object_type='" + str(data["object_type"]) + "'")

            if "standard_id" in data.keys() and data["standard_id"]:
                conditions.append("standard_id=" + str(data["standard_id"]))

            if "device" in data.keys() and data["device"]:
                search_value = str(data["device"])
                conditions.append("(device_ip LIKE '%" + search_value + "%' OR device_name LIKE '%" + search_value + "%')")

            if "device_ip" in data.keys() and data["device_ip"]:
                conditions.append("device_ip='" + str(data["device_ip"]) + "'")

            if "status" in data.keys() and data["status"]:
                conditions.append("status='" + str(data["status"]) + "'")

            if "issue_type" in data.keys() and data["issue_type"]:
                conditions.append("issue_type='" + str(data["issue_type"]) + "'")

            if "start_date" in data.keys() and data["start_date"]:
                conditions.append("created_at>='" + str(data["start_date"]) + "'")

            if "end_date" in data.keys() and data["end_date"]:
                conditions.append("created_at<='" + str(data["end_date"]) + "'")

            sql = """SELECT id, object_type, standard_id, standard_name, device_ip, device_name,
                     device_vendor, issue_type, dangling_refs, standard_entries, device_entries,
                     status, change_ticket_id, created_by, created_at, processed_at, remark
                     FROM policy_issue_records"""

            if len(conditions) > 0:
                sql = sql + " WHERE " + " AND ".join(conditions)

            sql = sql + " ORDER BY created_at DESC"

            proper = ["id", "object_type", "standard_id", "standard_name", "device_ip", "device_name",
                      "device_vendor", "issue_type", "dangling_refs", "standard_entries", "device_entries",
                      "status", "change_ticket_id", "created_by", "created_at", "processed_at", "remark"]

            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []

            for i in result1:
                results.append(self._decode_row(proper, i))

            return results

        except Exception as err:
            logger.error("======PolicyIssueDB getIssueRecordsList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getIssueRecordDetail(self, data):
        """
        获取问题处理记录详情
        :param data: {id}
        :return: 详情数据或"failed"
        """
        data = waf(data)
        try:
            if "id" not in data.keys():
                logger.error("参数不足: id")
                return "failed"

            sql = """SELECT id, object_type, standard_id, standard_name, device_ip, device_name,
                     device_vendor, issue_type, dangling_refs, standard_entries, device_entries,
                     status, change_ticket_id, created_by, created_at, processed_at, remark
                     FROM policy_issue_records WHERE id=%s"""

            proper = ["id", "object_type", "standard_id", "standard_name", "device_ip", "device_name",
                      "device_vendor", "issue_type", "dangling_refs", "standard_entries", "device_entries",
                      "status", "change_ticket_id", "created_by", "created_at", "processed_at", "remark"]

            self.cursor.execute(sql, (data["id"],))
            result = self.cursor.fetchone()

            if result:
                return self._decode_row(proper, result)
            else:
                return "failed"

        except Exception as err:
            logger.error("======PolicyIssueDB getIssueRecordDetail error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def createIssueRecord(self, data):
        """
        创建问题处理记录
        :param data: {object_type, standard_id, standard_name, device_ip, device_name, device_vendor,
                      issue_type, dangling_refs, standard_entries, device_entries, created_by, remark}
        :return: lastrowid或"failed"
        """
        try:
            check_params = ["object_type", "standard_id", "standard_name", "device_ip", "device_name",
                            "device_vendor", "issue_type", "standard_entries", "device_entries"]
            for i in check_params:
                if i not in data.keys():
                    logger.error("参数不足: {}".format(i))
                    return "failed"

            data = waf(data)

            sql = """INSERT INTO policy_issue_records
                     (object_type, standard_id, standard_name, device_ip, device_name, device_vendor,
                      issue_type, dangling_refs, standard_entries, device_entries,
                      created_by, remark, created_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

            dangling_refs = data.get("dangling_refs")
            dangling_json = json.dumps(dangling_refs, ensure_ascii=False) if dangling_refs else None
            standard_entries_json = json.dumps(data["standard_entries"], ensure_ascii=False)
            device_entries_json = json.dumps(data["device_entries"], ensure_ascii=False)
            created_at = str(int(time.time()))

            sqlParam = (
                data["object_type"],
                data["standard_id"],
                data["standard_name"],
                data["device_ip"],
                data["device_name"],
                data["device_vendor"],
                data["issue_type"],
                dangling_json,
                standard_entries_json,
                device_entries_json,
                data.get("created_by", ""),
                data.get("remark", ""),
                created_at
            )

            self.cursor.execute(sql, sqlParam)
            self.conn.commit()

            return self.cursor.lastrowid

        except Exception as err:
            logger.error("======PolicyIssueDB createIssueRecord error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateIssueRecordStatus(self, data):
        """
        更新问题处理记录状态
        :param data: {id, status, change_ticket_id, processed_at, remark}
        :return: affected rows或"failed"
        """
        try:
            if "id" not in data.keys():
                logger.error("参数不足: id")
                return "failed"

            data = waf(data)

            update_fields = []
            params = []

            if "status" in data.keys():
                update_fields.append("status=%s")
                params.append(data["status"])

            if "change_ticket_id" in data.keys():
                update_fields.append("change_ticket_id=%s")
                params.append(data["change_ticket_id"])

            if "processed_at" in data.keys():
                update_fields.append("processed_at=%s")
                params.append(data["processed_at"])

            if "remark" in data.keys():
                update_fields.append("remark=%s")
                params.append(data["remark"])

            if len(update_fields) == 0:
                logger.error("没有需要更新的字段")
                return "failed"

            params.append(data["id"])

            sql = "UPDATE policy_issue_records SET " + ", ".join(update_fields) + " WHERE id=%s"

            self.cursor.execute(sql, tuple(params))
            self.conn.commit()

            return self.cursor.rowcount

        except Exception as err:
            logger.error("======PolicyIssueDB updateIssueRecordStatus error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def deleteIssueRecord(self, data):
        """
        删除问题处理记录
        :param data: {id}
        :return: affected rows或"failed"
        """
        try:
            if "id" not in data.keys():
                logger.error("参数不足: id")
                return "failed"

            data = waf(data)

            sql = "DELETE FROM policy_issue_records WHERE id=%s"
            self.cursor.execute(sql, (data["id"],))
            self.conn.commit()

            return self.cursor.rowcount

        except Exception as err:
            logger.error("======PolicyIssueDB deleteIssueRecord error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateIssueStatus(self, data):
        """
        更新问题处理记录状态
        :param data: {id, status}
        :return: affected rows或"failed"
        """
        try:
            if "id" not in data.keys() or "status" not in data.keys():
                logger.error("参数不足: id 或 status")
                return "failed"

            data = waf(data)

            sql = "UPDATE policy_issue_records SET status=%s, processed_at=%s WHERE id=%s"
            current_time = int(time.time())
            self.cursor.execute(sql, (data["status"], current_time, data["id"]))
            self.conn.commit()

            return self.cursor.rowcount

        except Exception as err:
            logger.error("======PolicyIssueDB updateIssueStatus error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getIssuesByIds(self, issue_ids):
        """
        按ID列表批量获取问题记录，用于创建变更工单
        :param issue_ids: ID列表
        :return: {"records": [...], "not_found": [...]}或"failed"
        """
        if not issue_ids:
            return {"records": [], "not_found": []}

        try:
            placeholders = ", ".join(["%s"] * len(issue_ids))
            sql = """SELECT id, object_type, standard_id, standard_name, device_ip, device_name,
                     device_vendor, issue_type, dangling_refs, standard_entries, device_entries,
                     status, change_ticket_id, created_by, created_at, processed_at, remark
                     FROM policy_issue_records WHERE id IN ({})""".format(placeholders)

            proper = ["id", "object_type", "standard_id", "standard_name", "device_ip", "device_name",
                      "device_vendor", "issue_type", "dangling_refs", "standard_entries", "device_entries",
                      "status", "change_ticket_id", "created_by", "created_at", "processed_at", "remark"]

            self.cursor.execute(sql, tuple(issue_ids))
            rows = self.cursor.fetchall()

            records = [self._decode_row(proper, row) for row in rows]
            found_ids = {r["id"] for r in records}
            not_found = [i for i in issue_ids if i not in found_ids]

            return {"records": records, "not_found": not_found}

        except Exception as err:
            logger.error("======PolicyIssueDB getIssuesByIds error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()
