from daos.database import mysqldb_netops
from utils.utils import waf
import time
import logging


# 配置日志
logger = logging.getLogger(__name__)
'''
drop table IF EXISTS alarm_list;
create table alarm_list(
alarm_id bigint COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '告警ID',
ip varchar(300) COLLATE utf8_bin NOT NULL COMMENT '设备IP',
hostname varchar(300) COLLATE utf8_bin NOT NULL COMMENT '设备名称',
alarm_type varchar(40) COLLATE utf8_bin NOT NULL COMMENT '告警分类，日志、指标、其他',
group_label varchar(100) COLLATE utf8_bin NOT NULL COMMENT '分组标签 hash',
msg varchar(500) COLLATE utf8_bin NOT NULL COMMENT '原始信息',
group_name varchar(100) COLLATE utf8_bin NOT NULL COMMENT '分组名称',
alarm_object varchar(100) COLLATE utf8_bin NOT NULL COMMENT '告警对象',
keyword varchar(100) COLLATE utf8_bin NOT NULL COMMENT '关键字',
status varchar(1) COLLATE utf8_bin NOT NULL COMMENT '状态0=待处理 1=已确认 2=已处理 3=忽略 4=屏蔽',
create_time varchar(10) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '创建时间',
primary key(alarm_id)
);


drop table IF EXISTS alarm_log;
create table alarm_log(
log_id bigint COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '记录ID',
alarm_id bigint COLLATE utf8_bin NOT NULL COMMENT '规则ID',
handler varchar(100) COLLATE utf8_bin NOT NULL COMMENT '处理人',
msg  varchar(300) COLLATE utf8_bin NOT NULL COMMENT '处理内容',
create_time varchar(10) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '创建时间',
primary key(log_id)
);

'''

class AlarmDB(mysqldb_netops):
    def addAlarmList(self, data):
        try:
            check_params = ["ip", "hostname", "alarm_type", "group_label", "msg", "group_name",
                            "alarm_object", "keyword"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"

            timestamp = data.get("create_time", int(time.time()))
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["ip"], data["hostname"], data["alarm_type"], data["group_label"], data["msg"],
                             data["group_name"],data["alarm_object"],data["keyword"],"0", str(timestamp)))
            sql = '''
            insert into alarm_list(ip,hostname,alarm_type,group_label,msg,group_name,alarm_object,keyword,status,create_time)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
            '''
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======AlarmDB addAlarmList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


    def delAlarmList(self, data):
        data = waf(data)
        if "alarm_id" in data.keys():
            sql = "delete from alarm_list where alarm_id='{}'".format(int(data["alarm_id"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======AlarmDB delAlarmList error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"


    def updateAlarmList(self, data):
        data = waf(data)
        # ip,hostname,alarm_type,group_label,msg,group_name,alarm_object,keyword,status,create_time
        if "alarm_id" in data.keys():
            conditions = []
            params = []

            update_key = ["status"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])

            if len(conditions) > 0:
                sql = "update alarm_list set " + ",".join(conditions) + " where alarm_id='{}'".format(int(data["alarm_id"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======AlarmDB updateAlarmList error========\n{}".format(str(err)))
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"


    def getAlarmList(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "ip_reg", "value":"ip"},
            {"key": "msg_reg", "value": "msg"},
            {"key": "hostname_reg", "value": "hostname"},
            {"key": "group_name_reg", "value": "group_name"},
            {"key": "alarm_object_reg", "value": "alarm_object"},
            {"key": "keyword_reg", "value": "keyword"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append("{}".format(key_item["value"]) + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["alarm_type", "alarm_id", "status"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("{}".format(key) + "='" + str(data[key]) + "'")

        sql = '''
                select alarm_id,ip,hostname,alarm_type,group_label,msg,group_name,alarm_object,keyword,
                status,create_time from alarm_list '''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["alarm_id", "ip", "hostname", "alarm_type", "group_label", "msg", "group_name",
                  "alarm_object", "keyword", "status", "create_time"]
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
            logger.error("======AlarmDB getAlarmList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


    def addAlarmLog(self, data):
        try:
            check_params = ["alarm_id", "handler", "msg"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            timestamp = int(time.time())
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["alarm_id"], data["handler"], data["msg"], str(timestamp)))
            sql = '''
            insert into alarm_log(alarm_id,handler,msg,create_time)
            values(%s,%s,%s,%s);
            '''
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======AlarmDB addAlarmLog error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delAlarmLog(self, data):
        data = waf(data)
        if "log_id" in data.keys():
            sql = "delete from alarm_log where log_id='{}'".format(int(data["log_id"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======AlarmDB delAlarmLog error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def getAlarmLog(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "msg_reg", "value": "msg"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append("{}".format(key_item["value"]) + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["alarm_id"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("{}".format(key) + "='" + str(data[key]) + "'")

        sql = '''
                select log_id,alarm_id,handler,msg,create_time from alarm_log '''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["log_id", "alarm_id", "handler", "msg", "create_time"]
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
            logger.error("======AlarmDB getAlarmLog error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


    def getAlarmListGroup(self, data):
        data = waf(data)
        conditions = []

if __name__ == '__main__':
    aa = AlarmDB()

    li = aa.getAlarmList({})
    group_dict = {}
    for item in li:
        if item["group_label"] not in group_dict.keys():
            group_dict[item["group_label"]] = []
        group_dict[item["group_label"]].append(item)

    for group_label in group_dict.keys():
        print(group_label)
        print(group_dict[group_label][0]["group_name"], group_dict[group_label][0]["alarm_object"], group_dict[group_label][0]["keyword"])
        for item in group_dict[group_label]:
            print(item["msg"].strip(), item["create_time"])