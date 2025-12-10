from daos.database import mysqldb_netops
from utils.utils import waf
import logging


# 配置日志
logger = logging.getLogger(__name__)
'''
drop table IF EXISTS roles;
create table roles(
rid varchar(40) COLLATE utf8_bin NOT NULL COMMENT '角色ID',
name varchar(40) COLLATE utf8_bin NOT NULL COMMENT '角色名',
descr varchar(64) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '角色描述',
primary key(rid)
);

drop table IF EXISTS role_pages;
create table role_pages(
rid varchar(40) COLLATE utf8_bin NOT NULL COMMENT '角色ID',
page_id bigint COLLATE utf8_bin NOT NULL COMMENT '页面ID',
privilege varchar(1) COLLATE utf8_bin NOT NULL DEFAULT '0'  COMMENT '页面权限 0 只读 1读写',
primary key(rid, page_id)
);
'''
class RolesDB(mysqldb_netops):
    def addRole(self, data):
        try:
            check_params = ["rid", "name", "descr"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["rid"], data["name"], data["descr"]))
            sql = 'insert into roles(rid,name,descr)values(%s,%s,%s);'
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======RolesDB addroles error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delRole(self, data):
        data = waf(data)
        if "rid" in data.keys():
            sql = "delete from roles where rid='{}'".format(str(data["rid"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======RolesDB delroles error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def updateRole(self, data):
        data = waf(data)
        # rid, name, descr
        if "rid" in data.keys():
            conditions = []
            params = []

            update_key = ["name", "descr"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])

            if len(conditions) > 0:
                sql = "update roles set " + ",".join(conditions) + " where rid='{}'".format(str(data["rid"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======RolesDB updateroles error========\n{}".format(str(err)))
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"

    def getRoleList(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "name_reg", "value": "name"},
            {"key": "rid_reg", "value": "rid"}
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append(key_item["value"] + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["rid"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = '''select rid,name,descr from roles '''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["rid", "name", "descr"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as err:
            logger.error("======RolesDB getroles error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


    # 页面权限
    def addRolePage(self, data):
        data = waf(data)
        try:
            check_params = ["rid", "page_id", "privilege"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["rid"], data["page_id"], data["privilege"]))
            sql = 'insert into role_pages(rid,page_id,privilege)values(%s,%s,%s);'
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======RolesDB addrole_page error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateRolePage(self, data):
        data = waf(data)
        # rid, page_id, privilege
        if "rid" in data.keys() and "page_id" in data.keys():
            conditions = []
            params = []

            update_key = ["privilege"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])

            if len(conditions) > 0:
                sql = "update role_pages set " + ",".join(conditions) + " where rid='{}' and page_id='{}'".format(str(data["rid"]),str(data["page_id"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======RolesDB update role_page error========\n{}".format(str(err)))
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"

    def delRolePage(self, data):
        data = waf(data)
        conditions = []
        if "rid" in data.keys():
            conditions.append("rid='{}'".format(str(data["rid"])))
        if "page_id" in data.keys():
            conditions.append("page_id='{}'".format(str(data["page_id"])))
        if len(conditions) > 0:
            sql = "delete from role_pages where " + " and ".join(conditions)
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======RolesDB delrole_page error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def getRolePage(self, data):
        data = waf(data)
        conditions = []

        serach_eq_key = ["rid"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = '''select rid,page_id,privilege from role_pages '''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["rid", "page_id", "privilege"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as err:
            logger.error("======RolesDB get role page error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()



if __name__ == '__main__':
    aa = RolesDB()
    ret = aa.addRole({"rid":"system", "name":"系统管理", "descr":'管理员权限'})
    print(ret)