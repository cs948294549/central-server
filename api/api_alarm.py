from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_alarm import syslog_manage


# 创建蓝图
alarm_bp = Blueprint('alarm', __name__, url_prefix='/alarm')


def _dispatch(func, data):
    '''统一包一层：取结果 status，成功走 success，失败走 error，异常走 server_error'''
    try:
        ret = func(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


# ============== syslog_black_list（L2黑名单） ==============
@alarm_bp.route('/add_blacklist', methods=['POST'])
def addBlacklist():
    return _dispatch(syslog_manage.add_blacklist, request.json)

@alarm_bp.route('/del_blacklist', methods=['POST'])
def delBlacklist():
    return _dispatch(syslog_manage.del_blacklist, request.json)

@alarm_bp.route('/update_blacklist', methods=['POST'])
def updateBlacklist():
    return _dispatch(syslog_manage.update_blacklist, request.json)

@alarm_bp.route('/get_blacklist', methods=['POST'])
def getBlacklist():
    return _dispatch(syslog_manage.get_blacklist, request.json)


# ============== syslog_rule（L3解析规则） ==============
@alarm_bp.route('/add_rule', methods=['POST'])
def addRule():
    return _dispatch(syslog_manage.add_rule, request.json)

@alarm_bp.route('/del_rule', methods=['POST'])
def delRule():
    return _dispatch(syslog_manage.del_rule, request.json)

@alarm_bp.route('/update_rule', methods=['POST'])
def updateRule():
    return _dispatch(syslog_manage.update_rule, request.json)

@alarm_bp.route('/get_rule', methods=['POST'])
def getRule():
    return _dispatch(syslog_manage.get_rule, request.json)


# ============== syslog_event（L5事件属性） ==============
@alarm_bp.route('/add_event', methods=['POST'])
def addEvent():
    return _dispatch(syslog_manage.add_event, request.json)

@alarm_bp.route('/del_event', methods=['POST'])
def delEvent():
    return _dispatch(syslog_manage.del_event, request.json)

@alarm_bp.route('/update_event', methods=['POST'])
def updateEvent():
    return _dispatch(syslog_manage.update_event, request.json)

@alarm_bp.route('/get_event', methods=['POST'])
def getEvent():
    return _dispatch(syslog_manage.get_event, request.json)


# ============== syslog_severity_rule（L5事件定级） ==============
@alarm_bp.route('/add_severity_rule', methods=['POST'])
def addSeverityRule():
    return _dispatch(syslog_manage.add_severity_rule, request.json)

@alarm_bp.route('/del_severity_rule', methods=['POST'])
def delSeverityRule():
    return _dispatch(syslog_manage.del_severity_rule, request.json)

@alarm_bp.route('/update_severity_rule', methods=['POST'])
def updateSeverityRule():
    return _dispatch(syslog_manage.update_severity_rule, request.json)

@alarm_bp.route('/get_severity_rule', methods=['POST'])
def getSeverityRule():
    return _dispatch(syslog_manage.get_severity_rule, request.json)


# ============== syslog_mute_rule（L8告警静默） ==============
@alarm_bp.route('/add_mute_rule', methods=['POST'])
def addMuteRule():
    return _dispatch(syslog_manage.add_mute_rule, request.json)

@alarm_bp.route('/del_mute_rule', methods=['POST'])
def delMuteRule():
    return _dispatch(syslog_manage.del_mute_rule, request.json)

@alarm_bp.route('/update_mute_rule', methods=['POST'])
def updateMuteRule():
    return _dispatch(syslog_manage.update_mute_rule, request.json)

@alarm_bp.route('/get_mute_rule', methods=['POST'])
def getMuteRule():
    return _dispatch(syslog_manage.get_mute_rule, request.json)


@alarm_bp.route('/get_current_alarm', methods=['POST'])
def getCurrentAlarm():
    return _dispatch(syslog_manage.get_current_alarm, {})

@alarm_bp.route('/get_history_alarm', methods=['POST'])
def getHistoryAlarm():
    return _dispatch(syslog_manage.get_history_alarm, request.json)

@alarm_bp.route('/get_alarm_log_detail', methods=['POST'])
def getAlarmLogDetail():
    '''
    alarm_id 下钻查询支撑该告警的原子日志(alarm_log)
    :return:
    '''
    return _dispatch(syslog_manage.get_alarm_log_detail, request.json)

@alarm_bp.route('/handle_alarm_by_ids', methods=['POST'])
def handleAlarmByIds():
    return _dispatch(syslog_manage.handle_alarm_by_ids, request.json)

@alarm_bp.route('/get_handle_log', methods=['POST'])
def getHandleLog():
    '''
    alarm_id 根据告警ID查询人工处理历史
    :return:
    '''
    return _dispatch(syslog_manage.get_handle_log, request.json)

@alarm_bp.route('/get_alarm_by_ids', methods=['POST'])
def getAlarmByIds():
    '''
    alarm_ids 批量按告警ID取聚合告警行，导出等场景用
    :return:
    '''
    return _dispatch(syslog_manage.get_alarm_by_ids, request.json)