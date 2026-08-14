"""
消息队列统一适配器

根据配置自动选择 Kafka 或 Redis 队列实现
提供统一的接口供业务代码使用
"""

import logging
from config import Config

logger = logging.getLogger(__name__)


class MessageWrapper:
    """
    消息包装类，统一 Kafka 和 Redis 消息的访问接口

    Kafka 消息: message.value 访问内容
    Redis 消息: 直接是字典

    统一为: message.value 访问内容
    """
    def __init__(self, data, source="redis"):
        self.source = source
        if source == "kafka":
            # Kafka 消息已经有 value 属性
            self._raw = data
        else:
            # Redis 消息是字典，需要包装
            self._raw = data
            self.value = data
            self.key = None  # Redis 队列不支持 key

    def __getattr__(self, name):
        # 对于 Kafka 消息，直接转发属性访问
        if self.source == "kafka":
            return getattr(self._raw, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


# 根据配置选择队列实现
if Config.queue_type == "kafka":
    logger.info("✓ 使用 Kafka 消息队列")
    from function_messaging import kafka_client

    # Kafka 消息已经有 value 属性，直接使用
    def readDataFromSyslog():
        for message in kafka_client.readDataFromSyslog():
            yield MessageWrapper(message, source="kafka")

    def readDataFromCollect():
        for message in kafka_client.readDataFromCollect():
            yield MessageWrapper(message, source="kafka")

    # 发送函数保持不变
    sendDataToSyslog = kafka_client.sendDataToSyslog
    sendDataToCollector = kafka_client.sendDataToCollector

elif Config.queue_type == "redis":
    logger.info("✓ 使用 Redis 消息队列")
    from function_messaging import queue_client

    # Redis 消息是字典，需要包装成统一接口
    def readDataFromSyslog():
        for message in queue_client.readDataFromSyslog():
            yield MessageWrapper(message, source="redis")

    def readDataFromCollect():
        for message in queue_client.readDataFromCollect():
            yield MessageWrapper(message, source="redis")

    # 发送函数保持不变
    sendDataToSyslog = queue_client.sendDataToSyslog
    sendDataToCollector = queue_client.sendDataToCollector

else:
    raise ValueError(f"不支持的消息队列类型: {Config.queue_type}，请配置为 'kafka' 或 'redis'")

# 导出统一接口
__all__ = [
    'readDataFromSyslog',
    'readDataFromCollect',
    'sendDataToSyslog',
    'sendDataToCollector',
    'MessageWrapper'
]
