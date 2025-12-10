"""
黑名单过滤模块
"""
import re
import threading
import time
import requests
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from services.syslog.core import BaseComponent, MessageProcessor, BlacklistError
import logging


class BlacklistEntry:
    """
    黑名单条目
    """
    
    def __init__(self, entry_id: str, pattern: str, category: str, description: str = None):
        """
        初始化黑名单条目
        
        Args:
            entry_id: 条目ID
            pattern: 匹配模式（正则表达式）
            category: 类别
            description: 描述
        """
        self.id = entry_id
        self.pattern = pattern
        self.category = category
        self.description = description
        self._compiled_pattern = None
        
        try:
            self._compiled_pattern = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern}': {e}")
    
    def matches(self, text: str) -> bool:
        """
        检查文本是否匹配该黑名单条目
        
        Args:
            text: 要检查的文本
            
        Returns:
            是否匹配
        """
        if not text:
            return False
        return bool(self._compiled_pattern.search(text))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            字典表示
        """
        return {
            'id': self.id,
            'pattern': self.pattern,
            'category': self.category,
            'description': self.description
        }


class BlacklistManager(BaseComponent):
    """
    黑名单管理器，负责加载和管理黑名单规则
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化黑名单管理器
        
        Args:
            config: 配置
        """
        super().__init__(config)
        self._blacklist = []  # 黑名单条目列表
        self._categories = set()  # 启用的类别
        self._blacklist_lock = threading.RLock()
        self._last_refresh_time = None
        self._refresh_thread = None
        self._stop_event = threading.Event()
    
    def _initialize(self) -> bool:
        """
        初始化黑名单管理器
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 获取配置的黑名单类别
            categories = self.config.get('blacklist', {}).get('categories', [])
            self._categories = set(categories)
            
            # 如果启用了黑名单，立即刷新一次
            if self.config.get('blacklist', {}).get('enabled', False):
                self._refresh_blacklist()
                
                # 启动定期刷新线程
                refresh_interval = self.config.get('blacklist', {}).get('refresh_interval', 3600)
                if refresh_interval > 0:
                    self._start_blacklist_refresh_thread(refresh_interval)
            
            self.logger.info(f"Blacklist manager initialized, categories: {self._categories}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize blacklist manager: {e}")
            return False
    
    def _refresh_blacklist(self):
        """
        刷新黑名单配置
        """
        if not self.config.get('blacklist', {}).get('enabled', False):
            return
        
        blacklist_url = self.config.get('blacklist', {}).get('blacklist_url')
        if not blacklist_url:
            self.logger.warning("Blacklist URL not configured")
            return
        
        try:
            self.logger.info(f"Fetching blacklist from {blacklist_url}")
            response = requests.get(blacklist_url, timeout=30)
            response.raise_for_status()
            
            # 解析黑名单数据
            blacklist_data = response.json()
            new_entries = []
            
            for entry_data in blacklist_data.get('entries', []):
                # 只加载启用的类别
                if entry_data.get('category') in self._categories:
                    try:
                        entry = BlacklistEntry(
                            entry_id=entry_data.get('id', str(len(new_entries))),
                            pattern=entry_data.get('pattern', ''),
                            category=entry_data.get('category', 'unknown'),
                            description=entry_data.get('description')
                        )
                        new_entries.append(entry)
                    except ValueError as e:
                        self.logger.error(f"Invalid blacklist entry: {e}")
            
            # 更新黑名单
            with self._blacklist_lock:
                self._blacklist = new_entries
                self._last_refresh_time = datetime.now()
            
            self.logger.info(f"Blacklist refreshed, loaded {len(new_entries)} entries")
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch blacklist: {e}")
            raise BlacklistError(f"Failed to fetch blacklist: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Invalid blacklist data format: {e}")
            raise BlacklistError(f"Invalid blacklist data format: {e}")
    
    def _start_blacklist_refresh_thread(self, interval: int):
        """
        启动黑名单刷新线程
        
        Args:
            interval: 刷新间隔（秒）
        """
        self._stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=self._blacklist_refresh_loop,
            args=(interval,),
            daemon=True
        )
        self._refresh_thread.start()
    
    def _blacklist_refresh_loop(self, interval: int):
        """
        黑名单刷新循环
        
        Args:
            interval: 刷新间隔（秒）
        """
        while not self._stop_event.is_set():
            try:
                # 等待指定的间隔时间
                if self._stop_event.wait(timeout=interval):
                    break
                
                # 刷新黑名单
                self._refresh_blacklist()
                
            except Exception as e:
                self.logger.error(f"Error in blacklist refresh loop: {e}")
                # 出错后等待较短时间再重试
                time.sleep(min(interval, 60))
    
    def is_blacklisted(self, message: Dict[str, Any]) -> bool:
        """
        检查消息是否在黑名单中
        
        Args:
            message: 要检查的消息
            
        Returns:
            是否在黑名单中
        """
        if not self.config.get('blacklist', {}).get('enabled', False):
            return False
        
        with self._blacklist_lock:
            blacklist_entries = self._blacklist.copy()
        
        # 要检查的字段
        check_fields = ['message', 'host', 'program', 'raw']
        
        for entry in blacklist_entries:
            for field in check_fields:
                if field in message and message[field]:
                    if entry.matches(str(message[field])):
                        self.logger.debug(f"Message blacklisted by pattern '{entry.pattern}' (category: {entry.category})")
                        return True
        
        return False
    
    def get_blacklist_category(self, message: Dict[str, Any]) -> Optional[str]:
        """
        获取消息匹配的黑名单类别
        
        Args:
            message: 要检查的消息
            
        Returns:
            匹配的类别，如果没有匹配则返回None
        """
        if not self.config.get('blacklist', {}).get('enabled', False):
            return None
        
        with self._blacklist_lock:
            blacklist_entries = self._blacklist.copy()
        
        # 要检查的字段
        check_fields = ['message', 'host', 'program', 'raw']
        
        for entry in blacklist_entries:
            for field in check_fields:
                if field in message and message[field]:
                    if entry.matches(str(message[field])):
                        return entry.category
        
        return None
    
    def get_blacklist_stats(self) -> Dict[str, Any]:
        """
        获取黑名单统计信息
        
        Returns:
            统计信息
        """
        with self._blacklist_lock:
            stats = {
                'enabled': self.config.get('blacklist', {}).get('enabled', False),
                'entry_count': len(self._blacklist),
                'categories': list(self._categories),
                'last_refresh_time': self._last_refresh_time.isoformat() if self._last_refresh_time else None
            }
        return stats
    
    def _shutdown(self):
        """
        关闭黑名单管理器
        """
        # 停止刷新线程
        self._stop_event.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
            self._refresh_thread = None
        
        # 清空黑名单
        with self._blacklist_lock:
            self._blacklist = []
        
        self.logger.info("Blacklist manager shut down")


