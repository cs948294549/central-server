from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_tools.text_diff_tool import check_diff, check_diff_simple
from function_tools.ipprefix_tools import mergeNet
# 创建蓝图
tools_bp = Blueprint('tools', __name__, url_prefix='/tools')


@tools_bp.route('/check_diff', methods=['POST'])
def checkTextDiffHtml():
    try:
        data = request.json
        text_src = data.get('src')
        text_target = data.get('target')
        flag = data.get('flag', False)
        # 使用新方法 check_diff_simple，与 config 对比保持一致
        html_result = check_diff_simple(text_src, text_target, full_diff=flag)
        return APIResponse.success(data=html_result, message="解析成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@tools_bp.route('/network_merge', methods=['POST'])
def mergeNetwork():
    try:
        data = request.json
        net_list = data.get('net_list')
        final_list = mergeNet(net_list)
        return APIResponse.success(data=final_list, message="合并成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@tools_bp.route('/ip', methods=['POST',"GET"])
def get_real_ip():
    try:
        real_ip_data = {
            "ip": request.remote_addr,
        }
        # 优先从 X-Forwarded-For 获取
        if 'X-Forwarded-For' in request.headers:
            # 格式：客户端IP, 代理1, 代理2...
            ips = request.headers['X-Forwarded-For'].split(',')
            real_ip_data["x-forward"] = ips[0].strip()

        return APIResponse.success(data=real_ip_data, message="查询")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))