"""
Redis Queue Client 基于Redis的简单消息队列实现

使用lpush/rpop实现异步数据处理，作为kafka_client的替代方案
"""
import json
import logging
import time
from typing import Optional, Iterator, Any

from config import Config
from function_messaging.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class QueueProducer:
    """
    Redis队列生产者，向指定队列写入消息
    """

    def __init__(self, queue_key: str):
        self.queue_key = queue_key
        self._redis = get_redis_client()

    def send(self, data: Any, key: Optional[str] = None) -> bool:
        """
        发送单条消息

        Args:
            data: 要发送的数据（会被JSON序列化）
            key: 消息键（可选，用于保持与Kafka接口一致）

        Returns:
            bool: 发送是否成功
        """
        try:
            # 将key和data封装在一起
            payload = {
                "key": key,
                "value": data
            }
            message = json.dumps(payload, ensure_ascii=False)
            self._redis.lpush(self.queue_key, message)
            return True
        except Exception as e:
            logger.error(f"发送消息到队列 {self.queue_key} 失败: {str(e)}")
            return False

    def send_batch(self, messages: list) -> dict:
        """
        批量发送消息

        Args:
            messages: 消息列表

        Returns:
            dict: 发送结果统计
        """
        success_count = 0
        failed_count = 0
        for message in messages:
            try:
                data = json.dumps(message, ensure_ascii=False)
                self._redis.lpush(self.queue_key, data)
                success_count += 1
            except Exception as e:
                logger.error(f"批量发送消息到队列 {self.queue_key} 失败: {str(e)}")
                failed_count += 1
        return {"success": success_count, "failed": failed_count}


class QueueConsumer:
    """
    Redis队列消费者，从指定队列读取消息
    """

    def __init__(self, queue_key: str, timeout: int = 2):
        self.queue_key = queue_key
        self.timeout = timeout
        self._redis = get_redis_client()

    def pop(self) -> Optional[Any]:
        """
        从队列右侧弹出一条消息

        Returns:
            object: 包含key和value属性的消息对象，队列为空时返回None
        """
        try:
            raw = self._redis.rpop(self.queue_key)
            if raw is None:
                return None
            payload = json.loads(raw)
            # 返回一个简单对象，包含key和value属性
            return type('Message', (), payload)()
        except Exception as e:
            logger.error(f"从队列 {self.queue_key} 读取消息失败: {str(e)}")
            raise

    def blpop(self, timeout: int = None) -> Optional[Any]:
        """
        阻塞式从队列右侧弹出一条消息

        Args:
            timeout: 阻塞超时时间（秒），默认使用实例timeout

        Returns:
            object: 包含key和value属性的消息对象，超时返回None
        """
        t = timeout if timeout is not None else self.timeout
        try:
            result = self._redis.blpop(self.queue_key, timeout=t)
            if result is None:
                return None
            _, raw = result
            payload = json.loads(raw)
            # 返回一个简单对象，包含key和value属性
            return type('Message', (), payload)()
        except Exception as e:
            logger.error(f"从队列 {self.queue_key} 阻塞读取消息失败: {str(e)}")
            raise

    def close(self):
        """释放Redis连接（归还到连接池）"""
        self._redis.close()


# --- Syslog 数据通道 ---

_syslogProducer = None


def sendDataToSyslog(messages: Any, key: Optional[str] = None) -> bool:
    """
    发送数据到syslog队列

    Args:
        messages: 要发送的数据
        key: 消息键（可选，用于保持与Kafka接口一致）

    Returns:
        bool: 发送是否成功
    """
    global _syslogProducer
    retry = 3
    while retry > 0:
        retry -= 1
        if _syslogProducer is None:
            _syslogProducer = QueueProducer(Config.queue_key_syslog)

        rt = _syslogProducer.send(messages, key=key)
        if rt:
            return True
        else:
            logger.error(f"发送数据到syslog队列 {Config.queue_key_syslog} 失败")
            _syslogProducer = None
            time.sleep(1)
    return False


_syslogConsumer = None


def readDataFromSyslog() -> Iterator[Any]:
    """
    从syslog队列读取数据

    Yields:
        object: 包含key和value属性的消息对象
    """
    global _syslogConsumer
    retry = 3
    while retry > 0:
        try:
            if _syslogConsumer is None:
                _syslogConsumer = QueueConsumer(Config.queue_key_syslog)

            while True:
                message = _syslogConsumer.pop()
                if message is not None:
                    yield message
                else:
                    time.sleep(0.1)
        except Exception as e:
            retry -= 1
            _syslogConsumer = None
            logger.error(
                f"从syslog队列 {Config.queue_key_syslog} 读取数据失败: {str(e)}"
            )


# --- Collect 数据通道 ---

_collectProducer = None


def sendDataToCollector(messages: Any, key: Optional[str] = None) -> bool:
    """
    发送数据到collect队列

    Args:
        messages: 要发送的数据
        key: 消息键（可选，用于保持与Kafka接口一致）

    Returns:
        bool: 发送是否成功
    """
    global _collectProducer
    retry = 3
    while retry > 0:
        retry -= 1
        if _collectProducer is None:
            _collectProducer = QueueProducer(Config.queue_key_collect)

        rt = _collectProducer.send(messages, key=key)
        if rt:
            return True
        else:
            logger.error(f"发送数据到collect队列 {Config.queue_key_collect} 失败")
            _collectProducer = None
            time.sleep(1)
    return False


_collectConsumer = None


def readDataFromCollect() -> Iterator[Any]:
    """
    从collect队列读取数据

    Yields:
        object: 包含key和value属性的消息对象
    """
    global _collectConsumer
    retry = 3
    while retry > 0:
        try:
            if _collectConsumer is None:
                _collectConsumer = QueueConsumer(Config.queue_key_collect)

            while True:
                message = _collectConsumer.pop()
                if message is not None:
                    yield message
                else:
                    time.sleep(0.1)
        except Exception as e:
            retry -= 1
            _collectConsumer = None
            logger.error(
                f"从collect队列 {Config.queue_key_collect} 读取数据失败: {str(e)}"
            )
