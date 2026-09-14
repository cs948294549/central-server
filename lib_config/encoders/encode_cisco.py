"""
Cisco 配置编码器

将标准化模型转换为 Cisco NX-OS/IOS/IOS-XR 配置文本
"""

import logging
from typing import List
from lib_config.encoders.encode_base import BaseEncoder, register_encoder
from lib_config.models import PrefixListConfig, PrefixListEntry, Action

logger = logging.getLogger(__name__)


@register_encoder('cisco_nx')
@register_encoder('cisco_ios')
@register_encoder('cisco_xr')
class CiscoEncoder(BaseEncoder):
    """
    Cisco 配置编码器

    支持 NX-OS、IOS 和 IOS-XR 格式
    """

    def _init_available_sections(self) -> None:
        """初始化支持的配置项"""
        self.available_sections = {'prefix_lists'}

    def encode_prefix_lists(self, prefix_lists: List[PrefixListConfig], operation: str = 'add') -> str:
        """
        编码地址前缀列表为 Cisco 配置

        Cisco 格式:
        ip prefix-list <name> seq <num> <action> <prefix> [ge <num>] [le <num>]
        删除格式:
        no ip prefix-list <name> seq <num>

        Args:
            prefix_lists: 前缀列表模型列表
            operation: 操作类型，'add' 表示添加配置，'delete' 表示删除配置

        Returns:
            str: Cisco 配置文本
        """
        config_lines = []

        for prefix_list in prefix_lists:
            # 添加操作时，如果有描述信息，添加注释（Cisco 原生不支持 description，用注释代替）
            if operation == 'add' and prefix_list.description:
                config_lines.append(f"! {prefix_list.name}: {prefix_list.description}")

            # 编码每个条目
            for entry in prefix_list.entries:
                line = self._encode_prefix_entry(prefix_list.name, entry, operation)
                config_lines.append(line)

            # 添加空行分隔不同的前缀列表
            config_lines.append("")

        # 移除最后的空行
        if config_lines and config_lines[-1] == "":
            config_lines.pop()

        return "\n".join(config_lines)

    def _encode_prefix_entry(self, name: str, entry: PrefixListEntry, operation: str = 'add') -> str:
        """
        编码单个前缀列表条目

        Args:
            name: 前缀列表名称
            entry: 前缀列表条目
            operation: 操作类型，'add' 或 'delete'

        Returns:
            str: 配置行
        """
        if operation == 'delete':
            # 删除操作：no ip prefix-list <name> seq <seq>
            return f"no ip prefix-list {name} seq {entry.seq}"

        # 添加操作：基本格式: ip prefix-list <name> seq <seq> <action> <prefix>
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
