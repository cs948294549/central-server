"""
Cisco 配置解析器

支持解析 Cisco NX-OS / IOS / IOS-XR 设备的策略配置
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


@register_parser('cisco_nx')
@register_parser('cisco_ios')
@register_parser('cisco_xr')
class CiscoParser(BaseParser):
    """Cisco 设备配置解析器（支持 NX-OS、IOS、IOS-XR）"""

    def __init__(self, vendor: str, raw_cfg: str):
        super().__init__(vendor, raw_cfg)

    def _init_available_sections(self) -> None:
        """初始化支持的配置项"""
        self.available_sections = {
            'prefix_lists',  # 地址前缀列表
        }

    def parse_prefix_lists(self) -> List[PrefixListConfig]:
        """
        解析 Cisco 地址前缀列表

        使用 self.config_tree 节点树进行解析

        Cisco 格式示例:
        ip prefix-list idc-networks seq 10 permit 172.16.0.0/12 ge 16 le 24
        ip prefix-list idc-networks seq 20 permit 10.0.0.0/8 ge 16 le 24
        ip prefix-list idc-networks seq 100 deny 0.0.0.0/0 le 32

        Returns:
            List[PrefixListConfig]: 前缀列表配置列表
        """
        # 正则表达式匹配前缀列表条目
        # 格式: ip prefix-list <name> [seq <num>] <action> <prefix> [ge <num>] [le <num>]
        pattern = re.compile(
            r'^ip\s+prefix-list\s+'
            r'(?P<name>\S+)\s+'
            r'(?:seq\s+(?P<seq>\d+)\s+)?'  # seq 可选
            r'(?P<action>permit|deny)\s+'
            r'(?P<prefix>[\d.]+/\d+)'
            r'(?:\s+ge\s+(?P<ge>\d+))?'
            r'(?:\s+le\s+(?P<le>\d+))?',
            re.IGNORECASE
        )

        # 按名称分组存储条目
        prefix_lists_dict = {}

        # 遍历配置树节点
        if self.config_tree:
            for node in self.config_tree:
                content = node['content'].strip()
                match = pattern.match(content)

                if match:
                    name = match.group('name')
                    seq = int(match.group('seq')) if match.group('seq') else None
                    action = match.group('action').lower()
                    prefix = match.group('prefix')
                    ge = int(match.group('ge')) if match.group('ge') else None
                    le = int(match.group('le')) if match.group('le') else None

                    # 如果没有显式 seq，自动分配
                    if seq is None:
                        if name not in prefix_lists_dict:
                            seq = 10
                        else:
                            existing_seqs = [e.seq for e in prefix_lists_dict[name]]
                            seq = max(existing_seqs) + 10 if existing_seqs else 10

                    # 创建条目
                    entry = PrefixListEntry(
                        seq=seq,
                        action=Action.PERMIT if action == 'permit' else Action.DENY,
                        prefix=prefix,
                        ge=ge,
                        le=le,
                        description=None
                    )

                    # 按名称分组
                    if name not in prefix_lists_dict:
                        prefix_lists_dict[name] = []

                    prefix_lists_dict[name].append(entry)

        # 转换为 PrefixListConfig 列表
        prefix_lists = []
        for name, entries in prefix_lists_dict.items():
            # 按序列号排序
            entries.sort(key=lambda e: e.seq)

            prefix_list = PrefixListConfig(
                name=name,
                entries=entries,
                description=None,
                vendor_type=self.vendor
            )
            prefix_lists.append(prefix_list)

        logger.info(f"[{self.vendor}] 解析到 {len(prefix_lists)} 个前缀列表")
        for pl in prefix_lists:
            logger.debug(f"  - {pl.name}: {len(pl.entries)} 条规则")

        return prefix_lists


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Cisco 配置示例
    cisco_config = """
hostname cisco-router-01
!
ip prefix-list idc-networks seq 10 permit 172.16.0.0/12 ge 16 le 24
ip prefix-list idc-networks seq 20 permit 10.0.0.0/8 ge 16 le 24
ip prefix-list idc-networks seq 30 permit 192.168.0.0/16 ge 24 le 28
ip prefix-list idc-networks seq 100 deny 0.0.0.0/0 le 32
!
ip prefix-list partner-routes seq 5 permit 203.0.113.0/24
ip prefix-list partner-routes seq 10 permit 198.51.100.0/24
ip prefix-list partner-routes seq 15 deny 0.0.0.0/0 le 32
!
! 无 seq 的示例
ip prefix-list test-list permit 10.1.0.0/16
ip prefix-list test-list permit 10.2.0.0/16
ip prefix-list test-list deny 0.0.0.0/0
!
interface GigabitEthernet0/0
 ip address 192.168.1.1 255.255.255.0
!
router bgp 65001
 neighbor 10.0.0.2 remote-as 65002
 address-family ipv4 unicast
  neighbor 10.0.0.2 prefix-list idc-networks in
  neighbor 10.0.0.2 prefix-list partner-routes out
!
end
    """

    # 测试解析器
    from lib_config import get_parser

    print("=" * 60)
    print("Cisco 前缀列表解析测试")
    print("=" * 60)

    # 获取解析器
    parser = get_parser('cisco_nx', cisco_config)
    print(f"\n{parser}\n")

    # 只解析前缀列表
    print("=== parse(sections=['prefix_lists']) ===")
    result = parser.parse(sections=['prefix_lists'])

    print(f"\n解析结果:")
    print(f"  前缀列表数量: {len(result.prefix_lists)}")

    for pl in result.prefix_lists:
        print(f"\n  前缀列表: {pl.name}")
        print(f"    条目数: {len(pl.entries)}")
        for entry in pl.entries:
            ge_str = f" ge {entry.ge}" if entry.ge else ""
            le_str = f" le {entry.le}" if entry.le else ""
            print(f"      seq {entry.seq}: {entry.action} {entry.prefix}{ge_str}{le_str}")
