from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_alarm import syslog_manage
import logging
from function_collector.func_search import func_fulltext

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
collector_bp = Blueprint('collector', __name__, url_prefix='/collector')


@collector_bp.route('/getfullsearch',methods=['POST'])
def getfullsearch():
    try:
        query = request.json
        logger.info(f"{str(g.user)}搜索设备，条件{query}")
        if "query" in query.keys():
            respond = func_fulltext(query["query"])
            return APIResponse.success(data=respond, message="查询成功")
        else:
            return APIResponse.error(message="缺失参数 query")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))
