"""
任务工厂模块

负责创建和管理任务实例，提供通用的任务管理功能
"""
from typing import Type, Dict, Optional, Any, List
import logging
from task_core.task_base import BaseTask

# 获取logger实例
logger = logging.getLogger('task_factory')


class TaskFactory:
    """
    任务工厂类，负责创建和管理所有任务实例
    
    提供任务类注册、任务实例创建、任务配置管理等通用功能
    """
    
    # 任务类映射
    TASK_CLASSES: Dict[str, Type[BaseTask]] = {}
    
    # 任务默认配置映射
    TASK_CONFIGS: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def register_task_class(cls, task_id: str, task_class: Type[BaseTask]) -> None:
        """
        注册任务类
        
        Args:
            task_id: 任务ID
            task_class: 任务类
        """
        # 检查是否为BaseTask的子类
        if not issubclass(task_class, BaseTask):
            logger.error(f"任务类必须是BaseTask的子类: {task_class.__name__}")
            raise TypeError(f"任务类必须是BaseTask的子类: {task_class.__name__}")
        
        # 检查是否已存在
        if task_id in cls.TASK_CLASSES:
            logger.warning(f"任务类ID '{task_id}' 已存在，将被覆盖")
        
        # 存储任务类映射
        cls.TASK_CLASSES[task_id] = task_class
        logger.debug(f"成功注册任务类: {task_id} -> {task_class.__name__}")
    
    @classmethod
    def get_task_class(cls, task_id: str) -> Optional[Type[BaseTask]]:
        """
        获取任务类
        
        Args:
            task_id: 任务ID
            
        Returns:
            Type[BaseTask]: 任务类，如果不存在则返回None
        """
        if not cls.TASK_CLASSES:
            logger.warning("任务类映射为空，请先注册任务类")
        
        return cls.TASK_CLASSES.get(task_id)
    
    @classmethod
    def get_all_task_ids(cls) -> List[str]:
        """
        获取所有已注册的任务ID
        
        Returns:
            List[str]: 任务ID列表
        """
        return list(cls.TASK_CLASSES.keys())
    
    @classmethod
    def get_task_config(cls, task_id: str) -> Dict[str, Any]:
        """
        获取任务的默认配置
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务默认配置
        """
        return cls.TASK_CONFIGS.get(task_id, {})
    
    @classmethod
    def create_task(cls, task_id: str, base_config: Optional[Dict[str, Any]] = None) -> Optional[BaseTask]:
        """
        创建任务实例
        
        Args:
            task_id: 任务ID
            base_config: 基础配置
            
        Returns:
            BaseTask: 任务实例，如果创建失败则返回None
        """
        logger.debug(f"开始创建任务实例: {task_id}")
        
        # 获取任务类
        task_class = cls.get_task_class(task_id)
        if not task_class:
            logger.error(f"无法创建任务实例: 任务ID '{task_id}' 的任务类未注册")
            return None
        
        try:
            # 合并默认配置和基础配置
            logger.debug(f"获取任务 '{task_id}' 的默认配置")
            default_config = cls.get_task_config(task_id)
            merged_config = {**default_config, **(base_config or {})}
            logger.debug(f"任务 '{task_id}' 配置已合并: {merged_config}")
            
            # 创建任务实例
            logger.debug(f"实例化任务类: {task_class.__name__}")
            task_instance = task_class(merged_config)
            logger.info(f"成功创建任务实例: {task_id} -> {task_class.__name__}")
            return task_instance
        except Exception as e:
            logger.error(f"创建任务实例失败: {task_id}, 错误: {str(e)}")
            logger.debug(f"异常详情: {str(e)}", exc_info=True)
            return None