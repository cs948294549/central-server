from daos.database import mysqldb_netops
from utils.utils import waf
import json
import logging

logger = logging.getLogger(__name__)

'''
-- 流量看板数据表
CREATE TABLE flow_data (
    flow_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '看板ID',
    flow_name VARCHAR(100) NOT NULL COMMENT '看板名称',
    category_types JSON COMMENT '分类标签数组，如["按机房","IDC-A","核心网络"]',
    description TEXT COMMENT '描述',
    flow_json LONGTEXT NOT NULL COMMENT '面板配置',
    created_by VARCHAR(50) COMMENT '创建人',
    created_at VARCHAR(20) COMMENT '创建时间',
    updated_by VARCHAR(50) COMMENT '最后修改人',
    updated_at VARCHAR(20) COMMENT '更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    UNIQUE KEY uk_name (flow_name),
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流量看板数据表';
'''


class FlowBoardDB(mysqldb_netops):
    """流量看板数据库操作类"""

    def get_flow_list(self):
        """
        获取看板列表（不包含flow_json字段）
        :return: 列表数据或"failed"
        """
        try:
            sql = """SELECT flow_id, flow_name, category_types, description,
                     created_by, created_at, updated_by, updated_at, version
                     FROM flow_data
                     ORDER BY updated_at DESC"""

            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []

            if len(result1) > 0:
                proper = ["flow_id", "flow_name", "category_types", "description",
                          "created_by", "created_at", "updated_by", "updated_at", "version"]
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        if proper[num] == "category_types" and i[num]:
                            try:
                                result[proper[num]] = json.loads(i[num]) if isinstance(i[num], str) else i[num]
                            except:
                                result[proper[num]] = []
                        else:
                            result[proper[num]] = i[num] if i[num] is not None else ""
                    results.append(result)

            return results

        except Exception as err:
            logger.error("======FlowBoardDB get_flow_list error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_flow_by_id(self, flow_id):
        """
        根据ID获取看板详情（包含flow_json）
        :param flow_id: 看板ID
        :return: 看板数据或"failed"
        """
        try:
            sql = """SELECT flow_id, flow_name, category_types, description,
                     flow_json, created_by, created_at, updated_by, updated_at, version
                     FROM flow_data
                     WHERE flow_id = %s"""

            self.cursor.execute(sql, (flow_id,))
            result1 = self.cursor.fetchone()

            if result1:
                proper = ["flow_id", "flow_name", "category_types", "description",
                          "flow_json", "created_by", "created_at", "updated_by", "updated_at", "version"]
                result = {}
                for num in range(len(proper)):
                    if proper[num] in ["category_types", "flow_json"] and result1[num]:
                        try:
                            result[proper[num]] = json.loads(result1[num]) if isinstance(result1[num], str) else result1[num]
                        except:
                            result[proper[num]] = {} if proper[num] == "flow_json" else []
                    else:
                        result[proper[num]] = result1[num] if result1[num] is not None else ""
                return result
            else:
                return "failed"

        except Exception as err:
            logger.error("======FlowBoardDB get_flow_by_id error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_flow_by_name(self, flow_name):
        """
        根据名称获取看板
        :param flow_name: 看板名称
        :return: 看板数据或"failed"
        """
        try:
            sql = """SELECT flow_id, flow_name, version
                     FROM flow_data
                     WHERE flow_name = %s"""

            self.cursor.execute(sql, (flow_name,))
            result1 = self.cursor.fetchone()

            if result1:
                return {
                    "flow_id": result1[0],
                    "flow_name": result1[1],
                    "version": result1[2]
                }
            else:
                return "failed"

        except Exception as err:
            logger.error("======FlowBoardDB get_flow_by_name error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def create_flow(self, data):
        """
        创建看板
        :param data: 看板数据
        :return: flow_id或"failed"
        """
        try:
            check_params = ["flow_name"]
            for i in check_params:
                if i not in data.keys():
                    logger.error("参数不足: {}".format(i))
                    return "failed"

            data = waf(data)

            category_types = json.dumps(data.get("category_types", []), ensure_ascii=False)
            flow_json = data.get("flow_json", "{}")
            if isinstance(flow_json, (dict, list)):
                flow_json = json.dumps(flow_json, ensure_ascii=False)

            sql = """INSERT INTO flow_data
                     (flow_name, category_types, description, flow_json,
                      created_by, created_at, updated_by, updated_at, version)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""

            sqlParam = (
                data["flow_name"],
                category_types,
                data.get("description", ""),
                flow_json,
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
            logger.error("======FlowBoardDB create_flow error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def update_flow(self, data):
        """
        更新看板
        :param data: 看板数据（必须包含flow_id）
        :return: success或"failed"
        """
        try:
            if "flow_id" not in data.keys():
                logger.error("参数不足: flow_id")
                return "failed"

            data = waf(data)

            update_fields = []
            update_values = []

            if "flow_name" in data:
                update_fields.append("flow_name = %s")
                update_values.append(data["flow_name"])

            if "category_types" in data:
                category_types = json.dumps(data["category_types"], ensure_ascii=False) if isinstance(data["category_types"], list) else data["category_types"]
                update_fields.append("category_types = %s")
                update_values.append(category_types)

            if "description" in data:
                update_fields.append("description = %s")
                update_values.append(data["description"])

            if "flow_json" in data:
                flow_json = json.dumps(data["flow_json"], ensure_ascii=False) if isinstance(data["flow_json"], (dict, list)) else data["flow_json"]
                update_fields.append("flow_json = %s")
                update_values.append(flow_json)

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

            update_values.append(data["flow_id"])

            sql = "UPDATE flow_data SET " + ", ".join(update_fields) + " WHERE flow_id = %s"

            self.cursor.execute(sql, tuple(update_values))
            self.conn.commit()

            return "success"

        except Exception as err:
            logger.error("======FlowBoardDB update_flow error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_flow(self, flow_id):
        """
        删除看板
        :param flow_id: 看板ID
        :return: success或"failed"
        """
        try:
            sql = "DELETE FROM flow_data WHERE flow_id = %s"

            self.cursor.execute(sql, (flow_id,))
            self.conn.commit()

            return "success"

        except Exception as err:
            logger.error("======FlowBoardDB delete_flow error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()
