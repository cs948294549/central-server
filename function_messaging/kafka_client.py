from kafka import KafkaConsumer, KafkaProducer
import json
import logging
from typing import Optional, List, Dict, Any, Union
from config import Config
logger = logging.getLogger(__name__)

# Kafka服务器配置
kafka_servers = Config.kafka_server


class TopicProducer:
    """
    主题化的Kafka生产者，每个实例关联一个特定的topic
    """
    def __init__(self, topic: str, bootstrap_servers: Union[str, List[str]] = None):
        self.topic = topic
        self.servers = bootstrap_servers or kafka_servers
        self.producer = KafkaProducer(
            bootstrap_servers=self.servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
    
    def send(self, data: Any, key: Optional[str] = None, partition: Optional[int] = None) -> bool:
        """
        发送单条消息
        
        Args:
            data: 要发送的数据
            key: 消息键（可选）
            partition: 分区编号（可选）
            
        Returns:
            bool: 发送是否成功
        """
        try:
            future = self.producer.send(
                self.topic,
                value=data,
                key=key,
                partition=partition
            )
            # 阻塞等待发送结果
            future.get(timeout=10)
            return True
        except Exception as e:
            logger.error(f"发送消息到topic {self.topic} 失败: {str(e)}")
            return False
    
    def send_batch(self, messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        批量发送消息
        
        Args:
            messages: 消息列表，每条消息包含value和可选的key
            
        Returns:
            Dict: 发送结果统计
        """
        success_count = 0
        failed_count = 0
        
        for message in messages:
            try:
                future = self.producer.send(
                    self.topic,
                    value=message.get('value'),
                    key=message.get('key')
                )
                future.get(timeout=10)
                success_count += 1
            except Exception as e:
                logger.error(f"批量发送消息到topic {self.topic} 失败: {str(e)}")
                failed_count += 1
        
        return {"success": success_count, "failed": failed_count}
    
    def close(self):
        """关闭生产者连接"""
        try:
            self.producer.flush()
            self.producer.close()
        except Exception as e:
            logger.error(f"关闭Kafka生产者失败: {str(e)}")


class TopicConsumer:
    """
    主题化的Kafka消费者，每个实例关联一个特定的topic
    """
    def __init__(self, topic: str, group_id: Optional[str] = None, bootstrap_servers: Union[str, List[str]] = None):
        self.topic = topic
        self.group_id = group_id
        self.servers = bootstrap_servers or kafka_servers
        self.consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=self.servers,
            group_id=group_id,
            enable_auto_commit=True,
            auto_offset_reset='latest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
            key_deserializer=lambda m: m.decode('utf-8') if m else None
        )
    
    def get_consumer(self):
        """获取底层消费者实例"""
        return self.consumer
    
    def close(self):
        """关闭消费者连接"""
        try:
            self.consumer.close()
        except Exception as e:
            logger.error(f"关闭Kafka消费者失败: {str(e)}")



_collectProducer = None
_syslogProducer = None

def get_collect_producer() -> TopicProducer:
    """
    获取全局Kafka客户端实例
    Returns:
        KafkaClient: Kafka客户端实例
    """
    global _collectProducer
    if _collectProducer is None:
        _collectProducer = TopicProducer(Config.collect_kafka_topic)
    return _collectProducer

def get_syslog_producer() -> TopicProducer:
    """
    获取syslog服务的Kafka Producer实例
    Returns:
        TopicProducer: syslog的Kafka生产者实例
    """
    global _syslogProducer
    if _syslogProducer is None:
        _syslogProducer = TopicProducer("syslog_data")
    return _syslogProducer


if __name__ == '__main__':
    # 示例：使用TopicProducer发送消息
    producer = TopicProducer("collect_data")
    producer.send({"message": "Hello Kafka"}, key="test-key")
    producer.close()
    
    # 示例：使用TopicConsumer消费消息
    # consumer = TopicConsumer("collect_data", group_id="test_group")
    # for msg in consumer.get_consumer():
    #     print(f"Received: {msg.value}, key: {msg.key}")
    # consumer.close()
