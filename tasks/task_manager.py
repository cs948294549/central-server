"""
任务管理器

负责从配置文件加载和注册所有定时任务
参照 collector 项目的实现方式
"""
import logging
import yaml
from pathlib import Path
from core.scheduler import scheduler

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器"""

    def __init__(self, config_file='config/task_config.yaml'):
        self.config_file = config_file
        self.tasks = {}

    def load_task_config(self):
        """加载任务配置"""
        try:
            config_path = Path(self.config_file)
            if not config_path.exists():
                logger.warning(f"配置文件不存在: {self.config_file}")
                return []

            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            tasks = config.get('tasks', [])
            logger.info(f"从配置文件加载了 {len(tasks)} 个任务定义")
            return tasks
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return []

    def register_task(self, task_id: str, func, trigger_type: str = 'cron', **kwargs):
        """
        注册单个定时任务

        Args:
            task_id: 任务唯一标识
            func: 任务执行函数
            trigger_type: 触发器类型，'cron' 或 'interval'
            **kwargs: 触发器参数
                cron: hour, minute, day, month, day_of_week 等
                interval: seconds, minutes, hours, days 等
        """
        try:
            if trigger_type == 'cron':
                job = scheduler.add_job(
                    func,
                    trigger='cron',
                    id=task_id,
                    replace_existing=True,
                    **kwargs
                )
            elif trigger_type == 'interval':
                job = scheduler.add_job(
                    func,
                    trigger='interval',
                    id=task_id,
                    replace_existing=True,
                    **kwargs
                )
            else:
                logger.error(f"不支持的触发器类型: {trigger_type}")
                return False

            self.tasks[task_id] = {
                'job': job,
                'func': func,
                'trigger_type': trigger_type,
                'kwargs': kwargs
            }

            return True

        except Exception as e:
            logger.error(f"注册任务失败 {task_id}: {e}")
            return False

    def register_all_tasks(self):
        """
        从配置文件注册所有任务
        """
        tasks_config = self.load_task_config()

        if not tasks_config:
            logger.warning("没有找到任务配置")
            return

        registered_count = 0
        skipped_count = 0

        for task in tasks_config:
            # 检查任务是否启用
            if not task.get('enabled', True):
                task_id = task.get('id', 'unknown')
                logger.info(f"任务 {task_id} 已禁用，跳过")
                skipped_count += 1
                continue

            try:
                task_id = task['id']
                task_type = task['type']
                module_path = task['module']
                function_name = task['function']
                description = task.get('description', '')

                # 动态导入模块和函数
                import importlib
                module = importlib.import_module(module_path)
                func = getattr(module, function_name)

                # 根据任务类型注册
                if task_type == 'cron':
                    schedule = task['schedule']
                    # 解析 cron 表达式
                    parts = schedule.split()
                    if len(parts) != 5:
                        logger.error(f"任务 {task_id} cron 表达式格式错误: {schedule}")
                        continue

                    minute, hour, day, month, day_of_week = parts

                    success = self.register_task(
                        task_id=task_id,
                        func=func,
                        trigger_type='cron',
                        minute=minute,
                        hour=hour,
                        day=day,
                        month=month,
                        day_of_week=day_of_week
                    )

                    if success:
                        logger.info(f"✓ 注册 cron 任务: {task_id} - {description} - {schedule}")
                        registered_count += 1
                    else:
                        logger.error(f"✗ 注册 cron 任务失败: {task_id}")

                elif task_type == 'interval':
                    schedule = task['schedule']
                    hours = schedule.get('hours', 0)
                    minutes = schedule.get('minutes', 0)
                    seconds = schedule.get('seconds', 0)

                    success = self.register_task(
                        task_id=task_id,
                        func=func,
                        trigger_type='interval',
                        hours=hours,
                        minutes=minutes,
                        seconds=seconds
                    )

                    if success:
                        logger.info(f"✓ 注册间隔任务: {task_id} - {description} - {hours}h {minutes}m {seconds}s")
                        registered_count += 1
                    else:
                        logger.error(f"✗ 注册间隔任务失败: {task_id}")

            except Exception as e:
                logger.error(f"注册任务 {task.get('id', 'unknown')} 失败: {e}")

        logger.info(f"任务注册完成 - 成功: {registered_count}, 跳过: {skipped_count}")

    def remove_task(self, task_id: str):
        """移除任务"""
        try:
            scheduler.remove_job(task_id)
            if task_id in self.tasks:
                del self.tasks[task_id]
            logger.info(f"已移除任务: {task_id}")
            return True
        except Exception as e:
            logger.error(f"移除任务失败 {task_id}: {e}")
            return False

    def pause_task(self, task_id: str):
        """暂停任务"""
        try:
            scheduler.pause_job(task_id)
            logger.info(f"已暂停任务: {task_id}")
            return True
        except Exception as e:
            logger.error(f"暂停任务失败 {task_id}: {e}")
            return False

    def resume_task(self, task_id: str):
        """恢复任务"""
        try:
            scheduler.resume_job(task_id)
            logger.info(f"已恢复任务: {task_id}")
            return True
        except Exception as e:
            logger.error(f"恢复任务失败 {task_id}: {e}")
            return False

    def get_task_info(self):
        """获取所有任务信息"""
        task_list = []
        for task_id, task_data in self.tasks.items():
            try:
                job = scheduler.get_job(task_id)
                info = {
                    'id': task_id,
                    'trigger_type': task_data['trigger_type'],
                    'next_run_time': str(job.next_run_time) if job and job.next_run_time else 'N/A'
                }
                task_list.append(info)
            except Exception as e:
                logger.error(f"获取任务 {task_id} 信息失败: {e}")
        return task_list

    def stop_all_tasks(self):
        """停止所有任务"""
        logger.info("正在停止所有任务...")
        task_ids = list(self.tasks.keys())
        for task_id in task_ids:
            self.remove_task(task_id)
        logger.info("所有任务已停止")


# 创建全局任务管理器实例
task_manager = TaskManager()


# 导出
__all__ = ['task_manager', 'TaskManager']
