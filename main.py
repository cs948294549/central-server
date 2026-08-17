# 导入核心组件
from core.scheduler import scheduler
from core.app import create_app
from core.logger import setup_logger
from core.websocket_server import WebSocketServer
from config import Config
# 导入任务管理器
from task_core.task_manager import task_manager
from services.syslog_main import SyslogService
from services.data_main import DataService

# 导入 SSH 终端相关模块
from function_ssh.interactive_ssh import InteractiveSSHManager
from api.websocket_ssh_bp import init_websocket_ssh, send_to_websocket


# 初始化日志系统
logger = setup_logger()

from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.serving import WSGIRequestHandler


# 1. 自定义请求处理器：重写日志格式，优先读取真实 IP
class CustomWSGIRequestHandler(WSGIRequestHandler):
    def log_request(self, code='-', size='-'):
        """
        重写日志方法，自定义格式：
        格式示例：[时间] [IP] "请求方法 路径 协议" 状态码 响应大小
        """
        # 1. 安全获取 request_line（兼容 Werkzeug 新版/旧版）
        try:
            # 优先获取完整请求行（方法 + 路径 + 协议）
            request_line = self.request_line
        except AttributeError:
            # 降级方案：手动拼接请求行
            request_line = f"{self.command} {self.path} HTTP/{self.request_version}"

        # 获取真实 IP（优先 X-Forwarded-For，其次客户端原始 IP）
        # 处理多个代理层的情况（如 X-Forwarded-For: 192.168.1.100, 127.0.0.1）
        real_ip = self.headers.get('X-Forwarded-For', self.client_address[0])

        # 自定义日志格式（可根据需求修改）
        log_format = (
            f"[%(levelname)s] [IP: {real_ip}] "
            f'"{request_line}" {code} {size}'
        )
        # 调用日志方法输出
        self.log(
            'info',
            log_format % {
                'levelname': 'INFO',
            }
        )

def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("启动 Central-Server 服务")
    logger.info("=" * 60)

    # 启动调度器
    scheduler.start()
    logger.info("✓ 任务调度器已启动")

    # 启动 WebSocket 服务器
    websocket_server = None
    if Config.websocket_enable:
        try:
            websocket_server = WebSocketServer(
                host=Config.websocket_ip,
                port=Config.websocket_port
            )
            websocket_server.start()
            logger.info(f"✓ WebSocket 服务器已启动在 {Config.websocket_ip}:{Config.websocket_port}")
        except Exception as e:
            logger.error(f"✗ WebSocket 服务器启动失败: {str(e)}")

    # 启动syslog
    syslog_service = None
    if Config.syslog_enable:
        try:
            syslog_service = SyslogService()
            syslog_service.start()
            logger.info("✓ Syslog 日志处理器已启动")
        except Exception as e:
            logger.error(f"✗ Syslog 服务启动失败: {str(e)}")

    # 启动数据存储
    collect_service = None
    if Config.collect_enable:
        try:
            collect_service = DataService()
            collect_service.start()
            logger.info("✓ 数据采集处理器已启动")
        except Exception as e:
            logger.error(f"✗ 数据采集服务启动失败: {str(e)}")

    # 创建Flask应用
    app = create_app()

    # 初始化 SSH 终端功能
    if websocket_server:
        try:
            # 创建 SSH 会话管理器
            ssh_manager = InteractiveSSHManager(output_sender=send_to_websocket)

            # 获取 WebSocket 服务器地址
            ws_url = f"http://127.0.0.1:{Config.websocket_port}"

            # 初始化 SSH 终端蓝图
            init_websocket_ssh(ssh_manager, ws_url)

            logger.info(f"✓ SSH 终端功能已启用，WebSocket 服务器: {ws_url}")
        except Exception as e:
            logger.error(f"✗ SSH 终端功能启动失败: {str(e)}")

    # 关键：信任代理（解决反向代理下 IP 显示 127.0.0.1）
    # x_for=1 表示 1 层代理（如 Nginx → Flask），根据实际代理层数调整
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,  # 解析 X-Forwarded-For 头
        x_proto=1,  # 解析 X-Forwarded-Proto 头（http/https）
        x_host=1  # 解析 X-Forwarded-Host 头
    )

    # 运行Flask应用
    try:
        logger.info("=" * 60)
        logger.info(f"✓ API 服务器启动在 {Config.service_ip}:{Config.service_port}")
        logger.info("=" * 60)
        logger.info("所有服务已就绪，按 Ctrl+C 停止服务")
        app.run(
            host=Config.service_ip, port=Config.service_port, threaded=True, debug=False,
            request_handler=CustomWSGIRequestHandler
        )
    except KeyboardInterrupt:
        logger.info("\n收到停止信号，正在关闭服务...")
    finally:
        # 停止 WebSocket 服务器
        if websocket_server:
            websocket_server.stop()
            logger.info("✓ WebSocket 服务器已停止")

        # 停止 Syslog 服务
        if syslog_service:
            syslog_service.stop()
            logger.info("✓ Syslog 服务已停止")

        # 停止数据采集服务
        if collect_service:
            collect_service.stop()
            logger.info("✓ 数据采集服务已停止")

        # 停止所有任务
        task_manager.stop_all_tasks()
        logger.info("✓ 所有任务已停止")

        # 关闭调度器
        scheduler.shutdown()
        logger.info("✓ 任务调度器已关闭")

        logger.info("=" * 60)
        logger.info("Central-Server 服务已完全关闭")
        logger.info("=" * 60)


if __name__ == "__main__":
    # nohup python3 -u main.py > lweb.log 2>&1 &
    main()
