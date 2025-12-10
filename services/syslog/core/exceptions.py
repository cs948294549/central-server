"""
Syslog服务自定义异常类
"""


class SyslogServiceError(Exception):
    """Syslog服务基础异常"""
    pass


class ConfigurationError(SyslogServiceError):
    """配置相关错误"""
    pass


class InitializationError(SyslogServiceError):
    """初始化错误"""
    pass


class MessageProcessingError(SyslogServiceError):
    """消息处理错误"""
    pass


class BlacklistError(SyslogServiceError):
    """黑名单相关错误"""
    pass


class LogMergeError(SyslogServiceError):
    """日志合并相关错误"""
    pass


class AlertError(SyslogServiceError):
    """告警相关错误"""
    pass


class KafkaError(SyslogServiceError):
    """Kafka相关错误"""
    pass