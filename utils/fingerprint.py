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


def _seq_sort_key(entry):
    """
    条目排序键：seq 可能是 int / 数字字符串 / None，统一成可比较的元组

    取不到 seq 的条目排在最后，同键靠 sorted 的稳定性保持原有相对顺序
    """
    seq = entry.get("seq") if isinstance(entry, dict) else None
    if seq is None or seq == "":
        return (1, 0.0)
    try:
        return (0, float(seq))
    except (TypeError, ValueError):
        return (1, 0.0)


def sort_entries_by_seq(entries):
    """
    按 seq 升序排列配置条目（返回新对象，不改动入参）

    同一份配置在不同环节的条目顺序可能不同：设备按自身输出顺序、前端编辑时
    可能中间插入新行、从库里读出来的顺序也不保证。而配置的实际生效顺序由 seq
    决定，与数组下标无关，所以凡是比指纹、存库、生成命令、做文本对比之前，
    都先按 seq 排一次，避免顺序差异被当成配置漂移。

    支持两种入参形态，返回同形态：裸数组 [...] 或 {"entries": [...]}。

    Args:
        entries: 条目列表，元素为带 seq 字段的 dict

    Returns:
        排序后的新列表 / 新字典
    """
    if isinstance(entries, dict):
        if "entries" not in entries:
            return entries
        return {**entries, "entries": sort_entries_by_seq(entries["entries"])}
    if not isinstance(entries, list):
        return entries
    return sorted(entries, key=_seq_sort_key)


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
    # 1. 条目先按 seq 排序：数组顺序不是配置语义的一部分，
    #    同一份配置换个摆放顺序也必须算出相同的指纹
    if isinstance(data, dict) and "entries" in data:
        data = {**data, "entries": sort_entries_by_seq(data["entries"])}

    # 2. 序列化为 JSON（sorted keys 保证顺序一致）
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)

    # 3. 编码为 UTF-8 字节
    json_bytes = json_str.encode('utf-8')

    # 4. 计算哈希
    if algorithm == 'md5':
        hash_obj = hashlib.md5(json_bytes)
    elif algorithm == 'sha1':
        hash_obj = hashlib.sha1(json_bytes)
    elif algorithm == 'sha256':
        hash_obj = hashlib.sha256(json_bytes)
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")

    # 5. 返回十六进制字符串
    return hash_obj.hexdigest()
