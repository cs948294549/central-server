"""
Kafka消息消费者模块
"""
import json
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from kafka import KafkaConsumer
from kafka.errors import KafkaError, KafkaTimeoutError
from services.syslog.core import BaseComponent, MessageProcessor, KafkaError as SyslogKafkaError
from services.syslog.core.utils import parse_syslog_message
import logging


class KafkaMessageConsumer(BaseComponent):
    """
    Kafka消息消费者，负责从Kafka读取syslog消息
    """
    
    def __init__(self, config: Dict[str, Any], message_processor: Optional[MessageProcessor] = None):
        """
        初始化Kafka消费者
        
        Args:
            config: Kafka配置
            message_processor: 消息处理器，处理消费到的消息
        """
        super().__init__(config)
        self._consumer = None
        self._message_processor = message_processor
        self._consume_thread = None
        self._running = False
        self._stop_event = threading.Event()
    
    def _initialize(self) -> bool:
        """
        初始化Kafka消费者
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            kafka_config = self.config.get('kafka', {})
            
            # 创建Kafka消费者
            self._consumer = KafkaConsumer(
                *kafka_config.get('topics', ['syslog']),
                bootstrap_servers=kafka_config.get('bootstrap_servers', ['localhost:9092']),
                group_id=kafka_config.get('group_id', 'syslog_consumer'),
                auto_offset_reset=kafka_config.get('auto_offset_reset', 'latest'),
                enable_auto_commit=kafka_config.get('enable_auto_commit', True),
                value_deserializer=lambda m: self._deserialize_message(m)
            )
            
            self.logger.info(f"Kafka consumer initialized successfully, topics: {kafka_config.get('topics', ['syslog'])}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise SyslogKafkaError(f"Failed to initialize Kafka consumer: {e}")
    
    def start_consuming(self):
        """
        开始消费消息
        """
        if not self.is_initialized:
            if not self.initialize():
                raise RuntimeError("Cannot start consuming, consumer not initialized")
        
        if self._running:
            self.logger.warning("Consumer already running")
            return
        
        self._stop_event.clear()
        self._consume_thread = threading.Thread(target=self._consume_messages, daemon=True)
        self._running = True
        self._consume_thread.start()
        self.logger.info("Kafka consumer started")
    
    def stop_consuming(self):
        """
        停止消费消息
        """
        if not self._running:
            return
        
        self.logger.info("Stopping Kafka consumer...")
        self._stop_event.set()
        
        if self._consume_thread:
            self._consume_thread.join(timeout=10)
            self._consume_thread = None
        
        self._running = False
        self.logger.info("Kafka consumer stopped")
    
    def _consume_messages(self):
        """
        消费消息的内部方法
        """
        while not self._stop_event.is_set():
            try:
                # 批量获取消息，设置超时以允许检查停止事件
                messages = self._consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    for record in records:
                        if self._stop_event.is_set():
                            break
                        
                        try:
                            self._process_message(record.value)
                        except Exception as e:
                            self.logger.error(f"Error processing message: {e}")
                
                # 手动提交偏移量（如果配置为不自动提交）
                if not self.config.get('kafka', {}).get('enable_auto_commit', True):
                    self._consumer.commit()
                    
            except KafkaTimeoutError:
                # 超时是正常的，继续循环
                continue
            except KafkaError as e:
                self.logger.error(f"Kafka error during consumption: {e}")
                # 短暂暂停后重试
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"Unexpected error during consumption: {e}")
                # 短暂暂停后重试
                time.sleep(1)
    
    def _process_message(self, message: Dict[str, Any]):
        """
        处理单条消息
        
        Args:
            message: 消息内容
        """
        # 确保消息有必要的字段
        if 'message' not in message:
            self.logger.warning(f"Received message without 'message' field: {message}")
            return
        
        # 如果消息是原始的syslog格式，进行解析
        if isinstance(message['message'], str) and 'raw' not in message:
            parsed_message = parse_syslog_message(message['message'])
            message.update(parsed_message)
        
        # 调用消息处理器（如果有）
        if self._message_processor:
            self._message_processor.process(message)
        else:
            # 如果没有处理器，只是记录消息
            self.logger.debug(f"Received message: {message.get('message', '').strip()}")
    
    def _deserialize_message(self, message_bytes: bytes) -> Dict[str, Any]:
        """
        反序列化消息
        
        Args:
            message_bytes: 消息字节
            
        Returns:
            反序列化后的消息
        """
        try:
            # 尝试JSON解析
            return json.loads(message_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            # 如果不是JSON，包装成标准格式
            return {
                'message': message_bytes.decode('utf-8', errors='replace'),
                'raw': message_bytes.decode('utf-8', errors='replace')
            }
    
    def _shutdown(self):
        """
        关闭Kafka消费者
        """
        self.stop_consuming()
        
        if self._consumer:
            try:
                self._consumer.close()
                self.logger.info("Kafka consumer connection closed")
            except Exception as e:
                self.logger.error(f"Error closing Kafka consumer: {e}")
        
        self._consumer = None


class MessagePipeline:
    """
    消息处理管道，连接多个消息处理器
    """
    
    def __init__(self, processors: List[MessageProcessor] = None):
        """
        初始化消息处理管道
        
        Args:
            processors: 消息处理器列表
        """
        self._processors = processors or []
        self._lock = threading.RLock()
    
    def add_processor(self, processor: MessageProcessor):
        """
        添加消息处理器
        
        Args:
            processor: 消息处理器
        """
        with self._lock:
            self._processors.append(processor)
    
    def remove_processor(self, processor: MessageProcessor):
        """
        移除消息处理器
        
        Args:
            processor: 要移除的消息处理器
        """
        with self._lock:
            if processor in self._processors:
                self._processors.remove(processor)
    
    def process(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理消息，通过所有处理器
        
        Args:
            message: 待处理的消息
            
        Returns:
            处理后的消息，任一处理器返回None则整体返回None
        """
        with self._lock:
            current_message = message
            for processor in self._processors:
                if current_message is None:
                    return None
                current_message = processor.process(current_message)
            return current_message