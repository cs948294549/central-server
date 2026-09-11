"""
配置指纹计算模块

用于计算配置的唯一指纹，用于：
1. 配置去重和匹配
2. 配置变更检测
3. 配置一致性校验
"""

import json
import hashlib
from typing import Dict, Any


def calculate_fingerprint(data: Dict[str, Any], algorithm: str = 'sha256') -> str:
    """
    计算配置数据的指纹

    Args:
        data: 配置数据字典
        algorithm: 哈希算法，支持 'md5', 'sha1', 'sha256'

    Returns:
        str: 十六进制格式的指纹字符串

    Example:
        >>> data = {'name': 'test', 'entries': [...]}
        >>> fingerprint = calculate_fingerprint(data)
        >>> print(fingerprint)
        'a1b2c3d4e5f6...'
    """
    # 1. 序列化为 JSON（sorted keys 保证顺序一致）
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)

    # 2. 编码为 UTF-8 字节
    json_bytes = json_str.encode('utf-8')

    # 3. 计算哈希
    if algorithm == 'md5':
        hash_obj = hashlib.md5(json_bytes)
    elif algorithm == 'sha1':
        hash_obj = hashlib.sha1(json_bytes)
    elif algorithm == 'sha256':
        hash_obj = hashlib.sha256(json_bytes)
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")

    # 4. 返回十六进制字符串
    return hash_obj.hexdigest()
