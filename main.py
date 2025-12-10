# 导入核心组件
from core.scheduler import scheduler
from core.app import create_app
from core.logger import setup_logger
from config import Config
# 导入任务管理器
from task_core.task_manager import task_manager

# 初始化日志系统
logger = setup_logger()


def main():
    """主函数"""
    logger.info("启动任务调度系统")

    # 启动调度器
    scheduler.start()
    logger.info("任务调度器已启动")


    # 创建Flask应用
    app = create_app()

    # 运行Flask应用
    try:
        logger.info(f"Flask服务器启动在端口 {Config.service_port}")
        app.run(host=Config.service_ip, port=Config.service_port, threaded=True, debug=False)
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
