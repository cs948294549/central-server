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
group_label varchar(100) COLLATE utf8_bin NOT NULL COMMENT '分组标签 hash',
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

    def updateAlarmListByGroup(self, data):
        data = waf(data)
        print(data)
        # ip,hostname,alarm_type,group_label,msg,group_name,alarm_object,keyword,status,create_time
        if "group_labels" in data.keys():
            conditions = []
            params = []

            group_list_str = ",".join([f"'{label}'" for label in data["group_labels"]])

            update_key = ["status"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])

            if len(conditions) > 0:
                sql = "update alarm_list set " + ",".join(conditions) + " where group_label in ({})".format(str(group_list_str))
                print(sql)
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======AlarmDB updateAlarmListByGroup error========\n{}".format(str(err)))
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

        serach_eq_key = ["alarm_type", "alarm_id", "status", "group_label"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("{}".format(key) + "='" + str(data[key]) + "'")

        sql = '''
                select alarm_id,ip,hostname,alarm_type,group_label,msg,group_name,alarm_object,keyword,
                status,create_time from alarm_list '''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        print(sql)

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
            check_params = ["group_label", "handler", "msg"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            timestamp = int(time.time())
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["group_label"], data["handler"], data["msg"], str(timestamp)))
            sql = '''
            insert into alarm_log(group_label,handler,msg,create_time)
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

        serach_eq_key = ["group_label"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("{}".format(key) + "='" + str(data[key]) + "'")

        sql = '''
                select log_id,group_label,handler,msg,create_time from alarm_log '''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["log_id", "group_label", "handler", "msg", "create_time"]
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

    def addAlarmLogByGroup(self, data):
        try:
            check_params = ["group_labels", "handler", "msg"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"

            timestamp = int(time.time())
            sqlParam = []
            for g_label in data["group_labels"]:
                sqlParam.append((g_label, data["handler"], data["msg"], str(timestamp)))
            sql = '''
            insert into alarm_log(group_label,handler,msg,create_time)
            values(%s,%s,%s,%s);
            '''
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======AlarmDB addAlarmLog many error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


    def getAlarmListCurrent(self):
        sql = '''
        SELECT 
            a.group_label,a.ip,a.hostname,a.alarm_type,a.group_name,a.alarm_object,a.keyword,
            b.group_label_count,b.start_time,b.end_time
        FROM (
            SELECT
                group_label,MAX(ip) AS ip,
                MAX(hostname) AS hostname,
                MAX(alarm_type) AS alarm_type,
                MAX(group_name) AS group_name,
                MAX(alarm_object) AS alarm_object,
                MAX(keyword) AS keyword
	        FROM  alarm_list
	            where status='0'
	        GROUP BY group_label
            ) a
        LEFT JOIN (
            SELECT 
                group_label, COUNT(1) AS group_label_count,
                min(create_time) AS start_time,
                max(create_time) AS end_time
            FROM alarm_list
            GROUP BY group_label
            ) b ON a.group_label = b.group_label;'''
        proper = ["group_label", "ip", "hostname", "alarm_type", "group_name","alarm_object","keyword", "counter", "start_time", "end_time"]
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
            logger.error("======AlarmDB getAlarmListCurrent error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getAlarmListHistory(self, data):
        # 必须圈定时间
        if "start_time" not in data.keys() and "end_time" not in data.keys():
            logger.warning("======AlarmDB getAlarmListHistory waning========\n{}".format("查询缺少时间范围"))
            return "failed"
        time_range = int(data["end_time"]) - int(data["start_time"])
        if time_range >= 86401:
            logger.warning("======AlarmDB getAlarmListHistory waning========\n{}".format("告警时间跨度过大"))
            return "failed"

        conditions = []
        serach_reg_key = [
            {"key": "ip_reg", "value": "ip"},
            {"key": "hostname_reg", "value": "hostname"},
            {"key": "alarm_object_reg", "value": "alarm_object"},
            {"key": "keyword_reg", "value": "keyword"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append("{}".format(key_item["value"]) + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["group_label", "alarm_type"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("{}".format(key) + "='" + str(data[key]) + "'")

        if "start_time" in data.keys():
            conditions.append("create_time>='" + str(data["start_time"]) + "'")
        if "end_time" in data.keys():
            conditions.append("create_time<='" + str(data["end_time"]) + "'")

        sql = '''
        SELECT 
            a.group_label,a.ip,a.hostname,a.alarm_type,a.group_name,a.alarm_object,a.keyword,
            b.group_label_count,b.start_time,b.end_time
        FROM (
            SELECT
                group_label,MAX(ip) AS ip,
                MAX(hostname) AS hostname,
                MAX(alarm_type) AS alarm_type,
                MAX(group_name) AS group_name,
                MAX(alarm_object) AS alarm_object,
                MAX(keyword) AS keyword
            FROM  alarm_list
                where {}
            GROUP BY group_label
            ) a
        LEFT JOIN (
            SELECT 
                group_label, COUNT(1) AS group_label_count,
                min(create_time) AS start_time,
                max(create_time) AS end_time
            FROM alarm_list
            GROUP BY group_label
            ) b ON a.group_label = b.group_label;'''.format(" and ".join(conditions))
        proper = ["group_label", "ip", "hostname", "alarm_type", "group_name", "alarm_object", "keyword", "counter",
                  "start_time", "end_time"]
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
            logger.error("======AlarmDB getAlarmListHistory error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

if __name__ == '__main__':
    aa = AlarmDB()

    # li = aa.getAlarmList({})
    # group_dict = {}
    # for item in li:
    #     if item["group_label"] not in group_dict.keys():
    #         group_dict[item["group_label"]] = []
    #     group_dict[item["group_label"]].append(item)
    #
    # for group_label in group_dict.keys():
    #     print(group_label)
    #     print(group_dict[group_label][0]["group_name"], group_dict[group_label][0]["alarm_object"], group_dict[group_label][0]["keyword"])
    #     for item in group_dict[group_label]:
    #         print(item["msg"].strip(), item["create_time"])
    import json
    li = aa.getAlarmListHistory({"start_time": int(time.time())-86400, "end_time": int(time.time())})
    group_dict = {}
    for item in li:
        if item["ip"] not in group_dict.keys():
            group_dict[item["ip"]] = {
                "ip": item["ip"],
                "hostname": item["hostname"],
                "alarm_dict": []
            }
        group_dict[item["ip"]]["alarm_dict"].append(item)

    print(json.dumps(group_dict, indent=4, ensure_ascii=False))
