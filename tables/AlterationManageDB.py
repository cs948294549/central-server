from daos.database import mysqldb_netops
from utils.utils import waf, unwaf
import time
import json
import logging

logger = logging.getLogger(__name__)

'''
-- 工单类型表
CREATE TABLE op_types (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '类型ID',
    name VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '类型名称',
    op_group1 BIGINT COLLATE utf8_bin NULL COMMENT '审批组1',
    op_group2 BIGINT COLLATE utf8_bin NULL COMMENT '审批组2',
    op_group3 BIGINT COLLATE utf8_bin NULL COMMENT '审批组3',
    PRIMARY KEY (pid)
) COMMENT='工单类型配置表';

-- 审批分组表
CREATE TABLE op_groups (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '分组ID',
    name VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '分组名称',
    op_list TEXT COLLATE utf8_bin NULL COMMENT '成员列表(逗号分隔)',
    PRIMARY KEY (pid)
) COMMENT='审批分组表';

-- 工单列表表
CREATE TABLE op_lists (
    op_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '工单ID',
    op_type BIGINT COLLATE utf8_bin NOT NULL COMMENT '工单类型ID',
    title VARCHAR(200) COLLATE utf8_bin NOT NULL COMMENT '工单标题',
    descrip TEXT COLLATE utf8_bin NULL COMMENT '工单描述',
    status VARCHAR(2) COLLATE utf8_bin NOT NULL DEFAULT '00' COMMENT '工单状态',
    username VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '创建人',
    assigner VARCHAR(40) COLLATE utf8_bin NULL COMMENT '指定执行人',
    is_auto TINYINT NULL DEFAULT 0 COMMENT '是否自动执行',
    popo VARCHAR(100) COLLATE utf8_bin NULL COMMENT '通知群组',
    create_time VARCHAR(10) COLLATE utf8_bin NULL COMMENT '创建时间',
    update_time VARCHAR(10) COLLATE utf8_bin NULL COMMENT '更新时间',
    begin_time VARCHAR(10) COLLATE utf8_bin NULL COMMENT '变更开始时间',
    finish_time VARCHAR(10) COLLATE utf8_bin NULL COMMENT '变更结束时间',
    cur_group TEXT COLLATE utf8_bin NULL COMMENT '当前审批组成员列表',
    cur_user VARCHAR(40) COLLATE utf8_bin NULL COMMENT '当前处理人',
    step_name VARCHAR(50) COLLATE utf8_bin NULL COMMENT '当前步骤名称',
    step_id INT NULL COMMENT '当前步骤ID',
    node_info TEXT COLLATE utf8_bin NULL COMMENT '流程节点信息(JSON)',
    PRIMARY KEY (op_id),
    INDEX idx_status (status),
    INDEX idx_username (username),
    INDEX idx_create_time (create_time)
) COMMENT='工单列表表';

-- 设备命令表
CREATE TABLE op_devs (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    op_id BIGINT COLLATE utf8_bin NOT NULL COMMENT '工单ID',
    batch INT NULL DEFAULT 1 COMMENT '批次号',
    ip VARCHAR(50) COLLATE utf8_bin NOT NULL COMMENT '设备IP',
    sysname VARCHAR(100) COLLATE utf8_bin NULL COMMENT '设备名称',
    model VARCHAR(100) COLLATE utf8_bin NULL COMMENT '设备型号',
    asset_no VARCHAR(200) COLLATE utf8_bin NULL COMMENT '资产编号',
    status VARCHAR(2) COLLATE utf8_bin NULL COMMENT '执行状态',
    cmd_exec TEXT COLLATE utf8_bin NULL COMMENT '执行命令',
    cmd_roll TEXT COLLATE utf8_bin NULL COMMENT '回滚命令',
    result TEXT COLLATE utf8_bin NULL COMMENT '执行结果',
    tag VARCHAR(50) COLLATE utf8_bin NULL COMMENT '标签',
    is_auto TINYINT NULL DEFAULT 0 COMMENT '是否自动执行',
    pre_check TEXT COLLATE utf8_bin NULL COMMENT '预检查结果',
    timestamp VARCHAR(10) COLLATE utf8_bin NULL COMMENT '时间戳',
    PRIMARY KEY (pid),
    INDEX idx_op_id (op_id)
) COMMENT='设备命令执行表';

-- 审批记录表
CREATE TABLE op_approve (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    op_id BIGINT COLLATE utf8_bin NOT NULL COMMENT '工单ID',
    op_group BIGINT COLLATE utf8_bin NOT NULL COMMENT '审批分组ID',
    username VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '审批人',
    status VARCHAR(2) COLLATE utf8_bin NULL COMMENT '审批状态',
    timestamp VARCHAR(10) COLLATE utf8_bin NULL COMMENT '审批时间',
    PRIMARY KEY (pid),
    INDEX idx_op_id (op_id)
) COMMENT='审批记录表';

-- 操作日志表
CREATE TABLE op_logs (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    op_id BIGINT COLLATE utf8_bin NOT NULL COMMENT '工单ID',
    tag VARCHAR(2) COLLATE utf8_bin NULL COMMENT '日志标签',
    msg LONGTEXT COLLATE utf8_bin NOT NULL COMMENT '日志内容',
    username VARCHAR(40) COLLATE utf8_bin NULL COMMENT '操作人',
    timestamp VARCHAR(10) COLLATE utf8_bin NULL COMMENT '操作时间',
    PRIMARY KEY (pid),
    INDEX idx_op_id (op_id)
) COMMENT='操作日志表';

-- 通知群组表
CREATE TABLE op_notify (
    pid BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    name VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '群组名称',
    descrip VARCHAR(200) COLLATE utf8_bin NULL COMMENT '描述',
    target VARCHAR(100) COLLATE utf8_bin NOT NULL COMMENT '群组号',
    PRIMARY KEY (pid)
) COMMENT='通知群组表';
'''


