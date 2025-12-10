#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

# 导入项目中的kafka客户端
from function_messaging.kafka_client import get_syslog_consumer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('syslog_service')


class SyslogService:
    """
    Syslog服务类
    采用单例模式，负责处理syslog日志并根据配置进行处理
    """
    
    # 单例模式的私有实例
    _instance = None
    _lock = threading.RLock()
    
    # 默认配置
    DEFAULT_CONFIG = {
        'kafka_topic': 'syslog_messages',
        'config_file_path': 'config/syslog_config.json',
        'refresh_interval': 60,  # 默认60秒刷新一次配置
        'enabled_processors': ['default'],
        'processors': {
            'default': {
                'enabled': True,
                'pattern': '.*',
                'action': 'forward'
            }
        },
        # 日志黑名单配置
        'blacklist': {
            'enabled': True,
            'blacklist_url': 'http://localhost:8000/api/blacklist',  # 黑名单配置获取URL
            'refresh_interval': 300,  # 黑名单刷新间隔（秒）
            'categories': {
                'ip_addresses': [],  # 黑名单IP地址
                'hosts': [],  # 黑名单主机名
                'messages': [],  # 黑名单消息模式（正则表达式）
                'facilities': [],  # 黑名单设施
                'severities': []  # 黑名单严重程度
            }
        },
        # 日志合并配置
        'log_merge': {
            'enabled': True,
            'time_window': 300,  # 合并时间窗口（秒）
            'min_count': 3,  # 最小合并数量
            'max_count': 100,  # 最大合并数量
            'group_fields': ['source', 'facility', 'severity'],  # 分组字段
            'merge_rules': [
                {
                    'name': 'default_merge',
                    'enabled': True,
                    'match_pattern': '.*',
                    'group_pattern': '.*',  # 用于分组的正则表达式
                    'group_template': None  # 分组模板，可选
                },
                {
                    'name': 'authentication_errors',
                    'enabled': True,
                    'match_pattern': '.*authentication.*error.*',
                    'group_pattern': '.*authentication.*error.*',
                    'group_template': 'Multiple authentication errors detected'
                },
                {
                    'name': 'connection_refused',
                    'enabled': True,
                    'match_pattern': '.*connection.*refused.*',
                    'group_pattern': '.*connection.*refused.*',
                    'group_template': 'Connection refused errors'
                },
                {
                    'name': 'port_scan',
                    'enabled': True,
                    'match_pattern': '.*port.*scan.*|.*scanning.*',
                    'group_pattern': '.*port.*scan.*|.*scanning.*',
                    'group_template': 'Potential port scanning detected'
                }
            ]
        },
        # 告警配置
        'alert_config': {
            'enabled': True,
            'channels': ['kafka'],  # 告警发送渠道
            'alert_topic': 'syslog_alerts',
            'severity_map': {
                'emerg': 'critical',
                'alert': 'critical',
                'crit': 'critical',
                'err': 'error',
                'warning': 'warning',
                'notice': 'info',
                'info': 'info',
                'debug': 'debug'
            }
        }
    }
    
    def __new__(cls):
        """实现单例模式"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SyslogService, cls).__new__(cls)
                # 初始化实例属性
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化方法，确保只初始化一次"""
        with self._lock:
            if not self._initialized:
                self._config = self.DEFAULT_CONFIG.copy()
                self._kafka_client = None
                self._running = False
                self._config_thread = None
                self._consumer_thread = None
                self._blacklist_thread = None
                self._last_config_time = 0
                self._last_blacklist_refresh_time = 0
                # 日志合并相关属性
                self._log_groups = {}
                self._group_lock = threading.RLock()
                self._last_merge_time = {}
                # 黑名单相关属性
                self._blacklist = self._config.get('blacklist', {}).get('categories', {}).copy()
                self._blacklist_lock = threading.RLock()
                # 告警ID缓存，结构: {(host, rule_name): {'alert_id': str, 'created_at': float}}
                self._alert_cache = {}
                self._alert_cache_lock = threading.RLock()
                self._initialized = True
                logger.info("SyslogService instance initialized")
    
    def initialize(self):
        """初始化服务，连接Kafka并启动配置更新线程"""
        try:
            # 初始化Kafka客户端
            self._kafka_client = get_syslog_consumer()
            
            # 加载配置
            self._load_config()
            
            # 启动配置更新线程
            self._start_config_refresh_thread()
            
            # 启动黑名单更新线程
            self._start_blacklist_refresh_thread()
            
            # 启动消息消费线程
            self._start_message_consumer_thread()
            
            logger.info("SyslogService initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SyslogService: {str(e)}")
            return False
    
    def _start_message_consumer_thread(self):
        """启动消息消费线程"""
        if not self._running:
            self._running = True
        
        # 创建并启动消息消费线程
        self._consumer_thread = threading.Thread(target=self._consume_messages, daemon=True)
        self._consumer_thread.start()
        logger.info("Message consumer thread started")
    
    def _start_blacklist_refresh_thread(self):
        """启动黑名单更新线程"""
        if not self._running:
            self._running = True
        
        # 立即刷新一次黑名单
        self._refresh_blacklist()
        
        # 创建并启动黑名单更新线程
        self._blacklist_thread = threading.Thread(target=self._blacklist_refresh_loop, daemon=True)
        self._blacklist_thread.start()
        logger.info("Blacklist refresh thread started")
    
    def _blacklist_refresh_loop(self):
        """黑名单更新循环"""
        while self._running:
            try:
                # 获取黑名单刷新间隔
                refresh_interval = self._config.get('blacklist', {}).get('refresh_interval', 300)
                time.sleep(refresh_interval)
                self._refresh_blacklist()
            except Exception as e:
                logger.error(f"Error in blacklist refresh loop: {str(e)}")
                # 出错后短暂休眠再试
                time.sleep(10)
    
    def _refresh_blacklist(self):
        """从配置源刷新黑名单"""
        try:
            blacklist_config = self._config.get('blacklist', {})
            
            # 如果黑名单功能未启用，直接返回
            if not blacklist_config.get('enabled', False):
                return
            
            blacklist_url = blacklist_config.get('blacklist_url')
            
            if blacklist_url:
                # 尝试从URL获取黑名单
                try:
                    import requests
                    response = requests.get(blacklist_url, timeout=10)
                    response.raise_for_status()
                    new_blacklist = response.json()
                    
                    with self._blacklist_lock:
                        self._blacklist = new_blacklist.get('categories', {})
                    
                    self._last_blacklist_refresh_time = time.time()
                    logger.info(f"Successfully refreshed blacklist from {blacklist_url}")
                except Exception as e:
                    logger.error(f"Failed to get blacklist from URL: {str(e)}")
                    # 如果从URL获取失败，使用配置文件中的黑名单
                    with self._blacklist_lock:
                        self._blacklist = blacklist_config.get('categories', {}).copy()
            else:
                # 如果没有配置URL，使用配置文件中的黑名单
                with self._blacklist_lock:
                    self._blacklist = blacklist_config.get('categories', {}).copy()
                
            self._last_blacklist_refresh_time = time.time()
            logger.info(f"Blacklist updated, current entries: {json.dumps({k: len(v) for k, v in self._blacklist.items()})}")
            
        except Exception as e:
            logger.error(f"Error refreshing blacklist: {str(e)}")
    
    def _consume_messages(self):
        """持续从Kafka消费消息并处理"""
        try:
            logger.info("Starting to consume syslog messages from Kafka")
            
            if not self._kafka_client:
                logger.error("Kafka consumer not initialized")
                return
            
            while self._running:
                try:
                    # 从Kafka获取消息
                    message = self._kafka_client.poll(timeout=1.0)
                    
                    if message:
                        # 确保消息格式包含必要的字段
                        if isinstance(message, dict):
                            # 提取必要字段，如果不存在则使用默认值
                            syslog_message = {
                                'host': message.get('host', 'unknown'),
                                'timestamp': message.get('timestamp', datetime.now().isoformat()),
                                'msg': message.get('msg', '')
                            }
                            
                            # 处理日志消息
                            self.process_syslog_message(syslog_message)
                        else:
                            logger.warning(f"Received non-dictionary message: {type(message)}")
                except Exception as e:
                    logger.error(f"Error consuming message: {str(e)}")
                    # 短暂休眠后继续
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in message consumer thread: {str(e)}")
    
    def shutdown(self):
        """关闭服务"""
        self._running = False
        if self._config_thread and self._config_thread.is_alive():
            self._config_thread.join(timeout=5.0)
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5.0)
        if self._blacklist_thread and self._blacklist_thread.is_alive():
            self._blacklist_thread.join(timeout=5.0)
        if self._kafka_client:
            self._kafka_client.close()
        logger.info("SyslogService shutdown")
    
    def _load_config(self):
        """加载配置文件"""
        try:
            config_path = self._config.get('config_file_path')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    new_config = json.load(f)
                    # 合并配置，保留默认值
                    self._merge_config(new_config)
                    self._last_config_time = time.time()
                    logger.info(f"Config loaded from {config_path}")
            else:
                logger.warning(f"Config file not found: {config_path}, using default config")
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
    
    def _merge_config(self, new_config: Dict):
        """合并新配置到当前配置"""
        for key, value in new_config.items():
            if key in self._config and isinstance(self._config[key], dict) and isinstance(value, dict):
                # 递归合并字典
                self._config[key].update(value)
            else:
                self._config[key] = value
    
    def _start_config_refresh_thread(self):
        """启动配置更新线程"""
        self._running = True
        self._config_thread = threading.Thread(target=self._config_refresh_loop, daemon=True)
        self._config_thread.start()
        logger.info("Config refresh thread started")
    
    def _config_refresh_loop(self):
        """配置更新循环"""
        while self._running:
            try:
                interval = self._config.get('refresh_interval', 60)
                time.sleep(interval)
                self._load_config()
            except Exception as e:
                logger.error(f"Error in config refresh loop: {str(e)}")
                # 出错后短暂休眠再试
                time.sleep(10)
    
    def _is_blacklisted(self, message: Dict) -> bool:
        """
        检查消息是否在黑名单中
        
        Args:
            message: 日志消息
            
        Returns:
            bool: 是否在黑名单中
        """
        with self._blacklist_lock:
            # 深拷贝当前黑名单以避免在检查过程中被修改
            current_blacklist = {k: v.copy() for k, v in self._blacklist.items()}
        
        # 检查IP地址黑名单
        source_ip = message.get('host')
        if source_ip and source_ip in current_blacklist.get('ip_addresses', []):
            logger.debug(f"Message from blacklisted IP: {source_ip}")
            return True
        
        # 检查主机名黑名单
        if source_ip and source_ip in current_blacklist.get('hosts', []):
            logger.debug(f"Message from blacklisted host: {source_ip}")
            return True
        
        # 检查设施黑名单
        facility = message.get('facility')
        if facility and facility in current_blacklist.get('facilities', []):
            logger.debug(f"Message with blacklisted facility: {facility}")
            return True
        
        # 检查严重程度黑名单
        severity = message.get('severity')
        if severity and severity in current_blacklist.get('severities', []):
            logger.debug(f"Message with blacklisted severity: {severity}")
            return True
        
        # 检查消息模式黑名单
        msg_content = message.get('msg', '')
        if msg_content:
            for pattern in current_blacklist.get('messages', []):
                if self._match_message(message, pattern):
                    logger.debug(f"Message matched blacklisted pattern: {pattern}")
                    return True
        
        return False
    
    def process_syslog_message(self, message: Dict):
        """
        处理接收到的syslog消息
        
        Args:
            message: syslog消息字典，包含必要的字段
        
        Returns:
            bool: 处理是否成功
        """
        try:
            # 确保消息格式正确
            if not isinstance(message, dict):
                logger.error(f"Invalid message type: {type(message)}")
                return False
            
            # 添加时间戳
            if 'timestamp' not in message:
                message['timestamp'] = datetime.now().isoformat()
            
            # 检查黑名单过滤
            if self._config.get('blacklist', {}).get('enabled', False) and self._is_blacklisted(message):
                logger.debug(f"Message filtered by blacklist: {message.get('host')} - {message.get('msg', '')[:50]}...")
                return True
            
            # 根据配置处理消息
            processed_message = self._apply_processors(message)
            
            # 如果消息被处理器标记为丢弃，则返回
            if processed_message is None:
                return True
            
            # 检查是否启用日志合并
            if self._config.get('log_merge', {}).get('enabled', False):
                # 尝试合并日志
                if self._try_merge_log(processed_message):
                    # 日志被合并，不需要立即发送
                    return True
            
            # 发送到Kafka
            self._send_to_kafka(processed_message)
            
            return True
        except Exception as e:
            logger.error(f"Error processing syslog message: {str(e)}")
            return False
    
    def _try_merge_log(self, message: Dict) -> bool:
        """
        尝试合并日志消息，支持黑名单分组和正则表达式分组
        
        Args:
            message: 日志消息
            
        Returns:
            bool: 是否成功合并
        """
        try:
            merge_config = self._config.get('log_merge', {})
            time_window = merge_config.get('time_window', 300)
            min_count = merge_config.get('min_count', 3)
            max_count = merge_config.get('max_count', 100)
            
            current_time = time.time()
            
            with self._group_lock:
                # 检查是否需要清理过期的组
                self._cleanup_old_groups(current_time, time_window)
                
                # 查找匹配的合并规则
                matching_rule = self._find_matching_merge_rule(message)
                if not matching_rule:
                    return False
                
                # 使用更新后的方法生成分组键，考虑黑名单和规则匹配
                group_key = self._generate_group_key(
                    message, 
                    merge_config.get('group_fields', []),
                    matching_rule
                )
                
                # 获取或创建日志组
                if group_key not in self._log_groups:
                    self._log_groups[group_key] = {
                        'messages': [],
                        'count': 0,
                        'first_timestamp': current_time,
                        'last_timestamp': current_time,
                        'rule_name': matching_rule['name'],
                        'host': message.get('host', message.get('source', 'unknown')),
                        'group_name': matching_rule.get('name', 'default')
                    }
                
                log_group = self._log_groups[group_key]
                
                # 检查是否可以合并到现有组
                if self._is_mergeable(message, log_group, matching_rule):
                    # 添加到组
                    log_group['messages'].append(message.copy())
                    log_group['count'] += 1
                    log_group['last_timestamp'] = current_time
                    
                    logger.debug(f"Message merged into group {group_key}, current count: {log_group['count']}")
                    
                    # 检查是否达到合并阈值
                    if log_group['count'] >= min_count:
                        # 生成合并告警
                        self._create_merge_alert(log_group)
                        # 清空组
                        if log_group['count'] >= max_count:
                            logger.info(f"Group {group_key} reached max count, clearing")
                            del self._log_groups[group_key]
                        return True
            
            return False
        except Exception as e:
            logger.error(f"Error merging log: {str(e)}")
            return False
    
    def _generate_group_key(self, message: Dict, group_fields: List[str], matching_rule: Optional[Dict] = None) -> str:
        """
        根据指定字段和规则生成分组键，优先考虑黑名单分组
        
        Args:
            message: 日志消息
            group_fields: 分组字段列表
            matching_rule: 匹配的合并规则
            
        Returns:
            分组键字符串
        """
        # 获取主机信息
        host = message.get('host', message.get('source', 'unknown'))
        
        # 检查消息是否匹配黑名单模式
        is_blacklist_match = False
        with self._blacklist_lock:
            # 检查消息模式黑名单
            msg_content = message.get('msg', message.get('message', ''))
            if msg_content:
                for pattern in self._blacklist.get('messages', []):
                    try:
                        import re
                        if re.search(pattern, msg_content, re.IGNORECASE):
                            is_blacklist_match = True
                            # 使用黑名单模式作为分组的一部分
                            return f"blacklist_{host}_{pattern[:50]}"  # 限制模式长度
                    except Exception as e:
                        logger.error(f"Error checking blacklist pattern {pattern}: {str(e)}")
        
        # 如果有匹配的规则，使用规则名作为分组的一部分
        if matching_rule and matching_rule.get('name') != 'default_merge':
            rule_name = matching_rule.get('name', 'unknown')
            return f"rule_{host}_{rule_name}"
        
        # 如果没有匹配的规则，使用传统的字段分组
        if group_fields:
            key_parts = [host]  # 始终包含主机信息
            for field in group_fields:
                if field not in ['host', 'source']:  # 避免重复包含主机信息
                    key_parts.append(str(message.get(field, 'unknown')))
            return '_'.join(key_parts)
        
        # 默认分组
        return f"default_{host}"
    
    def _find_matching_merge_rule(self, message: Dict) -> Optional[Dict]:
        """
        查找匹配的合并规则
        
        Args:
            message: 日志消息
            
        Returns:
            匹配的规则，如果没有匹配则返回None
        """
        merge_rules = self._config.get('log_merge', {}).get('merge_rules', [])
        
        for rule in merge_rules:
            if not rule.get('enabled', False):
                continue
            
            # 检查消息是否匹配规则的匹配模式
            match_pattern = rule.get('match_pattern', '.*')
            if self._match_message(message, match_pattern):
                return rule
        
        return None
    
    def _is_mergeable(self, message: Dict, log_group: Dict, rule: Dict) -> bool:
        """
        检查消息是否可以合并到日志组
        
        Args:
            message: 新消息
            log_group: 日志组
            rule: 合并规则
            
        Returns:
            是否可合并
        """
        # 空组可以添加任何匹配规则的消息
        if not log_group['messages']:
            return True
        
        # 检查主机是否匹配
        host = message.get('host', message.get('source', 'unknown'))
        group_host = log_group.get('host', '')
        if host != group_host:
            return False
        
        # 获取分组正则表达式
        group_pattern = rule.get('group_pattern', '.*')
        
        # 检查消息是否匹配分组规则
        return self._match_message(message, group_pattern)
    
    def _find_merge_group_by_rule(self, message: Dict, rule_name: str) -> Optional[str]:
        """
        根据规则名查找匹配的合并组
        
        Args:
            message: 日志消息
            rule_name: 规则名称
            
        Returns:
            匹配的组键，如果没有则返回None
        """
        host = message.get('host', message.get('source', 'unknown'))
        
        with self._group_lock:
            for group_key, group in self._log_groups.items():
                if (group.get('rule_name') == rule_name and 
                    group.get('host') == host and 
                    len(group.get('messages', [])) < self._config.get('log_merge', {}).get('max_count', 100)):
                    return group_key
        
        return None
    
    def _extract_group_template(self, message: Dict, rule: Dict) -> str:
        """
        根据正则表达式提取消息的模板
        
        Args:
            message: 日志消息
            rule: 合并规则
            
        Returns:
            提取的模板字符串
        """
        # 如果规则中指定了模板，则使用指定的模板
        template = rule.get('group_template')
        if template:
            return template
        
        # 否则，使用消息本身作为模板
        return message.get('message', '')
    
    def _create_merge_alert(self, log_group: Dict):
        """
        根据合并的日志组创建告警
        
        Args:
            log_group: 合并的日志组
        """
        try:
            # 检查告警配置是否启用
            alert_config = self._config.get('alert_config', {})
            if not alert_config.get('enabled', False):
                return
            
            # 获取第一个消息作为基准
            if not log_group.get('messages'):
                return
            
            base_message = log_group['messages'][0]
            
            # 提取消息模板
            # 查找匹配的合并规则
            matching_rule = self._find_matching_merge_rule(base_message)
            template = self._extract_group_template(base_message, matching_rule)
            
            # 获取主机和规则名
            host = base_message.get('source', 'unknown')
            rule_name = log_group.get('rule_name', 'unknown')
            
            # 生成或获取告警ID（使用缓存机制）
            alert_id = self._get_alert_id(host, rule_name)
            
            # 生成告警消息
            alert = {
                'alert_id': alert_id,
                'timestamp': datetime.now().isoformat(),
                'alert_type': 'log_merge',
                'count': log_group['count'],
                'first_seen': datetime.fromtimestamp(log_group['first_timestamp']).isoformat(),
                'last_seen': datetime.fromtimestamp(log_group['last_timestamp']).isoformat(),
                'message_template': template,
                'rule_name': rule_name,
                'source': host,
                'facility': base_message.get('facility', 'unknown'),
                'severity': self._map_severity(base_message.get('severity', 'info')),
                'sample_messages': log_group['messages'][:3]  # 包含最多3条样例消息
            }
            
            # 发送告警
            self._send_alert(alert)
            
            logger.info(f"Created merge alert with ID {alert_id}, {log_group['count']} messages from host {host} using rule {rule_name}")
            
        except Exception as e:
            logger.error(f"Error creating merge alert: {str(e)}")
    
    def _map_severity(self, original_severity: str) -> str:
        """
        根据配置映射原始严重程度到标准严重程度
        
        Args:
            original_severity: 原始严重程度
            
        Returns:
            映射后的标准严重程度
        """
        severity_map = self._config.get('alert_config', {}).get('severity_map', {})
        return severity_map.get(original_severity.lower(), original_severity)
    
    def _send_alert(self, alert: Dict):
        """
        发送告警到配置的渠道
        
        Args:
            alert: 告警消息字典
        """
        try:
            alert_config = self._config.get('alert_config', {})
            channels = alert_config.get('channels', ['kafka'])
            
            for channel in channels:
                if channel == 'kafka':
                    self._send_alert_to_kafka(alert)
                else:
                    logger.warning(f"Unknown alert channel: {channel}")
                    
        except Exception as e:
            logger.error(f"Error sending alert: {str(e)}")
    
    def _send_alert_to_kafka(self, alert: Dict):
        """
        将告警发送到Kafka
        
        Args:
            alert: 告警消息字典
        """
        try:
            if not self._kafka_client:
                logger.error("Kafka client not initialized for alert sending")
                return
            
            # 获取告警主题
            alert_topic = self._config.get('alert_config', {}).get('alert_topic', 'syslog_alerts')
            
            # 序列化告警
            alert_str = json.dumps(alert, ensure_ascii=False)
            
            # 发送到Kafka
            self._kafka_client.send(alert_topic, alert_str)
            logger.debug(f"Alert sent to Kafka topic {alert_topic}: {alert_str[:100]}...")
            
        except Exception as e:
            logger.error(f"Error sending alert to Kafka: {str(e)}")
    
    def _get_alert_id(self, host: str, rule_name: str) -> str:
        """
        获取或生成告警ID，基于host+分组名+时间窗口的缓存机制
        
        Args:
            host: 主机名
            rule_name: 规则名称
            
        Returns:
            告警ID
        """
        current_time = time.time()
        cache_key = (host, rule_name)
        time_window = self._config.get('log_merge', {}).get('time_window', 300)
        
        # 先清理过期的缓存
        self._cleanup_expired_alert_cache(current_time, time_window)
        
        with self._alert_cache_lock:
            # 检查缓存中是否已有对应的告警ID
            if cache_key in self._alert_cache:
                cache_entry = self._alert_cache[cache_key]
                # 检查是否在时间窗口内
                if current_time - cache_entry['created_at'] < time_window:
                    return cache_entry['alert_id']
            
            # 生成新的告警ID
            new_alert_id = f"{host}_{rule_name}_{int(current_time)}"
            # 更新缓存
            self._alert_cache[cache_key] = {
                'alert_id': new_alert_id,
                'created_at': current_time
            }
            
            logger.debug(f"Generated new alert ID {new_alert_id} for host {host} and rule {rule_name}")
            return new_alert_id
    
    def _cleanup_expired_alert_cache(self, current_time: float, time_window: int):
        """
        清理过期的告警ID缓存
        
        Args:
            current_time: 当前时间戳
            time_window: 时间窗口（秒）
        """
        with self._alert_cache_lock:
            expired_keys = []
            for key, entry in self._alert_cache.items():
                if current_time - entry['created_at'] >= time_window:
                    expired_keys.append(key)
            
            # 删除过期的缓存条目
            for key in expired_keys:
                del self._alert_cache[key]
                host, rule_name = key
                logger.debug(f"Removed expired alert cache for host {host} and rule {rule_name}")
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired alert cache entries")
    
    def _cleanup_old_groups(self, current_time: float, time_window: int):
        """
        清理过期的日志组
        
        Args:
            current_time: 当前时间戳
            time_window: 时间窗口（秒）
        """
        expired_groups = []
        
        for group_key, log_group in self._log_groups.items():
            # 检查是否过期
            if current_time - log_group['last_timestamp'] > time_window:
                # 如果有足够的消息，生成告警
                if log_group['count'] >= self._config.get('log_merge', {}).get('min_count', 3):
                    self._create_merge_alert(log_group)
                expired_groups.append(group_key)
        
        # 删除过期的组
        for group_key in expired_groups:
            del self._log_groups[group_key]
    
    def _apply_processors(self, message: Dict) -> Optional[Dict]:
        """
        根据配置的处理器处理消息
        
        Args:
            message: 原始消息
            
        Returns:
            处理后的消息，或None表示丢弃
        """
        # 获取启用的处理器
        enabled_processors = self._config.get('enabled_processors', ['default'])
        processors = self._config.get('processors', {})
        
        # 应用每个启用的处理器
        for processor_name in enabled_processors:
            if processor_name in processors:
                processor_config = processors[processor_name]
                
                # 检查处理器是否启用
                if not processor_config.get('enabled', False):
                    continue
                
                # 应用处理器逻辑
                processed_message = self._apply_processor(message, processor_config)
                
                # 如果消息被丢弃
                if processed_message is None:
                    logger.debug(f"Message dropped by processor: {processor_name}")
                    return None
                
                # 更新消息为处理后的结果
                message = processed_message
        
        return message
    
    def _apply_processor(self, message: Dict, processor_config: Dict) -> Optional[Dict]:
        """
        应用单个处理器的配置
        
        Args:
            message: 原始消息
            processor_config: 处理器配置
            
        Returns:
            处理后的消息，或None表示丢弃
        """
        # 复制消息避免修改原始数据
        processed_message = message.copy()
        
        # 获取处理器配置
        pattern = processor_config.get('pattern', '.*')
        action = processor_config.get('action', 'forward')
        
        try:
            # 检查消息是否匹配模式
            if self._match_message(message, pattern):
                # 根据动作处理消息
                if action == 'discard':
                    return None
                elif action == 'forward':
                    # 向前转发，添加处理器标记
                    processed_message['processed_by'] = processor_config.get('name', 'unknown')
                    return processed_message
                elif action == 'enrich':
                    # 丰富消息内容
                    enrich_fields = processor_config.get('enrich_fields', {})
                    processed_message.update(enrich_fields)
                    processed_message['processed_by'] = processor_config.get('name', 'unknown')
                    return processed_message
                else:
                    # 未知动作，默认向前转发
                    logger.warning(f"Unknown processor action: {action}")
                    return processed_message
            else:
                # 不匹配模式，返回原始消息
                return message
        except Exception as e:
            logger.error(f"Error applying processor: {str(e)}")
            return message
    
    def _match_message(self, message: Dict, pattern: str) -> bool:
        """
        检查消息是否匹配指定模式
        
        Args:
            message: 消息字典
            pattern: 正则表达式或简单匹配模式
            
        Returns:
            是否匹配
        """
        try:
            import re
            
            # 将消息转换为字符串进行匹配
            message_str = json.dumps(message)
            return bool(re.match(pattern, message_str))
        except Exception as e:
            logger.error(f"Error matching message pattern: {str(e)}")
            return False
    
    def _send_to_kafka(self, message: Dict):
        """
        将消息发送到Kafka
        
        Args:
            message: 要发送的消息
        """
        try:
            if not self._kafka_client:
                logger.error("Kafka client not initialized")
                return
            
            # 获取目标主题
            topic = self._config.get('kafka_topic', 'syslog_messages')
            
            # 序列化消息
            message_str = json.dumps(message, ensure_ascii=False)
            
            # 发送到Kafka
            self._kafka_client.send(topic, message_str)
            logger.debug(f"Message sent to Kafka topic {topic}: {message_str[:100]}...")
        except Exception as e:
            logger.error(f"Error sending message to Kafka: {str(e)}")
    
    def get_status(self) -> Dict:
        """
        获取服务状态
        
        Returns:
            服务状态字典
        """
        return {
            'running': self._running,
            'kafka_connected': self._kafka_client is not None,
            'config_loaded': self._last_config_time > 0,
            'last_config_time': datetime.fromtimestamp(self._last_config_time).isoformat() if self._last_config_time > 0 else None,
            'enabled_processors': self._config.get('enabled_processors', [])
        }

