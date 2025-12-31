#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据处理策略模块
实现策略模式，用于根据不同的metric_name处理不同类型的数据
"""

from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class DataStrategy(ABC):
    """
    数据处理策略接口
    所有具体的数据处理策略都需要实现这个接口
    """
    
    @abstractmethod
    def process_data(self, data):
        """
        处理数据的抽象方法
        
        Args:
            data: 需要处理的数据
            
        Returns:
            处理后的结果
        """
        pass

class StrategyFactory:
    """
    策略工厂类
    根据metric_name返回对应的策略实例
    使用手动维护的字典来管理策略
    """
    
    def __init__(self):
        self._strategies = {}

    def register_strategy(self, metric_name, strategy):
        """
        手动注册一个策略
        
        Args:
            metric_name: 指标名称
            strategy: 策略实例
        """
        if not isinstance(strategy, DataStrategy):
            raise ValueError("策略必须是DataStrategy的实例")
        
        self._strategies[metric_name] = strategy
        logger.info(f"手动注册策略: {metric_name} -> {strategy.__class__.__name__}")
    
    def unregister_strategy(self, metric_name):
        """
        手动注销一个策略
        
        Args:
            metric_name: 指标名称
        
        Returns:
            如果策略存在并被成功注销，则返回True；否则返回False
        """
        if metric_name in self._strategies:
            del self._strategies[metric_name]
            logger.info(f"注销策略: {metric_name}")
            return True
        return False
    
    def get_strategy(self, metric_name):
        """
        根据metric_name获取对应的策略实例
        
        Args:
            metric_name: 指标名称
            
        Returns:
            对应的策略实例，如果找不到则返回None
        """
        return self._strategies.get(metric_name)
    
    def get_all_strategies(self):
        """
        获取所有注册的策略
        
        Returns:
            所有注册的策略字典
        """
        return self._strategies.copy()

# 静态导入ifTable相关的所有解析器类
from services.dataStrategy.syslog_strategy import SyslogStrategy

_PARSER_CLASSES = {
    "syslog_data": SyslogStrategy,
}


# 创建全局策略工厂实例
strategy_factory = StrategyFactory()

# 在模块加载时自动注册默认解析器
try:
    for key, value in _PARSER_CLASSES.items():
        strategy_factory.register_strategy(key, value())
    logger.info(f"模块初始化时自动注册解析器完成")
except Exception as e:
    logger.error(f"注册数据存储器时发生错误: {str(e)}", exc_info=True)


# 便捷函数
def get_strategy(metric_name):
    """
    便捷函数，根据metric_name获取对应的策略实例
    
    Args:
        metric_name: 指标名称
        
    Returns:
        对应的策略实例，如果找不到则返回None
    """
    return strategy_factory.get_strategy(metric_name)

__all__ = ["get_strategy", "DataStrategy"]