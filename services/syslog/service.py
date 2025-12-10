"""
Syslog服务主文件
整合各个功能模块，提供完整的syslog处理流程
"""
import os
import json
import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# 导入项目中的kafka客户端
from function_messaging.kafka_client import get_syslog_consumer

# 导入我们创建的模块
from services.syslog.core import BaseComponent, ServiceManager, ConfigManager, get_alert_severity
from services.syslog.consumers import KafkaMessageConsumer, MessagePipeline
from services.syslog.filters import BlacklistManager, BlacklistFilter
from services.syslog.mergers import LogMerger
from services.syslog.alerts import AlertManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('syslog_service')


class SyslogService(BaseComponent):
    """
    Syslog服务类
    整合各个功能模块，提供完整的syslog处理流程
    """
    
    # 默认配置
    DEFAULT_CONFIG = {
        'kafka_topic': 'syslog_messages',
        'config_file_path': 'config/syslog_config.json',
        'refresh_interval': 60,  # 默认60秒刷新一次配置
        'enabled_processors': ['default'],
        'processors': {
            'default': {
                'enabled': True,
                'pattern': '.*',
                'action': 'forward'
            }
        },
        # 日志黑名单配置
        'blacklist': {
            'enabled': True,
            'blacklist_url': 'http://localhost:8000/api/blacklist',  # 黑名单配置获取URL
            'refresh_interval': 300,  # 黑名单刷新间隔（秒）
            'categories': {
                'ip_addresses': [],  # 黑名单IP地址
                'hosts': [],  # 黑名单主机名
                'messages': [],  # 黑名单消息模式（正则表达式）
                'facilities': [],  # 黑名单设施
                'severities': []  # 黑名单严重程度
            }
        },
        # 日志合并配置
        'log_merge': {
            'enabled': True,
            'time_window': 300,  # 合并时间窗口（秒）
            'min_count': 3,  # 最小合并数量
            'max_count': 100,  # 最大合并数量
            'group_fields': ['source', 'facility', 'severity'],  # 分组字段
            'merge_rules': [
                {
                    'name': 'default_merge',
                    'enabled': True,
                    'match_pattern': '.*',
                    'group_pattern': '.*',  # 用于分组的正则表达式
                    'group_template': None  # 分组模板，可选
                },
                {
                    'name': 'authentication_errors',
                    'enabled': True,
                    'match_pattern': '.*authentication.*error.*',
                    'group_pattern': '.*authentication.*error.*',
                    'group_template': 'Multiple authentication errors detected'
                },
                {
                    'name': 'connection_refused',
                    'enabled': True,
                    'match_pattern': '.*connection.*refused.*',
                    'group_pattern': '.*connection.*refused.*',
                    'group_template': 'Connection refused errors'
                },
                {
                    'name': 'port_scan',
                    'enabled': True,
                    'match_pattern': '.*port.*scan.*|.*scanning.*',
                    'group_pattern': '.*port.*scan.*|.*scanning.*',
                    'group_template': 'Potential port scanning detected'
                }
            ]
        },
        # 告警配置
        'alert_config': {
            'enabled': True,
            'channels': ['kafka'],  # 告警发送渠道
            'kafka': {
                'bootstrap_servers': ['localhost:9092'],
                'topic': 'syslog_alerts'
            },
            'min_severity': 'warning',
            'alert_id_cache_ttl': 3600,
            'severity_map': {
                'emerg': 'critical',
                'alert': 'critical',
                'crit': 'critical',
                'err': 'error',
                'warning': 'warning',
                'notice': 'info',
                'info': 'info',
                'debug': 'debug'
            }
        }
    }
    
    def __init__(self):
        """
        初始化Syslog服务
        """
        # 使用默认配置初始化
        super().__init__(self.DEFAULT_CONFIG)
        
        # 服务状态
        self._running = False
        
        # 组件引用
        self._config_manager = None
        self._service_manager = None
        self._kafka_consumer = None
        self._blacklist_filter = None
        self._blacklist_manager = None
        self._log_merger = None
        self._alert_manager = None
        
        # 消息处理管道
        self._message_pipeline = None
        
        # 线程
        self._config_thread = None
        self._consumer_thread = None
        
        logger.info("SyslogService instance created")
    
    def _initialize(self) -> bool:
        """
        初始化服务，创建并初始化各个组件
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 创建服务管理器
            self._service_manager = ServiceManager()
            
            # 创建配置管理器
            self._config_manager = ConfigManager(self.config)
            self._service_manager.register('config_manager', self._config_manager)
            
            # 加载配置
            self._load_config()
            
            # 初始化黑名单管理器
            self._blacklist_manager = BlacklistManager(self.config)
            self._service_manager.register('blacklist_manager', self._blacklist_manager)
            
            # 初始化黑名单过滤器
            self._blacklist_filter = BlacklistFilter(self.config, self._blacklist_manager)
            self._service_manager.register('blacklist_filter', self._blacklist_filter)
            
            # 初始化日志合并器
            self._log_merger = LogMerger(self.config)
            self._service_manager.register('log_merger', self._log_merger)
            
            # 初始化告警管理器
            self._alert_manager = AlertManager(self.config)
            self._service_manager.register('alert_manager', self._alert_manager)
            
            # 创建消息处理管道
            self._create_message_pipeline()
            
            # 初始化各个组件
            if not self._service_manager.initialize_all():
                logger.error("Failed to initialize service components")
                return False
            
            logger.info("SyslogService components initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SyslogService: {str(e)}")
            return False
    
    def _create_message_pipeline(self):
        """
        创建消息处理管道
        """
        self._message_pipeline = MessagePipeline()
        
        # 添加处理器到管道
        self._message_pipeline.add_processor(self._process_message)
    
    def start(self):
        """
        启动服务
        
        Returns:
            bool: 启动是否成功
        """
        try:
            # 初始化服务
            if not self._initialize():
                return False
            
            # 启动组件
            self._running = True
            
            # 启动配置更新线程
            self._start_config_refresh_thread()
            
            # 启动消息消费线程
            self._start_message_consumer_thread()
            
            logger.info("SyslogService started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start SyslogService: {str(e)}")
            return False
    
    def _start_message_consumer_thread(self):
        """
        启动消息消费线程
        """
        # 获取Kafka消费者
        self._kafka_consumer = get_syslog_consumer()
        
        # 创建并启动消息消费线程
        self._consumer_thread = threading.Thread(target=self._consume_messages, daemon=True)
        self._consumer_thread.start()
        logger.info("Message consumer thread started")
    
    def _start_config_refresh_thread(self):
        """
        启动配置更新线程
        """
        self._config_thread = threading.Thread(target=self._config_refresh_loop, daemon=True)
        self._config_thread.start()
        logger.info("Config refresh thread started")
    
    def _config_refresh_loop(self):
        """
        配置更新循环
        """
        while self._running:
            try:
                interval = self.config.get('refresh_interval', 60)
                time.sleep(interval)
                self._load_config()
                self._update_component_configs()
            except Exception as e:
                logger.error(f"Error in config refresh loop: {str(e)}")
                # 出错后短暂休眠再试
                time.sleep(10)
    
    def _load_config(self):
        """
        加载配置文件
        """
        try:
            config_path = self.config.get('config_file_path')
            if os.path.exists(config_path):
                new_config = self._config_manager.load_config(config_path)
                if new_config:
                    self.config = new_config
                    logger.info(f"Config loaded from {config_path}")
            else:
                logger.warning(f"Config file not found: {config_path}, using current config")
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
    
    def _update_component_configs(self):
        """
        更新所有组件的配置
        """
        try:
            self._service_manager.update_configs(self.config)
            logger.info("Component configurations updated")
        except Exception as e:
            logger.error(f"Error updating component configurations: {str(e)}")
    
    def _consume_messages(self):
        """
        持续从Kafka消费消息并处理
        """
        try:
            logger.info("Starting to consume syslog messages from Kafka")
            
            if not self._kafka_consumer:
                logger.error("Kafka consumer not initialized")
                return
            
            while self._running:
                try:
                    # 从Kafka获取消息
                    message = self._kafka_consumer.poll(timeout=1.0)
                    
                    if message:
                        # 确保消息格式包含必要的字段
                        if isinstance(message, dict):
                            # 提取必要字段，如果不存在则使用默认值
                            syslog_message = {
                                'host': message.get('host', 'unknown'),
                                'timestamp': message.get('timestamp', datetime.now().isoformat()),
                                'msg': message.get('msg', ''),
                                'source': message.get('source', message.get('host', 'unknown')),
                                'facility': message.get('facility'),
                                'severity': message.get('severity')
                            }
                            
                            # 通过处理管道处理消息
                            self._message_pipeline.process(syslog_message)
                        else:
                            logger.warning(f"Received non-dictionary message: {type(message)}")
                except Exception as e:
                    logger.error(f"Error consuming message: {str(e)}")
                    # 短暂休眠后继续
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in message consumer thread: {str(e)}")
    
    def _process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理单个syslog消息
        
        Args:
            message: 消息字典
            
        Returns:
            处理后的消息，如果过滤掉则返回None
        """
        try:
            # 1. 黑名单过滤
            if self.config.get('blacklist', {}).get('enabled', True):
                if self._blacklist_filter.is_blacklisted(message):
                    logger.debug(f"Message filtered by blacklist: {message.get('host')}")
                    return None
            
            # 2. 应用处理器
            processed_message = self._apply_processors(message)
            if not processed_message:
                return None
            
            # 3. 日志合并
            if self.config.get('log_merge', {}).get('enabled', True):
                merged = self._log_merger.try_merge_log(processed_message)
                if merged and self._log_merger.should_create_alert(merged):
                    # 4. 为合并组创建告警
                    self._alert_manager.create_merge_alert(merged)
            else:
                # 如果未启用合并，直接检查是否需要告警
                severity = get_alert_severity(processed_message)
                if self._alert_manager.SEVERITY_LEVELS[severity] >= \
                   self._alert_manager.SEVERITY_LEVELS.get(self.config.get('alert_config', {}).get('min_severity', 'warning'), 3):
                    # 创建非合并告警
                    self._alert_manager.create_alert(
                        alert_type='single_log',
                        summary=processed_message.get('msg', '').split('\n')[0][:100],
                        details=processed_message,
                        severity=severity,
                        source={'host': processed_message.get('host'), 'type': 'single_log'}
                    )
            
            # 5. 转发消息
            if self.config.get('processors', {}).get('default', {}).get('action') == 'forward':
                self._send_to_kafka(processed_message)
            
            return processed_message
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return None
    
    def _apply_processors(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        应用处理器到消息
        
        Args:
            message: 原始消息
            
        Returns:
            处理后的消息
        """
        try:
            enabled_processors = self.config.get('enabled_processors', ['default'])
            processors = self.config.get('processors', {})
            
            processed_message = message.copy()
            
            for processor_name in enabled_processors:
                if processor_name in processors:
                    processor_config = processors[processor_name]
                    if processor_config.get('enabled', True):
                        result = self._apply_processor(processed_message, processor_config)
                        if result is None:
                            return None
                        processed_message = result
            
            return processed_message
        except Exception as e:
            logger.error(f"Error applying processors: {str(e)}")
            return message
    
    def _apply_processor(self, message: Dict[str, Any], processor_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        应用单个处理器
        
        Args:
            message: 消息
            processor_config: 处理器配置
            
        Returns:
            处理后的消息
        """
        try:
            pattern = processor_config.get('pattern', '.*')
            action = processor_config.get('action', 'forward')
            
            # 简化的模式匹配
            import re
            if not re.search(pattern, message.get('msg', '')):
                return message
            
            # 执行动作
            if action == 'drop':
                return None
            elif action == 'modify':
                # 这里可以添加修改逻辑
                pass
            
            return message
        except Exception as e:
            logger.error(f"Error applying processor: {str(e)}")
            return message
    
    def _send_to_kafka(self, message: Dict[str, Any]):
        """
        发送消息到Kafka
        
        Args:
            message: 要发送的消息
        """
        try:
            # 这里应该使用项目的Kafka生产者
            # 暂时只记录日志
            logger.debug(f"Forwarding message to Kafka: {message.get('host')}")
        except Exception as e:
            logger.error(f"Error sending message to Kafka: {str(e)}")
    
    def shutdown(self):
        """
        关闭服务
        """
        try:
            self._running = False
            
            # 等待线程结束
            if self._config_thread and self._config_thread.is_alive():
                self._config_thread.join(timeout=5.0)
            if self._consumer_thread and self._consumer_thread.is_alive():
                self._consumer_thread.join(timeout=5.0)
            
            # 关闭Kafka消费者
            if self._kafka_consumer:
                try:
                    self._kafka_consumer.close()
                except Exception:
                    pass
            
            # 关闭所有组件
            if self._service_manager:
                self._service_manager.shutdown_all()
            
            logger.info("SyslogService shutdown successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取服务状态
        
        Returns:
            服务状态字典
        """
        status = {
            'service': {
                'running': self._running,
                'config_path': self.config.get('config_file_path'),
                'refresh_interval': self.config.get('refresh_interval')
            },
            'components': {}
        }
        
        # 获取各个组件的状态
        if self._blacklist_manager:
            status['components']['blacklist'] = self._blacklist_manager.get_stats()
        
        if self._log_merger:
            status['components']['log_merger'] = self._log_merger.get_stats()
        
        if self._alert_manager:
            status['components']['alert_manager'] = self._alert_manager.get_stats()
        
        return status


def main():
    """
    主函数，用于演示和测试
    """
    print("=== Syslog Service Demo - Complete Workflow ===")
    print("This demo showcases the complete syslog processing workflow:")
    print("1. Kafka message consumption using get_syslog_consumer")
    print("2. Blacklist filtering with periodic configuration updates")
    print("3. Log merging with regex-based grouping")
    print("4. Alert caching with host+group_name+time_window management\n")
    
    # 创建服务实例
    syslog_service = SyslogService()
    
    # 启动服务
    if syslog_service.start():
        print("✓ SyslogService started successfully")
        print("✓ All components initialized")
        print("✓ Processing threads started\n")
        
        try:
            # 运行一段时间后显示状态
            time.sleep(2)
            
            print("\n=== Service Status ===")
            status = syslog_service.get_status()
            print(json.dumps(status, indent=2))
            
            print("\n=== Service Running ===")
            print("Now running in continuous mode. The service is:")
            print("1. Consuming messages from Kafka")
            print("2. Applying blacklist filtering")
            print("3. Merging logs based on configured rules")
            print("4. Managing alerts with ID caching mechanism")
            print("\nPress Ctrl+C to stop the service")
            
            # 保持运行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping service...")
        finally:
            print("Shutting down threads...")
            syslog_service.shutdown()
            print("Service stopped successfully")
    else:
        print("Failed to start syslog service")


if __name__ == '__main__':
    main()