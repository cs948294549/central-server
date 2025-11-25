"""
调度器模块

本模块提供APScheduler实例，用于任务调度管理
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

# 配置APScheduler日志器，设置为WARNING级别以去除调试日志
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.executors').setLevel(logging.WARNING)
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('apscheduler.jobstores').setLevel(logging.WARNING)

# 配置执行器
executors = {
    'default': ThreadPoolExecutor(20)  # 使用线程池执行器，最多20个线程
}

# 创建并配置调度器实例
scheduler = BackgroundScheduler(
    executors=executors,
    timezone='Asia/Shanghai',  # 设置时区为上海
    job_defaults={'coalesce': False, 'max_instances': 2}  # 可选：配置作业默认值
)
'''
配置max_instances=1时，可避免重复采集
设置成2时，可生成
'''

# 导出scheduler实例
__all__ = ['scheduler']