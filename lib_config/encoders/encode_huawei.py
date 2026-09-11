"""
Huawei 配置编码器

将标准化模型转换为 Huawei 配置文本
"""

import logging
from typing import List
from lib_config.encoders.encode_base import BaseEncoder, register_encoder
from lib_config.models import PrefixListConfig, PrefixListEntry, Action

logger = logging.getLogger(__name__)


@register_encoder('huawei')
class HuaweiEncoder(BaseEncoder):
    """
    Huawei 配置编码器
    """

    def _init_available_sections(self) -> None:
        """初始化支持的配置项"""
        # Huawei 设备暂无地址前缀列表需求
        self.available_sections = set()

    def encode_prefix_lists(self, prefix_lists: List[PrefixListConfig]) -> str:
        """
        编码地址前缀列表为 Huawei 配置

        Huawei 格式:
        ip ip-prefix <name> index <num> <action> <prefix> <masklen> [greater-equal <num>] [less-equal <num>]

        Args:
            prefix_lists: 前缀列表模型列表

        Returns:
            str: Huawei 配置文本
        """
        # TODO: 实现 Huawei 前缀列表编码
        logger.warning(f"[{self.vendor}] encode_prefix_lists 方法尚未实现")
        return ""
