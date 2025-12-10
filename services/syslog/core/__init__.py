"""
Syslog服务核心模块
"""

from .base import BaseComponent, MessageProcessor, ServiceManager
from .config import ConfigManager
from .exceptions import (
    SyslogServiceError,
    ConfigurationError,
    InitializationError,
    MessageProcessingError,
    BlacklistError,
    LogMergeError,
    AlertError,
    KafkaError
)
from .utils import (
    parse_timestamp,
    format_timestamp,
    extract_fields_from_message,
    generate_hash,
    sanitize_log_message,
    parse_syslog_message,
    get_alert_severity,
    filter_messages,
    group_messages_by_field
)

__all__ = [
    # 基础类
    'BaseComponent',
    'MessageProcessor',
    'ServiceManager',
    # 配置管理
    'ConfigManager',
    # 异常类
    'SyslogServiceError',
    'ConfigurationError',
    'InitializationError',
    'MessageProcessingError',
    'BlacklistError',
    'LogMergeError',
    'AlertError',
    'KafkaError',
    # 工具函数
    'parse_timestamp',
    'format_timestamp',
    'extract_fields_from_message',
    'generate_hash',
    'sanitize_log_message',
    'parse_syslog_message',
    'get_alert_severity',
    'filter_messages',
    'group_messages_by_field'
]