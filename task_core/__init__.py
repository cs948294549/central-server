'''
基础用法
1.启动scheduler
from core.scheduler import scheduler
scheduler.start()

2.初始化任务工厂并注册自定义任务类
TaskFactory.register_task_class(HeartbeatTask.TASK_ID, HeartbeatTask)

3.创建任务管理器实例
task_manager = TaskManager()

4.注册任务，设置参数
task_manager.register_task(
        task_id=HeartbeatTask.TASK_ID,
        config={"initial_count": 0},
        schedule_type="interval",
        schedule_config={"seconds": 5}
    )


任务属性
warning_interval 告警检测
send_to_kafka true/false 任务数据是否推送到kafka



'''

__all__ = []

