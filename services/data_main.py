from function_messaging.kafka_client import readDataFromCollect
import threading
import logging

logger = logging.getLogger(__name__)

class DataService:
    def __init__(self, refresh_interval:int=300, time_window:int=300):
        self._refresh_interval = refresh_interval
        self._time_window = time_window
        self.messages = readDataFromCollect()
        self._handle_thread = None
        self._running = False

    def start(self):
        self._running = True
        self._handle_thread = threading.Thread(
            target=self._handle_data,
            args=(),
            daemon=True
        )
        self._handle_thread.start()

    def _handle_data(self):
        """
        处理数据，根据metric_name不同分发到不同的策略去处理数据
        """
        # 导入策略工厂
        from services.dataStrategy import get_strategy
        
        for message in self.messages:
            if self._running:
                try:
                    message_value = message.value
                    logger.info(f"接收到数据: {message_value}")
                    
                    # 获取metric_name
                    metric_name = message_value.get("metric_name")
                    if not metric_name:
                        logger.warning(f"数据缺少metric_name字段: {message_value}")
                        continue
                    
                    # 获取对应的数据处理策略
                    strategy = get_strategy(metric_name)
                    if not strategy:
                        logger.warning(f"未找到对应的处理策略: {metric_name}")
                        continue
                    
                    # 使用策略处理数据
                    processed_result = strategy.process_data(message_value)
                    if not processed_result:
                        logger.error("failed to handle data {}; reason:{}".format(str(message), "处理失败"))
                    logger.info(f"数据处理完成，metric_name: {metric_name}, 原始数据: {message_value}, 处理结果: {processed_result}")
                except Exception as e:
                    logger.error("failed to handle data {}; reason:{}".format(str(message), str(e)))
            else:
                break

    def stop(self):
        self._running = False

if __name__ == '__main__':
    import time
    from core.logger import setup_logger

    logger = setup_logger()
    service = DataService()
    service.start()

    while True:
        time.sleep(60)