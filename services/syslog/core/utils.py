"""
Syslog服务工具函数集合
"""
import re
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    解析日志时间戳
    
    Args:
        timestamp_str: 时间戳字符串
        
    Returns:
        datetime对象或None
    """
    formats = [
        '%b %d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%b %d %H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f%z'
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            # 如果没有时区信息，添加UTC时区
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    return None


def format_timestamp(dt: datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    格式化时间戳
    
    Args:
        dt: datetime对象
        format_str: 格式字符串
        
    Returns:
        格式化后的时间字符串
    """
    return dt.strftime(format_str)


def extract_fields_from_message(message: str, patterns: Dict[str, str]) -> Dict[str, str]:
    """
    从消息中提取字段
    
    Args:
        message: 消息内容
        patterns: 字段名和对应正则表达式的映射
        
    Returns:
        提取的字段映射
    """
    extracted = {}
    for field_name, pattern in patterns.items():
        match = re.search(pattern, message)
        if match:
            extracted[field_name] = match.group(1) if match.groups() else match.group(0)
    return extracted


def generate_hash(data: Any) -> str:
    """
    生成数据的哈希值
    
    Args:
        data: 要哈希的数据
        
    Returns:
        哈希字符串
    """
    if not isinstance(data, str):
        data = json.dumps(data, sort_keys=True)
    return hashlib.md5(data.encode('utf-8')).hexdigest()


def sanitize_log_message(message: str, max_length: int = 1000) -> str:
    """
    清理和截断日志消息
    
    Args:
        message: 原始消息
        max_length: 最大长度
        
    Returns:
        清理后的消息
    """
    # 移除控制字符，保留换行符和制表符
    message = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', message)
    # 截断过长的消息
    if len(message) > max_length:
        message = message[:max_length] + '...(truncated)'
    return message


def parse_syslog_message(syslog_line: str) -> Dict[str, Any]:
    """
    解析syslog格式的消息
    
    Args:
        syslog_line: syslog格式的消息行
        
    Returns:
        解析后的消息字典
    """
    # 简单的syslog格式解析
    # 格式示例: "Jan 1 12:34:56 hostname program[pid]: message"
    pattern = r'^([A-Za-z]{3} \d{1,2} \d{2}:\d{2}:\d{2}) (\S+) (\S+)(?:\[(\d+)\])?: (.+)$'
    match = re.match(pattern, syslog_line)
    
    if match:
        timestamp_str, hostname, program, pid, message = match.groups()
        timestamp = parse_timestamp(timestamp_str)
        return {
            'timestamp': timestamp,
            'host': hostname,
            'program': program,
            'pid': pid,
            'message': message,
            'raw': syslog_line
        }
    
    # 如果解析失败，返回基础信息
    return {
        'timestamp': datetime.now(timezone.utc),
        'raw': syslog_line,
        'message': syslog_line
    }


def get_alert_severity(message: Dict[str, Any]) -> str:
    """
    根据消息内容推断告警级别
    
    Args:
        message: 消息字典
        
    Returns:
        告警级别字符串
    """
    severity_map = {
        'emergency': ['emergency', 'panic'],
        'alert': ['alert'],
        'critical': ['critical', 'fatal'],
        'error': ['error', 'exception', 'fail'],
        'warning': ['warning', 'warn'],
        'notice': ['notice'],
        'info': ['info', 'notice'],
        'debug': ['debug', 'trace']
    }
    
    message_text = message.get('message', '').lower()
    
    for severity, keywords in severity_map.items():
        for keyword in keywords:
            if keyword in message_text:
                return severity
    
    return 'info'


def filter_messages(messages: List[Dict[str, Any]], filter_func) -> List[Dict[str, Any]]:
    """
    根据过滤函数过滤消息列表
    
    Args:
        messages: 消息列表
        filter_func: 过滤函数，接收消息返回布尔值
        
    Returns:
        过滤后的消息列表
    """
    return [msg for msg in messages if filter_func(msg)]


def group_messages_by_field(messages: List[Dict[str, Any]], field: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    根据指定字段对消息进行分组
    
    Args:
        messages: 消息列表
        field: 分组字段名
        
    Returns:
        分组后的消息字典
    """
    groups = {}
    for message in messages:
        key = message.get(field, 'unknown')
        if key not in groups:
            groups[key] = []
        groups[key].append(message)
    return groups