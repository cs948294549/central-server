"""
Huawei 配置解析器

支持解析 Huawei 设备的策略配置
"""

import re
import logging
from typing import List
from lib_config.parsers.parser_base import BaseParser, register_parser
from lib_config.models import (
    PrefixListConfig,
    PrefixListEntry,
    Action
)

logger = logging.getLogger(__name__)


@register_parser('huawei')
class HuaweiParser(BaseParser):
    """Huawei 设备配置解析器"""

    def __init__(self, vendor: str, raw_cfg: str):
        super().__init__(vendor, raw_cfg)

    def _init_available_sections(self) -> None:
        """初始化支持的配置项"""
        # Huawei 设备暂无地址前缀列表需求
        self.available_sections = set()

    def parse_prefix_lists(self) -> List[PrefixListConfig]:
        """
        解析 Huawei 地址前缀列表

        使用 self.config_tree 节点树进行解析

        Huawei 格式示例:
        ip ip-prefix idc-networks index 10 permit 172.16.0.0 12 greater-equal 16 less-equal 24
        ip ip-prefix idc-networks index 20 permit 10.0.0.0 8 greater-equal 16 less-equal 24
        ip ip-prefix idc-networks index 100 deny 0.0.0.0 0 less-equal 32

        Returns:
            List[PrefixListConfig]: 前缀列表配置列表
        """
        # TODO: 实现 Huawei 前缀列表解析
        logger.warning(f"[{self.vendor}] parse_prefix_lists 方法尚未实现")
        return []