class AlterationManageDB(mysqldb_netops):
    """变更工单数据库操作类"""

    # ==================== 工单类型管理 ====================

    def add_op_type(self, data):
        """添加工单类型"""
        try:
            data = waf(data)
            sql = '''INSERT INTO op_types (name, op_group1, op_group2, op_group3)
                     VALUES (%s, %s, %s, %s)'''
            params = (
                data["name"],
                data.get("op_group1"),
                data.get("op_group2"),
                data.get("op_group3")
            )
            self.cursor.execute(sql, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            logger.error(f"添加工单类型失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def update_op_type(self, type_id, data):
        """更新工单类型"""
        try:
            data = waf(data)
            sql = '''UPDATE op_types
                     SET name = %s, op_group1 = %s, op_group2 = %s, op_group3 = %s
                     WHERE pid = %s'''
            params = (
                data["name"],
                data.get("op_group1"),
                data.get("op_group2"),
                data.get("op_group3"),
                type_id
            )
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"更新工单类型失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_op_type(self, type_id):
        """删除工单类型"""
        try:
            sql = "DELETE FROM op_types WHERE pid = %s"
            self.cursor.execute(sql, (type_id,))
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"删除工单类型失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_op_type_list(self, data):
        """查询工单类型列表"""
        try:
            data = waf(data)
            conditions = []
            params = []

            if "pid" in data:
                conditions.append("pid = %s")
                params.append(data["pid"])
            if "name" in data:
                conditions.append("name LIKE %s")
                params.append(f"%{data['name']}%")

            sql = "SELECT pid, name, op_group1, op_group2, op_group3 FROM op_types"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY pid DESC"

            proper = ["pid", "name", "op_group1", "op_group2", "op_group3"]
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
            logger.error(f"查询工单类型列表失败: {err}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 审批分组管理 ====================

    def add_op_group(self, data):
        """添加审批分组"""
        try:
            data = waf(data)
            sql = "INSERT INTO op_groups (name, op_list) VALUES (%s, %s)"
            params = (data["name"], data.get("op_list", ""))
            self.cursor.execute(sql, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            logger.error(f"添加审批分组失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def update_op_group(self, group_id, data):
        """更新审批分组"""
        try:
            data = waf(data)
            sql = "UPDATE op_groups SET name = %s, op_list = %s WHERE pid = %s"
            params = (data["name"], data.get("op_list", ""), group_id)
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"更新审批分组失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_op_group(self, group_id):
        """删除审批分组"""
        try:
            sql = "DELETE FROM op_groups WHERE pid = %s"
            self.cursor.execute(sql, (group_id,))
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"删除审批分组失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_op_group_list(self, data):
        """查询审批分组列表"""
        try:
            data = waf(data)
            conditions = []
            params = []

            if "pid" in data:
                conditions.append("pid = %s")
                params.append(data["pid"])
            if "name" in data:
                conditions.append("name LIKE %s")
                params.append(f"%{data['name']}%")

            sql = "SELECT pid, name, op_list FROM op_groups"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY pid DESC"

            proper = ["pid", "name", "op_list"]
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
            logger.error(f"查询审批分组列表失败: {err}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 通知群组管理 ====================

    def add_notify_group(self, data):
        """添加通知群组"""
        try:
            data = waf(data)
            sql = "INSERT INTO op_notify (name, descrip, target) VALUES (%s, %s, %s)"
            params = (data["name"], data.get("descrip", ""), data["target"])
            self.cursor.execute(sql, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            logger.error(f"添加通知群组失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def update_notify_group(self, notify_id, data):
        """更新通知群组"""
        try:
            data = waf(data)
            sql = "UPDATE op_notify SET name = %s, descrip = %s, target = %s WHERE pid = %s"
            params = (data["name"], data.get("descrip", ""), data["target"], notify_id)
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"更新通知群组失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_notify_group(self, notify_id):
        """删除通知群组"""
        try:
            sql = "DELETE FROM op_notify WHERE pid = %s"
            self.cursor.execute(sql, (notify_id,))
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"删除通知群组失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_notify_group_list(self, data):
        """查询通知群组列表"""
        try:
            data = waf(data)
            conditions = []
            params = []

            if "pid" in data:
                conditions.append("pid = %s")
                params.append(data["pid"])
            if "name" in data:
                conditions.append("name LIKE %s")
                params.append(f"%{data['name']}%")

            sql = "SELECT pid, name, descrip, target FROM op_notify"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY pid DESC"

            proper = ["pid", "name", "descrip", "target"]
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
            logger.error(f"查询通知群组列表失败: {err}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 工单管理 ====================

    def add_op_order(self, data):
        """创建工单"""
        try:
            data = waf(data)
            current_time = str(int(time.time()))
            sql = '''INSERT INTO op_lists
                     (op_type, title, descrip, status, username, assigner, is_auto, popo,
                      create_time, update_time, begin_time, finish_time, cur_group, cur_user,
                      step_name, step_id, node_info)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
            params = (
                data["op_type"],
                data["title"],
                data.get("descrip", ""),
                data.get("status", "00"),
                data["username"],
                data.get("assigner", ""),
                data.get("is_auto", 0),
                data.get("popo", ""),
                current_time,
                current_time,
                data.get("begin_time", ""),
                data.get("finish_time", ""),
                data.get("cur_group", ""),
                data.get("cur_user", ""),
                data.get("step_name", ""),
                data.get("step_id", 0),
                data.get("node_info", "")
            )
            self.cursor.execute(sql, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            logger.error(f"创建工单失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def update_op_order(self, op_id, data):
        """更新工单"""
        try:
            data = waf(data)
            current_time = str(int(time.time()))

            update_fields = []
            params = []

            for key in ['op_type', 'title', 'descrip', 'status', 'assigner', 'is_auto',
                       'popo', 'begin_time', 'finish_time', 'cur_group', 'cur_user',
                       'step_name', 'step_id', 'node_info']:
                if key in data:
                    update_fields.append(f"{key} = %s")
                    params.append(data[key])

            if not update_fields:
                return "success"

            update_fields.append("update_time = %s")
            params.append(current_time)
            params.append(op_id)

            sql = f"UPDATE op_lists SET {', '.join(update_fields)} WHERE op_id = %s"
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"更新工单失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_op_order(self, op_id):
        """删除工单"""
        try:
            sql = "DELETE FROM op_lists WHERE op_id = %s"
            self.cursor.execute(sql, (op_id,))
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"删除工单失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_op_order_by_id(self, op_id):
        """根据ID获取工单详情"""
        try:
            sql = """SELECT op_id, op_type, title, descrip, status, username, assigner,
                     is_auto, popo, create_time, update_time, begin_time, finish_time,
                     cur_group, cur_user, step_name, step_id, node_info
                     FROM op_lists WHERE op_id = %s"""
            proper = ["op_id", "op_type", "title", "descrip", "status", "username", "assigner",
                     "is_auto", "popo", "create_time", "update_time", "begin_time", "finish_time",
                     "cur_group", "cur_user", "step_name", "step_id", "node_info"]
            self.cursor.execute(sql, (op_id,))
            result1 = self.cursor.fetchone()

            if result1:
                result = {}
                for num in range(len(proper)):
                    value = result1[num] if result1[num] != None else ""
                    # node_info 需要 unwaf 处理
                    if proper[num] == "node_info" and value:
                        value = unwaf(value)
                    result[proper[num]] = value
                return result
            return None
        except Exception as err:
            logger.error(f"获取工单详情失败: {err}")
            return None
        finally:
            self.cursor.close()
            self.conn.close()

    def get_op_order_list(self, data):
        """查询工单列表"""
        try:
            data = waf(data)
            conditions = []
            params = []

            if "op_id" in data:
                conditions.append("op_id = %s")
                params.append(data["op_id"])
            if "title" in data:
                conditions.append("title LIKE %s")
                params.append(f"%{data['title']}%")
            if "status" in data:
                if isinstance(data["status"], list):
                    placeholders = ','.join(['%s'] * len(data["status"]))
                    conditions.append(f"status IN ({placeholders})")
                    params.extend(data["status"])
                else:
                    conditions.append("status = %s")
                    params.append(data["status"])
            if "username" in data:
                conditions.append("username = %s")
                params.append(data["username"])
            if "op_type" in data:
                conditions.append("op_type = %s")
                params.append(data["op_type"])
            if "create_time_start" in data:
                conditions.append("create_time >= %s")
                params.append(data["create_time_start"])
            if "create_time_end" in data:
                conditions.append("create_time <= %s")
                params.append(data["create_time_end"])
            if "cur_user" in data:
                conditions.append("FIND_IN_SET(%s, cur_group) > 0")
                params.append(data["cur_user"])

            sql = """SELECT op_id, op_type, title, descrip, status, username, assigner,
                     is_auto, popo, create_time, update_time, begin_time, finish_time,
                     cur_group, cur_user, step_name, step_id, node_info
                     FROM op_lists"""
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY op_id DESC"

            if "limit" in data:
                sql += " LIMIT %s"
                params.append(data["limit"])

            proper = ["op_id", "op_type", "title", "descrip", "status", "username", "assigner",
                     "is_auto", "popo", "create_time", "update_time", "begin_time", "finish_time",
                     "cur_group", "cur_user", "step_name", "step_id", "node_info"]
            self.cursor.execute(sql, params)
            result1 = self.cursor.fetchall()
            results = []

            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        value = i[num] if i[num] != None else ""
                        # node_info 需要 unwaf 处理
                        if proper[num] == "node_info" and value:
                            value = unwaf(value)
                        result[proper[num]] = value
                    results.append(result)

            return results
        except Exception as err:
            logger.error(f"查询工单列表失败: {err}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 设备命令管理 ====================

    def add_op_device(self, data):
        """添加设备"""
        try:
            data = waf(data)
            current_time = str(int(time.time()))
            sql = '''INSERT INTO op_devs
                     (op_id, batch, ip, sysname, model, asset_no, status, cmd_exec, cmd_roll,
                      result, tag, is_auto, pre_check, timestamp)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
            params = (
                data["op_id"],
                data.get("batch", 1),
                data["ip"],
                data.get("sysname", ""),
                data.get("model", ""),
                data.get("asset_no", ""),
                data.get("status", "00"),
                data.get("cmd_exec", ""),
                data.get("cmd_roll", ""),
                data.get("result", ""),
                data.get("tag", ""),
                data.get("is_auto", 0),
                data.get("pre_check", ""),
                current_time
            )
            self.cursor.execute(sql, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            logger.error(f"添加设备失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def update_op_device(self, dev_id, data):
        """更新设备"""
        try:
            data = waf(data)
            current_time = str(int(time.time()))

            update_fields = []
            params = []

            for key in ['batch', 'ip', 'sysname', 'model', 'asset_no', 'status', 'cmd_exec',
                       'cmd_roll', 'result', 'tag', 'is_auto', 'pre_check']:
                if key in data:
                    update_fields.append(f"{key} = %s")
                    params.append(data[key])

            if not update_fields:
                return "success"

            update_fields.append("timestamp = %s")
            params.append(current_time)
            params.append(dev_id)

            sql = f"UPDATE op_devs SET {', '.join(update_fields)} WHERE pid = %s"
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"更新设备失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_op_device(self, dev_id):
        """删除单个设备"""
        try:
            sql = "DELETE FROM op_devs WHERE pid = %s"
            self.cursor.execute(sql, (dev_id,))
            self.conn.commit()
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"删除设备失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_op_devices_by_order(self, op_id):
        """删除工单的所有设备"""
        try:
            sql = "DELETE FROM op_devs WHERE op_id = %s"
            self.cursor.execute(sql, (op_id,))
            self.conn.commit()
            deleted_count = self.cursor.rowcount
            logger.info(f"删除工单 {op_id} 的 {deleted_count} 个设备")
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"批量删除设备失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_op_device_list(self, op_id):
        """获取工单的设备列表"""
        try:
            sql = """SELECT pid, op_id, batch, ip, sysname, model, asset_no, status,
                     cmd_exec, cmd_roll, result, tag, is_auto, pre_check, timestamp
                     FROM op_devs WHERE op_id = %s ORDER BY batch, pid"""
            proper = ["pid", "op_id", "batch", "ip", "sysname", "model", "asset_no", "status",
                     "cmd_exec", "cmd_roll", "result", "tag", "is_auto", "pre_check", "timestamp"]
            self.cursor.execute(sql, (op_id,))
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
            logger.error(f"获取设备列表失败: {err}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_op_device_by_id(self, dev_id):
        """根据设备ID获取设备详细信息"""
        try:
            sql = """SELECT pid, op_id, batch, ip, sysname, model, asset_no, status,
                     cmd_exec, cmd_roll, result, tag, is_auto, pre_check, timestamp
                     FROM op_devs WHERE pid = %s"""
            proper = ["pid", "op_id", "batch", "ip", "sysname", "model", "asset_no", "status",
                     "cmd_exec", "cmd_roll", "result", "tag", "is_auto", "pre_check", "timestamp"]
            self.cursor.execute(sql, (dev_id,))
            result1 = self.cursor.fetchone()

            if result1:
                result = {}
                for num in range(len(proper)):
                    result[proper[num]] = result1[num] if result1[num] != None else ""
                return result
            else:
                return None
        except Exception as err:
            logger.error(f"获取设备信息失败: {err}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 审批记录管理 ====================

    def add_op_approval(self, data):
        """添加审批记录"""
        try:
            data = waf(data)
            current_time = str(int(time.time()))
            sql = '''INSERT INTO op_approve (op_id, op_group, username, status, timestamp)
                     VALUES (%s, %s, %s, %s, %s)'''
            params = (data["op_id"], data["op_group"], data["username"], data["status"], current_time)
            self.cursor.execute(sql, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            logger.error(f"添加审批记录失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_op_approval_list(self, op_id):
        """获取工单的审批记录"""
        try:
            sql = """SELECT pid, op_id, op_group, username, status, timestamp
                     FROM op_approve WHERE op_id = %s ORDER BY timestamp DESC"""
            proper = ["pid", "op_id", "op_group", "username", "status", "timestamp"]
            self.cursor.execute(sql, (op_id,))
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
            logger.error(f"获取审批记录失败: {err}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_op_approvals_by_order(self, op_id):
        """删除工单的所有审批记录"""
        try:
            sql = "DELETE FROM op_approve WHERE op_id = %s"
            self.cursor.execute(sql, (op_id,))
            self.conn.commit()
            deleted_count = self.cursor.rowcount
            logger.info(f"删除工单 {op_id} 的 {deleted_count} 条审批记录")
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"批量删除审批记录失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 操作日志管理 ====================

    def add_op_log(self, data):
        """添加操作日志"""
        try:
            data = waf(data)
            current_time = str(int(time.time()))
            sql = '''INSERT INTO op_logs (op_id, tag, msg, username, timestamp)
                     VALUES (%s, %s, %s, %s, %s)'''
            params = (data["op_id"], data.get("tag", "11"), data["msg"], data.get("username", ""), current_time)
            self.cursor.execute(sql, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            logger.error(f"添加操作日志失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def get_username_subname(self, username):
        """根据登录用户名查询中文名"""
        try:
            sql = "SELECT subname FROM users WHERE username = %s"
            self.cursor.execute(sql, (username,))
            row = self.cursor.fetchone()
            return row[0] if row and row[0] else ""
        except Exception as e:
            logger.error(f"查询用户中文名失败: {e}")
            return ""
        finally:
            self.cursor.close()
            self.conn.close()

    def get_op_log_list(self, op_id):
        """获取工单的操作日志"""
        try:
            sql = """SELECT pid, op_id, tag, msg, username, timestamp
                     FROM op_logs WHERE op_id = %s ORDER BY timestamp DESC"""
            proper = ["pid", "op_id", "tag", "msg", "username", "timestamp"]
            self.cursor.execute(sql, (op_id,))
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
            logger.error(f"获取操作日志失败: {err}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delete_op_logs_by_order(self, op_id):
        """删除工单的所有操作日志"""
        try:
            sql = "DELETE FROM op_logs WHERE op_id = %s"
            self.cursor.execute(sql, (op_id,))
            self.conn.commit()
            deleted_count = self.cursor.rowcount
            logger.info(f"删除工单 {op_id} 的 {deleted_count} 条操作日志")
            return "success"
        except Exception as e:
            self.conn.rollback()
            logger.error(f"批量删除操作日志失败: {e}")
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

