"""
Syslog服务基础组件定义
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import threading
import logging


class BaseComponent(ABC):
    """组件基类，所有syslog服务组件的父类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化基础组件
        
        Args:
            config: 组件配置
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"syslog.{self.__class__.__name__}")
        self._lock = threading.RLock()
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        初始化组件
        
        Returns:
            bool: 初始化是否成功
        """
        with self._lock:
            if not self._initialized:
                try:
                    result = self._initialize()
                    self._initialized = result
                    return result
                except Exception as e:
                    self.logger.error(f"Failed to initialize component: {e}")
                    return False
            return True
    
    @abstractmethod
    def _initialize(self) -> bool:
        """
        具体初始化逻辑，由子类实现
        
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    def shutdown(self):
        """
        关闭组件
        """
        with self._lock:
            if self._initialized:
                try:
                    self._shutdown()
                    self._initialized = False
                except Exception as e:
                    self.logger.error(f"Error during shutdown: {e}")
    
    @abstractmethod
    def _shutdown(self):
        """
        具体关闭逻辑，由子类实现
        """
        pass
    
    @property
    def is_initialized(self) -> bool:
        """
        组件是否已初始化
        
        Returns:
            bool: 是否已初始化
        """
        return self._initialized


class MessageProcessor(ABC):
    """消息处理器接口"""
    
    @abstractmethod
    def process(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理消息
        
        Args:
            message: 待处理的消息
            
        Returns:
            处理后的消息，返回None表示消息被过滤
        """
        pass


class ServiceManager:
    """服务管理器，管理所有组件的生命周期"""
    
    def __init__(self):
        """初始化服务管理器"""
        self._components = []
        self._lock = threading.RLock()
        self._started = False
    
    def register_component(self, component: BaseComponent):
        """
        注册组件
        
        Args:
            component: 要注册的组件
        """
        with self._lock:
            self._components.append(component)
    
    def start(self) -> bool:
        """
        启动所有组件
        
        Returns:
            bool: 是否全部启动成功
        """
        with self._lock:
            if not self._started:
                all_success = True
                for component in self._components:
                    if not component.initialize():
                        all_success = False
                self._started = all_success
                return all_success
            return True
    
    def stop(self):
        """
        停止所有组件
        """
        with self._lock:
            if self._started:
                # 逆序关闭组件，确保依赖关系正确
                for component in reversed(self._components):
                    component.shutdown()
                self._started = False
    
    @property
    def is_started(self) -> bool:
        """
        服务是否已启动
        
        Returns:
            bool: 是否已启动
        """
        return self._started