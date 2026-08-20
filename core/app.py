from flask import Flask, request, g
import logging
import time
from hashlib import md5

# 导入API蓝图和设置函数
from api.api_response import APIResponse
from api.api_routes import api_bp
from api.api_system import system_bp
from api.api_tools import tools_bp
from api.api_kafka_data import data_bp
from api.api_alarm import alarm_bp
from api.api_agent import agent_bp
from api.api_collector import collector_bp
from api.api_command import command
from api.api_ipam import ipam_bp

# 导入 SSH 终端蓝图
from api.websocket_ssh_bp import websocket_ssh_bp

# 导入认证相关功能
from function_system.user_manage import verify_access_token, verify_url_privilege, verify_secret_token

# 导入配置
from config.config import Config

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
    app.register_blueprint(tools_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(alarm_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(collector_bp)
    app.register_blueprint(command)
    app.register_blueprint(ipam_bp)

    # 注册 SSH 终端蓝图
    app.register_blueprint(websocket_ssh_bp)
    logger.info("SSH 终端蓝图已注册")

    def check_url_privilege(path):
        """
        检查用户是否有权限访问指定路径

        Args:
            path: 请求路径

        Returns:
            None: 有权限
            Response: 无权限时返回 403 错误响应
        """
        # system 和 admin 角色拥有全部权限
        if g.user["rid"] in ["system", "admin"]:
            return None

        # 其他角色需要检查 URL 权限
        if verify_url_privilege(g.user["rid"], path):
            return None
        else:
            logger.warning(f"权限不足: 用户 {g.user['username']} ({g.user['rid']}) 无权访问 {path}")
            return APIResponse.forbidden_error(message="权限不足")

    # 认证和鉴权中间件
    @app.before_request
    def before_request():
        """
        请求前处理：进行认证和鉴权
        """
        # 排除不需要认证的路由
        excluded_routes = [
            '/system/login',  # 登录路由
            '/system/health',  # 健康检查
            '/tools/ip'
        ]

        # 获取请求路径
        path = request.path

        # 如果是排除的路由，直接通过
        if path in excluded_routes:
            return None

        auth_timestamp = request.headers.get('Apptime')

        if not auth_timestamp:
            return APIResponse.error("未提供时间戳", 401)

        # 验证时间戳有效性，防止重放攻击
        try:
            timestamp = int(auth_timestamp)
            current_time = int(time.time())
            time_diff = abs(current_time - timestamp)

            if time_diff > Config.timestamp_tolerance:
                logger.warning(f"时间戳过期: 请求时间={timestamp}, 当前时间={current_time}, 差值={time_diff}秒")
                return APIResponse.error("时间戳过期", 401)
        except ValueError:
            return APIResponse.error("时间戳格式错误", 401)

        api_key = request.headers.get('key')
        api_secret = request.headers.get('secret')
        if api_key and api_secret:
            # API Key/Secret 认证（从数据库用户表验证）
            try:
                ret_auth = verify_secret_token(api_key, api_secret, auth_timestamp)
                if ret_auth and isinstance(ret_auth, dict):
                    # 认证成功，将用户信息存储到上下文
                    g.user = ret_auth
                    logger.info(f"API Key认证成功: 用户 {ret_auth['username']} ({ret_auth['rid']}) 访问接口 {path}")
                else:
                    return APIResponse.error("API认证失败", 401)
            except Exception as e:
                logger.error(f"API认证异常: {str(e)}")
                return APIResponse.error("API认证失败", 401)
        else:
            # JWT Token 认证
            auth_header = request.headers.get('Authorization')

            # 检查认证头是否存在
            if not auth_header:
                return APIResponse.error("未提供认证信息", 401)

            # 检查认证头格式
            if not auth_header.startswith('Bearer '):
                return APIResponse.error("认证格式错误", 401)

            # 提取token
            token = auth_header[7:]
            auth_sessionid = request.headers.get('Sessionid')

            if not auth_sessionid:
                return APIResponse.error("未提供会话ID", 401)

            try:
                # 验证token
                user_info = verify_access_token(token)

                if not user_info:
                    return APIResponse.error("无效的认证信息", 401)

                sign = md5((str(user_info["sign"])+str(auth_timestamp)).encode("utf-8")).hexdigest()
                if sign != auth_sessionid:
                    return APIResponse.error("认证签名异常", 401)

                # 将用户信息存储到全局上下文
                g.user = user_info
                logger.info(f"JWT认证成功: 用户 {user_info['username']} ({user_info['rid']}) 访问接口 {path}")

            except Exception as e:
                logger.error(f"认证失败: {str(e)}")
                return APIResponse.error("认证失败", 401)

        # 统一的权限检查（认证通过后执行）
        return check_url_privilege(path)
    
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