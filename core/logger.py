"""
日志配置模块

提供按天切割的日志配置功能
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from logging import Formatter
from config import Config

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件路径
LOG_FILE = os.path.join(LOG_DIR, 'agent-node.log')


def setup_logger(log_level=None):
    """
    设置日志配置，实现按天切割
    
    Args:
        log_level: 日志级别，默认为配置中的级别
    
    Returns:
        logging.Logger: 根日志记录器
    """
    # 确保日志目录存在 (使用预定义的LOG_DIR)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # 获取日志级别
    level = log_level or Config.log_level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建按天切割的文件处理器
    file_handler = TimedRotatingFileHandler(
        LOG_FILE,
        when='midnight',  # 在午夜进行切割
        interval=1,       # 每天切割一次
        backupCount=7,    # 保留7天的日志
        encoding='utf-8'
    )
    
    # 设置文件日志格式
    file_formatter = Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(numeric_level)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    
    # 设置控制台日志格式
    console_formatter = Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(numeric_level)
    
    # 添加处理器到根日志记录器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 创建一个专用的agent日志记录器
    agent_logger = logging.getLogger('agent')
    
    logging.info(f"日志系统初始化完成，日志级别: {level}")
    
    return root_logger


# 导出函数
__all__ = ['setup_logger', 'LOG_DIR']