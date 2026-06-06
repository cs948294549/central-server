from flask import Blueprint, request, g
from api.api_response import APIResponse

# 创建蓝图
agent_bp = Blueprint('agent', __name__, url_prefix='/agent')


@agent_bp.route('/tasks', methods=['GET'])
def get_task_list():
    """
    获取任务列表
    Query参数: agent_id (可选)
    """
    try:
        agent_id = request.args.get('agent_id')

        tasks = [

        ]

        return APIResponse.success(data={"tasks": tasks})
    except Exception as e:
        return APIResponse.server_error(message="获取任务列表失败: {}".format(str(e)))


@agent_bp.route('/task_report', methods=['POST'])
def submit_task_report():
    """
    提交任务执行结果
    Body: {"task_id": "...", "result": ..., "timestamp": ...}
    """
    try:
        data = request.json
        if not data:
            return APIResponse.param_error(message="请求体不能为空")

        task_id = data.get('task_id')
        result = data.get('result')
        timestamp = data.get('timestamp')

        if not task_id:
            return APIResponse.param_error(message="task_id不能为空")

        print("收到的消息==", data)

        return APIResponse.success(data={"task_id": task_id, "received": True})
    except Exception as e:
        return APIResponse.server_error(message="任务上报失败: {}".format(str(e)))


# 导出蓝图
__all__ = ['agent_bp']
