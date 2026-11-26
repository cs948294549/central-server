"""
业务架构模板（配置模板）数据库操作类
提供模板的 CRUD 和版本管理
表结构：arch_template（主表）+ arch_template_config（配置表，按厂商分行）
"""
import json
import logging
import time
from utils.db_connector import DBConnector
from utils.waf import waf

logger = logging.getLogger(__name__)


class ArchTemplateDB(DBConnector):
    """
    arch_template + arch_template_config 表操作类
    """

    def __init__(self):
        super().__init__()

    def getTemplateList(self, data):
        """
        获取模板列表
        :param data: {
            keyword: str (可选，模糊搜索 name/arch_type),
            arch_type: str (可选，精确匹配),
            is_active: int (可选，0/1),
            vendor: str (可选，只返回支持该厂商的模板),
            page: int (可选，默认 1),
            page_size: int (可选，默认 20)
        }
        :return: {
            list: [{id, tid, name, arch_type, description, tags, is_active, has_z_side,
                    vendors: [厂商列表], created_by, updated_by, created_at, updated_at}],
            total: int
        } 或 "failed"
        """
        data = waf(data)
        try:
            keyword = data.get("keyword", "").strip()
            arch_type = data.get("arch_type", "").strip()
            is_active = data.get("is_active")
            vendor = data.get("vendor", "").strip()
            page = int(data.get("page", 1))
            page_size = int(data.get("page_size", 20))
            offset = (page - 1) * page_size

            where_parts = []
            params = []

            if keyword:
                where_parts.append("(t.name LIKE %s OR t.arch_type LIKE %s OR t.description LIKE %s)")
                like_kw = f"%{keyword}%"
                params.extend([like_kw, like_kw, like_kw])

            if arch_type:
                where_parts.append("t.arch_type = %s")
                params.append(arch_type)

            if is_active is not None:
                where_parts.append("t.is_active = %s")
                params.append(int(is_active))

            # 筛选支持指定厂商的模板
            vendor_join = ""
            if vendor:
                vendor_join = "INNER JOIN arch_template_config c ON t.tid = c.tid AND c.vendor = %s"
                params.append(vendor)

            where_clause = " AND ".join(where_parts) if where_parts else "1=1"

            # 总数
            count_sql = f"SELECT COUNT(DISTINCT t.tid) FROM arch_template t {vendor_join} WHERE {where_clause}"
            self.cursor.execute(count_sql, tuple(params))
            total = self.cursor.fetchone()[0]

            # 列表（主表信息 + 支持的厂商列表）
            list_sql = f"""
                SELECT DISTINCT t.id, t.tid, t.name, t.arch_type, t.description, t.tags,
                       t.is_active, t.has_z_side, t.min_expand_unit, t.created_by, t.updated_by,
                       t.created_at, t.updated_at
                FROM arch_template t
                {vendor_join}
                WHERE {where_clause}
                ORDER BY t.updated_at DESC
                LIMIT %s OFFSET %s
            """
            self.cursor.execute(list_sql, tuple(params + [page_size, offset]))
            rows = self.cursor.fetchall()

            proper = ["id", "tid", "name", "arch_type", "description", "tags",
                     "is_active", "has_z_side", "min_expand_unit", "created_by", "updated_by",
                     "created_at", "updated_at"]

            result_list = []
            for row in rows:
                item = {}
                for i, key in enumerate(proper):
                    val = row[i]
                    if key == "tags" and val:
                        item[key] = json.loads(val) if isinstance(val, str) else val
                    else:
                        item[key] = val

                # 查询该模板支持的厂商列表
                vendor_sql = "SELECT vendor FROM arch_template_config WHERE tid = %s"
                self.cursor.execute(vendor_sql, (item["tid"],))
                vendors = [r[0] for r in self.cursor.fetchall()]
                item["vendors"] = vendors

                result_list.append(item)

            return {"list": result_list, "total": total}

        except Exception as err:
            logger.error(f"获取模板列表失败: {err}")
            return "failed"

    def getTemplateDetail(self, data):
        """
        获取模板详情（主表信息 + 所有厂商配置）
        :param data: {tid: str} 或 {id: int}
        :return: {
            id, tid, name, arch_type, description, tags, is_active, has_z_side, min_expand_unit,
            created_by, updated_by, created_at, updated_at,
            configs: {
                厂商: {vendor, version, config_a, config_z, params, created_at, updated_at}
            }
        } 或 "failed"
        """
        data = waf(data)
        try:
            tid = data.get("tid")
            template_id = data.get("id")

            if not tid and not template_id:
                logger.error("参数不足: 需要 tid 或 id")
                return "failed"

            # 查询主表
            if tid:
                sql = """
                    SELECT id, tid, name, arch_type, description, tags, is_active, has_z_side,
                           min_expand_unit, created_by, updated_by, created_at, updated_at
                    FROM arch_template WHERE tid=%s
                """
                self.cursor.execute(sql, (tid,))
            else:
                sql = """
                    SELECT id, tid, name, arch_type, description, tags, is_active, has_z_side,
                           min_expand_unit, created_by, updated_by, created_at, updated_at
                    FROM arch_template WHERE id=%s
                """
                self.cursor.execute(sql, (template_id,))

            row = self.cursor.fetchone()
            if not row:
                return "failed"

            proper = ["id", "tid", "name", "arch_type", "description", "tags", "is_active", "has_z_side",
                     "min_expand_unit", "created_by", "updated_by", "created_at", "updated_at"]

            detail = {}
            for i, key in enumerate(proper):
                val = row[i]
                if key == "tags" and val:
                    detail[key] = json.loads(val) if isinstance(val, str) else val
                else:
                    detail[key] = val

            # 查询配置表（所有厂商）
            config_sql = """
                SELECT vendor, version, config_a, config_z, params, created_at, updated_at
                FROM arch_template_config WHERE tid = %s
            """
            self.cursor.execute(config_sql, (detail["tid"],))
            config_rows = self.cursor.fetchall()

            configs = {}
            for config_row in config_rows:
                vendor = config_row[0]
                configs[vendor] = {
                    "vendor": vendor,
                    "version": config_row[1],
                    "config_a": config_row[2] or "",
                    "config_z": config_row[3] or "",
                    "params": json.loads(config_row[4]) if config_row[4] else [],
                    "created_at": config_row[5],
                    "updated_at": config_row[6]
                }

            detail["configs"] = configs
            return detail

        except Exception as err:
            logger.error(f"获取模板详情失败: {err}")
            return "failed"

    def createTemplate(self, data):
        """
        创建新模板（主表 + 配置表）
        :param data: {
            tid: str (UUID),
            name: str,
            arch_type: str (可选),
            description: str (可选),
            tags: list (可选),
            has_z_side: int (0/1),
            min_expand_unit: int (可选，默认 1，每次扩容的最小设备台数),
            created_by: str,
            configs: {
                厂商: {config_a: str, config_z: str, params: list}
            }
        }
        :return: {tid: str} 或 "failed"
        """
        data = waf(data)
        try:
            if "tid" not in data or "name" not in data:
                logger.error("参数不足: tid, name")
                return "failed"

            now = str(int(time.time()))

            # 插入主表
            main_sql = """
                INSERT INTO arch_template
                (tid, name, arch_type, description, tags, is_active, has_z_side,
                 min_expand_unit, created_by, updated_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            tags_json = json.dumps(data.get("tags", []), ensure_ascii=False) if data.get("tags") else None

            main_values = (
                data["tid"],
                data["name"],
                data.get("arch_type", ""),
                data.get("description", ""),
                tags_json,
                data.get("is_active", 1),
                data.get("has_z_side", 0),
                data.get("min_expand_unit", 1),
                data.get("created_by", ""),
                data.get("created_by", ""),
                now,
                now
            )

            self.cursor.execute(main_sql, main_values)

            # 插入配置表（每个厂商一行）
            configs = data.get("configs", {})
            if configs:
                config_sql = """
                    INSERT INTO arch_template_config
                    (tid, vendor, version, config_a, config_z, params, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                for vendor, cfg in configs.items():
                    params_json = json.dumps(cfg.get("params", []), ensure_ascii=False)
                    config_values = (
                        data["tid"],
                        vendor,
                        1,  # 初始版本号
                        cfg.get("config_a", ""),
                        cfg.get("config_z", ""),
                        params_json,
                        now,
                        now
                    )
                    self.cursor.execute(config_sql, config_values)

            self.db.commit()
            return {"tid": data["tid"]}

        except Exception as err:
            self.db.rollback()
            logger.error(f"创建模板失败: {err}")
            return "failed"

    def updateTemplate(self, data):
        """
        更新模板（主表 + 配置表）
        :param data: {
            tid: str,
            name: str (可选),
            arch_type: str (可选),
            description: str (可选),
            tags: list (可选),
            is_active: int (可选),
            has_z_side: int (可选),
            min_expand_unit: int (可选),
            updated_by: str,
            configs: {
                厂商: {config_a: str, config_z: str, params: list, increment_version: bool}
            } (可选)
        }
        :return: {tid: str, updated_vendors: [厂商列表]} 或 "failed"
        """
        data = waf(data)
        try:
            if "tid" not in data:
                logger.error("参数不足: tid")
                return "failed"

            now = str(int(time.time()))
            updated_vendors = []

            # 更新主表
            update_parts = []
            params = []

            if "name" in data:
                update_parts.append("name = %s")
                params.append(data["name"])

            if "arch_type" in data:
                update_parts.append("arch_type = %s")
                params.append(data["arch_type"])

            if "description" in data:
                update_parts.append("description = %s")
                params.append(data["description"])

            if "tags" in data:
                update_parts.append("tags = %s")
                params.append(json.dumps(data["tags"], ensure_ascii=False))

            if "is_active" in data:
                update_parts.append("is_active = %s")
                params.append(int(data["is_active"]))

            if "has_z_side" in data:
                update_parts.append("has_z_side = %s")
                params.append(int(data["has_z_side"]))

            if "min_expand_unit" in data:
                update_parts.append("min_expand_unit = %s")
                params.append(int(data["min_expand_unit"]))

            update_parts.append("updated_by = %s")
            params.append(data.get("updated_by", ""))

            update_parts.append("updated_at = %s")
            params.append(now)

            if update_parts:
                main_sql = f"""
                    UPDATE arch_template
                    SET {", ".join(update_parts)}
                    WHERE tid = %s
                """
                params.append(data["tid"])
                self.cursor.execute(main_sql, tuple(params))

            # 更新配置表（按厂商更新）
            configs = data.get("configs", {})
            for vendor, cfg in configs.items():
                # 检查该厂商配置是否存在
                check_sql = "SELECT version FROM arch_template_config WHERE tid = %s AND vendor = %s"
                self.cursor.execute(check_sql, (data["tid"], vendor))
                existing = self.cursor.fetchone()

                params_json = json.dumps(cfg.get("params", []), ensure_ascii=False)

                if existing:
                    # 更新现有配置
                    increment_version = cfg.get("increment_version", True)
                    version_part = "version = version + 1" if increment_version else "version = version"

                    config_update_sql = f"""
                        UPDATE arch_template_config
                        SET config_a = %s, config_z = %s, params = %s,
                            {version_part}, updated_at = %s
                        WHERE tid = %s AND vendor = %s
                    """
                    self.cursor.execute(config_update_sql, (
                        cfg.get("config_a", ""),
                        cfg.get("config_z", ""),
                        params_json,
                        now,
                        data["tid"],
                        vendor
                    ))

                    # 保存快照
                    if increment_version:
                        new_version = existing[0] + 1
                        self._saveSnapshot(data["tid"], vendor, new_version,
                                          cfg.get("config_a", ""),
                                          cfg.get("config_z", ""),
                                          params_json,
                                          data.get("updated_by", ""),
                                          now,
                                          cfg.get("change_summary", ""))
                else:
                    # 新增厂商配置
                    config_insert_sql = """
                        INSERT INTO arch_template_config
                        (tid, vendor, version, config_a, config_z, params, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    self.cursor.execute(config_insert_sql, (
                        data["tid"],
                        vendor,
                        1,
                        cfg.get("config_a", ""),
                        cfg.get("config_z", ""),
                        params_json,
                        now,
                        now
                    ))

                updated_vendors.append(vendor)

            self.db.commit()
            return {"tid": data["tid"], "updated_vendors": updated_vendors}

        except Exception as err:
            self.db.rollback()
            logger.error(f"更新模板失败: {err}")
            return "failed"

    def deleteTemplate(self, data):
        """
        删除模板（软删除：设为停用）
        :param data: {tid: str}
        :return: "success" 或 "failed"
        """
        data = waf(data)
        try:
            if "tid" not in data:
                logger.error("参数不足: tid")
                return "failed"

            now = str(int(time.time()))
            sql = "UPDATE arch_template SET is_active = 0, updated_at = %s WHERE tid = %s"
            self.cursor.execute(sql, (now, data["tid"]))
            self.db.commit()

            return "success"

        except Exception as err:
            self.db.rollback()
            logger.error(f"删除模板失败: {err}")
            return "failed"

    def duplicateTemplate(self, data):
        """
        复制模板（生成新 tid，name 加「副本」后缀，配置表一并复制）
        :param data: {tid: str (源模板), new_tid: str, created_by: str}
        :return: {tid: str (新模板)} 或 "failed"
        """
        data = waf(data)
        try:
            if "tid" not in data or "new_tid" not in data:
                logger.error("参数不足: tid, new_tid")
                return "failed"

            source = self.getTemplateDetail({"tid": data["tid"]})
            if source == "failed":
                return "failed"

            new_data = {
                "tid": data["new_tid"],
                "name": f"{source['name']} - 副本",
                "arch_type": source.get("arch_type", ""),
                "description": source.get("description", ""),
                "tags": source.get("tags", []),
                "has_z_side": source.get("has_z_side", 0),
                "min_expand_unit": source.get("min_expand_unit", 1),
                "created_by": data.get("created_by", ""),
                "configs": {}
            }

            # 复制所有厂商配置
            for vendor, cfg in source.get("configs", {}).items():
                new_data["configs"][vendor] = {
                    "config_a": cfg.get("config_a", ""),
                    "config_z": cfg.get("config_z", ""),
                    "params": cfg.get("params", [])
                }

            return self.createTemplate(new_data)

        except Exception as err:
            logger.error(f"复制模板失败: {err}")
            return "failed"

    def _saveSnapshot(self, tid, vendor, version, config_a, config_z, params_json, updated_by, updated_at, change_summary):
        """
        保存版本快照（内部方法）
        """
        try:
            snapshot_sql = """
                INSERT INTO arch_template_snapshot
                (tid, vendor, version, config_a, config_z, params, updated_by, updated_at, change_summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                config_a = VALUES(config_a),
                config_z = VALUES(config_z),
                params = VALUES(params),
                updated_by = VALUES(updated_by),
                updated_at = VALUES(updated_at),
                change_summary = VALUES(change_summary)
            """
            self.cursor.execute(snapshot_sql, (
                tid, vendor, version, config_a, config_z, params_json,
                updated_by, updated_at, change_summary or ""
            ))
        except Exception as err:
            logger.error(f"保存快照失败: {err}")

    def getSnapshot(self, data):
        """
        获取指定版本快照
        :param data: {tid: str, vendor: str, version: int}
        :return: {tid, vendor, version, config_a, config_z, params, updated_by, updated_at, change_summary} 或 "failed"
        """
        data = waf(data)
        try:
            if "tid" not in data or "vendor" not in data or "version" not in data:
                logger.error("参数不足: tid, vendor, version")
                return "failed"

            sql = """
                SELECT tid, vendor, version, config_a, config_z, params, updated_by, updated_at, change_summary
                FROM arch_template_snapshot
                WHERE tid = %s AND vendor = %s AND version = %s
            """
            self.cursor.execute(sql, (data["tid"], data["vendor"], data["version"]))
            row = self.cursor.fetchone()

            if not row:
                return "failed"

            proper = ["tid", "vendor", "version", "config_a", "config_z", "params", "updated_by", "updated_at", "change_summary"]
            snapshot = {}
            for i, key in enumerate(proper):
                val = row[i]
                if key == "params" and val:
                    snapshot[key] = json.loads(val) if isinstance(val, str) else val
                else:
                    snapshot[key] = val

            return snapshot

        except Exception as err:
            logger.error(f"获取版本快照失败: {err}")
            return "failed"

    def getSnapshotList(self, data):
        """
        获取某个模板某个厂商的版本历史
        :param data: {tid: str, vendor: str}
        :return: [{version, updated_by, updated_at, change_summary}] 或 "failed"
        """
        data = waf(data)
        try:
            if "tid" not in data or "vendor" not in data:
                logger.error("参数不足: tid, vendor")
                return "failed"

            sql = """
                SELECT version, updated_by, updated_at, change_summary
                FROM arch_template_snapshot
                WHERE tid = %s AND vendor = %s
                ORDER BY version DESC
            """
            self.cursor.execute(sql, (data["tid"], data["vendor"]))
            rows = self.cursor.fetchall()

            result = []
            for row in rows:
                result.append({
                    "version": row[0],
                    "updated_by": row[1],
                    "updated_at": row[2],
                    "change_summary": row[3] or ""
                })

            return result

        except Exception as err:
            logger.error(f"获取版本历史失败: {err}")
            return "failed"
