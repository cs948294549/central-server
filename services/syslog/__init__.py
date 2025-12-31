import logging
import re
from typing import Dict, Any, List, Optional, Set
from tables.SyslogDB import SyslogDB

logger = logging.getLogger(__name__)

class BlacklistEntry:
    """
    黑名单条目
    """

    def __init__(self, rule_id: str, pattern: str, description: str = None):
        """
        初始化黑名单条目

        Args:
            rule_id: 条目ID
            pattern: 匹配模式（正则表达式）
            description: 描述
        """
        self.rule_id = rule_id
        self.pattern = pattern
        self.description = description
        self._matched_sum = 0
        self._compiled_pattern = None

        try:
            self._compiled_pattern = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern}': {e}")

    def matches(self, text: str) -> bool:
        """
        检查文本是否匹配该黑名单条目

        Args:
            text: 要检查的文本

        Returns:
            是否匹配
        """
        if not text:
            return False
        return bool(self._compiled_pattern.search(text))

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            字典表示
        """
        return {
            'rule_id': self.rule_id,
            'pattern': self.pattern,
            'description': self.description,
            'matched_sum': self._matched_sum,
        }

    def increase(self):
        self._matched_sum += 1

def get_blacklisted_entries() -> List[BlacklistEntry]:
    try:
        bl_db = SyslogDB()
        black_list = bl_db.getBlackList({})
        blacklisted_entries = []

        for blacklisted_entry in black_list:
            entry = BlacklistEntry(
                rule_id=blacklisted_entry.get('rule_id', ''),
                pattern=blacklisted_entry.get('pattern', ''),
                description=blacklisted_entry.get('descr', '')
            )
            blacklisted_entries.append(entry)
        return blacklisted_entries
    except Exception as e:
        logger.error("Failed to get blacklisted entries: {}".format(str(e)))
        return []


class MergeRule:
    """
    日志合并规则
    """

    def __init__(self, entry_id: str, group_name: str, pattern: str, description: str = None):
        """
        初始化合并规则

        Args:
            name: 规则名称
            pattern: 匹配模式（正则表达式）
            fields: 用于分组的字段列表
        """
        self.id = entry_id
        self.group_name = group_name
        self.pattern = pattern
        self.description = description
        self._matched_sum = 0
        self._compiled_pattern = None

        try:
            self._compiled_pattern = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern}': {e}")

    def matches(self, text: str) -> bool:
        """
        检查消息是否匹配该规则

        Args:
            text: 要检查的消息

        Returns:
            是否匹配
        """
        if not text:
            return False
        return bool(self._compiled_pattern.search(text))

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            字典表示
        """
        return {
            'id': self.id,
            'group_name': self.group_name,
            'pattern': self.pattern,
            'description': self.description,
            'matched_sum': self._matched_sum,
        }

    def increase(self):
        self._matched_sum += 1

def get_mergelisted_entries() -> List[MergeRule]:
    try:
        ml_db = SyslogDB()
        merge_list = ml_db.getMergeList({})
        mergelisted_entries = []
        for mergelisted_entry in merge_list:
            entry = MergeRule(
                entry_id=mergelisted_entry.get('rule_id', ''),
                group_name=mergelisted_entry.get('group_name', ''),
                pattern=mergelisted_entry.get('pattern', ''),
                description=mergelisted_entry.get('descr', '')
            )
            mergelisted_entries.append(entry)
        return mergelisted_entries
    except Exception as e:
        logger.error("Failed to get mergelisted entries: {}".format(str(e)))
        return []