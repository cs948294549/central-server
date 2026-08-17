"""
消息队列统一适配器

根据配置自动选择 Kafka 或 Redis 队列实现
提供统一的接口供业务代码使用

两种队列实现现在具有一致的接口:
- 消息都包含 key 和 value 属性
- 发送函数都支持 key 参数
"""

import logging
from config import Config

logger = logging.getLogger(__name__)

# 根据配置选择队列实现
if Config.queue_type == "kafka":
    logger.info("✓ 使用 Kafka 消息队列")
    from function_messaging.kafka_client import (
        readDataFromSyslog,
        readDataFromCollect,
        sendDataToSyslog,
        sendDataToCollector
    )

elif Config.queue_type == "redis":
    logger.info("✓ 使用 Redis 消息队列")
    from function_messaging.queue_client import (
        readDataFromSyslog,
        readDataFromCollect,
        sendDataToSyslog,
        sendDataToCollector
    )

else:
    raise ValueError(f"不支持的消息队列类型: {Config.queue_type}，请配置为 'kafka' 或 'redis'")

# 导出统一接口
__all__ = [
    'readDataFromSyslog',
    'readDataFromCollect',
    'sendDataToSyslog',
    'sendDataToCollector'
]
