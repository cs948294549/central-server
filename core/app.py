from flask import Flask, request, jsonify, g
import logging
from functools import wraps
from hashlib import md5

# 导入API蓝图和设置函数
from api.api_routes import api_bp
from api.api_system import system_bp
from api.api_response import APIResponse

# 导入认证相关功能
from function_system.user_manage import verify_access_token, verify_url_privilege

# 配置日志
logger = logging.getLogger(__name__)



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

    app.register_blueprint(system_bp)

    # 认证和鉴权中间件
    @app.before_request
    def before_request():
        """
        请求前处理：进行认证和鉴权
        """
        # 排除不需要认证的路由
        excluded_routes = [
            '/system/login',  # 登录路由
        ]
        
        # 获取请求路径
        path = request.path
        
        # 如果是排除的路由，直接通过
        if path in excluded_routes or path.startswith('/static/'):
            return None

        logger.info(request.headers)
        # 获取认证信息
        auth_header = request.headers.get('Authorization')
        
        # 检查认证头是否存在
        if not auth_header:
            return APIResponse.error("未提供认证信息", 401)
        
        # 检查认证头格式
        if not auth_header.startswith('Bearer '):
            return APIResponse.error("认证格式错误", 401)
        
        # 提取token
        token = auth_header[7:]

        auth_timestamp = request.headers.get('Apptime')

        if not auth_timestamp:
            return APIResponse.error("未提供时间戳", 401)

        auth_sessionid = request.headers.get('Sessionid')
        if not auth_sessionid:
            return APIResponse.error("未提供会话ID", 401)
        
        try:
            # 验证token
            user_info = verify_access_token(token)
            
            if not user_info:
                return APIResponse.error("无效的认证信息", 401)
            logger.info(user_info)
            logger.info(auth_timestamp)
            sign = md5((str(user_info["sign"])+str(auth_timestamp)).encode("utf-8")).hexdigest()
            if sign != auth_sessionid:
                return APIResponse.error("认证签名异常", 401)

            # 将用户信息存储到全局上下文
            g.user = user_info
            logger.info("用户{} {}访问接口{}".format(user_info['username'], user_info['rid'], path))
            # 可以在这里添加更细粒度的鉴权逻辑
            # 例如：检查用户是否有权限访问当前资源
            if g.user["rid"] in ["system", "admin"]:
                pass
            else:
                priv = verify_url_privilege(g.user["rid"], path)
                if priv:
                    pass
                else:
                    return APIResponse.forbidden_error(message="权限不足")

            
        except Exception as e:
            logger.error(f"认证失败: {str(e)}")
            return APIResponse.error("认证失败", 401)
    
    @app.after_request
    def after_request(response):
        """
        请求后处理：可以在这里添加日志记录、响应处理等
        """
        # 记录请求信息
        logger.info(f"Request: {request.method} {request.path} Status: {response.status_code}")


        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,session_id,sessionid,apptime')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS,HEAD')
        # 这里不能使用add方法，否则会出现 The 'Access-Control-Allow-Origin' header contains multiple values 的问题
        response.headers['Access-Control-Allow-Origin'] = '*'

        # 添加自定义响应头
        response.headers['X-App-Name'] = 'NetOps-Central-Server'
        
        return response

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