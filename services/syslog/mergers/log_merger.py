"""
日志合并模块
"""
import re
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from services.syslog.core import BaseComponent, MessageProcessor, LogMergeError
from services.syslog.filters import BlacklistManager
import logging


class MergeRule:
    """
    日志合并规则
    """
    
    def __init__(self, name: str, pattern: str, fields: List[str] = None):
        """
        初始化合并规则
        
        Args:
            name: 规则名称
            pattern: 匹配模式（正则表达式）
            fields: 用于分组的字段列表
        """
        self.name = name
        self.pattern = pattern
        self.fields = fields or ['host', 'program']
        self._compiled_pattern = None
        
        try:
            self._compiled_pattern = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern}' for rule '{name}': {e}")
    
    def matches(self, message: Dict[str, Any]) -> bool:
        """
        检查消息是否匹配该规则
        
        Args:
            message: 要检查的消息
            
        Returns:
            是否匹配
        """
        message_text = message.get('message', '')
        return bool(self._compiled_pattern.search(message_text))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            字典表示
        """
        return {
            'name': self.name,
            'pattern': self.pattern,
            'fields': self.fields
        }


class MergeGroup:
    """
    合并组，包含一组相似的消息
    """
    
    def __init__(self, group_key: str, rule_name: str, first_message: Dict[str, Any]):
        """
        初始化合并组
        
        Args:
            group_key: 分组键
            rule_name: 匹配的规则名称
            first_message: 第一条消息
        """
        self.group_key = group_key
        self.rule_name = rule_name
        self.messages = [first_message]
        self.created_at = datetime.now()
        self.last_updated_at = datetime.now()
        self.hosts = set()
        self.programs = set()
        
        # 初始化主机和程序集合
        if 'host' in first_message:
            self.hosts.add(first_message['host'])
        if 'program' in first_message:
            self.programs.add(first_message['program'])
    
    def add_message(self, message: Dict[str, Any]):
        """
        添加消息到合并组
        
        Args:
            message: 要添加的消息
        """
        self.messages.append(message)
        self.last_updated_at = datetime.now()
        
        # 更新主机和程序集合
        if 'host' in message:
            self.hosts.add(message['host'])
        if 'program' in message:
            self.programs.add(message['program'])
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取合并组的摘要信息
        
        Returns:
            摘要信息
        """
        return {
            'group_key': self.group_key,
            'rule_name': self.rule_name,
            'message_count': len(self.messages),
            'hosts': list(self.hosts),
            'programs': list(self.programs),
            'created_at': self.created_at.isoformat(),
            'last_updated_at': self.last_updated_at.isoformat(),
            'first_message': self.messages[0].get('message', ''),
            'last_message': self.messages[-1].get('message', '')
        }
    
    def is_expired(self, expiration_time: timedelta) -> bool:
        """
        检查合并组是否过期
        
        Args:
            expiration_time: 过期时间间隔
            
        Returns:
            是否过期
        """
        return datetime.now() - self.last_updated_at > expiration_time


