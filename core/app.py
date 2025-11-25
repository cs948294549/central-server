from flask import Flask

# 导入API蓝图和设置函数
from api.api_routes import api_bp



# 导入任务管理器
# from task_core.task_manager import task_manager

def create_app():
    """
    创建并配置Flask应用
    Returns:
        Flask应用实例
    """
    
    # 创建Flask应用实例
    app = Flask(__name__)
    
    # 配置应用
    app.config.update(
        JSON_SORT_KEYS=False,  # 保持JSON响应中键的顺序
        JSONIFY_MIMETYPE='application/json',
        DEBUG=False  # 生产环境应关闭调试模式
    )
    
    # 注册API蓝图
    app.register_blueprint(api_bp)
    # 注：其他蓝图可以根据需要在这里注册



    # 向中心注册自身
    # 修改成中心主动探测proxy，实现监控一体化
    # task_manager.register_task(
    #     task_instance_id="heartbeat",
    #     task_class_id="heartbeat",
    #     config={"interval": 10},
    #     schedule_type="interval",
    #     schedule_config={"seconds": 10}
    # )
    
    return app


# 导出应用创建函数
__all__ = ['create_app']