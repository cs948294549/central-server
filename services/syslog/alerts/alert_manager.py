"""
告警管理模块
"""
import threading
import time
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
from kafka import KafkaProducer
import json
from services.syslog.core import BaseComponent, AlertError, get_alert_severity
from services.syslog.mergers import MergeGroup
import logging


class Alert:
    """
    告警类
    """
    
    def __init__(self, alert_id: str, alert_type: str, severity: str, summary: str, 
                 details: Dict[str, Any], source: Dict[str, Any] = None):
        """
        初始化告警
        
        Args:
            alert_id: 告警ID
            alert_type: 告警类型
            severity: 告警级别
            summary: 告警摘要
            details: 告警详情
            source: 告警来源信息
        """
        self.alert_id = alert_id
        self.alert_type = alert_type
        self.severity = severity
        self.summary = summary
        self.details = details
        self.source = source or {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            字典表示
        """
        return {
            'alert_id': self.alert_id,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'summary': self.summary,
            'details': self.details,
            'source': self.source,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def update(self, severity: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        更新告警信息
        
        Args:
            severity: 新的告警级别
            details: 新的告警详情
        """
        if severity:
            self.severity = severity
        if details:
            self.details.update(details)
        self.updated_at = datetime.now()


class AlertCacheEntry:
    """
    告警缓存条目
    """
    
    def __init__(self, alert_id: str, created_at: datetime):
        """
        初始化缓存条目
        
        Args:
            alert_id: 告警ID
            created_at: 创建时间
        """
        self.alert_id = alert_id
        self.created_at = created_at
        self.last_used = created_at
    
    def is_expired(self, ttl: timedelta) -> bool:
        """
        检查是否过期
        
        Args:
            ttl: 生存时间
            
        Returns:
            是否过期
        """
        return datetime.now() - self.created_at > ttl
    
    def touch(self):
        """
        更新最后使用时间
        """
        self.last_used = datetime.now()


class AlertManager(BaseComponent):
    """
    告警管理器，负责生成、缓存和发送告警
    """
    
    # 告警级别优先级
    SEVERITY_LEVELS = {
        'debug': 0,
        'info': 1,
        'notice': 2,
        'warning': 3,
        'error': 4,
        'critical': 5,
        'alert': 6,
        'emergency': 7
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化告警管理器
        
        Args:
            config: 配置
        """
        super().__init__(config)
        self._alert_cache = {}
        self._alert_cache_lock = threading.RLock()
        self._producer = None
        self._ttl = timedelta(seconds=config.get('alert_config', {}).get('alert_id_cache_ttl', 3600))
        self._min_severity = config.get('alert_config', {}).get('min_severity', 'warning')
    
    def _initialize(self) -> bool:
        """
        初始化告警管理器
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 初始化Kafka生产者
            if 'kafka' in self.config.get('alert_config', {}).get('channels', []):
                self._initialize_kafka_producer()
            
            self.logger.info("Alert manager initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize alert manager: {e}")
            return False
    
    def _initialize_kafka_producer(self):
        """
        初始化Kafka生产者
        """
        kafka_config = self.config.get('alert_config', {}).get('kafka', {})
        try:
            self._producer = KafkaProducer(
                bootstrap_servers=kafka_config.get('bootstrap_servers', ['localhost:9092']),
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            self.logger.info(f"Kafka producer initialized for alerts")
        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka producer: {e}")
            raise AlertError(f"Failed to initialize Kafka producer: {e}")
    
    def create_alert(self, alert_type: str, summary: str, details: Dict[str, Any], 
                    severity: Optional[str] = None, source: Optional[Dict[str, Any]] = None) -> Optional[Alert]:
        """
        创建告警
        
        Args:
            alert_type: 告警类型
            summary: 告警摘要
            details: 告警详情
            severity: 告警级别（可选）
            source: 告警来源（可选）
            
        Returns:
            创建的告警，如果告警级别低于最小级别则返回None
        """
        # 如果未指定告警级别，从详情中推断
        if not severity and 'message' in details:
            severity = get_alert_severity({'message': details['message']})
        elif not severity:
            severity = 'warning'
        
        # 检查告警级别是否满足最小要求
        if self._is_severity_too_low(severity):
            self.logger.debug(f"Skipping alert of type '{alert_type}' with low severity '{severity}'")
            return None
        
        # 生成告警ID
        alert_id = self._generate_alert_id(alert_type, source or {})
        
        # 创建告警对象
        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            summary=summary,
            details=details,
            source=source
        )
        
        # 发送告警
        self._send_alert(alert)
        
        return alert
    
    def create_merge_alert(self, merge_group: MergeGroup) -> Optional[Alert]:
        """
        为合并组创建告警
        
        Args:
            merge_group: 合并组
            
        Returns:
            创建的告警
        """
        # 提取消息模板
        template = self._extract_group_template(merge_group)
        
        # 生成告警详情
        details = {
            'message_count': len(merge_group.messages),
            'hosts': list(merge_group.hosts),
            'programs': list(merge_group.programs),
            'template': template,
            'first_message_time': merge_group.messages[0].get('timestamp', merge_group.created_at).isoformat() if merge_group.messages[0].get('timestamp') else merge_group.created_at.isoformat(),
            'last_message_time': merge_group.messages[-1].get('timestamp', merge_group.last_updated_at).isoformat() if merge_group.messages[-1].get('timestamp') else merge_group.last_updated_at.isoformat()
        }
        
        # 从消息中推断严重程度
        severity = self._determine_group_severity(merge_group)
        
        # 生成告警摘要
        host_str = merge_group.hosts.pop() if merge_group.hosts else 'unknown'
        if merge_group.hosts:
            host_str += f" and {len(merge_group.hosts)} others"
        summary = f"{len(merge_group.messages)} similar messages from {host_str} (Rule: {merge_group.rule_name})"
        
        # 创建告警
        source = {
            'type': 'merged_logs',
            'rule_name': merge_group.rule_name,
            'group_key': merge_group.group_key
        }
        
        return self.create_alert(
            alert_type='log_merged',
            summary=summary,
            details=details,
            severity=severity,
            source=source
        )
    
    def _generate_alert_id(self, alert_type: str, source: Dict[str, Any]) -> str:
        """
        生成告警ID，使用host+规则名+时间窗口的缓存机制
        
        Args:
            alert_type: 告警类型
            source: 告警来源
            
        Returns:
            告警ID
        """
        # 清理过期缓存
        self._cleanup_expired_alert_cache()
        
        # 生成缓存键
        cache_key_parts = [alert_type]
        
        # 添加主机信息（如果有）
        if 'host' in source:
            cache_key_parts.append(source['host'])
        elif 'hosts' in source and source['hosts']:
            # 如果有多个主机，使用第一个作为标识
            cache_key_parts.append(source['hosts'][0])
        
        # 添加规则名（如果有）
        if 'rule_name' in source:
            cache_key_parts.append(source['rule_name'])
        
        cache_key = ":".join(cache_key_parts)
        
        # 尝试获取现有告警ID或生成新的
        return self._get_alert_id(cache_key)
    
    def _get_alert_id(self, cache_key: str) -> str:
        """
        获取告警ID，优先使用缓存中的ID
        
        Args:
            cache_key: 缓存键
            
        Returns:
            告警ID
        """
        with self._alert_cache_lock:
            if cache_key in self._alert_cache:
                # 更新最后使用时间
                self._alert_cache[cache_key].touch()
                return self._alert_cache[cache_key].alert_id
            
            # 生成新的告警ID
            timestamp = int(time.time() * 1000)
            # 使用缓存键和时间戳生成唯一ID
            alert_id = f"{cache_key}:{timestamp}"
            
            # 存储到缓存
            self._alert_cache[cache_key] = AlertCacheEntry(alert_id, datetime.now())
            
            return alert_id
    
    def _cleanup_expired_alert_cache(self):
        """
        清理过期的告警缓存
        """
        expired_keys = []
        
        with self._alert_cache_lock:
            for key, entry in self._alert_cache.items():
                if entry.is_expired(self._ttl):
                    expired_keys.append(key)
            
            # 删除过期的缓存项
            for key in expired_keys:
                del self._alert_cache[key]
        
        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired alert cache entries")
    
    def _is_severity_too_low(self, severity: str) -> bool:
        """
        检查告警级别是否低于最小要求
        
        Args:
            severity: 告警级别
            
        Returns:
            是否低于最小级别
        """
        current_level = self.SEVERITY_LEVELS.get(severity.lower(), 0)
        min_level = self.SEVERITY_LEVELS.get(self._min_severity.lower(), 3)  # 默认warning
        return current_level < min_level
    
    def _determine_group_severity(self, merge_group: MergeGroup) -> str:
        """
        确定合并组的告警级别
        
        Args:
            merge_group: 合并组
            
        Returns:
            告警级别
        """
        # 统计各级别的消息数
        severity_counts = defaultdict(int)
        
        for message in merge_group.messages:
            severity = get_alert_severity(message)
            severity_counts[severity] += 1
        
        # 返回出现最多的最高级别
        highest_severity = 'info'
        highest_count = 0
        
        for severity, count in severity_counts.items():
            if self.SEVERITY_LEVELS[severity] > self.SEVERITY_LEVELS[highest_severity] or \
               (self.SEVERITY_LEVELS[severity] == self.SEVERITY_LEVELS[highest_severity] and count > highest_count):
                highest_severity = severity
                highest_count = count
        
        return highest_severity
    
    def _extract_group_template(self, merge_group: MergeGroup) -> str:
        """
        提取合并组的消息模板
        
        Args:
            merge_group: 合并组
            
        Returns:
            消息模板
        """
        # 简单实现：使用第一条消息作为模板
        if merge_group.messages:
            return merge_group.messages[0].get('message', '')
        return ''
    
    def _send_alert(self, alert: Alert):
        """
        发送告警
        
        Args:
            alert: 要发送的告警
        """
        channels = self.config.get('alert_config', {}).get('channels', [])
        
        for channel in channels:
            try:
                if channel == 'kafka':
                    self._send_alert_to_kafka(alert)
                else:
                    self.logger.warning(f"Unknown alert channel: {channel}")
            except Exception as e:
                self.logger.error(f"Failed to send alert to {channel}: {e}")
    
    def _send_alert_to_kafka(self, alert: Alert):
        """
        通过Kafka发送告警
        
        Args:
            alert: 要发送的告警
        """
        if not self._producer:
            self.logger.error("Kafka producer not initialized")
            return
        
        topic = self.config.get('alert_config', {}).get('kafka', {}).get('topic', 'syslog_alerts')
        
        try:
            # 发送告警到Kafka
            future = self._producer.send(topic, value=alert.to_dict())
            # 等待发送结果
            future.get(timeout=10)
            self.logger.info(f"Alert {alert.alert_id} sent to Kafka topic {topic}")
        except Exception as e:
            self.logger.error(f"Failed to send alert to Kafka: {e}")
            raise AlertError(f"Failed to send alert to Kafka: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取告警管理器统计信息
        
        Returns:
            统计信息
        """
        with self._alert_cache_lock:
            cache_size = len(self._alert_cache)
        
        return {
            'enabled': self.config.get('alert_config', {}).get('enabled', True),
            'min_severity': self._min_severity,
            'cache_size': cache_size,
            'cache_ttl': self._ttl.total_seconds(),
            'channels': self.config.get('alert_config', {}).get('channels', [])
        }
    
    def _shutdown(self):
        """
        关闭告警管理器
        """
        # 关闭Kafka生产者
        if self._producer:
            try:
                self._producer.flush()
                self._producer.close()
                self.logger.info("Kafka producer closed")
            except Exception as e:
                self.logger.error(f"Error closing Kafka producer: {e}")
        
        # 清空告警缓存
        with self._alert_cache_lock:
            self._alert_cache.clear()
        
        self.logger.info("Alert manager shut down")