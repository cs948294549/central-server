"""
消息消费模块
"""

from .kafka_consumer import KafkaMessageConsumer, MessagePipeline

__all__ = [
    'KafkaMessageConsumer',
    'MessagePipeline'
]