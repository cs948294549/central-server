"""
WebSocket 服务器模块

提供实时消息推送功能，通过 Flask-SocketIO 实现 WebSocket 通信
"""
import logging
import threading
from flask import Flask, request
from flask_socketio import SocketIO
import json

logger = logging.getLogger(__name__)


class WebSocketServer:
    """
    WebSocket 服务器封装类

    提供独立的 WebSocket 服务，支持实时消息推送和客户端连接管理
    """

    def __init__(self, host='0.0.0.0', port=8081):
        """
        初始化 WebSocket 服务器

        Args:
            host: 监听地址，默认 0.0.0.0
            port: 监听端口，默认 8081
        """
        self.host = host
        self.port = port
        self._thread = None
        self._running = False

        # 创建独立的 Flask 应用（不与主应用共享）
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'secret!'

        # 创建 SocketIO 实例
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",  # 跨域支持
            async_mode='threading'
        )

        # 注册事件处理器
        self._register_handlers()

        # 注册 HTTP 路由
        self._register_routes()

    def _register_handlers(self):
        """注册 SocketIO 事件处理器"""

        @self.socketio.on('connect')
        def handle_connect():
            """处理客户端连接事件"""
            client_id = request.sid
            logger.info(f"WebSocket 客户端已连接: {client_id}")

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """处理客户端断开事件"""
            client_id = request.sid
            logger.info(f"WebSocket 客户端已断开: {client_id}")

    def _register_routes(self):
        """注册 HTTP 路由"""

        @self.app.route('/', methods=['GET', 'POST'])
        def health_check():
            """健康检查接口"""
            return {"status": "ok", "service": "websocket"}

        @self.app.route('/send_msg', methods=['POST'])
        def send_message():
            """
            发送消息到指定频道

            请求体格式:
            {
                "target": "channel_name",  # 目标频道
                "msg": "message_content"    # 消息内容（字符串或对象）
            }
            """
            try:
                postdata = request.get_data(as_text=True)
                query_data = json.loads(postdata)

                # 验证必要参数
                if "target" not in query_data or "msg" not in query_data:
                    return {"status": "error", "message": "缺少 target 或 msg 参数"}, 400

                target = str(query_data["target"])
                msg = query_data["msg"]

                # 处理消息格式
                if isinstance(msg, str):
                    self.socketio.emit(target, msg)
                else:
                    self.socketio.emit(target, json.dumps(msg))

                logger.info(f"消息已发送到频道 {target}")
                return {"status": "success", "target": target}

            except json.JSONDecodeError:
                return {"status": "error", "message": "无效的 JSON 格式"}, 400
            except Exception as e:
                logger.error(f"发送消息失败: {str(e)}")
                return {"status": "error", "message": str(e)}, 500

        @self.app.after_request
        def after_request(response):
            """请求后处理：添加 CORS 头"""
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,session_id')
            response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS,HEAD')
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

    def start(self):
        """在独立线程中启动 WebSocket 服务器"""
        if self._running:
            logger.warning("WebSocket 服务器已在运行中")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="WebSocketServerThread"
        )
        self._thread.start()
        logger.info(f"WebSocket 服务器已启动在 {self.host}:{self.port}")

    def _run_server(self):
        """运行服务器的内部方法"""
        try:
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                allow_unsafe_werkzeug=True,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            logger.error(f"WebSocket 服务器运行异常: {str(e)}")
            self._running = False

    def stop(self):
        """停止 WebSocket 服务器"""
        self._running = False
        logger.info("WebSocket 服务器已停止")

    def emit_message(self, target, message):
        """
        主动发送消息到指定频道

        Args:
            target: 目标频道名称
            message: 消息内容
        """
        try:
            if isinstance(message, str):
                self.socketio.emit(target, message)
            else:
                self.socketio.emit(target, json.dumps(message))
            logger.debug(f"主动推送消息到频道 {target}")
        except Exception as e:
            logger.error(f"推送消息失败: {str(e)}")


# 导出类
__all__ = ['WebSocketServer']
