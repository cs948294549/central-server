from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_alarm import syslog_manage


# 创建蓝图
alarm_bp = Blueprint('alarm', __name__, url_prefix='/alarm')

# 黑名单和聚合规则测试功能
@alarm_bp.route('/check_blacklist', methods=['POST'])
def checkBlacklist():
    try:
        data = request.json
        ret = syslog_manage.check_blacklist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/check_mergelist', methods=['POST'])
def checkMergelist():
    try:
        data = request.json
        ret = syslog_manage.check_mergelist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


# 黑名单操作
@alarm_bp.route('/add_blacklist', methods=['POST'])
def addBlacklist():
    try:
        data = request.json
        ret = syslog_manage.add_blacklist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/del_blacklist', methods=['POST'])
def delBlacklist():
    try:
        data = request.json
        ret = syslog_manage.del_blacklist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/update_blacklist', methods=['POST'])
def updateBlacklist():
    try:
        data = request.json
        ret = syslog_manage.update_blacklist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/get_blacklist', methods=['POST'])
def getBlacklist():
    try:
        data = request.json
        ret = syslog_manage.get_blacklist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


# 聚合规则操作
@alarm_bp.route('/add_mergelist', methods=['POST'])
def addMergelist():
    try:
        data = request.json
        ret = syslog_manage.add_mergelist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/del_mergelist', methods=['POST'])
def delMergelist():
    try:
        data = request.json
        ret = syslog_manage.del_mergelist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/update_mergelist', methods=['POST'])
def updateMergelist():
    try:
        data = request.json
        ret = syslog_manage.update_mergelist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/get_mergelist', methods=['POST'])
def getMergelist():
    try:
        data = request.json
        ret = syslog_manage.get_mergelist(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@alarm_bp.route('/get_current_alarm', methods=['POST'])
def getCurrentAlarm():
    try:
        ret = syslog_manage.get_current_alarm({})
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/get_history_alarm', methods=['POST'])
def getHistoryAlarm():
    try:
        data = request.json
        ret = syslog_manage.get_history_alarm(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/get_alarm_by_group', methods=['POST'])
def getAlarmByGroup():
    try:
        data = request.json
        ret = syslog_manage.get_alarm_by_group(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/handle_alarm_by_group', methods=['POST'])
def handleAlarmByGroup():
    try:
        data = request.json
        ret = syslog_manage.handle_alarm_by_group(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@alarm_bp.route('/get_alarm_log', methods=['POST'])
def getAlarmLog():
    '''
    alarm_id 根据告警ID查询处理记录
    :return:
    '''
    try:
        data = request.json
        ret = syslog_manage.get_alarm_log(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))
