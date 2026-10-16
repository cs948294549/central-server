"""
Cisco 配置解析器

支持解析 Cisco NX-OS / IOS / IOS-XR 设备的策略配置
"""

import ipaddress
import re
import logging
from typing import Any, Dict, List, Optional
from lib_config.parsers.parser_base import BaseParser, register_parser
from lib_config.models import (
    PrefixListConfig,
    PrefixListEntry,
    AclConfig,
    AclEntry,
    AddrGroupConfig,
    AddrGroupEntry,
    PortGroupConfig,
    PortGroupEntry,
    Action
)
from utils.ipaddr import wildcard2length, length2netmask, getNet

logger = logging.getLogger(__name__)

# 系统自动生成的 ACL, 名称统一以 copp 开头, 不属于业务策略, 不采集
IGNORED_ACL_PREFIXES = ('copp',)


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
            'prefix_lists',    # 地址前缀列表
            'access_lists',    # 访问控制列表
            'address_groups',  # 地址组（地址簿）
            'port_groups',     # 端口组（端口簿）
        }

    # ==================== 地址 / 端口文本归一化 ====================

    def _parse_addr(self, text: Optional[str]) -> Optional[Dict[str, Any]]:
        """地址文本归一化为 AddressSpec"""
        if not text:
            return None

        tokens = text.split()
        lowered = tokens[0].lower()

        if lowered == 'any':
            return {'type': 'any'}

        if lowered == 'host':
            return {'type': 'host', 'address': f'{tokens[1]}/{"128" if ":" in tokens[1] else "32"}'}

        if lowered in ('addrgroup', 'object-group'):
            return {'type': 'addrgroup', 'name': tokens[-1]}

        if '/' in tokens[0]:
            address, length = tokens[0].split('/', 1)
            if not length.isdigit():
                logger.debug(f"[{self.vendor}] 无法识别的地址掩码长度: {text}")
                return None
            if ':' in address:
                return {'type': 'host' if length == '128' else 'network', 'address': tokens[0]}
            if length == '32':
                return {'type': 'host', 'address': tokens[0]}
            return {'type': 'network',
                    'address': f'{getNet(address, length2netmask(int(length)))}/{length}'}

        # 点分十进制, 可能跟反掩码
        if len(tokens) == 1:
            return {'type': 'host', 'address': f'{tokens[0]}/32'}

        length = wildcard2length(tokens[1])
        if length == 32:
            return {'type': 'host', 'address': f'{tokens[0]}/32'}
        return {'type': 'network',
                'address': f'{getNet(tokens[0], length2netmask(length))}/{length}'}

    def _parse_port(self, text: Optional[str]) -> Optional[Dict[str, Any]]:
        """端口文本归一化为 PortSpec, 数字存整数, 别名存字符串"""
        if not text:
            return None

        tokens = text.split()
        lowered = tokens[0].lower()

        if lowered in ('portgroup', 'object-group'):
            return {'type': 'portgroup', 'name': tokens[-1]}

        ports = []
        for token in tokens[1:]:
            ports.append(int(token) if token.isdigit() else token)
        return {'type': 'direct', 'op': lowered, 'ports': ports}

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
                description=None
            )
            prefix_lists.append(prefix_list)

        logger.info(f"[{self.vendor}] 解析到 {len(prefix_lists)} 个前缀列表")
        for pl in prefix_lists:
            logger.debug(f"  - {pl.name}: {len(pl.entries)} 条规则")

        return prefix_lists

    def parse_access_lists(self) -> List[AclConfig]:
        """
        解析 Cisco 访问控制列表

        Cisco 格式示例:
        ip access-list acl_office_to_idc
          statistics per-entry
          100 permit tcp any any established
          200 permit tcp any addrgroup og_ip_idcnet portgroup og_port_per
          230 permit tcp any 10.37.0.0/16 eq 2181
          910 deny tcp any addrgroup og_ip_idcnet

        Returns:
            List[AclConfig]: ACL 配置列表
        """
        # 块头: ip access-list [standard|extended] <标识> / ipv6 access-list <标识>
        header_pattern = re.compile(
            r'^(?P<family>ipv6|ip)\s+access-list\s+'
            r'(?:(?P<kind>standard|extended)\s+)?'
            r'(?P<ident>\S+)$',
            re.IGNORECASE
        )

        # 地址: any / host x / addrgroup x / x.x.x.x [反掩码] / x/n / v6字面量
        addr = (r'(?:any|host\s+\S+|(?:addrgroup|object-group(?:\s+network)?)\s+\S+'
                r'|[0-9a-fA-F:.]+(?:/\d+)?(?:\s+(?:0|[\d.]+))?)')
        # 端口: portgroup x / object-group service x / eq 80 / range 5900 5930
        port = r'(?:(?:portgroup|object-group(?:\s+service)?)\s+\S+|(?:eq|gt|lt|neq|range)\s+\S+(?:\s+\S+)?)'

        # 带端口的规则: [seq] <action> <protocol> <src> [src_port] <dst> [dst_port] [options]
        rule_port_pattern = re.compile(
            r'^(?:(?P<seq>\d+)\s+)?(?P<action>permit|deny)\s+(?P<protocol>\S+)\s+'
            r'(?P<src>' + addr + r')\s*(?P<src_port>' + port + r')?\s+'
            r'(?P<dst>' + addr + r')\s*(?P<dst_port>' + port + r')?'
            r'(?P<options>.*)$',
            re.IGNORECASE
        )

        # 无端口的规则: [seq] <action> <protocol> <src> <dst> [options]
        rule_pattern = re.compile(
            r'^(?:(?P<seq>\d+)\s+)?(?P<action>permit|deny)\s+(?P<protocol>\S+)\s+'
            r'(?P<src>' + addr + r')\s+'
            r'(?P<dst>' + addr + r')\s*'
            r'(?P<options>.*)$',
            re.IGNORECASE
        )

        # 按 (标识, 地址族) 分组存储
        access_lists_dict = {}

        if self.config_tree:
            for node in self.config_tree:
                header = header_pattern.match(node['content'].strip())
                if not header:
                    continue

                ident = header.group('ident')

                # copp 开头的 ACL 是系统策略, 直接跳过（含 ipv6）
                if ident.lower().startswith(IGNORED_ACL_PREFIXES):
                    logger.debug(f"[{self.vendor}] 跳过系统 ACL: {ident}")
                    continue

                kind = header.group('kind')
                acl_type = 'ipv6' if header.group('family').lower() == 'ipv6' else 'ipv4'
                if kind:
                    acl_kind = 'basic' if kind.lower() == 'standard' else 'advanced'
                else:
                    acl_kind = 'advanced' if ident.isdigit() else 'named'

                key = (ident, acl_type)
                if key not in access_lists_dict:
                    access_lists_dict[key] = {
                        'acl_name': ident,
                        'acl_number': int(ident) if ident.isdigit() else None,
                        'acl_type': acl_type,
                        'acl_kind': acl_kind,
                        'entries': []
                    }

                for child in node['child']:
                    content = child['content'].strip()

                    # 行尾 ! 之后是描述, 只取规则部分
                    if '!' in content:
                        content = content.split('!', 1)[0].strip()
                    if not content:
                        continue

                    # 块内非规则行: statistics per-entry / remark 等
                    if content.split()[0].lower() in (
                        'statistics', 'no', 'remark', 'description', 'counters', 'evaluate'
                    ):
                        continue

                    rule = None
                    for pattern in (rule_port_pattern, rule_pattern):
                        candidate = pattern.match(content)
                        if candidate:
                            # 端口位置解析不出来说明该规则无端口
                            if candidate.groupdict().get('src_port') is not None and \
                                    self._parse_port(candidate.group('src_port')) is None:
                                continue
                            if candidate.groupdict().get('dst_port') is not None and \
                                    self._parse_port(candidate.group('dst_port')) is None:
                                continue
                            rule = candidate
                            break

                    if not rule:
                        logger.debug(f"[{self.vendor}] 忽略无法识别的行: {content}")
                        continue

                    src = self._parse_addr(rule.group('src'))
                    dst = self._parse_addr(rule.group('dst'))

                    # 目的地址省略时补 any
                    if src is not None and dst is None and not rule.group('dst'):
                        dst = {'type': 'any'}
                    if src is None or dst is None:
                        logger.debug(f"[{self.vendor}] 忽略地址不全的规则: {content}")
                        continue

                    options = {}
                    if 'established' in (rule.group('options') or '').lower():
                        options['established'] = True

                    seq = int(rule.group('seq')) if rule.group('seq') else None
                    if seq is None:
                        existing_seqs = [e.seq for e in access_lists_dict[key]['entries']]
                        seq = max(existing_seqs) + 10 if existing_seqs else 10

                    access_lists_dict[key]['entries'].append(AclEntry(
                        seq=seq,
                        action=Action.PERMIT if rule.group('action').lower() == 'permit' else Action.DENY,
                        protocol=rule.group('protocol').lower(),
                        src=src,
                        src_port=self._parse_port(rule.group('src_port')),
                        dst=dst,
                        dst_port=self._parse_port(rule.group('dst_port')),
                        options=options
                    ))

        # 转换为 AclConfig 列表
        access_lists = []
        for data in access_lists_dict.values():
            data['entries'].sort(key=lambda e: e.seq)
            access_lists.append(AclConfig(
                acl_name=data['acl_name'],
                entries=data['entries'],
                acl_number=data['acl_number'],
                acl_type=data['acl_type'],
                acl_kind=data['acl_kind']
            ))

        logger.info(f"[{self.vendor}] 解析到 {len(access_lists)} 个 ACL")
        for acl in access_lists:
            logger.debug(f"  - {acl.acl_name}({acl.acl_type}): {len(acl.entries)} 条规则")

        return access_lists

    def parse_address_groups(self) -> List[AddrGroupConfig]:
        """
        解析 Cisco 地址组（地址簿）

        Cisco 格式示例:
        object-group ip address og_ip_relay
          10 host 10.33.144.129
          20 host 10.32.19.83
        object-group ip address og_ip_idcnet
          10 10.32.0.0/14
          20 10.36.0.0/16
        object-group ipv6 address og_ip_v6
          10 host 2408:8000::1

        条目只有两种写法: host <IP> 与 <IP>/<LEN>，均归一化为 CIDR

        Returns:
            List[AddrGroupConfig]: 地址组配置列表（ACL 规则内以 addrgroup 名称引用）
        """
        header_pattern = re.compile(
            r'^object-group\s+(?P<family>ipv6|ip)\s+address\s+(?P<name>\S+)$',
            re.IGNORECASE
        )

        # [seq] host x | [seq] x/n
        entry_pattern = re.compile(
            r'^(?:\d+\s+)?'
            r'(?:(?P<host>host)\s+)?'
            r'(?P<value>\S+)$',
            re.IGNORECASE
        )

        def normalize_net(cidr: str) -> str:
            """x/n 归一化为网络号/长度, 如 10.32.1.5/14 -> 10.32.0.0/14"""
            net = ipaddress.ip_network(cidr, strict=False)
            return f'{net.network_address}/{net.prefixlen}'

        groups = []
        if not self.config_tree:
            return groups

        for node in self.config_tree:
            header = header_pattern.match(node['content'].strip())
            if not header:
                continue

            name = header.group('name')
            addr_type = 'ipv6' if header.group('family').lower() == 'ipv6' else 'ipv4'
            k = 0
            entries = []

            for child in node['child']:
                content = child['content'].strip()
                if '!' in content:
                    content = content.split('!', 1)[0].strip()
                if not content:
                    continue

                k += 1
                seq = int(content.split()[0]) if content.split()[0].isdigit() else k * 10

                match = entry_pattern.match(content)
                if not match:
                    logger.debug(f"[{self.vendor}] 忽略无法识别的地址组行: {content}")
                    continue

                literal = match.group('value')

                try:
                    if match.group('host'):
                        kind = 'host'
                        addresses = [f'{literal}/{"128" if ":" in literal else "32"}']
                    else:
                        kind = 'network'
                        addresses = [normalize_net(literal)]
                except ValueError as err:
                    logger.debug(f"[{self.vendor}] 地址组 {name} 行解析失败({err}): {content}")
                    continue

                entries.append(AddrGroupEntry(
                    seq=seq, kind=kind, addresses=addresses, description=None
                ))

            entries.sort(key=lambda e: e.seq)
            groups.append(AddrGroupConfig(name=name, entries=entries, addr_type=addr_type))

        logger.info(f"[{self.vendor}] 解析到 {len(groups)} 个地址组")
        for group in groups:
            logger.debug(f"  - {group.name}({group.addr_type}): {len(group.entries)} 条")

        return groups

    def parse_port_groups(self) -> List[PortGroupConfig]:
        """
        解析 Cisco 端口组（端口簿）

        Cisco 格式示例:
        object-group ip port og_port_bigdata_proxy
          10 eq 7777
          20 eq 8042
        object-group ip port og_port_web
          10 range 8080 8090
          20 gt 1024
          30 neq 80

        条目为 <op> <端口号>，op 取 eq / gt / lt / neq / range（range 带两个端口号）

        Returns:
            List[PortGroupConfig]: 端口组配置列表（ACL 规则内以 portgroup 名称引用）
        """
        header_pattern = re.compile(
            r'^object-group\s+\S+\s+port\s+(?P<name>\S+)$',
            re.IGNORECASE
        )

        # eq 80 / gt 1024 / lt 1024 / neq 80 / range 80 90
        entry_pattern = re.compile(
            r'^(?:\d+\s+)?'
            r'(?P<op>eq|gt|lt|neq|range)\s+'
            r'(?P<value>.+)$',
            re.IGNORECASE
        )

        groups = []
        if not self.config_tree:
            return groups

        for node in self.config_tree:
            header = header_pattern.match(node['content'].strip())
            if not header:
                continue

            name = header.group('name')
            k = 0
            entries = []

            for child in node['child']:
                content = child['content'].strip()
                if '!' in content:
                    content = content.split('!', 1)[0].strip()
                if not content:
                    continue

                k += 1
                seq = int(content.split()[0]) if content.split()[0].isdigit() else k * 10

                match = entry_pattern.match(content)
                if not match:
                    logger.debug(f"[{self.vendor}] 忽略无法识别的端口组行: {content}")
                    continue

                op = match.group('op').lower()
                tokens = match.group('value').split()

                # 端口值, 数字存整数, 别名(domain/www)存字符串
                try:
                    ports = [int(t) if t.isdigit() else t for t in tokens[:2 if op == 'range' else 1]]
                except (ValueError, IndexError) as err:
                    logger.debug(f"[{self.vendor}] 端口组 {name} 行解析失败({err}): {content}")
                    continue

                entries.append(PortGroupEntry(
                    seq=seq, op=op, ports=ports, description=None
                ))

            entries.sort(key=lambda e: e.seq)
            groups.append(PortGroupConfig(name=name, entries=entries))

        logger.info(f"[{self.vendor}] 解析到 {len(groups)} 个端口组")
        for group in groups:
            logger.debug(f"  - {group.name}: {len(group.entries)} 条")

        return groups


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    cisco_config = '''
object-group ip address og_ip_idcnet
  10 10.32.0.0/14 
  20 10.36.0.0/16 
  30 10.16.0.0/16 
  40 10.128.0.0/12 
object-group ip address og_ip_relay
  10 host 10.33.144.129
  20 host 10.32.19.83
  30 host 10.33.102.136
  40 host 10.39.128.29
  50 host 10.39.128.30
  60 host 10.33.144.157
object-group ip address og_ip_security_source
  10 host 172.24.33.97
  20 host 172.24.33.126
object-group ip address og_ip_vdds
  10 host 10.39.160.8
object-group ip port og_port_bigdata_proxy
  10 eq 7777
  20 eq 8042
  30 eq 8080
  40 eq 8088
  50 eq 16010
  60 eq 16030
  70 eq 18080
  80 eq 18088
  90 eq 19888
  100 eq 50070
  110 eq 10002
object-group ip port og_port_db
  10 eq 27017
object-group ip port og_port_deny
  10 eq 23
  20 eq 22
  30 eq 2181
object-group ip port og_port_oa
  10 range 8080 8090
  20 eq domain
  30 gt 1024
  40 lt 1024
  50 neq 80
ip access-list 2999
  10 permit ip 10.143.170.0/24 any
  100 permit ip 10.33.103.136/32 any
  10000 deny ip any any
ip access-list acl_office_to_idc
  statistics per-entry
  100 permit tcp any any established
  200 permit tcp any addrgroup og_ip_idcnet portgroup og_port_per
  210 permit tcp any addrgroup og_ip_relay eq 22
  340 permit tcp any addrgroup og_ip_bigdata_proxy portgroup og_port_bigdata_proxy
  900 deny tcp any any portgroup og_port_deny
  910 deny tcp any addrgroup og_ip_idcnet
  1000 permit ip any any
'''

    # 测试解析器
    from lib_config import get_parser
    import json

    print("=" * 60)
    print("Cisco 配置解析测试")
    print("=" * 60)

    # 获取解析器
    parser = get_parser('cisco_nx', cisco_config)
    print(f"\n{parser}\n")

    # 解析 ACL / 地址组 / 端口组
    result = parser.parse(sections=['access_lists', 'address_groups', 'port_groups'])

    print("\n解析结果:")
    print(f"  ACL 数量: {len(result.access_lists)}")
    print(f"  地址组数量: {len(result.address_groups)}")
    print(f"  端口组数量: {len(result.port_groups)}")
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    for acl in result.access_lists:
        print(f"\n  ACL: {acl.acl_name}  type={acl.acl_type}  kind={acl.acl_kind}  number={acl.acl_number}")
        print(f"    规则数: {len(acl.entries)}")
        for entry in acl.entries:
            print(f"      {json.dumps(entry.to_dict(), ensure_ascii=False)}")

    for group in result.address_groups:
        print(f"\n  地址组: {group.name}  type={group.addr_type}")
        for entry in group.entries:
            print(f"      {json.dumps(entry.to_dict(), ensure_ascii=False)}")

    for group in result.port_groups:
        print(f"\n  端口组: {group.name}")
        for entry in group.entries:
            print(f"      {json.dumps(entry.to_dict(), ensure_ascii=False)}")
