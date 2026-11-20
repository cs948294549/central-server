from tables.AlarmDB import AlarmDB
from tables.SyslogRuleDB import SyslogRuleDB
import json
import logging
from utils.utils import decorator_checkparams

logger = logging.getLogger(__name__)

# ============== syslog_black_list（L2黑名单） ==============
@decorator_checkparams(key_array=["pattern", "descr"])
def add_blacklist(data):
    try:
        db = SyslogRuleDB()
        ret = db.addBlackList(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def del_blacklist(data):
    try:
        db = SyslogRuleDB()
        ret = db.delBlackList({"rule_id": data["rule_id"]})
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def update_blacklist(data):
    try:
        db = SyslogRuleDB()
        ret = db.updateBlackList(data)
        if ret != "failed":
            return {"status":"success","message": "修改成功", "data": ret}
        else:
            return {"status": "failed", "message": "修改失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_blacklist(data):
    try:
        db = SyslogRuleDB()
        ret = db.getBlackList(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}


# ============== syslog_rule（L3解析规则） ==============
@decorator_checkparams(key_array=["mnemonic", "match_type", "event_code", "descr"])
def add_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.addRule(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def del_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.delRule({"rule_id": data["rule_id"]})
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def update_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.updateRule(data)
        if ret != "failed":
            return {"status":"success","message": "修改成功", "data": ret}
        else:
            return {"status": "failed", "message": "修改失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.getRule(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}


# ============== syslog_event（L5事件属性） ==============
@decorator_checkparams(key_array=["event_code", "descr"])
def add_event(data):
    try:
        db = SyslogRuleDB()
        ret = db.addEvent(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["event_code"])
def del_event(data):
    try:
        db = SyslogRuleDB()
        ret = db.delEvent({"event_code": data["event_code"]})
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["event_code"])
def update_event(data):
    try:
        db = SyslogRuleDB()
        ret = db.updateEvent(data)
        if ret != "failed":
            return {"status":"success","message": "修改成功", "data": ret}
        else:
            return {"status": "failed", "message": "修改失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_event(data):
    try:
        db = SyslogRuleDB()
        ret = db.getEvent(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}


# ============== syslog_severity_rule（L5事件定级） ==============
@decorator_checkparams(key_array=["descr"])
def add_severity_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.addSeverityRule(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def del_severity_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.delSeverityRule({"rule_id": data["rule_id"]})
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def update_severity_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.updateSeverityRule(data)
        if ret != "failed":
            return {"status":"success","message": "修改成功", "data": ret}
        else:
            return {"status": "failed", "message": "修改失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_severity_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.getSeverityRule(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}


# ============== syslog_mute_rule（L8告警静默） ==============
@decorator_checkparams(key_array=["descr"])
def add_mute_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.addMuteRule(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def del_mute_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.delMuteRule({"rule_id": data["rule_id"]})
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def update_mute_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.updateMuteRule(data)
        if ret != "failed":
            return {"status":"success","message": "修改成功", "data": ret}
        else:
            return {"status": "failed", "message": "修改失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_mute_rule(data):
    try:
        db = SyslogRuleDB()
        ret = db.getMuteRule(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_current_alarm(data):
    '''
    当前告警：alarm_list 一行已经是一个聚合好的告警，这里只按 (ip, hostname)
    分组给前端做两层折叠展示，不再是"多条日志合成一组"的旧模型
    '''
    try:
        alarm_db = AlarmDB()
        li = alarm_db.getAlarmListCurrent()
        if li != "failed":
            group_alarm = {}
            for item in li:
                label = "{}_{}".format(item["ip"], item["hostname"])
                if label not in group_alarm.keys():
                    # vendor/hardware 是设备级信息，同一设备下所有告警都一样，
                    # 放外层分组头只展示一次，不用塞进每条 children
                    group_alarm[label] = {
                        "ip": item["ip"],
                        "hostname": item["hostname"],
                        "vendor": item.get("vendor", ""),
                        "hardware": item.get("hardware", ""),
                        "children": []
                    }
                group_alarm[label]["children"].append(item)
            return {"status":"success","message": "查询成功", "data": list(group_alarm.values())}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["start_time", "end_time"])
def get_history_alarm(data):
    try:
        alarm_db = AlarmDB()
        li = alarm_db.getAlarmListHistory(data)
        if li != "failed":
            group_alarm = {}
            for item in li:
                label = "{}_{}".format(item["ip"], item["hostname"])
                if label not in group_alarm.keys():
                    # vendor/hardware 是设备级信息，同一设备下所有告警都一样，
                    # 放外层分组头只展示一次，不用塞进每条 children
                    group_alarm[label] = {
                        "ip": item["ip"],
                        "hostname": item["hostname"],
                        "vendor": item.get("vendor", ""),
                        "hardware": item.get("hardware", ""),
                        "children": []
                    }
                group_alarm[label]["children"].append(item)
            return {"status":"success","message": "查询成功", "data": list(group_alarm.values())}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["ip", "start_ts", "end_ts"])
def get_device_log_detail(data):
    '''
    按设备看一段时间内的全部原子日志，不限指纹

    看板上设备分组那一行的"查看日志"按钮调这个。和 get_alarm_log_detail
    的区别：那个只给某一条告警的日志，这个把这段时间里这台设备所有进了
    管线的日志都拉出来（含没产生告警的、被 ignore 的、噪声码），按时间
    排序 —— 排查一个口为什么抖，要看的就是夹在 down/up 中间的那些
    速率协商、双工变化。
    '''
    try:
        ret = AlarmDB().getAlarmLogsByDevice({
            "ip": data["ip"],
            "start_ts": data["start_ts"],
            "end_ts": data["end_ts"],
            "limit": data.get("limit", 500),
        })
        if ret == "failed":
            return {"status": "failed", "message": "查询失败", "data": None}
        return {"status": "success", "message": "查询成功", "data": ret}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["alarm_id"])
def get_alarm_log_detail(data):
    '''
    下钻：取支撑某条聚合告警的原子日志（alarm_log，只留7天）
    '''
    try:
        alarm_db = AlarmDB()
        ret = alarm_db.getAlarmLogsByAlarm({"alarm_id": data["alarm_id"]})
        if ret == "failed":
            return {"status": "failed", "message": "查询失败", "data": None}
        if ret is None:
            return {"status": "failed", "message": "告警不存在", "data": None}
        return {"status": "success", "message": "查询成功", "data": ret}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}


@decorator_checkparams(key_array=["alarm_ids", "status", "handler"])
def handle_alarm_by_ids(data):
    '''
    人工处理告警，三件事：

        1. 写处理历史 alarm_handle_log（央端自建表，不是 switchlog 的 alarm_log）
        2. 改 alarm_list.status（人工处理到哪一步）
        3. 离开"待处理"时，把这些告警对应指纹的 alarm_log 标成 is_read=1

    第 3 件只在 status != '0' 时做：退回待处理说明这条还得再看，日志不能
    标掉。按指纹整批标、不卡时间范围，所以同指纹的历史日志会一起变灰 ——
    is_read 只是看板上的颜色标记，标失败也不影响前两件。

    :param data: {
        alarm_ids:[12345,12346],
        status:"1",   0待处理 1已确认 2已处理 3忽略 4屏蔽（5是系统判定，人工选不到）
        handler:"chensong",
        descr:"" (可选)
    }
    '''
    try:
        if len(data["alarm_ids"]) <= 0:
            return {"status": "failed", "message": "待处理数据条目为空", "data": None}

        ret1 = AlarmDB().addHandleLogByIds({
            "alarm_ids": data["alarm_ids"],
            "handler": data["handler"],
            "status": data["status"],
            "msg": data.get("descr", "")
        })
        if ret1 == "failed":
            return {"status": "failed", "message": "处理失败,写入处理记录出错", "data": None}

        # 每个 AlarmDB 方法用完都会在 finally 里自己关连接（self.conn.close()），
        # 一个实例只能安全调一次方法 —— 复用上面那个 alarm_db 调第二个方法，
        # 连接已经被第一次调用关掉了，会报 pymysql "Already closed"。
        # 这里必须用新实例
        ret = AlarmDB().updateAlarmStatusByIds({"alarm_ids": data["alarm_ids"], "status": data["status"]})
        if ret == "failed":
            return {"status": "failed", "message": "处理失败", "data": None}

        # 处理过的告警，对应指纹的原子日志跟着标已读 —— 看板上那批日志
        # 从黄色（未读）变灰（已读）。
        #
        # 只在离开"待处理"时标：status='0' 是退回待处理（故障还在持续，或者
        # 之前标错了），那种情况下日志还得再看一遍，不能标掉。
        #
        # 标失败不影响处理结果：status 已经改完了，is_read 只是颜色标记，
        # 丢了不影响告警本身。所以这里只记日志、不回滚、不报错
        # 单独 try：这一步抛异常不能让外层 except 把整个请求报成"处理失败" ——
        # status 和处理记录都已经写成功了，报失败会让人以为没生效、再点一次
        marked = None
        if str(data["status"]) != "0":
            try:
                marked = AlarmDB().markAlarmLogsReadByAlarmIds(
                    {"alarm_ids": data["alarm_ids"]})
            except Exception as err:
                marked = "failed"
                logger.error("======handle_alarm_by_ids mark read error========\n{}".format(
                    str(err)))
            if marked == "failed":
                logger.warning("======handle_alarm_by_ids warning========\n{}".format(
                    "状态已改，但 alarm_log 标已读失败：alarm_ids={}".format(data["alarm_ids"])))
                marked = None

        return {"status": "success", "message": "处理成功",
                "data": {"updated": ret, "marked_read": marked}}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["alarm_id"])
def get_handle_log(data):
    try:
        alarm_db = AlarmDB()
        li = alarm_db.getHandleLog(data)
        if li != "failed":
            return {"status":"success","message": "查询成功", "data": li}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["alarm_ids"])
def get_alarm_by_ids(data):
    '''
    导出等场景：按 alarm_id 批量取聚合告警行本身
    '''
    try:
        alarm_db = AlarmDB()
        li = alarm_db.getAlarmListByIds(data)
        if li != "failed":
            return {"status": "success", "message": "查询成功", "data": li}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}



if __name__ == '__main__':
    data1 = get_current_alarm({})
    for group in data1["data"]:
        print(group['ip'], group['hostname'])
        for alarm in group['children']:
            print(alarm)



