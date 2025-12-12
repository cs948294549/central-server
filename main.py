# 导入核心组件
from core.scheduler import scheduler
from core.app import create_app
from core.logger import setup_logger
from config import Config
# 导入任务管理器
from task_core.task_manager import task_manager

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
        # 获取真实 IP（优先 X-Forwarded-For，其次客户端原始 IP）
        # 处理多个代理层的情况（如 X-Forwarded-For: 192.168.1.100, 127.0.0.1）
        real_ip = self.headers.get('X-Forwarded-For', self.client_address[0])
        real_ip = real_ip.split(',')[0].strip() if real_ip else self.client_address[0]

        # 自定义日志格式（可根据需求修改）
        log_format = (
            f"[%(asctime)s] [%(levelname)s] [IP: {real_ip}] "
            f'"{self.request_line}" {code} {size}'
        )
        # 调用日志方法输出
        self.log(
            'info',
            log_format % {
                'asctime': self.log_date_time_string(),
                'levelname': 'INFO',
            }
        )

def main():
    """主函数"""
    logger.info("启动任务调度系统")

    # 启动调度器
    scheduler.start()
    logger.info("任务调度器已启动")


    # 创建Flask应用
    app = create_app()

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
        logger.info(f"Flask服务器启动在端口 {Config.service_port}")
        app.run(
            host=Config.service_ip, port=Config.service_port, threaded=True, debug=False,
            request_handler=CustomWSGIRequestHandler
        )
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭...")
    finally:
        # 停止所有任务
        task_manager.stop_all_tasks()
        # 关闭调度器
        scheduler.shutdown()
        logger.info("任务调度系统已关闭")


if __name__ == "__main__":
    # nohup python3 -u main.py > lweb.log 2>&1 &
    main()
