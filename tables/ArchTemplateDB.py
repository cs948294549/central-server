from daos.database import mysqldb_netops
from utils.utils import waf
import json
import time
import logging

logger = logging.getLogger(__name__)

'''
业务架构模板（配置模板）数据库操作
对应表：arch_template（主表）+ arch_template_config（配置表，按厂商分行）
       + arch_template_snapshot（版本快照表）
建表见 scripts/arch_template.sql

SQL 一律参数化，连接在 finally 中关闭，每个实例只能调用一次方法。
'''


class ArchTemplateDB(mysqldb_netops):
    """业务架构模板数据库操作类"""

    # ==================== 模板主表 ====================

    def getTemplateList(self, data):
        """
        获取模板列表
        :param data: {keyword, arch_type, is_active, vendor, page, page_size}
        :return: {list: [...], total: int} 或 "failed"
        """
        try:
            data = waf(data)
            keyword = data.get("keyword", "").strip()
            arch_type = data.get("arch_type", "").strip()
            is_active = data.get("is_active")
            vendor = data.get("vendor", "").strip()
            page = int(data.get("page", 1))
            page_size = int(data.get("page_size", 20))
            offset = (page - 1) * page_size

            # JOIN 的占位符在 SQL 里排在 WHERE 之前，vendor 参数必须先入列
            join_params = []
            vendor_join = ""
            if vendor:
                vendor_join = "INNER JOIN arch_template_config c ON t.tid = c.tid AND c.vendor = %s"
                join_params.append(vendor)

            where_parts = []
            where_params = []
            if keyword:
                where_parts.append("(t.name LIKE %s OR t.arch_type LIKE %s OR t.description LIKE %s)")
                like_kw = "%{}%".format(keyword)
                where_params.extend([like_kw, like_kw, like_kw])
            if arch_type:
                where_parts.append("t.arch_type = %s")
                where_params.append(arch_type)
            if is_active not in (None, ""):
                where_parts.append("t.is_active = %s")
                where_params.append(int(is_active))

            where_clause = " AND ".join(where_parts) if where_parts else "1=1"
            params = join_params + where_params

            count_sql = '''SELECT COUNT(DISTINCT t.tid) FROM arch_template t
                           {} WHERE {}'''.format(vendor_join, where_clause)
            self.cursor.execute(count_sql, tuple(params))
            total = self.cursor.fetchone()[0]

            fields = ["id", "tid", "name", "arch_type", "description", "tags",
                      "is_active", "min_expand_unit", "created_by",
                      "updated_by", "created_at", "updated_at"]
            list_sql = '''SELECT DISTINCT t.id, t.tid, t.name, t.arch_type, t.description, t.tags,
                                 t.is_active, t.min_expand_unit, t.created_by,
                                 t.updated_by, t.created_at, t.updated_at
                          FROM arch_template t
                          {} WHERE {}
                          ORDER BY t.updated_at DESC
                          LIMIT %s OFFSET %s'''.format(vendor_join, where_clause)
            self.cursor.execute(list_sql, tuple(params + [page_size, offset]))

            result_list = []
            for row in self.cursor.fetchall():
                item = dict(zip(fields, row))
                item["tags"] = json.loads(item["tags"]) if isinstance(item["tags"], str) else (item["tags"] or [])
                item["vendors"] = []
                result_list.append(item)

            # 一次查出所有模板支持的厂商，按 tid 回填
            if result_list:
                tids = [item["tid"] for item in result_list]
                vendor_sql = "SELECT tid, vendor FROM arch_template_config WHERE tid IN ({})".format(
                    ", ".join(["%s"] * len(tids)))
                self.cursor.execute(vendor_sql, tuple(tids))
                vendor_map = {}
                for tid, vendor_name in self.cursor.fetchall():
                    vendor_map.setdefault(tid, []).append(vendor_name)
                for item in result_list:
                    item["vendors"] = vendor_map.get(item["tid"], [])

            return {"list": result_list, "total": total}

        except Exception as err:
            logger.error("======ArchTemplateDB getTemplateList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getTemplateDetail(self, data):
        """
        获取模板详情（主表信息 + 所有厂商配置）
        :param data: {tid} 或 {id}
        :return: {..., configs: {厂商: {...}}} 或 "failed"
        """
        try:
            data = waf(data)
            if not data.get("tid") and not data.get("id"):
                logger.error("ArchTemplateDB getTemplateDetail 参数不足: 需要 tid 或 id")
                return "failed"

            detail = self._fetchDetail(tid=data.get("tid"), template_id=data.get("id"))
            return detail if detail else "failed"

        except Exception as err:
            logger.error("======ArchTemplateDB getTemplateDetail error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def _fetchDetail(self, tid=None, template_id=None):
        """
        查模板详情（内部方法，不关连接，供 getTemplateDetail / duplicateTemplate 复用）
        :return: 字典 或 None
        """
        fields = ["id", "tid", "name", "arch_type", "description", "tags", "is_active",
                  "min_expand_unit", "created_by", "updated_by",
                  "created_at", "updated_at"]
        base_sql = '''SELECT id, tid, name, arch_type, description, tags, is_active,
                             min_expand_unit, created_by, updated_by, created_at, updated_at
                      FROM arch_template WHERE {} = %s'''
        if tid:
            self.cursor.execute(base_sql.format("tid"), (tid,))
        else:
            self.cursor.execute(base_sql.format("id"), (template_id,))

        row = self.cursor.fetchone()
        if not row:
            return None

        detail = dict(zip(fields, row))
        detail["tags"] = json.loads(detail["tags"]) if isinstance(detail["tags"], str) else (detail["tags"] or [])

        config_sql = '''SELECT vendor, version, config_a, params, created_at, updated_at
                        FROM arch_template_config WHERE tid = %s'''
        self.cursor.execute(config_sql, (detail["tid"],))

        configs = {}
        for vendor, version, config_a, params, created_at, updated_at in self.cursor.fetchall():
            configs[vendor] = {
                "vendor": vendor,
                "version": version,
                "config_a": config_a or "",
                "params": json.loads(params) if isinstance(params, str) else (params or []),
                "created_at": created_at,
                "updated_at": updated_at
            }
        detail["configs"] = configs
        return detail

    def createTemplate(self, data):
        """
        创建新模板（主表 + 配置表）
        :param data: {tid, name, arch_type, description, tags, is_active,
                      min_expand_unit, created_by, configs: {厂商: {config_a, params}}}
        :return: {tid} 或 "failed"
        """
        try:
            data = waf(data)
            if not data.get("tid") or not data.get("name"):
                logger.error("ArchTemplateDB createTemplate 参数不足: tid, name")
                return "failed"

            self._insertTemplate(data)
            self.conn.commit()
            return {"tid": data["tid"]}

        except Exception as err:
            self.conn.rollback()
            logger.error("======ArchTemplateDB createTemplate error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def _insertTemplate(self, data):
        """
        插入主表与各厂商配置（内部方法，不提交不关连接）
        """
        timestamp = str(int(time.time()))
        main_sql = '''INSERT INTO arch_template
                      (tid, name, arch_type, description, tags, is_active,
                       min_expand_unit, created_by, updated_by, created_at, updated_at)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
        self.cursor.execute(main_sql, (
            data["tid"],
            data["name"],
            data.get("arch_type", ""),
            data.get("description", ""),
            json.dumps(data.get("tags", []), ensure_ascii=False),
            int(data.get("is_active", 1)),
            int(data.get("min_expand_unit", 1)),
            data.get("created_by", ""),
            data.get("created_by", ""),
            timestamp,
            timestamp
        ))

        configs = data.get("configs") or {}
        if not configs:
            return

        config_sql = '''INSERT INTO arch_template_config
                        (tid, vendor, version, config_a, params, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)'''
        config_params = [
            (
                data["tid"],
                vendor,
                1,
                cfg.get("config_a", ""),
                json.dumps(cfg.get("params", []), ensure_ascii=False),
                timestamp,
                timestamp
            )
            for vendor, cfg in configs.items()
        ]
        self.cursor.executemany(config_sql, config_params)

    def updateTemplate(self, data):
        """
        更新模板（主表 + 配置表，配置按厂商逐个更新或新增）
        :param data: {tid, name?, arch_type?, description?, tags?, is_active?,
                      min_expand_unit?, updated_by,
                      configs?: {厂商: {config_a, params, increment_version, change_summary}}}
        :return: {tid, updated_vendors: [厂商]} 或 "failed"
        """
        try:
            data = waf(data)
            if not data.get("tid"):
                logger.error("ArchTemplateDB updateTemplate 参数不足: tid")
                return "failed"

            timestamp = str(int(time.time()))
            updated_by = data.get("updated_by", "")

            # 主表：只更新传进来的字段
            sets = []
            params = []
            for key in ("name", "arch_type", "description"):
                if key in data.keys():
                    sets.append("{} = %s".format(key))
                    params.append(data[key])
            if "tags" in data.keys():
                sets.append("tags = %s")
                params.append(json.dumps(data["tags"], ensure_ascii=False))
            for key in ("is_active", "min_expand_unit"):
                if key in data.keys():
                    sets.append("{} = %s".format(key))
                    params.append(int(data[key]))

            sets.extend(["updated_by = %s", "updated_at = %s"])
            params.extend([updated_by, timestamp, data["tid"]])

            main_sql = "UPDATE arch_template SET " + ", ".join(sets) + " WHERE tid = %s"
            self.cursor.execute(main_sql, tuple(params))

            updated_vendors = []
            for vendor, cfg in (data.get("configs") or {}).items():
                config_a = cfg.get("config_a", "")
                params_json = json.dumps(cfg.get("params", []), ensure_ascii=False)

                self.cursor.execute(
                    "SELECT version FROM arch_template_config WHERE tid = %s AND vendor = %s",
                    (data["tid"], vendor))
                existing = self.cursor.fetchone()

                if not existing:
                    self.cursor.execute(
                        '''INSERT INTO arch_template_config
                           (tid, vendor, version, config_a, params, created_at, updated_at)
                           VALUES (%s, %s, 1, %s, %s, %s, %s)''',
                        (data["tid"], vendor, config_a, params_json, timestamp, timestamp))
                    updated_vendors.append(vendor)
                    continue

                increment_version = cfg.get("increment_version", True)
                version_part = "version = version + 1, " if increment_version else ""
                self.cursor.execute(
                    '''UPDATE arch_template_config
                       SET config_a = %s, params = %s, {}updated_at = %s
                       WHERE tid = %s AND vendor = %s'''.format(version_part),
                    (config_a, params_json, timestamp, data["tid"], vendor))

                if increment_version:
                    self._saveSnapshot(data["tid"], vendor, existing[0] + 1, config_a,
                                       params_json, updated_by, timestamp,
                                       cfg.get("change_summary", ""))
                updated_vendors.append(vendor)

            self.conn.commit()
            return {"tid": data["tid"], "updated_vendors": updated_vendors}

        except Exception as err:
            self.conn.rollback()
            logger.error("======ArchTemplateDB updateTemplate error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def deleteTemplate(self, data):
        """
        删除模板（软删除，设 is_active = 0）
        :param data: {tid, updated_by?}
        :return: "success" 或 "failed"
        """
        try:
            data = waf(data)
            if not data.get("tid"):
                logger.error("ArchTemplateDB deleteTemplate 参数不足: tid")
                return "failed"

            timestamp = str(int(time.time()))
            self.cursor.execute(
                "UPDATE arch_template SET is_active = 0, updated_by = %s, updated_at = %s WHERE tid = %s",
                (data.get("updated_by", ""), timestamp, data["tid"]))
            self.conn.commit()
            return "success"

        except Exception as err:
            self.conn.rollback()
            logger.error("======ArchTemplateDB deleteTemplate error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def duplicateTemplate(self, data):
        """
        复制模板（读源模板 + 以新 tid 写入，在同一连接内完成）
        :param data: {tid（源模板）, new_tid, created_by?}
        :return: {tid: new_tid} 或 "failed"
        """
        try:
            data = waf(data)
            if not data.get("tid") or not data.get("new_tid"):
                logger.error("ArchTemplateDB duplicateTemplate 参数不足: tid, new_tid")
                return "failed"

            source = self._fetchDetail(tid=data["tid"])
            if not source:
                logger.error("ArchTemplateDB duplicateTemplate 源模板不存在: {}".format(data["tid"]))
                return "failed"

            new_data = {
                "tid": data["new_tid"],
                "name": source["name"] + "_copy",
                "arch_type": source["arch_type"],
                "description": source["description"],
                "tags": source["tags"],
                "is_active": source["is_active"],
                "min_expand_unit": source["min_expand_unit"],
                "created_by": data.get("created_by", ""),
                "configs": {
                    vendor: {
                        "config_a": cfg["config_a"],
                        "params": cfg["params"],
                    }
                    for vendor, cfg in source["configs"].items()
                }
            }
            self._insertTemplate(new_data)
            self.conn.commit()
            return {"tid": data["new_tid"]}

        except Exception as err:
            self.conn.rollback()
            logger.error("======ArchTemplateDB duplicateTemplate error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 版本快照 ====================

    def _saveSnapshot(self, tid, vendor, version, config_a, params_json,
                      updated_by, timestamp, change_summary=""):
        """
        写入版本快照（内部方法，不提交不关连接，异常向上冒泡由调用方回滚）
        """
        self.cursor.execute(
            '''INSERT INTO arch_template_snapshot
               (tid, vendor, version, config_a, params, change_summary, updated_by, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
            (tid, vendor, version, config_a, params_json,
             change_summary, updated_by, timestamp))

    def getSnapshotList(self, data):
        """
        获取某模板某厂商的版本历史列表
        :param data: {tid, vendor}
        :return: [...] 或 "failed"
        """
        try:
            data = waf(data)
            if not data.get("tid") or not data.get("vendor"):
                logger.error("ArchTemplateDB getSnapshotList 参数不足: tid, vendor")
                return "failed"

            fields = ["tid", "vendor", "version", "change_summary", "updated_by", "updated_at"]
            self.cursor.execute(
                '''SELECT tid, vendor, version, change_summary, updated_by, updated_at
                   FROM arch_template_snapshot
                   WHERE tid = %s AND vendor = %s
                   ORDER BY version DESC''',
                (data["tid"], data["vendor"]))

            result = []
            for row in self.cursor.fetchall():
                result.append(dict(zip(fields, row)))
            return result

        except Exception as err:
            logger.error("======ArchTemplateDB getSnapshotList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getSnapshot(self, data):
        """
        获取指定版本快照详情
        :param data: {tid, vendor, version}
        :return: {...} 或 "failed"
        """
        try:
            data = waf(data)
            if not data.get("tid") or not data.get("vendor") or data.get("version") is None:
                logger.error("ArchTemplateDB getSnapshot 参数不足: tid, vendor, version")
                return "failed"

            fields = ["tid", "vendor", "version", "config_a",
                      "params", "change_summary", "updated_by", "updated_at"]
            self.cursor.execute(
                '''SELECT tid, vendor, version, config_a,
                          params, change_summary, updated_by, updated_at
                   FROM arch_template_snapshot
                   WHERE tid = %s AND vendor = %s AND version = %s''',
                (data["tid"], data["vendor"], int(data["version"])))

            row = self.cursor.fetchone()
            if not row:
                return "failed"

            item = dict(zip(fields, row))
            item["config_a"] = item["config_a"] or ""
            item["params"] = json.loads(item["params"]) if isinstance(item["params"], str) else (item["params"] or [])
            return item

        except Exception as err:
            logger.error("======ArchTemplateDB getSnapshot error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()
