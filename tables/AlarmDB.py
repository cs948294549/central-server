from daos.database import mysqldb_netops
from utils.utils import waf
import time
import logging


# 配置日志
logger = logging.getLogger(__name__)
'''
alarm_list / alarm_log 由 switchlog 管线写入，表结构见
projects/switchlog/sql/schema.sql，这里只读、只改人工处理状态，不建表。

alarm_list 一行是一个已经聚合好的告警（一个指纹一行）：
    severity   1=P1 2=P2 3=P3
    state      open=告警中 clear=已恢复，由L7状态机维护
    status     人工处理状态 0待处理1已确认2已处理3忽略4屏蔽，只有人点才变
    muted      1=被静默规则压住，不发通知，窗口过了自动恢复
    counter/first_seen/last_seen/clear_time  聚合窗口内的统计

alarm_log 一行是一条原子日志（L6写，只留7天），靠 fingerprint 关联
alarm_list，下钻用 getAlarmLogsByAlarm(alarm_id)。

alarm_handle_log 是人工处理历史，central-server 自建，不属于 switchlog：

CREATE TABLE IF NOT EXISTS alarm_handle_log(
    log_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    alarm_id BIGINT NOT NULL DEFAULT 0 COMMENT '对应alarm_list.alarm_id',
    handler VARCHAR(100) NOT NULL DEFAULT '' COMMENT '处理人',
    status VARCHAR(1) NOT NULL DEFAULT '0' COMMENT '处理后的状态，同alarm_list.status',
    msg VARCHAR(300) NOT NULL DEFAULT '' COMMENT '处理说明',
    create_time VARCHAR(10) NOT NULL DEFAULT '' COMMENT '创建时间(epoch秒)',
    PRIMARY KEY(log_id),
    INDEX idx_alarm_id (alarm_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警人工处理历史';
'''

# alarm_log 的保留天数，和 switchlog 那边的 DEFAULT_LOG_RETENTION_DAYS
# 对齐（projects/switchlog/pipeline/l6_aggregate.py）。
# "日志已过期"的判断按它算
LOG_RETENTION_DAYS = 7

# 按设备查日志的默认返回上限。超了在返回里标 truncated，由调用方提示，
# 不是静默截断 —— 看到 500 条就以为只有 500 条是最糟的情况。
# 带 no_limit=True 时不设上限，全量返回
DEVICE_LOG_DEFAULT_LIMIT = 1000

