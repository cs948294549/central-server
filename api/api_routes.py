from flask import Blueprint, request
from api.api_response import APIResponse

# 导入必要的模块
from core.scheduler import scheduler

# 创建蓝图
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/scheduler/jobs', methods=['GET'])
def get_scheduler_jobs():
    """获取调度器任务信息"""
    try:
        if scheduler.running:
            jobs = []
            for job in scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': str(job.next_run_time) if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'func': job.func.__name__ if hasattr(job.func, '__name__') else str(job.func)
                })
            return APIResponse.success(data=jobs)
        return APIResponse.server_error(message='调度器未运行')
    except Exception as e:
        return APIResponse.server_error(message=str(e))

@api_bp.route('/scheduler/jobs', methods=['POST'])
def add_scheduled_job():
    try:
        data = request.get_json()
        if not data:
            return APIResponse.param_error(message='请求体不能为空')
            
        # 验证必要参数
        required_fields = ['name', 'func', 'trigger_type']
        for field in required_fields:
            if field not in data:
                return APIResponse.param_error(message=f'缺少必要参数: {field}')
                
        # 添加调度任务（实际实现中需要根据trigger_type创建不同类型的触发器）
        # 这里只是一个示例
        job_id = scheduler.add_job(
            func=data['func'],
            trigger=data['trigger_type'],
            args=data.get('args', []),
            kwargs=data.get('kwargs', {}),
            id=data.get('id', None),
            name=data['name']
        ).id
        
        return APIResponse.success(data={'job_id': job_id})
    except Exception as e:
        return APIResponse.server_error(message=str(e))

@api_bp.route('/scheduler/jobs/<job_id>', methods=['DELETE'])
def delete_scheduled_job(job_id):
    try:
        scheduler.remove_job(job_id)
        return APIResponse.success(message='任务删除成功')
    except Exception as e:
        return APIResponse.server_error(message=str(e))

@api_bp.route('/scheduler/jobs/<job_id>/pause', methods=['POST'])
def pause_scheduled_job(job_id):
    try:
        scheduler.pause_job(job_id)
        return APIResponse.success(message='任务暂停成功')
    except Exception as e:
        return APIResponse.server_error(message=str(e))

@api_bp.route('/scheduler/jobs/<job_id>/resume', methods=['POST'])
def resume_scheduled_job(job_id):
    try:
        scheduler.resume_job(job_id)
        return APIResponse.success(message='任务恢复成功')
    except Exception as e:
        return APIResponse.server_error(message=str(e))

# 导出蓝图和设置函数
__all__ = ['api_bp']