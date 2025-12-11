from daos.database import mysqldb_netops
from utils.utils import waf
import time
import logging


# 配置日志
logger = logging.getLogger(__name__)
'''
drop table IF EXISTS users;
create table users(
username varchar(40) COLLATE utf8_bin NOT NULL COMMENT '用户名',
identify varchar(64) COLLATE utf8_bin NOT NULL COMMENT '密码hash或API key',
subname varchar(40) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '中文名',
phone varchar(20) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '电话',
mail varchar(50) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '邮箱',
rid varchar(40) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '角色ID',
update_time varchar(10) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '最近更新时间',
last_login varchar(10) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '最近登陆时间',
primary key(username)
);
'''
class UsersDB(mysqldb_netops):
    def addUser(self, data):
        try:
            check_params = ["username", "identify", "subname", "phone", "mail", "rid"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            timestamp = int(time.time())
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["username"], data["identify"], data["subname"], data["phone"], data["mail"], data["rid"], str(timestamp), str(timestamp)))
            sql = 'insert into users(username,identify,subname,phone,mail,rid,update_time,last_login)values(%s,%s,%s,%s,%s,%s,%s,%s);'
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======UserDB adduser error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delUser(self, data):
        data = waf(data)
        if "username" in data.keys():
            sql = "delete from users where username='{}'".format(str(data["username"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======UserDB deluser error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def updateUser(self, data):
        data = waf(data)
        # username, identify, subame, phone, mail, rid
        if "username" in data.keys():
            conditions = []
            params = []

            update_key = ["identify", "subname", "phone", "mail", "rid", "last_login"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])
                    if key == "identify":
                        conditions.append("update_time = %s")
                        params.append(str(int(time.time())))


            if len(conditions) > 0:
                sql = "update users set " + ",".join(conditions) + " where username='{}'".format(str(data["username"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======UserDB updateuser error========\n{}".format(str(err)))
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"

    def defaultRoleByRole(self, data):
        data = waf(data)
        # username, identify, subame, phone, mail, rid
        if "rid" in data.keys():
            sql = "update users set rid='default'  where rid='{}'".format(str(data["rid"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======UserDB default role error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()

    def getUser(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "username_reg", "value": "username"},
            {"key": "rid_reg", "value": "rid"}
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append("users.{}".format(key_item["value"]) + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["username", "rid"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("users.{}".format(key) + "='" + str(data[key]) + "'")

        sql = '''
        select users.username,users.identify,users.subname,users.phone,users.mail,roles.rid,users.update_time,users.last_login,roles.name,roles.descr from users 
        left join roles on users.rid = roles.rid'''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["username", "identify", "subname", "phone", "mail", "rid", "update_time", "last_login", "role_name", "role_descr"]
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
            logger.error("======UserDB getuser error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


if __name__ == '__main__':
    # aa = UsersDB()
    #
    # ret = aa.addUser({
    #     "username": "admin",
    #     "identify": "4340591ea641d101104b653dd27b01fd",
    #     "subame": "管理员",
    #     "phone": "",
    #     "mail": "",
    #     "rid": "system"
    # })
    # print(ret)

    aa = UsersDB()
    res = aa.getUser({"username": 'admin'})
    print(res)