class LogMerger(BaseComponent, MessageProcessor):
    """
    日志合并器，负责将相似的日志消息合并
    """
    
    def __init__(self, config: Dict[str, Any], blacklist_manager: Optional[BlacklistManager] = None):
        """
        初始化日志合并器
        
        Args:
            config: 配置
            blacklist_manager: 黑名单管理器（可选）
        """
        super().__init__(config)
        self._blacklist_manager = blacklist_manager
        self._rules = []
        self._merge_groups = {}
        self._merge_groups_lock = threading.RLock()
        self._time_window = timedelta(seconds=config.get('log_merge', {}).get('time_window', 60))
        self._min_messages = config.get('log_merge', {}).get('min_messages', 5)
        self._max_messages = config.get('log_merge', {}).get('max_messages', 1000)
        self._default_group_by_blacklist = config.get('log_merge', {}).get('default_group_by_blacklist', True)
        self._on_merge_complete = None
    
    def _initialize(self) -> bool:
        """
        初始化日志合并器
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 加载合并规则
            self._load_rules()
            self.logger.info(f"Log merger initialized with {len(self._rules)} rules")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize log merger: {e}")
            return False
    
    def _load_rules(self):
        """
        加载合并规则
        """
        rules_config = self.config.get('log_merge', {}).get('group_by_rules', [])
        for rule_config in rules_config:
            try:
                rule = MergeRule(
                    name=rule_config.get('name'),
                    pattern=rule_config.get('pattern', ''),
                    fields=rule_config.get('fields')
                )
                self._rules.append(rule)
            except ValueError as e:
                self.logger.error(f"Invalid merge rule: {e}")
    
    def set_on_merge_complete(self, callback: Callable[[MergeGroup], None]):
        """
        设置合并完成回调函数
        
        Args:
            callback: 当合并组满足条件时调用的回调函数
        """
        self._on_merge_complete = callback
    
    def process(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理消息，尝试进行合并
        
        Args:
            message: 待处理的消息
            
        Returns:
            如果消息被合并，返回None；否则返回原始消息
        """
        if not self.config.get('log_merge', {}).get('enabled', True):
            return message
        
        # 清理过期的合并组
        self._cleanup_old_groups()
        
        # 尝试合并消息
        if self._try_merge_log(message):
            return None
        
        return message
    
    def _try_merge_log(self, message: Dict[str, Any]) -> bool:
        """
        尝试合并日志消息
        
        Args:
            message: 待合并的消息
            
        Returns:
            是否成功合并
        """
        # 生成分组键
        group_key = self._generate_group_key(message)
        if not group_key:
            return False
        
        # 查找匹配的合并规则
        matching_rule = self._find_matching_merge_rule(message)
        rule_name = matching_rule.name if matching_rule else 'default'
        
        # 完整的分组键包括规则名
        full_group_key = f"{group_key}:{rule_name}"
        
        with self._merge_groups_lock:
            if full_group_key in self._merge_groups:
                # 添加到现有合并组
                merge_group = self._merge_groups[full_group_key]
                if self._is_mergeable(merge_group, message):
                    merge_group.add_message(message)
                    
                    # 检查是否达到合并条件
                    if len(merge_group.messages) >= self._min_messages:
                        self.logger.debug(f"Merge group {full_group_key} reached {len(merge_group.messages)} messages")
                        
                        # 如果达到最大消息数，触发合并完成
                        if len(merge_group.messages) >= self._max_messages:
                            self._finalize_merge_group(full_group_key)
                    
                    return True
            else:
                # 创建新的合并组
                self._merge_groups[full_group_key] = MergeGroup(full_group_key, rule_name, message)
                self.logger.debug(f"Created new merge group {full_group_key}")
                return True
        
        return False
    
    def _generate_group_key(self, message: Dict[str, Any]) -> str:
        """
        生成消息的分组键
        
        Args:
            message: 消息
            
        Returns:
            分组键
        """
        # 首先检查是否可以按黑名单类别分组
        if self._default_group_by_blacklist and self._blacklist_manager:
            blacklist_category = self._blacklist_manager.get_blacklist_category(message)
            if blacklist_category:
                host = message.get('host', 'unknown')
                return f"blacklist:{blacklist_category}:{host}"
        
        # 查找匹配的合并规则
        matching_rule = self._find_matching_merge_rule(message)
        if matching_rule:
            # 使用规则定义的字段生成分组键
            key_parts = [matching_rule.name]
            for field in matching_rule.fields:
                key_parts.append(message.get(field, 'unknown'))
            return ":".join(key_parts)
        
        # 默认分组键：host + program
        host = message.get('host', 'unknown')
        program = message.get('program', 'unknown')
        return f"default:{host}:{program}"
    
    def _find_matching_merge_rule(self, message: Dict[str, Any]) -> Optional[MergeRule]:
        """
        查找匹配消息的合并规则
        
        Args:
            message: 消息
            
        Returns:
            匹配的规则，如果没有匹配则返回None
        """
        for rule in self._rules:
            if rule.matches(message):
                return rule
        return None
    
    def _find_merge_group_by_rule(self, rule_name: str) -> List[MergeGroup]:
        """
        查找指定规则的所有合并组
        
        Args:
            rule_name: 规则名称
            
        Returns:
            合并组列表
        """
        result = []
        with self._merge_groups_lock:
            for group in self._merge_groups.values():
                if group.rule_name == rule_name:
                    result.append(group)
        return result
    
    def _is_mergeable(self, merge_group: MergeGroup, message: Dict[str, Any]) -> bool:
        """
        检查消息是否可以合并到指定的合并组
        
        Args:
            merge_group: 合并组
            message: 消息
            
        Returns:
            是否可以合并
        """
        # 检查时间窗口
        if merge_group.is_expired(self._time_window):
            return False
        
        # 检查主机匹配（如果配置了按主机分组）
        host = message.get('host')
        if host and host not in merge_group.hosts:
            # 如果消息来自新主机，不进行合并
            return False
        
        # 检查消息数量限制
        if len(merge_group.messages) >= self._max_messages:
            return False
        
        return True
    
    def _cleanup_old_groups(self):
        """
        清理过期的合并组
        """
        expired_keys = []
        
        with self._merge_groups_lock:
            for key, group in self._merge_groups.items():
                if group.is_expired(self._time_window):
                    expired_keys.append(key)
        
        # 处理过期的合并组
        for key in expired_keys:
            self._finalize_merge_group(key)
    
    def _finalize_merge_group(self, group_key: str):
        """
        完成合并组处理
        
        Args:
            group_key: 合并组键
        """
        with self._merge_groups_lock:
            if group_key in self._merge_groups:
                merge_group = self._merge_groups.pop(group_key)
                
                # 如果消息数量足够，触发回调
                if len(merge_group.messages) >= self._min_messages and self._on_merge_complete:
                    try:
                        self._on_merge_complete(merge_group)
                    except Exception as e:
                        self.logger.error(f"Error in merge complete callback: {e}")
                
                self.logger.info(f"Finalized merge group {group_key} with {len(merge_group.messages)} messages")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取合并器统计信息
        
        Returns:
            统计信息
        """
        with self._merge_groups_lock:
            stats = {
                'enabled': self.config.get('log_merge', {}).get('enabled', True),
                'active_groups': len(self._merge_groups),
                'total_rules': len(self._rules),
                'time_window': self._time_window.total_seconds(),
                'min_messages': self._min_messages,
                'max_messages': self._max_messages
            }
        return stats
    
    def _shutdown(self):
        """
        关闭日志合并器
        """
        # 处理所有剩余的合并组
        with self._merge_groups_lock:
            remaining_groups = list(self._merge_groups.keys())
        
        for group_key in remaining_groups:
            self._finalize_merge_group(group_key)
        
        self.logger.info("Log merger shut down")