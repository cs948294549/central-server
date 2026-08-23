from daos.database import mysqldb_netops
from utils.utils import waf
import json
import logging

logger = logging.getLogger(__name__)

'''
-- 拓扑数据表
CREATE TABLE topology_data (
    topology_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '拓扑ID',
    topology_name VARCHAR(100) NOT NULL COMMENT '拓扑名称',
    category_types JSON COMMENT '分类标签数组，如["按机房","IDC-A","核心网络"]',
    description TEXT COMMENT '描述',
    topology_json LONGTEXT NOT NULL COMMENT '拓扑JSON数据',
    created_by VARCHAR(50) COMMENT '创建人',
    created_at VARCHAR(20) COMMENT '创建时间',
    updated_by VARCHAR(50) COMMENT '最后修改人',
    updated_at VARCHAR(20) COMMENT '更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    UNIQUE KEY uk_name (topology_name),
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='拓扑数据表';
'''


class TopologyDB(mysqldb_netops):
    """拓扑数据库操作类"""

    def get_topology_list(self):
        """
        获取拓扑列表（不包含topology_json字段）
        :return: 列表数据或"failed"
        """
        try:
            sql = """SELECT topology_id, topology_name, category_types, description,
                     created_by, created_at, updated_by, updated_at, version
                     FROM topology_data
                     ORDER BY updated_at DESC"""

            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []

            if len(result1) > 0:
                proper = ["topology_id", "topology_name", "category_types", "description",
                          "created_by", "created_at", "updated_by", "updated_at", "version"]
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        if proper[num] == "category_types" and i[num]:
                            # 解析JSON字段
                            try:
                                result[proper[num]] = json.loads(i[num]) if isinstance(i[num], str) else i[num]
                            except:
                                result[proper[num]] = []
                        else:
                            result[proper[num]] = i[num] if i[num] is not None else ""
                    results.append(result)

            return results

        except Exception as err:
            logger.error("======TopologyDB get_topology_list error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_topology_by_id(self, topology_id):
        """
        根据ID获取拓扑详情（包含topology_json）
        :param topology_id: 拓扑ID
        :return: 拓扑数据或"failed"
        """
        try:
            sql = """SELECT topology_id, topology_name, category_types, description,
                     topology_json, created_by, created_at, updated_by, updated_at, version
                     FROM topology_data
                     WHERE topology_id = %s"""

            self.cursor.execute(sql, (topology_id,))
            result1 = self.cursor.fetchone()

            if result1:
                proper = ["topology_id", "topology_name", "category_types", "description",
                          "topology_json", "created_by", "created_at", "updated_by", "updated_at", "version"]
                result = {}
                for num in range(len(proper)):
                    if proper[num] in ["category_types", "topology_json"] and result1[num]:
                        # 解析JSON字段
                        try:
                            result[proper[num]] = json.loads(result1[num]) if isinstance(result1[num], str) else result1[num]
                        except:
                            result[proper[num]] = {} if proper[num] == "topology_json" else []
                    else:
                        result[proper[num]] = result1[num] if result1[num] is not None else ""
                return result
            else:
                return "failed"

        except Exception as err:
            logger.error("======TopologyDB get_topology_by_id error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_topology_by_name(self, topology_name):
        """
        根据名称获取拓扑
        :param topology_name: 拓扑名称
        :return: 拓扑数据或"failed"
        """
        try:
            sql = """SELECT topology_id, topology_name, version
                     FROM topology_data
                     WHERE topology_name = %s"""

            self.cursor.execute(sql, (topology_name,))
            result1 = self.cursor.fetchone()

            if result1:
                return {
                    "topology_id": result1[0],
                    "topology_name": result1[1],
                    "version": result1[2]
                }
            else:
                return "failed"

        except Exception as err:
            logger.error("======TopologyDB get_topology_by_name error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def create_topology(self, data):
        """
        创建拓扑
        :param data: 拓扑数据
        :return: topology_id或"failed"
        """
        try:
            check_params = ["topology_name"]
            for i in check_params:
                if i not in data.keys():
                    logger.error("参数不足: {}".format(i))
                    return "failed"

            data = waf(data)

            # 处理JSON字段
            category_types = json.dumps(data.get("category_types", []), ensure_ascii=False)
            topology_json = data.get("topology_json", "{}")
            if isinstance(topology_json, dict):
                topology_json = json.dumps(topology_json, ensure_ascii=False)

            sql = """INSERT INTO topology_data
                     (topology_name, category_types, description, topology_json,
                      created_by, created_at, updated_by, updated_at, version)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""

            sqlParam = (
                data["topology_name"],
                category_types,
                data.get("description", ""),
                topology_json,
                data.get("created_by", ""),
                data.get("created_at", ""),
                data.get("updated_by", ""),
                data.get("updated_at", ""),
                data.get("version", 1)
            )

            self.cursor.execute(sql, sqlParam)
            self.conn.commit()

            return self.cursor.lastrowid

        except Exception as err:
            logger.error("======TopologyDB create_topology error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def update_topology(self, data):
        """
        更新拓扑
        :param data: 拓扑数据（必须包含topology_id）
        :return: success或"failed"
        """
        try:
            if "topology_id" not in data.keys():
                logger.error("参数不足: topology_id")
                return "failed"

            data = waf(data)

            # 构建更新字段
            update_fields = []
            update_values = []

            if "topology_name" in data:
                update_fields.append("topology_name = %s")
                update_values.append(data["topology_name"])

            if "category_types" in data:
                category_types = json.dumps(data["category_types"], ensure_ascii=False) if isinstance(data["category_types"], list) else data["category_types"]
                update_fields.append("category_types = %s")
                update_values.append(category_types)

            if "description" in data:
                update_fields.append("description = %s")
                update_values.append(data["description"])

            if "topology_json" in data:
                topology_json = json.dumps(data["topology_json"], ensure_ascii=False) if isinstance(data["topology_json"], dict) else data["topology_json"]
                update_fields.append("topology_json = %s")
                update_values.append(topology_json)

            if "updated_by" in data:
                update_fields.append("updated_by = %s")
                update_values.append(data["updated_by"])

            if "updated_at" in data:
                update_fields.append("updated_at = %s")
                update_values.append(data["updated_at"])

            if "version" in data:
                update_fields.append("version = %s")
                update_values.append(data["version"])

            if len(update_fields) == 0:
                logger.warning("没有需要更新的字段")
                return "failed"

            # 添加WHERE条件
            update_values.append(data["topology_id"])

            sql = "UPDATE topology_data SET " + ", ".join(update_fields) + " WHERE topology_id = %s"

            self.cursor.execute(sql, tuple(update_values))
            self.conn.commit()

            return "success"

        except Exception as err:
            logger.error("======TopologyDB update_topology error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_topology(self, topology_id):
        """
        删除拓扑
        :param topology_id: 拓扑ID
        :return: success或"failed"
        """
        try:
            sql = "DELETE FROM topology_data WHERE topology_id = %s"

            self.cursor.execute(sql, (topology_id,))
            self.conn.commit()

            return "success"

        except Exception as err:
            logger.error("======TopologyDB delete_topology error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()