class BlacklistFilter(MessageProcessor):
    """
    黑名单过滤器，实现消息处理器接口
    """
    
    def __init__(self, blacklist_manager: BlacklistManager):
        """
        初始化黑名单过滤器
        
        Args:
            blacklist_manager: 黑名单管理器实例
        """
        self.blacklist_manager = blacklist_manager
        self.logger = logging.getLogger('syslog.BlacklistFilter')
        self._blacklisted_count = 0
        self._total_count = 0
        self._stats_lock = threading.Lock()
    
    def process(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理消息，检查是否在黑名单中
        
        Args:
            message: 待处理的消息
            
        Returns:
            如果消息不在黑名单中，返回原消息；否则返回None
        """
        with self._stats_lock:
            self._total_count += 1
        
        if self.blacklist_manager.is_blacklisted(message):
            with self._stats_lock:
                self._blacklisted_count += 1
            # 如果需要记录被过滤的消息，可以在这里添加日志
            # self.logger.debug(f"Filtered blacklisted message: {message.get('message', '').strip()}")
            return None
        
        return message
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取过滤器统计信息
        
        Returns:
            统计信息
        """
        with self._stats_lock:
            stats = {
                'total_messages': self._total_count,
                'blacklisted_messages': self._blacklisted_count,
                'pass_rate': 0.0
            }
            if self._total_count > 0:
                stats['pass_rate'] = (self._total_count - self._blacklisted_count) / self._total_count * 100
        return stats