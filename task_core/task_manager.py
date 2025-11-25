"""
任务管理器模块

负责管理所有任务的注册、调度和执行
"""
import logging
from typing import Dict, Any, List, Optional, Type
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from core.scheduler import scheduler
from task_core.task_base import BaseTask
from task_core.task_factory import TaskFactory

logger = logging.getLogger('task_manager')


class TaskManager:
    """
    任务管理器，负责管理所有定时任务
    
    提供任务的注册、调度、执行和监控功能，支持高并发任务处理
    """
    
    def __init__(self):
        """
        初始化任务管理器
        """
        self.tasks: Dict[str, BaseTask] = {}
        self.task_classes: Dict[str, Type[BaseTask]] = {}
        self.task_schedules: Dict[str, Dict[str, Any]] = {}
    
    def register_task_class(self, task_id: str, task_class: Type[BaseTask]) -> None:
        """
        注册任务类
        
        Args:
            task_class: 任务类
        """
        # 通过任务工厂注册任务类
        TaskFactory.register_task_class(task_id, task_class)
        # 将任务类添加到本地缓存
        self.task_classes[task_id] = task_class
    
    def register_task(self, task_instance_id: str, task_class_id: str, config: Optional[Dict[str, Any]] = None,
                      schedule_type: str = 'interval', schedule_config: Optional[Dict[str, Any]] = None, 
                      ) -> str:
        """
        注册并调度任务
        
        Args:
            task_class_id: 任务类ID
            config: 任务配置
            schedule_type: 调度类型 ('interval' 或 'cron')
            schedule_config: 调度配置参数
                - 对于interval: { 'seconds': 60, 'minutes': 0, ... }
                - 对于cron: { 'year': None, 'month': None, 'day': None, ... }
            task_instance_id: 任务实例ID（必填），用于唯一标识任务实例
        
        Returns:
            str: 注册的任务实例ID
            
        Raises:
            Exception: 任务注册失败时抛出异常
        """
        # 使用提供的任务实例ID
        effective_task_id = task_instance_id
            
        # 如果任务已存在，先移除旧任务
        if effective_task_id in self.tasks:
            self.unregister_task(effective_task_id)
        
        try:
            # 使用任务工厂创建任务实例（使用任务类ID）
            task_instance = TaskFactory.create_task(task_class_id, config)
            if not task_instance:
                raise ValueError(f"无法创建任务实例: {task_class_id}")
            
            self.tasks[effective_task_id] = task_instance
            
            # 保存调度配置
            self.task_schedules[effective_task_id] = {
                'type': schedule_type,
                'config': schedule_config or {}
            }
            
            # 创建调度器任务
            if schedule_type == 'interval':
                # 使用schedule_config或默认值
                if not schedule_config:
                    trigger = IntervalTrigger(seconds=60)  # 默认间隔1分钟
                else:
                    trigger = IntervalTrigger(**schedule_config)
            elif schedule_type == 'cron':
                trigger = CronTrigger(**(schedule_config or {}))
            else:
                logger.error(f"不支持的调度类型: {schedule_type}")
                raise ValueError(f"不支持的调度类型: {schedule_type}")
            
            # 添加到调度器
            scheduler.add_job(
                func=task_instance.run,
                trigger=trigger,
                id=f"task_{effective_task_id}",
                name=task_instance.TASK_NAME,
                replace_existing=True
            )
            
            logger.info(f"任务注册成功: {task_instance.TASK_NAME} ({effective_task_id}), 任务类: {task_class_id}, 调度类型: {schedule_type}")
            return effective_task_id
            
        except Exception as e:
            logger.error(f"任务注册失败: {task_class_id}, 实例ID: {effective_task_id}, 错误: {str(e)}")
            # 清理可能的部分注册
            if effective_task_id in self.tasks:
                del self.tasks[effective_task_id]
            if effective_task_id in self.task_schedules:
                del self.task_schedules[effective_task_id]
            raise ValueError("任务{}注册失败,错误：{}".format(effective_task_id, str(e)))
    
    def unregister_task(self, task_instance_id: str) -> bool:
        """
        取消注册任务
        
        Args:
            task_instance_id: 任务实例ID
        
        Returns:
            bool: 取消注册是否成功
        """
        if task_instance_id not in self.tasks:
            logger.warning(f"任务不存在: {task_instance_id}")
            return False
        
        try:
            # 从调度器移除
            job_id = f"task_{task_instance_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
            
            # 从管理器移除
            task_name = self.tasks[task_instance_id].TASK_NAME
            del self.tasks[task_instance_id]
            
            if task_instance_id in self.task_schedules:
                del self.task_schedules[task_instance_id]
            
            logger.info(f"任务取消注册成功: {task_name} ({task_instance_id})")
            return True
            
        except Exception as e:
            logger.error(f"任务取消注册失败: {task_instance_id}, 错误: {str(e)}")
            return False
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有任务信息
        
        Returns:
            List[Dict[str, Any]]: 任务信息列表
        """
        tasks_info = []
        for task_id, task in self.tasks.items():
            task_info = task.get_status()
            # 添加调度信息
            if task_id in self.task_schedules:
                task_info['schedule'] = self.task_schedules[task_id]
            tasks_info.append(task_info)
        return tasks_info
    
    def get_task_info(self, task_instance_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定任务的详细信息（兼容API调用）
        
        Args:
            task_instance_id: 任务实例ID
        
        Returns:
            Optional[Dict[str, Any]]: 任务信息，如果任务不存在则返回None
        """
        return self.get_task(task_instance_id)
        
    def get_task(self, task_instance_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定任务信息
        
        Args:
            task_instance_id: 任务实例ID
        
        Returns:
            Optional[Dict[str, Any]]: 任务信息，如果任务不存在则返回None
        """
        if task_instance_id not in self.tasks:
            return None
        
        task_info = self.tasks[task_instance_id].get_status()
        # 添加调度信息
        if task_instance_id in self.task_schedules:
            task_info['schedule'] = self.task_schedules[task_instance_id]
        
        return task_info
    
    def update_task_config(self, task_instance_id: str, config: Dict[str, Any]) -> bool:
        """
        更新任务配置
        
        Args:
            task_instance_id: 任务实例ID
            config: 新的配置参数
        
        Returns:
            bool: 更新是否成功
        """
        if task_instance_id not in self.tasks:
            logger.warning(f"任务不存在: {task_instance_id}")
            return False
        
        try:
            self.tasks[task_instance_id].update_config(config)
            logger.info(f"任务配置更新成功: {task_instance_id}")
            return True
        except Exception as e:
            logger.error(f"任务配置更新失败: {task_instance_id}, 错误: {str(e)}")
            return False
    
    def update_task_schedule(self, task_instance_id: str, schedule_type: str, 
                            schedule_config: Dict[str, Any]) -> bool:
        """
        更新任务调度配置
        
        Args:
            task_instance_id: 任务实例ID
            schedule_type: 调度类型 ('interval' 或 'cron')
            schedule_config: 调度配置参数
        
        Returns:
            bool: 更新是否成功
        """
        if task_instance_id not in self.tasks:
            logger.warning(f"任务不存在: {task_instance_id}")
            return False
        
        try:
            # 更新调度配置
            self.task_schedules[task_instance_id] = {
                'type': schedule_type,
                'config': schedule_config
            }
            
            # 重新创建调度器任务
            job_id = f"task_{task_instance_id}"
            task = self.tasks[task_instance_id]
            
            if schedule_type == 'interval':
                trigger = IntervalTrigger(**schedule_config)
            elif schedule_type == 'cron':
                trigger = CronTrigger(**schedule_config)
            else:
                logger.error(f"不支持的调度类型: {schedule_type}")
                return False
            
            if scheduler.get_job(job_id):
                scheduler.reschedule_job(job_id, trigger=trigger)
            else:
                scheduler.add_job(
                    func=task.run,
                    trigger=trigger,
                    id=job_id,
                    name=task.TASK_NAME,
                    replace_existing=True
                )
            
            logger.info(f"任务调度更新成功: {task.TASK_NAME} ({task_instance_id})")
            return True
            
        except Exception as e:
            logger.error(f"任务调度更新失败: {task_instance_id}, 错误: {str(e)}")
            return False
    
    def execute_task_now(self, task_instance_id: str) -> Optional[Dict[str, Any]]:
        """
        立即执行指定任务
        
        Args:
            task_instance_id: 任务实例ID
        
        Returns:
            Optional[Dict[str, Any]]: 任务执行结果，如果任务不存在则返回None
        """
        if task_instance_id not in self.tasks:
            logger.warning(f"任务不存在: {task_instance_id}")
            return None
        
        try:
            logger.info(f"立即执行任务: {task_instance_id}")
            return self.tasks[task_instance_id].run()
        except Exception as e:
            logger.error(f"任务立即执行失败: {task_instance_id}, 错误: {str(e)}")
            return None
    
    def stop_all_tasks(self) -> None:
        """
        停止并取消注册所有任务
        """
        task_instance_ids = list(self.tasks.keys())
        for task_instance_id in task_instance_ids:
            self.unregister_task(task_instance_id)
        logger.info("所有任务已停止")
    
    def get_all_available_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有可用的任务信息
        
        Returns:
            List[Dict[str, Any]]: 任务信息列表
        """
        tasks_info = []
        for task_id in TaskFactory.get_all_task_ids():
            task_class = TaskFactory.get_task_class(task_id)
            if task_class:
                tasks_info.append({
                    'task_id': task_id,
                    'task_name': task_class.TASK_NAME,
                    'description': task_class.TASK_DESCRIPTION
                })
        return tasks_info


# 注册task_implements目录中的任务类
from task_implements.HeartbeatTask import HeartbeatTask

# 创建全局任务管理器实例
task_manager = TaskManager()

# 注册任务类到TaskFactory
# 将任务类组织成列表，通过循环批量注册
task_classes = [
    HeartbeatTask
]

for task_class in task_classes:
    task_manager.register_task_class(task_class.TASK_ID, task_class)


__all__ = ["task_manager"]