class AlarmDB(mysqldb_netops):
    # ---------------- alarm_list（读 + 改人工处理状态） ----------------

    def updateAlarmStatus(self, data):
        '''
        只改一条告警的人工处理状态。只有人点才会变，不碰 state/muted 等
        由管线维护的字段
        :param data: {"alarm_id":.., "status":..}
        '''
        data = waf(data)
        if "alarm_id" not in data or "status" not in data:
            return "failed"
        sql = "update alarm_list set status=%s where alarm_id=%s"
        try:
            self.cursor.execute(sql, (data["status"], int(data["alarm_id"])))
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======AlarmDB updateAlarmStatus error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateAlarmStatusByIds(self, data):
        '''
        批量改人工处理状态
        :param data: {"alarm_ids":[1,2,3], "status":".."}
        '''
        data = waf(data)
        if "alarm_ids" not in data or "status" not in data or len(data["alarm_ids"]) <= 0:
            return "failed"
        id_list_str = ",".join([str(int(i)) for i in data["alarm_ids"]])
        sql = "update alarm_list set status=%s where alarm_id in ({})".format(id_list_str)
        try:
            self.cursor.execute(sql, (data["status"],))
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======AlarmDB updateAlarmStatusByIds error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getAlarmList(self, data):
        '''
        通用查询，走各种正则/等值筛选
        '''
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "ip_reg", "value": "ip"},
            {"key": "msg_reg", "value": "msg"},
            {"key": "hostname_reg", "value": "hostname"},
            {"key": "group_name_reg", "value": "group_name"},
            {"key": "alarm_object_reg", "value": "alarm_object"},
            {"key": "keyword_reg", "value": "keyword"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append("{}".format(key_item["value"]) + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["alarm_type", "alarm_id", "status", "state", "fingerprint", "severity"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("{}".format(key) + "='" + str(data[key]) + "'")

        sql = '''
                select alarm_id,ip,hostname,alarm_type,group_label,msg,group_name,alarm_object,keyword,
                fingerprint,vendor,hardware,object_name,object_alias,severity,state,status,
                muted,mute_rule_id,counter,
                first_seen,last_seen,clear_time,create_time from alarm_list '''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        sql = sql + " order by create_time desc"

        proper = ["alarm_id", "ip", "hostname", "alarm_type", "group_label", "msg", "group_name",
                  "alarm_object", "keyword", "fingerprint", "vendor", "hardware", "object_name",
                  "object_alias", "severity", "state", "status", "muted", "mute_rule_id",
                  "counter", "first_seen", "last_seen", "clear_time", "create_time"]
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

    def getAlarmListCurrent(self):
        '''
        当前告警：待处理（status=0）的聚合告警，一行就是一条

        按 status 过滤，不按 state —— 这一页是值班的待办队列，不是
        "当前还断着的东西"的快照：

          * 一个口掉了又自己恢复了（state=clear），但没人看过
            （status=0），照样要留在页面上。按 state='open' 过滤的话
            这种告警会凭空消失，只能去历史页翻 —— 等于漏掉了
          * 反过来，还断着但已经有人处理了（state=open, status=2）的，
            不该再占着待办列表

        state 字段仍然返回，前端用它显示"告警"/"恢复"标签。

        status=5 是 L5 定级规则判定不告警的（系统自动打的，不是人工
        操作），这类压根不该进待办，所以条件写 status='0' 而不是
        status<>'0' 取反。muted 排在前面方便优先看没被压住的
        '''
        sql = '''
        select alarm_id,ip,hostname,alarm_type,group_label,msg,group_name,alarm_object,keyword,
        fingerprint,vendor,hardware,object_name,object_alias,severity,state,status,
        muted,mute_rule_id,counter,
        first_seen,last_seen,clear_time,create_time
        from alarm_list
        where status='0'
        order by muted asc, severity asc, last_seen desc
        '''
        proper = ["alarm_id", "ip", "hostname", "alarm_type", "group_label", "msg", "group_name",
                  "alarm_object", "keyword", "fingerprint", "vendor", "hardware", "object_name",
                  "object_alias", "severity", "state", "status", "muted", "mute_rule_id",
                  "counter", "first_seen", "last_seen", "clear_time", "create_time"]
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
        '''
        历史告警：按 create_time 圈时间范围，不限 state（open/clear都要看）
        '''
        if "start_time" not in data.keys() or "end_time" not in data.keys():
            logger.warning("======AlarmDB getAlarmListHistory waning========\n{}".format("查询缺少时间范围"))
            return "failed"
        time_range = int(data["end_time"]) - int(data["start_time"])
        if time_range >= 86401:
            logger.warning("======AlarmDB getAlarmListHistory waning========\n{}".format("告警时间跨度过大"))
            return "failed"

        data = waf(data)
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

        serach_eq_key = ["fingerprint", "alarm_type", "severity", "state", "status"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append("{}".format(key) + "='" + str(data[key]) + "'")

        conditions.append("create_time>='" + str(data["start_time"]) + "'")
        conditions.append("create_time<='" + str(data["end_time"]) + "'")

        sql = '''
        select alarm_id,ip,hostname,alarm_type,group_label,msg,group_name,alarm_object,keyword,
        fingerprint,vendor,hardware,object_name,object_alias,severity,state,status,
        muted,mute_rule_id,counter,
        first_seen,last_seen,clear_time,create_time
        from alarm_list where {} order by create_time desc
        '''.format(" and ".join(conditions))
        proper = ["alarm_id", "ip", "hostname", "alarm_type", "group_label", "msg", "group_name",
                  "alarm_object", "keyword", "fingerprint", "vendor", "hardware", "object_name",
                  "object_alias", "severity", "state", "status", "muted", "mute_rule_id",
                  "counter", "first_seen", "last_seen", "clear_time", "create_time"]
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

    def getAlarmListByIds(self, data):
        '''
        按 alarm_id 批量取，处理告警提交前的二次确认、导出等场景用
        '''
        data = waf(data)
        if "alarm_ids" not in data.keys() or len(data["alarm_ids"]) <= 0:
            return "failed"
        id_list_str = ",".join([str(int(i)) for i in data["alarm_ids"]])
        sql = '''
        select alarm_id,ip,hostname,alarm_type,group_label,msg,group_name,alarm_object,keyword,
        fingerprint,vendor,hardware,object_name,object_alias,severity,state,status,
        muted,mute_rule_id,counter,
        first_seen,last_seen,clear_time,create_time
        from alarm_list where alarm_id in ({}) order by create_time
        '''.format(id_list_str)
        proper = ["alarm_id", "ip", "hostname", "alarm_type", "group_label", "msg", "group_name",
                  "alarm_object", "keyword", "fingerprint", "vendor", "hardware", "object_name",
                  "object_alias", "severity", "state", "status", "muted", "mute_rule_id",
                  "counter", "first_seen", "last_seen", "clear_time", "create_time"]
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
            logger.error("======AlarmDB getAlarmListByIds error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ---------------- alarm_log（原子日志，只读下钻） ----------------

    def getAlarmLogsByAlarm(self, data):
        '''
        按 alarm_id 下钻到支撑它的原子日志，带 pad_seconds 的时间范围自动从
        alarm_list 取（first_seen ~ clear_time或last_seen），不用调用方自己拼。
        expired=True 表示告警结束时间已经超过 alarm_log 的7天保留期，
        查不到日志是正常现象，不是查询失败。
        :param data: {"alarm_id":.., "limit":200(可选)}
        '''
        data = waf(data)
        if "alarm_id" not in data.keys():
            return "failed"
        limit = int(data.get("limit", 200))
        pad = 2

        head_sql = '''
        select fingerprint, first_seen, last_seen, clear_time
        from alarm_list where alarm_id=%s
        '''
        try:
            self.cursor.execute(head_sql, (int(data["alarm_id"]),))
            head = self.cursor.fetchone()
        except Exception as err:
            logger.error("======AlarmDB getAlarmLogsByAlarm error========\n{}".format(str(err)))
            self.cursor.close()
            self.conn.close()
            return "failed"

        if not head:
            self.cursor.close()
            self.conn.close()
            return None

        fingerprint, first_seen, last_seen, clear_time = head
        start = self._safeInt(first_seen) - pad
        upper = clear_time if clear_time else last_seen
        end = self._safeInt(upper) + pad
        expired = bool(end) and end < int(time.time()) - LOG_RETENTION_DAYS * 86400

        if start <= 0 or end <= 0:
            self.cursor.close()
            self.conn.close()
            return {"logs": [], "truncated": False, "expired": False}

        log_sql = '''
        select log_id, fingerprint, ip, hostname, event_code, alarm_object, severity,
        mnemonic, msg, is_read, ingest_ts
        from alarm_log
        where fingerprint=%s and ingest_ts >= %s and ingest_ts <= %s
        order by ingest_ts limit %s
        '''
        proper = ["log_id", "fingerprint", "ip", "hostname", "event_code", "alarm_object",
                  "severity", "mnemonic", "msg", "is_read", "ingest_ts"]
        try:
            self.cursor.execute(log_sql, (fingerprint, str(start), str(end), limit + 1))
            result1 = self.cursor.fetchall()
            results = []
            for i in result1:
                result = {}
                for num in range(len(proper)):
                    result[proper[num]] = i[num] if i[num] != None else ""
                results.append(result)
            truncated = len(results) > limit
            return {"logs": results[:limit], "truncated": truncated, "expired": expired,
                    "start_ts": start, "end_ts": end, "fingerprint": fingerprint}
        except Exception as err:
            logger.error("======AlarmDB getAlarmLogsByAlarm error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getAlarmLogsByDevice(self, data):
        '''
        按设备取一段时间内的全部原子日志，不限指纹

        和 getAlarmLogsByAlarm 的区别：那个按指纹查，只能看到某一条告警
        自己的日志；这个按 ip 查，这段时间里这台设备所有进了管线的日志
        都在，包括没产生告警的（没到阈值的、被定级规则 ignore 的、噪声
        事件码）。排查"这个口为什么抖"时要看的恰恰是这些上下文 ——
        单条告警的下钻只有 IF_DOWN/IF_UP 两行，看不出中间还夹着速率协商、
        双工变化这些伴生日志。

        **不限时间跨度。** 原来限 1 天，但看板算窗口用的是"这台设备最早
        first_seen ~ 最晚 last_seen"，只要有一条还没恢复的老告警挂着
        （一个口 down 了三天没人管），窗口就超 1 天，点"全部日志"直接被拒。
        真实边界本来就是保留期 —— 再往前查 alarm_log 已经删了。

        量靠条数兜：默认返回 DEVICE_LOG_DEFAULT_LIMIT 条，超了在返回里
        标 truncated=True 并带上 limit，由调用方提示用户。带
        no_limit=True 时不设上限，全量返回。

        **截断时留最近的那批**，不是最早的：排查一个口为什么抖，要看的是
        刚才发生了什么。所以 SQL 倒序取，取完翻回正序 —— 返回给前端的
        logs 仍然是按时间从早到晚排的，只是起点落在"最近 N 条"的那个点上。

        :param data: {"ip":.., "start_ts":.., "end_ts":..,
                      "limit":1000(可选), "no_limit":False(可选)}
        :return: {"logs":[...], "truncated":bool, "limit":实际用的上限(0=不限),
                  "start_ts":.., "end_ts":..}；失败返回 "failed"
        '''
        if "ip" not in data.keys() or "start_ts" not in data.keys() \
                or "end_ts" not in data.keys():
            logger.warning("======AlarmDB getAlarmLogsByDevice warning========\n{}".format(
                "缺少 ip 或时间范围"))
            return "failed"

        start = self._safeInt(data["start_ts"])
        end = self._safeInt(data["end_ts"])
        if start <= 0 or end <= 0 or end < start:
            logger.warning("======AlarmDB getAlarmLogsByDevice warning========\n{}".format(
                "时间范围不合法"))
            return "failed"
        data = waf(data)
        no_limit = bool(data.get("no_limit"))
        limit = 0 if no_limit else int(data.get("limit", DEVICE_LOG_DEFAULT_LIMIT))
        if limit < 0:
            limit = DEVICE_LOG_DEFAULT_LIMIT

        # 倒序取，截断时留下的是**最近**那批。升序 + limit 留下的是最早
        # 那批 —— 排查一个口为什么抖，要看的是刚才发生了什么，不是一周前
        # 那几条。取完在 Python 里翻回正序，展示仍然是按时间从早到晚
        base_sql = '''
        select log_id, fingerprint, ip, hostname, event_code, alarm_object, severity,
        mnemonic, msg, is_read, ingest_ts
        from alarm_log
        where ip=%s and ingest_ts >= %s and ingest_ts <= %s
        order by ingest_ts desc, log_id desc
        '''
        params = [str(data["ip"]), str(start), str(end)]
        if limit > 0:
            # 多取一条用来判断有没有被截断，返回时再切掉
            base_sql += " limit %s"
            params.append(limit + 1)

        proper = ["log_id", "fingerprint", "ip", "hostname", "event_code", "alarm_object",
                  "severity", "mnemonic", "msg", "is_read", "ingest_ts"]
        try:
            self.cursor.execute(base_sql, tuple(params))
            result1 = self.cursor.fetchall()
            results = []
            for i in result1:
                result = {}
                for num in range(len(proper)):
                    result[proper[num]] = i[num] if i[num] != None else ""
                results.append(result)
            truncated = limit > 0 and len(results) > limit
            if truncated:
                logger.warning("======AlarmDB getAlarmLogsByDevice warning========\n"
                               "ip={} 的日志超过 {} 条，只返回最近的（跨度 {} 秒）".format(
                                   data["ip"], limit, end - start))
            # 先切掉多取的那一条（它是更早的，倒序排在末尾），再翻回正序
            logs = results[:limit] if limit > 0 else results
            logs.reverse()
            return {"logs": logs,
                    "truncated": truncated, "limit": limit,
                    "start_ts": start, "end_ts": end}
        except Exception as err:
            logger.error("======AlarmDB getAlarmLogsByDevice error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def markAlarmLogsRead(self, data):
        '''
        :param data: {"log_ids":[1,2,3]} 或 {"fingerprint":.., "start_ts":.., "end_ts":..}
        '''
        data = waf(data)
        if "log_ids" in data.keys() and len(data["log_ids"]) > 0:
            marks = ",".join([str(int(i)) for i in data["log_ids"]])
            sql = "update alarm_log set is_read=1 where log_id in ({})".format(marks)
            params = ()
        elif "fingerprint" in data.keys() and "start_ts" in data.keys() and "end_ts" in data.keys():
            sql = ("update alarm_log set is_read=1 "
                   "where fingerprint=%s and ingest_ts >= %s and ingest_ts <= %s")
            params = (data["fingerprint"], str(data["start_ts"]), str(data["end_ts"]))
        else:
            return "failed"

        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
            return "success"
        except Exception as err:
            self.conn.rollback()
            logger.error("======AlarmDB markAlarmLogsRead error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def markAlarmLogsReadByAlarmIds(self, data):
        '''
        把这批告警对应指纹的原子日志标成已读

        人工处理告警（status 从待处理改成已确认/已处理/忽略/屏蔽）时跟着调。

        **按指纹整批标，不卡时间范围。** 指纹不含时间，所以这会把同一个口
        同一类故障的历史日志一起标掉（alarm_log 只留 7 天，范围就是这 7 天
        以内）。这是有意的：is_read 只是看板上的颜色标记（LogDisplay.vue
        里未读是黄色左标、已读是灰色），不参与任何判断，也没有"只看未读"
        的筛选。按指纹一条 UPDATE 比一个 alarm_id 一条 UPDATE 简单得多，
        走 idx_fingerprint_ts 索引。

        副作用：同一指纹下还有一条没处理的告警时，它的日志也会变灰。
        只是颜色不准，不影响告警本身。

        :param data: {"alarm_ids":[1,2,3]}
        :return: {"fingerprints":涉及几个指纹, "logs":标掉的日志行数}；
                 失败返回 "failed"
        '''
        data = waf(data)
        if "alarm_ids" not in data.keys() or len(data["alarm_ids"]) <= 0:
            logger.warning("======AlarmDB markAlarmLogsReadByAlarmIds warning========\n{}".format(
                "alarm_ids 为空"))
            return "failed"

        id_list_str = ",".join([str(int(i)) for i in data["alarm_ids"]])
        head_sql = '''
        select distinct fingerprint from alarm_list
        where alarm_id in ({}) and fingerprint<>''
        '''.format(id_list_str)
        try:
            self.cursor.execute(head_sql)
            # SQL 里已经 distinct 了，这里再去一遍重：返回的 fingerprints
            # 条数是给调用方看的，不该依赖"数据库一定去过重"这个前提。
            # 顺便挡住 NULL（distinct 不会把 NULL 和 '' 合成一个）
            seen = set()
            fingerprints = []
            for row in (self.cursor.fetchall() or []):
                value = row[0]
                if not value or value in seen:
                    continue
                seen.add(value)
                fingerprints.append(value)
            if not fingerprints:
                # 选中的告警都没有指纹（历史脏数据），没有日志可标
                logger.warning("======AlarmDB markAlarmLogsReadByAlarmIds warning========\n"
                               "alarm_ids={} 取不到指纹".format(data["alarm_ids"]))
                return {"fingerprints": 0, "logs": 0}

            # 一条 UPDATE 批量标。指纹是从库里查出来的 md5，不是用户输入，
            # 但仍然走占位符 —— 不给以后改这段的人留下拼串的样板
            marks = ",".join(["%s"] * len(fingerprints))
            log_sql = ("update alarm_log set is_read=1 "
                       "where fingerprint in ({}) and is_read=0".format(marks))
            self.cursor.execute(log_sql, tuple(fingerprints))
            marked = self.cursor.rowcount
            self.conn.commit()
            return {"fingerprints": len(fingerprints), "logs": marked}
        except Exception as err:
            self.conn.rollback()
            logger.error("======AlarmDB markAlarmLogsReadByAlarmIds error========\n{}".format(
                str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    @staticmethod
    def _safeInt(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    # ---------------- alarm_handle_log（人工处理历史，central-server自建） ----------------

    def addHandleLog(self, data):
        '''
        :param data: {"alarm_id":.., "handler":.., "status":.., "msg":"" (可选)}
        '''
        check_params = ["alarm_id", "handler", "status"]
        for i in check_params:
            if i not in data.keys():
                logger.error("======AlarmDB addHandleLog error 参数不足========\n{}".format(str(i)))
                return "failed"
        try:
            data = waf(data)
            timestamp = str(int(time.time()))
            sql = '''
            insert into alarm_handle_log(alarm_id,handler,status,msg,create_time)
            values(%s,%s,%s,%s,%s)
            '''
            self.cursor.execute(sql, (int(data["alarm_id"]), data["handler"], data["status"],
                                      data.get("msg", ""), timestamp))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======AlarmDB addHandleLog error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def addHandleLogByIds(self, data):
        '''
        批量写处理历史，和 updateAlarmStatusByIds 配套使用
        :param data: {"alarm_ids":[1,2,3], "handler":.., "status":.., "msg":"" (可选)}
        '''
        check_params = ["alarm_ids", "handler", "status"]
        for i in check_params:
            if i not in data.keys():
                logger.error("======AlarmDB addHandleLogByIds error 参数不足========\n{}".format(str(i)))
                return "failed"
        if len(data["alarm_ids"]) <= 0:
            return "failed"
        try:
            data = waf(data)
            timestamp = str(int(time.time()))
            sqlParam = []
            for alarm_id in data["alarm_ids"]:
                sqlParam.append((int(alarm_id), data["handler"], data["status"],
                                 data.get("msg", ""), timestamp))
            sql = '''
            insert into alarm_handle_log(alarm_id,handler,status,msg,create_time)
            values(%s,%s,%s,%s,%s)
            '''
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======AlarmDB addHandleLogByIds error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getHandleLog(self, data):
        '''
        :param data: {"alarm_id":..}
        '''
        data = waf(data)
        if "alarm_id" not in data.keys():
            return "failed"
        sql = '''
        select log_id,alarm_id,handler,status,msg,create_time
        from alarm_handle_log where alarm_id=%s order by create_time
        '''
        proper = ["log_id", "alarm_id", "handler", "status", "msg", "create_time"]
        try:
            self.cursor.execute(sql, (int(data["alarm_id"]),))
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
            logger.error("======AlarmDB getHandleLog error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()
