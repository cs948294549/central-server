from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_tools.text_diff_tool import check_diff
from function_tools.ipprefix_tools import mergeNet
# 创建蓝图
tools_bp = Blueprint('tools', __name__, url_prefix='/tools')


@tools_bp.route('/submit_syslog', methods=['POST'])
def submitDataToKafka():
    try:
        data = request.json
        text_src = data.get('src')
        text_target = data.get('target')
        flag = data.get('flag', False)
        html_result = check_diff(text_src, text_target, flag)
        return APIResponse.success(data=html_result, message="解析成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@tools_bp.route('/submit_collect', methods=['POST'])
def submitDataToKafka():
    try:
        data = request.json
        text_src = data.get('src')
        text_target = data.get('target')
        flag = data.get('flag', False)
        html_result = check_diff(text_src, text_target, flag)
        return APIResponse.success(data=html_result, message="解析成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))