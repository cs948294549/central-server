"""
Cisco 配置编码器

将标准化模型转换为 Cisco NX-OS/IOS 配置文本
"""

import logging
from typing import List
from lib_config.encoders.encode_base import BaseEncoder, register_encoder
from lib_config.models import PrefixListConfig, PrefixListEntry, Action

logger = logging.getLogger(__name__)


@register_encoder('cisco_nx')
@register_encoder('cisco_ios')
class CiscoEncoder(BaseEncoder):
    """
    Cisco 配置编码器

    支持 NX-OS 和 IOS 格式
    """

    def _init_available_sections(self) -> None:
        """初始化支持的配置项"""
        self.available_sections = {'prefix_lists'}

    def encode_prefix_lists(self, prefix_lists: List[PrefixListConfig]) -> str:
        """
        编码地址前缀列表为 Cisco 配置

        Cisco 格式:
        ip prefix-list <name> seq <num> <action> <prefix> [ge <num>] [le <num>]

        Args:
            prefix_lists: 前缀列表模型列表

        Returns:
            str: Cisco 配置文本
        """
        config_lines = []

        for prefix_list in prefix_lists:
            # 如果有描述信息，添加注释（Cisco 原生不支持 description，用注释代替）
            if prefix_list.description:
                config_lines.append(f"! {prefix_list.name}: {prefix_list.description}")

            # 编码每个条目
            for entry in prefix_list.entries:
                line = self._encode_prefix_entry(prefix_list.name, entry)
                config_lines.append(line)

            # 添加空行分隔不同的前缀列表
            config_lines.append("")

        # 移除最后的空行
        if config_lines and config_lines[-1] == "":
            config_lines.pop()

        return "\n".join(config_lines)

    def _encode_prefix_entry(self, name: str, entry: PrefixListEntry) -> str:
        """
        编码单个前缀列表条目

        Args:
            name: 前缀列表名称
            entry: 前缀列表条目

        Returns:
            str: 配置行
        """
        # 基本格式: ip prefix-list <name> seq <seq> <action> <prefix>
        action = "permit" if entry.action == Action.PERMIT else "deny"
        line = f"ip prefix-list {name} seq {entry.seq} {action} {entry.prefix}"

        # 添加 ge 和 le 参数
        if entry.ge is not None:
            line += f" ge {entry.ge}"
        if entry.le is not None:
            line += f" le {entry.le}"

        # 如果有描述，添加为行尾注释
        if entry.description:
            line += f"  ! {entry.description}"

        return line
