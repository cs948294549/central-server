from daos.database import mysqldb_netops
from utils.utils import waf
import time
import logging


# 配置日志
logger = logging.getLogger(__name__)
'''
drop table IF EXISTS syslog_black_list;
create table syslog_black_list(
rule_id bigint COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '规则ID',
pattern varchar(300) COLLATE utf8_bin NOT NULL COMMENT '规则',
descr varchar(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '规则描述',
update_time varchar(10) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '最近更新时间',
primary key(rule_id)
);

drop table IF EXISTS syslog_merge_list;
create table syslog_merge_list(
rule_id bigint COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '规则ID',
group_name varchar(100) COLLATE utf8_bin NOT NULL COMMENT '分组名称',
pattern varchar(300) COLLATE utf8_bin NOT NULL COMMENT '规则',
descr varchar(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '规则描述',
update_time varchar(10) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '最近更新时间',
primary key(rule_id)
);
'''

class SyslogDB(mysqldb_netops):
    def addBlackList(self, data):
        try:
            check_params = ["pattern", "descr"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            timestamp = int(time.time())
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["pattern"], data["descr"], str(timestamp)))
            sql = 'insert into syslog_black_list(pattern,descr,update_time)values(%s,%s,%s);'
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogDB add black list error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delBlackList(self, data):
        data = waf(data)
        if "rule_id" in data.keys():
            sql = "delete from syslog_black_list where rule_id='{}'".format(int(data["rule_id"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======SyslogDB del blacklist error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def updateBlackList(self, data):
        data = waf(data)
        # "pattern", "descr"
        if "rule_id" in data.keys():
            conditions = []
            params = []

            conditions.append("update_time = %s")
            params.append(str(int(time.time())))


            update_key = ["pattern", "descr"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])


            if len(conditions) > 0:
                sql = "update syslog_black_list set " + ",".join(conditions) + " where rule_id='{}'".format(int(data["rule_id"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======SyslogDB update black list error========\n{}".format(str(err)))
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"

    def addMergeList(self, data):
        try:
            check_params = ["group_name", "pattern", "descr"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            timestamp = int(time.time())
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["group_name"], data["pattern"], data["descr"], str(timestamp)))
            sql = 'insert into syslog_merge_list(group_name,pattern,descr,update_time)values(%s,%s,%s,%s);'
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogDB add merge list error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delMergeList(self, data):
        data = waf(data)
        if "rule_id" in data.keys():
            sql = "delete from syslog_merge_list where rule_id='{}'".format(int(data["rule_id"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======SyslogDB del merge_list error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def updateMergeList(self, data):
        data = waf(data)
        # "group_name", "pattern", "descr"
        if "rule_id" in data.keys():
            conditions = []
            params = []

            conditions.append("update_time = %s")
            params.append(str(int(time.time())))


            update_key = ["group_name", "pattern", "descr"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])


            if len(conditions) > 0:
                sql = "update syslog_merge_list set " + ",".join(conditions) + " where rule_id='{}'".format(int(data["rule_id"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======SyslogDB update merge list error========\n{}".format(str(err)))
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"

    def getBlackList(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key":"pattern_reg", "value":"pattern"},
            {"key": "descr_reg", "value": "descr"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append("{}".format(key_item["value"]) + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["rule_id"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("{}".format(key) + "='" + str(data[key]) + "'")

        sql = '''
                select rule_id,pattern,descr,update_time from syslog_black_list'''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["rule_id", "pattern", "descr", "update_time"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                        if proper[num] == "pattern":
                            result[proper[num]] = result[proper[num]].replace("\\'", "'").replace('\\"', '"')
                    results.append(result)
                return results
            else:
                return []
        except Exception as err:
            logger.error("======SyslogDB getBlackList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getMergeList(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key":"pattern_reg", "value":"pattern"},
            {"key": "descr_reg", "value": "descr"},
            {"key": "group_name_reg", "value": "group_name"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append("{}".format(key_item["value"]) + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["rule_id", "group_name"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("{}".format(key) + "='" + str(data[key]) + "'")

        sql = '''
                select rule_id,group_name,pattern,descr,update_time from syslog_merge_list'''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions) + " order by group_name,rule_id "
        proper = ["rule_id", "group_name", "pattern", "descr", "update_time"]
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
            logger.error("======SyslogDB getMergeList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()



if __name__ == '__main__':
    # bl = SyslogDB()
    # bl.addBlackList({"pattern": '"a"', "descr": "过程控制"})

    # bl.ping()
    # bl.addBlackList({"pattern": "/SSH", "descr": "登陆控制"})
    #
    # bl.ping()
    # bl.addBlackList({"pattern": "/SHELL_CMD", "descr": "登陆控制"})
    #
    # bl.ping()
    # bl.addBlackList({"pattern": "SHELL_LOGIN|SHELL_LOGOUT", "descr": "登陆控制"})
    #
    #
    #
    # ml = SyslogDB()
    # ml.addMergeList({"group_name":"change_passwd","pattern": "/system/change_passwd", "descr": "修改密码"})
    #
    # ml.ping()
    # ml.addMergeList({"group_name": "login", "pattern": "/system/login", "descr": "登陆"})
    #
    # ml.ping()
    # ml.addMergeList({"group_name": "login", "pattern": "/SSH", "descr": "登陆"})
    #
    # ml.ping()
    # ml.addMergeList({"group_name": "up/down状态", "pattern": "PHY_UPDOWN|LINK_UPDOWN", "descr": "端口状态"})
    #
    # ml.ping()
    # ml.addMergeList({"group_name": "lagg_status", "pattern": "LAGG_", "descr": "聚合口状态"})

    bl=SyslogDB()
    res = bl.getBlackList({})
    print(res)

