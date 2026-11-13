from daos.database import mysqldb_netops
from utils.utils import waf
import time
import logging

logger = logging.getLogger(__name__)
'''
五张表的 CREATE TABLE 见 projects/switchlog/sql/schema.sql，由 switchlog
管线维护表结构，这里只做增删改查，不建表。

syslog_black_list    L2黑名单，解析前拦截
syslog_rule          L3匹配规则，(vendor,mnemonic) -> event_code
syslog_event         L5事件属性，事件码的全网统一行为
syslog_severity_rule L5事件定级，(event_code, 设备) -> severity
syslog_mute_rule     L8告警静默
'''


class SyslogRuleDB(mysqldb_netops):
    # ================= syslog_black_list =================

    def addBlackList(self, data):
        check_params = ["pattern", "descr"]
        for i in check_params:
            if i not in data.keys():
                logger.error("======SyslogRuleDB addBlackList 参数不足========\n{}".format(str(i)))
                return "failed"
        try:
            data = waf(data)
            timestamp = str(int(time.time()))
            sql = '''
            insert into syslog_black_list(pattern,scope,ip,ignore_case,enabled,descr,update_time)
            values(%s,%s,%s,%s,%s,%s,%s)
            '''
            self.cursor.execute(sql, (
                data["pattern"], data.get("scope", "mnemonic"), data.get("ip", ""),
                1 if data.get("ignore_case") else 0, 1 if data.get("enabled", True) else 0,
                data["descr"], timestamp
            ))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB addBlackList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delBlackList(self, data):
        data = waf(data)
        if "rule_id" not in data.keys():
            return "failed"
        sql = "delete from syslog_black_list where rule_id=%s"
        try:
            self.cursor.execute(sql, (int(data["rule_id"]),))
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB delBlackList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateBlackList(self, data):
        data = waf(data)
        if "rule_id" not in data.keys():
            return "failed"
        conditions = ["update_time = %s"]
        params = [str(int(time.time()))]
        update_key = ["pattern", "scope", "ip", "descr"]
        for key in update_key:
            if key in data.keys():
                conditions.append(key + " = %s")
                params.append(data[key])
        bool_key = ["ignore_case", "enabled"]
        for key in bool_key:
            if key in data.keys():
                conditions.append(key + " = %s")
                params.append(1 if data[key] else 0)

        sql = "update syslog_black_list set " + ",".join(conditions) + " where rule_id=%s"
        params.append(int(data["rule_id"]))
        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB updateBlackList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getBlackList(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "pattern_reg", "value": "pattern"},
            {"key": "descr_reg", "value": "descr"},
            {"key": "ip_reg", "value": "ip"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append(key_item["value"] + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["rule_id", "scope", "enabled"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = ("select rule_id,pattern,scope,ip,ignore_case,enabled,descr,"
               "hit_count,last_hit_time,update_time from syslog_black_list")
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + " order by rule_id"
        proper = ["rule_id", "pattern", "scope", "ip", "ignore_case", "enabled", "descr",
                  "hit_count", "last_hit_time", "update_time"]
        return self._fetchAll(sql, proper, ["pattern", "descr"])

    # ================= syslog_rule =================

    def addRule(self, data):
        check_params = ["mnemonic", "match_type", "event_code", "descr"]
        for i in check_params:
            if i not in data.keys():
                logger.error("======SyslogRuleDB addRule 参数不足========\n{}".format(str(i)))
                return "failed"
        try:
            data = waf(data)
            timestamp = str(int(time.time()))
            sql = '''
            insert into syslog_rule(vendor,mnemonic,match_type,pattern,body_match,event_code,
            object_regex,priority,enabled,descr,update_time)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            '''
            self.cursor.execute(sql, (
                data.get("vendor", "*"), data["mnemonic"], data["match_type"],
                data.get("pattern", ""), data.get("body_match", ""), data["event_code"],
                data.get("object_regex", ""), int(data.get("priority", 100)),
                1 if data.get("enabled", True) else 0, data["descr"], timestamp
            ))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB addRule error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delRule(self, data):
        data = waf(data)
        if "rule_id" not in data.keys():
            return "failed"
        sql = "delete from syslog_rule where rule_id=%s"
        try:
            self.cursor.execute(sql, (int(data["rule_id"]),))
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB delRule error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateRule(self, data):
        data = waf(data)
        if "rule_id" not in data.keys():
            return "failed"
        conditions = ["update_time = %s"]
        params = [str(int(time.time()))]
        update_key = ["vendor", "mnemonic", "match_type", "pattern", "body_match",
                      "event_code", "object_regex", "descr"]
        for key in update_key:
            if key in data.keys():
                conditions.append(key + " = %s")
                params.append(data[key])
        if "priority" in data.keys():
            conditions.append("priority = %s")
            params.append(int(data["priority"]))
        if "enabled" in data.keys():
            conditions.append("enabled = %s")
            params.append(1 if data["enabled"] else 0)

        sql = "update syslog_rule set " + ",".join(conditions) + " where rule_id=%s"
        params.append(int(data["rule_id"]))
        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB updateRule error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getRule(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "mnemonic_reg", "value": "mnemonic"},
            {"key": "pattern_reg", "value": "pattern"},
            {"key": "descr_reg", "value": "descr"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append(key_item["value"] + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["rule_id", "vendor", "event_code", "match_type", "enabled"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = '''select rule_id,vendor,mnemonic,match_type,pattern,body_match,event_code,
        object_regex,priority,enabled,descr,update_time from syslog_rule'''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + " order by priority,rule_id"
        proper = ["rule_id", "vendor", "mnemonic", "match_type", "pattern", "body_match",
                  "event_code", "object_regex", "priority", "enabled", "descr", "update_time"]
        return self._fetchAll(sql, proper, ["pattern", "body_match", "object_regex", "descr"])

    # ================= syslog_event =================

    def addEvent(self, data):
        check_params = ["event_code", "descr"]
        for i in check_params:
            if i not in data.keys():
                logger.error("======SyslogRuleDB addEvent 参数不足========\n{}".format(str(i)))
                return "failed"
        try:
            data = waf(data)
            timestamp = str(int(time.time()))
            sql = '''
            insert into syslog_event(event_code,state,object_type,window_sec,threshold,
            clear_code,descr,enabled,update_time)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s)
            '''
            self.cursor.execute(sql, (
                data["event_code"], data.get("state", "stateless"),
                data.get("object_type", "none"), int(data.get("window_sec", 300)),
                int(data.get("threshold", 1)), data.get("clear_code", ""),
                data["descr"], 1 if data.get("enabled", True) else 0, timestamp
            ))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB addEvent error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delEvent(self, data):
        data = waf(data)
        if "event_code" not in data.keys():
            return "failed"
        sql = "delete from syslog_event where event_code=%s"
        try:
            self.cursor.execute(sql, (data["event_code"],))
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB delEvent error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateEvent(self, data):
        data = waf(data)
        if "event_code" not in data.keys():
            return "failed"
        conditions = ["update_time = %s"]
        params = [str(int(time.time()))]
        update_key = ["state", "object_type", "clear_code", "descr"]
        for key in update_key:
            if key in data.keys():
                conditions.append(key + " = %s")
                params.append(data[key])
        int_key = ["window_sec", "threshold"]
        for key in int_key:
            if key in data.keys():
                conditions.append(key + " = %s")
                params.append(int(data[key]))
        if "enabled" in data.keys():
            conditions.append("enabled = %s")
            params.append(1 if data["enabled"] else 0)

        sql = "update syslog_event set " + ",".join(conditions) + " where event_code=%s"
        params.append(data["event_code"])
        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB updateEvent error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getEvent(self, data):
        data = waf(data)
        conditions = []
        if "event_code_reg" in data.keys():
            conditions.append("event_code regexp '" + str(data["event_code_reg"]) + "'")
        if "descr_reg" in data.keys():
            conditions.append("descr regexp '" + str(data["descr_reg"]) + "'")

        serach_eq_key = ["event_code", "state", "object_type", "enabled"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = '''select event_code,state,object_type,window_sec,threshold,clear_code,
        descr,enabled,update_time from syslog_event'''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + " order by event_code"
        proper = ["event_code", "state", "object_type", "window_sec", "threshold",
                  "clear_code", "descr", "enabled", "update_time"]
        return self._fetchAll(sql, proper, ["descr"])

    # ================= syslog_severity_rule =================

    def addSeverityRule(self, data):
        check_params = ["descr"]
        for i in check_params:
            if i not in data.keys():
                logger.error("======SyslogRuleDB addSeverityRule 参数不足========\n{}".format(str(i)))
                return "failed"
        try:
            data = waf(data)
            timestamp = str(int(time.time()))
            sql = '''
            insert into syslog_severity_rule(event_code,ip_reg,sysname_reg,severity,action,
            priority,enabled,descr,update_time)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s)
            '''
            self.cursor.execute(sql, (
                data.get("event_code", "*"), data.get("ip_reg", ""), data.get("sysname_reg", ""),
                int(data.get("severity", 3)), data.get("action", ""),
                int(data.get("priority", 100)), 1 if data.get("enabled", True) else 0,
                data["descr"], timestamp
            ))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB addSeverityRule error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delSeverityRule(self, data):
        data = waf(data)
        if "rule_id" not in data.keys():
            return "failed"
        sql = "delete from syslog_severity_rule where rule_id=%s"
        try:
            self.cursor.execute(sql, (int(data["rule_id"]),))
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB delSeverityRule error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateSeverityRule(self, data):
        data = waf(data)
        if "rule_id" not in data.keys():
            return "failed"
        conditions = ["update_time = %s"]
        params = [str(int(time.time()))]
        update_key = ["event_code", "ip_reg", "sysname_reg", "action", "descr"]
        for key in update_key:
            if key in data.keys():
                conditions.append(key + " = %s")
                params.append(data[key])
        int_key = ["severity", "priority"]
        for key in int_key:
            if key in data.keys():
                conditions.append(key + " = %s")
                params.append(int(data[key]))
        if "enabled" in data.keys():
            conditions.append("enabled = %s")
            params.append(1 if data["enabled"] else 0)

        sql = "update syslog_severity_rule set " + ",".join(conditions) + " where rule_id=%s"
        params.append(int(data["rule_id"]))
        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB updateSeverityRule error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getSeverityRule(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "ip_reg_reg", "value": "ip_reg"},
            {"key": "sysname_reg_reg", "value": "sysname_reg"},
            {"key": "descr_reg", "value": "descr"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append(key_item["value"] + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["rule_id", "event_code", "severity", "action", "enabled"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = '''select rule_id,event_code,ip_reg,sysname_reg,severity,action,priority,
        enabled,descr,update_time from syslog_severity_rule'''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + " order by priority,rule_id"
        proper = ["rule_id", "event_code", "ip_reg", "sysname_reg", "severity", "action",
                  "priority", "enabled", "descr", "update_time"]
        return self._fetchAll(sql, proper, ["ip_reg", "sysname_reg", "descr"])

    # ================= syslog_mute_rule =================

    def addMuteRule(self, data):
        check_params = ["descr"]
        for i in check_params:
            if i not in data.keys():
                logger.error("======SyslogRuleDB addMuteRule 参数不足========\n{}".format(str(i)))
                return "failed"
        try:
            data = waf(data)
            timestamp = str(int(time.time()))
            sql = '''
            insert into syslog_mute_rule(ip_reg,event_code_reg,object_reg,start_time,end_time,
            enabled,descr,update_time)
            values(%s,%s,%s,%s,%s,%s,%s,%s)
            '''
            self.cursor.execute(sql, (
                data.get("ip_reg", ""), data.get("event_code_reg", ""), data.get("object_reg", ""),
                str(data.get("start_time", "")), str(data.get("end_time", "")),
                1 if data.get("enabled", True) else 0, data["descr"], timestamp
            ))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB addMuteRule error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delMuteRule(self, data):
        data = waf(data)
        if "rule_id" not in data.keys():
            return "failed"
        sql = "delete from syslog_mute_rule where rule_id=%s"
        try:
            self.cursor.execute(sql, (int(data["rule_id"]),))
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB delMuteRule error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateMuteRule(self, data):
        data = waf(data)
        if "rule_id" not in data.keys():
            return "failed"
        conditions = ["update_time = %s"]
        params = [str(int(time.time()))]
        update_key = ["ip_reg", "event_code_reg", "object_reg", "descr"]
        for key in update_key:
            if key in data.keys():
                conditions.append(key + " = %s")
                params.append(data[key])
        time_key = ["start_time", "end_time"]
        for key in time_key:
            if key in data.keys():
                conditions.append(key + " = %s")
                params.append(str(data[key]))
        if "enabled" in data.keys():
            conditions.append("enabled = %s")
            params.append(1 if data["enabled"] else 0)

        sql = "update syslog_mute_rule set " + ",".join(conditions) + " where rule_id=%s"
        params.append(int(data["rule_id"]))
        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======SyslogRuleDB updateMuteRule error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getMuteRule(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "ip_reg_reg", "value": "ip_reg"},
            {"key": "event_code_reg_reg", "value": "event_code_reg"},
            {"key": "descr_reg", "value": "descr"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append(key_item["value"] + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["rule_id", "enabled"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = '''select rule_id,ip_reg,event_code_reg,object_reg,start_time,end_time,
        enabled,descr,hit_count,last_hit_time,update_time from syslog_mute_rule'''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + " order by rule_id"
        proper = ["rule_id", "ip_reg", "event_code_reg", "object_reg", "start_time", "end_time",
                  "enabled", "descr", "hit_count", "last_hit_time", "update_time"]
        return self._fetchAll(sql, proper, ["ip_reg", "event_code_reg", "object_reg", "descr"])

    # ================= 公共 =================

    def _fetchAll(self, sql, proper, unwaf_keys):
        '''
        通用查询执行 + 行转 dict。unwaf_keys 里的字段把 waf() 转义的引号还原，
        避免列表页把存库时转义的 \\' \\" 原样显示给用户
        '''
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        value = i[num] if i[num] != None else ""
                        if proper[num] in unwaf_keys and isinstance(value, str):
                            value = value.replace("\\'", "'").replace('\\"', '"')
                        result[proper[num]] = value
                    results.append(result)
                return results
            else:
                return []
        except Exception as err:
            logger.error("======SyslogRuleDB query error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()
