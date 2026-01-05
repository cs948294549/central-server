from services.syslog import get_blacklisted_entries,get_mergelisted_entries
from tables.AlarmDB import AlarmDB
from tables.SyslogDB import SyslogDB
import json
from utils.utils import decorator_checkparams

@decorator_checkparams(key_array=["message", "ip"])
def check_blacklist(message):
    '''
    :param message: {"message":"", "ip":""}
    :return:
    '''
    blacklisted_entries = get_blacklisted_entries()
    for entry in blacklisted_entries:
        if entry.matches(str(message["message"])):
            return {"status": "matched", "entry": entry.to_dict()}
    return {"status": "unmatched", "entry": {}}

@decorator_checkparams(key_array=["message", "ip"])
def check_mergelist(message):
    '''
    :param message: {"message":"", "ip":""}
    :return:
    '''
    mergelisted_entries = get_mergelisted_entries()
    for entry in mergelisted_entries:
        if entry.matches(str(message["message"])):
            return {"status": "matched", "entry": entry.to_dict()}
    return {"status": "unmatched", "entry": {}}

# 日志黑名单操作
@decorator_checkparams(key_array=["pattern", "descr"])
def add_blacklist(data):
    try:
        syslog_db = SyslogDB()
        ret = syslog_db.addBlackList({"pattern": data["pattern"], "descr": data["descr"]})
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def del_blacklist(data):
    try:
        syslog_db = SyslogDB()
        ret = syslog_db.delBlackList({"rule_id": data["rule_id"]})
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def update_blacklist(data):
    try:
        syslog_db = SyslogDB()
        ret = syslog_db.updateBlackList(data)
        if ret != "failed":
            return {"status":"success","message": "修改成功", "data": ret}
        else:
            return {"status": "failed", "message": "修改失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_blacklist(data):
    try:
        syslog_db = SyslogDB()
        ret = syslog_db.getBlackList(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

# 日志聚合规则操作
@decorator_checkparams(key_array=["group_name", "pattern", "descr"])
def add_mergelist(data):
    try:
        syslog_db = SyslogDB()
        ret = syslog_db.addMergeList(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def del_mergelist(data):
    try:
        syslog_db = SyslogDB()
        ret = syslog_db.delMergeList({"rule_id": data["rule_id"]})
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rule_id"])
def update_mergelist(data):
    try:
        syslog_db = SyslogDB()
        ret = syslog_db.updateMergeList(data)
        if ret != "failed":
            return {"status":"success","message": "修改成功", "data": ret}
        else:
            return {"status": "failed", "message": "修改失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_mergelist(data):
    try:
        syslog_db = SyslogDB()
        ret = syslog_db.getMergeList(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_current_alarm(data):
    try:
        alarm_db = AlarmDB()
        li = alarm_db.getAlarmListCurrent()
        if li != "failed":
            group_alarm = {}
            for item in li:
                label = "{}_{}".format(item["ip"], item["hostname"])
                if label not in group_alarm.keys():
                    group_alarm[label] = {
                        "ip": item["ip"],
                        "hostname": item["hostname"],
                        "children": []
                    }
                group_alarm[label]["children"].append(item)
            return {"status":"success","message": "查询成功", "data": list(group_alarm.values())}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["group_label"])
def get_alarm_by_group(data):
    try:
        alarm_db = AlarmDB()
        li = alarm_db.getAlarmList({"group_label": data["group_label"]})
        if li != "failed":
            return {"status":"success","message": "查询成功", "data": li}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}


@decorator_checkparams(key_array=["group_labels", "status", "handler"])
def handle_alarm_by_group(data):
    '''
    :param data: {
        group_labels:["328078962c656cdcfd724235828e9f54","328078962c656cdcfd724235828e9f54"],
        status:"success",
        handler:"success"
    }
    :return:
    '''
    try:
        # 添加日志
        handle_msg = "状态修改成{}".format(data["status"])
        alarm_db = AlarmDB()
        ret1 = alarm_db.addAlarmLogByGroup({
            "group_labels": data["group_labels"],
            "msg": handle_msg,
            "handler": data["handler"]
        })

        # 更新记录
        alarm_db = AlarmDB()
        group_label_str = ",".join(data["group_labels"])
        if '"' in group_label_str or "'" in group_label_str:
            return {"status": "failed", "message": "处理失败,数据存在问题", "data": None}
        ret = alarm_db.updateAlarmListByGroup({"group_labels": data["group_labels"], "status": data["status"]})



        if ret != "failed":
            return {"status": "success", "message": "处理成功", "data": ret}
        else:
            return {"status": "failed", "message": "处理失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["alarm_id"])
def get_alarm_log(data):
    try:
        alarm_db = AlarmDB()
        li = alarm_db.getAlarmLog(data)
        if li != "failed":
            return {"status":"success","message": "查询成功", "data": li}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

if __name__ == '__main__':
    # ret11 = check_mergelist({"message": "%Jan  1 08:46:32:471 2011 vrrp-test-2 %%IFNET/3/PHY_UPDO1WN: Vlan-interface162 link status is up.","ip":"1.1.1.1"})
    # print(ret11)
    #
    data1 = get_current_alarm({})
    for key, value in data1["data"].items():
        print(value['ip'], value['hostname'])
        for alarm in value['alarm_list']:
            print(alarm)

    # aa = handle_alarm_by_group({"group_labels":["328078962c656cdcfd724235828e9f54"], "status": "3", "handler":"chensong1"})
    # print(aa)
    #
    #
    #
    # bb = get_alarm_by_group({"group_label": "328078962c656cdcfd724235828e9f54"})
    # for item in bb["data"]:
    #     print(item)
    #
    # cc = get_alarm_log({"alarm_id": 27300})
    # print(cc)