# 使用示例
if __name__ == '__main__':
    print("=== Syslog Service Demo - Complete Workflow ===")
    print("This demo showcases the complete syslog processing workflow:")
    print("1. Kafka message consumption using get_syslog_consumer")
    print("2. Blacklist filtering with periodic configuration updates")
    print("3. Log merging with regex-based grouping")
    print("4. Alert caching with host+group_name+time_window management\n")
    
    # 获取单例实例
    syslog_service = SyslogService()
    
    # 初始化服务 - 这将启动消息消费线程和黑名单更新线程
    if syslog_service.initialize():
        print("✓ SyslogService initialized successfully")
        print("✓ Kafka consumer thread started")
        print("✓ Blacklist refresh thread started")
        
        # 处理符合Kafka输入格式的示例消息（包含host、timestamp、msg字段）
        print("\n=== Processing Sample Kafka Messages ===")
        kafka_format_messages = [
            {
                'host': '192.168.1.101',
                'timestamp': datetime.now().isoformat(),
                'msg': 'Failed authentication attempt for user admin from 10.0.0.5',
                'source': '192.168.1.101',  # 兼容原有字段
                'facility': 'auth',
                'severity': 'error'
            },
            {
                'host': '192.168.1.101',
                'timestamp': datetime.now().isoformat(),
                'msg': 'Failed authentication attempt for user admin from 10.0.0.6',
                'source': '192.168.1.101',
                'facility': 'auth',
                'severity': 'error'
            },
            {
                'host': '192.168.1.101',
                'timestamp': datetime.now().isoformat(),
                'msg': 'Failed authentication attempt for user admin from 10.0.0.7',
                'source': '192.168.1.101',
                'facility': 'auth',
                'severity': 'error'
            }
        ]
        
        # 处理多条消息以触发合并功能
        print("Processing messages to trigger log merging...")
        for i, msg in enumerate(kafka_format_messages):
            result = syslog_service.process_syslog_message(msg)
            print(f"Processed message {i+1}/{len(kafka_format_messages)}: {result}")
        
        # 演示告警ID缓存机制 - 同一主机和规则的消息应使用相同的告警ID
        print("\n=== Demonstrating Alert ID Caching ===")
        print("Sending another message to verify alert ID reuse within time window...")
        
        # 发送另一条消息，应该使用相同的告警ID（在时间窗口内）
        follow_up_message = {
            'host': '192.168.1.101',
            'timestamp': datetime.now().isoformat(),
            'msg': 'Failed authentication attempt for user admin from 10.0.0.8',
            'source': '192.168.1.101',
            'facility': 'auth',
            'severity': 'error'
        }
        syslog_service.process_syslog_message(follow_up_message)
        
        # 处理不同主机的消息 - 应该生成不同的告警ID
        print("\nSending message from different host (should generate new alert ID)...")
        different_host_message = {
            'host': '192.168.1.103',
            'timestamp': datetime.now().isoformat(),
            'msg': 'Failed authentication attempt for user admin from 10.0.0.9',
            'source': '192.168.1.103',
            'facility': 'auth',
            'severity': 'error'
        }
        syslog_service.process_syslog_message(different_host_message)
        
        # 处理不同规则的消息
        print("\nSending message matching different rule (should generate new alert ID)...")
        different_rule_message = {
            'host': '192.168.1.101',
            'timestamp': datetime.now().isoformat(),
            'msg': 'Connection refused to port 22 from 10.0.1.15',
            'source': '192.168.1.101',
            'facility': 'local0',
            'severity': 'warning'
        }
        syslog_service.process_syslog_message(different_rule_message)
        
        # 显示服务状态
        print("\n=== Service Status ===")
        status = syslog_service.get_status()
        print(json.dumps(status, indent=2))
        
        try:
            # 启动服务，持续运行
            print("\n=== Service Running ===")
            print("Now running in continuous mode. The service is:")
            print("1. Consuming messages from Kafka")
            print("2. Applying blacklist filtering")
            print("3. Merging logs based on configured rules")
            print("4. Managing alerts with ID caching mechanism")
            print("\nPress Ctrl+C to stop the service")
            
            # 保持服务运行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping service...")
        finally:
            # 关闭服务，确保所有线程正确终止
            print("Shutting down threads...")
            syslog_service.shutdown()
            print("Service stopped successfully")
    else:
        print("Failed to initialize syslog service")