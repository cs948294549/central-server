from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_messaging.kafka_client import sendDataToSyslog, sendDataToCollector
import time

# 创建蓝图
data_bp = Blueprint('data', __name__, url_prefix='/data')


@data_bp.route('/submit_syslog', methods=['POST'])
def submitDataToSyslog():
    try:
        data = request.json
        ip = data.get('ip', "0.0.0.0")
        message = data.get('message', "")
        kafka_syslog = {
            "ip": ip,
            "message": message,
        }
        ret = sendDataToSyslog(messages=kafka_syslog, key=ip)
        if ret:
            return APIResponse.success(data=kafka_syslog, message="发送成功")
        else:
            return APIResponse.error(data=kafka_syslog, message="发送失败")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@data_bp.route('/submit_collect', methods=['POST'])
def submitDataToCollect():
    try:
        data = request.json
        ip = data.get('ip', "0.0.0.0")
        metric_name = data.get('metric_name', "")
        data = data.get('data', [])
        if metric_name!="":
            kafka_msg = {
                "ip": ip,
                "metric_name": metric_name,
                "status": "ok",
                "message": "接口推送",
                "timestamp": int(time.time()),
                "data": data
            }
            ret = sendDataToCollector(messages=kafka_msg, key=ip)
            if ret:
                return APIResponse.success(data=kafka_msg, message="发送成功")
            else:
                return APIResponse.error(data=kafka_msg, message="发送失败")
        else:
            return APIResponse.param_error(message="缺少metric_name参数")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))