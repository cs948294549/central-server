"""
Cisco 配置解析器

支持解析 Cisco NX-OS / IOS / IOS-XR 设备的策略配置
"""

import re
import logging
from typing import Any, Dict, List, Optional
from lib_config.parsers.parser_base import BaseParser, register_parser
from lib_config.models import (
    PrefixListConfig,
    PrefixListEntry,
    AclConfig,
    AclEntry,
    Action
)
from utils.ipaddr import wildcard2length, length2netmask, getNet

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
            'prefix_lists',   # 地址前缀列表
            'access_lists',   # 访问控制列表
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

        def parse_addr(text: Optional[str]) -> Optional[Dict[str, Any]]:
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

        def parse_port(text: Optional[str]) -> Optional[Dict[str, Any]]:
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

        # 按 (标识, 地址族) 分组存储
        access_lists_dict = {}

        if self.config_tree:
            for node in self.config_tree:
                header = header_pattern.match(node['content'].strip())
                if not header:
                    continue

                ident = header.group('ident')
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
                                    parse_port(candidate.group('src_port')) is None:
                                continue
                            if candidate.groupdict().get('dst_port') is not None and \
                                    parse_port(candidate.group('dst_port')) is None:
                                continue
                            rule = candidate
                            break

                    if not rule:
                        logger.debug(f"[{self.vendor}] 忽略无法识别的行: {content}")
                        continue

                    src = parse_addr(rule.group('src'))
                    dst = parse_addr(rule.group('dst'))

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
                        src_port=parse_port(rule.group('src_port')),
                        dst=dst,
                        dst_port=parse_port(rule.group('dst_port')),
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


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Cisco 配置示例
    cisco_config = """
ip access-list 2999
  10 permit ip 10.143.170.0/24 any 
  100 permit ip 10.33.103.136/32 any 
  500 permit ip 10.33.130.3/32 any 
  510 permit ip 10.33.130.7/32 any 
  520 permit ip 10.33.130.4/32 any 
  530 permit ip 10.33.130.6/32 any 
  540 permit ip 10.33.130.8/32 any 
  550 permit ip 10.33.162.163/32 any 
  560 permit ip 10.33.162.164/32 any 
  570 permit ip 10.33.162.161/32 any 
  580 permit ip 10.33.194.150/32 any 
  590 permit ip 10.33.194.3/32 any 
  600 permit ip 10.33.130.17/32 any 
  610 permit ip 10.32.228.179/32 any 
  620 permit ip 10.32.0.164/32 any 
  630 permit ip 10.32.0.134/32 any 
  640 permit ip 10.33.114.19/32 any 
  650 permit ip 10.32.116.124/32 any 
  660 permit ip 10.32.115.190/32 any 
  10000 deny ip any any 
ipv6 access-list 3999
  10000 deny ipv6 any any 
ip access-list acl_office_to_idc
  statistics per-entry
  100 permit tcp any any established 
  110 permit icmp any any 
  200 permit tcp any addrgroup og_ip_idcnet portgroup og_port_per 
  210 permit ip any addrgroup og_ip_ad_idc 
  230 permit tcp any 10.37.0.0/16 eq 2181 
  240 permit tcp any addrgroup op_ip_oa_zhiyuan portgroup og_port_oa_zhiyuan 
  260 permit tcp any addrgroup og_ip_relay eq 22 
  280 permit tcp any addrgroup og_ip_git eq 60022 
  281 permit tcp any 10.19.46.19/32 eq 8099 
  290 permit tcp any 10.8.83.96/32 portgroup og_port_payftp 
  320 permit ip addrgroup og_ip_ad_office addrgroup og_ip_ad_idc 
  330 permit tcp addrgroup og_ip_ob_relay addrgroup og_ip_idcnet eq 3389 
  340 permit tcp any addrgroup og_ip_bigdata_proxy portgroup og_port_bigdata_proxy 
  370 permit tcp any addrgroup og_ip_jindie portgroup og_port_jindie 
  380 permit tcp any addrgroup og_ip_oa portgroup og_port_oa 
  400 permit tcp addrgroup og_ip_ob_relay addrgroup og_ip_idcnet range 5900 5930 
  420 permit tcp any addrgroup og_ip_vdds eq 3308 
  430 permit tcp addrgroup og_ip_ob_relay addrgroup og_ip_jindie eq 139 
  440 permit tcp addrgroup og_ip_ob_relay addrgroup og_ip_jindie eq 445 
  450 permit ip any 10.32.226.210/32 
  500 permit ip any 10.18.24.12/32 
  510 permit ip any 10.32.192.148/32 
  520 permit ip 172.24.12.14/32 any 
  550 permit udp any addrgroup og_ip_dns_24h eq domain 
  560 permit tcp any addrgroup og_ip_dns_24h eq domain 
  600 permit tcp addrgroup og_ip_ob_relay 10.18.8.8/32 eq 1433 
  610 permit tcp addrgroup og_ip_ob_relay 10.18.8.3/32 eq 1433 
  615 permit tcp any 10.18.24.49/32 eq 27017 
  620 permit tcp any 10.32.113.34/32 eq 4430 
  630 permit ip any 172.31.3.100/32 
  640 permit tcp any 10.19.47.6/32 eq 56666 
  645 permit tcp any 10.32.88.201/32 eq 9210 
  655 permit tcp any 10.19.19.73/32 eq 9092 
  660 permit ip any 10.37.2.106/32 
  661 permit ip any 10.37.12.84/32 
  675 permit tcp any 10.34.131.176/32 range 60001 60099 
  720 permit tcp any 10.19.46.53/32 eq 3389 
  725 permit tcp any 10.33.160.148/32 eq 222 
  730 permit tcp any 10.26.0.128/28 range 18000 19000 
  900 deny tcp any any portgroup og_port_deny 
  910 deny tcp any addrgroup og_ip_idcnet 
  1000 permit ip any any 
ip access-list copp-system-acl-eigrp
  10 permit eigrp any 224.0.0.10/32 
ipv6 access-list copp-system-acl-eigrp6
  10 permit eigrp any ff02::a/128 
ip access-list copp-system-acl-icmp
  10 permit icmp any any 
    """
    cisco_config='''
ip access-list 2999
  10 permit ip 10.143.170.0/24 any 
  100 permit ip 10.33.103.136/32 any 
  500 permit ip 10.33.130.3/32 any 
  510 permit ip 10.33.130.7/32 any 
  520 permit ip 10.33.130.4/32 any 
  530 permit ip 10.33.130.6/32 any 
  540 permit ip 10.33.130.8/32 any 
  550 permit ip 10.33.162.163/32 any 
  560 permit ip 10.33.162.164/32 any 
  570 permit ip 10.33.162.161/32 any 
  580 permit ip 10.33.194.150/32 any 
  590 permit ip 10.33.194.3/32 any 
  600 permit ip 10.33.130.17/32 any 
  610 permit ip 10.32.228.179/32 any 
  620 permit ip 10.32.0.164/32 any 
  630 permit ip 10.32.0.134/32 any 
  640 permit ip 10.33.114.19/32 any 
  650 permit ip 10.32.116.124/32 any 
  660 permit ip 10.32.115.190/32 any 
  10000 deny ip any any 
ipv6 access-list 3999
  10000 deny ipv6 any any 
ip access-list QOS-test
  10 permit ip 172.25.40.176/32 10.0.0.0/8 
  20 permit ip 172.25.40.176/32 172.16.0.0/12 
  30 permit ip 172.25.40.176/32 192.168.0.0/16 
ip access-list QOS-test-all
  10 permit ip 172.25.44.111/32 172.25.200.202/32 
ip access-list acl_office_to_idc
  statistics per-entry
  10 permit ip any 10.32.192.148/32 
  90 permit udp any any 
  100 permit tcp any any established 
  110 permit icmp any any 
  120 permit tcp any addrgroup og_ip_idcnet portgroup og_port_per 
  140 permit ip any 172.17.5.101/32 
  150 permit ip any 172.17.5.102/32 
  160 permit ip any 10.32.0.133/32 
  165 permit ip any 172.26.3.100/32 
  170 permit tcp any 10.33.19.17/32 eq 60022 
  171 permit tcp any 10.33.19.20/32 eq 60022 
  210 permit tcp any addrgroup og_ip_relay eq 22 
  230 permit tcp any 10.37.0.0/16 eq 2181 
  231 permit tcp any 10.37.0.0/16 eq 8081 
  240 permit tcp any addrgroup og_ip_git eq 60022 
  260 permit tcp any 10.8.83.96/32 portgroup og_port_payftp 
  270 permit tcp any 10.8.80.144/32 eq 8082 
  280 permit tcp any 10.33.144.131/32 eq 65231 
  290 permit ip 172.25.3.100/32 addrgroup og_ip_ad_idc 
  300 permit ip 172.25.7.253/32 addrgroup og_ip_ad_idc 
  305 permit ip 172.25.7.254/32 addrgroup og_ip_ad_idc 
  306 permit ip 172.31.3.100/32 addrgroup og_ip_ad_idc 
  310 permit tcp any addrgroup og_ip_bigdata_proxy portgroup og_port_bigdata_proxy 
  330 permit tcp addrgroup og_ip_zeus_office addrgroup og_ip_zeus_idc eq 22 
  360 permit tcp any addrgroup og_ip_jindie portgroup og_port_jindie 
  410 permit tcp any addrgroup og_ip_vdds eq 3308 
  450 permit ip any 10.32.226.210/32 
  470 permit tcp any 10.19.47.4/32 eq 8864 
  480 permit tcp any 10.32.208.163/32 eq 8888 
  490 permit tcp any 10.19.47.13/32 eq 3306 
  491 remark oa_daily_db_wangzhicheng
  495 permit tcp any 10.19.46.19/32 eq 8099 
  496 permit tcp any 10.19.46.19/32 eq 8864 
  497 remark oa_daily_server_zhangji
  498 permit tcp any 10.19.47.11/32 eq 8864 
  499 remark oa_prod_server_zhangji
  500 permit ip any 10.18.24.12/32 
  510 permit tcp any 10.33.96.171/32 eq 9200 
  520 permit tcp any 10.32.229.17/32 eq 4242 
  560 permit udp any addrgroup og_ip_dns_24h eq domain 
  570 permit tcp any addrgroup og_ip_dns_24h eq domain 
  580 permit tcp any 10.39.160.14/32 eq 1883 
  581 permit tcp any 10.39.160.21/32 eq 1883 
  582 permit tcp any 10.39.160.18/32 eq 10000 
  583 permit tcp any 10.39.160.18/32 range 10002 10004 
  584 permit tcp any 10.39.160.19/32 eq 10000 
  585 permit tcp any 10.39.160.19/32 range 10002 10004 
  600 permit tcp any 10.129.18.128/32 eq 58901 
  610 permit tcp any 10.32.0.168/32 eq 8089 
  611 remark rejie-sdwan
  612 permit tcp any 10.32.0.168/32 eq 30001 
  613 permit tcp any 10.32.0.168/32 eq 4334 
  615 permit tcp any 10.18.24.49/32 eq 27017 
  616 permit tcp any 10.18.24.46/32 eq 27017 
  617 permit tcp any 10.18.24.29/32 eq 27017 
  618 permit tcp any 10.19.64.9/32 eq 27017 
  619 permit tcp any 10.32.227.130/32 eq 32080 
  620 permit tcp any 10.20.17.12/32 eq 32080 
  633 permit tcp any 10.39.160.24/32 eq 20006 
  635 permit tcp any 10.14.1.10/32 eq 1433 
  640 permit tcp any 10.32.118.72/32 eq 22 
  645 permit tcp any 10.32.88.201/32 eq 9210 
  650 permit tcp any 10.49.16.156/32 eq 20881 
  655 permit ip any 10.20.49.16/32 
  660 permit ip any 10.20.49.8/32 
  665 permit tcp any 10.49.32.207/32 eq www 
  670 permit tcp any 10.32.100.216/32 eq 9621 
  675 permit tcp any 10.34.131.176/32 range 60001 60099 
  700 permit tcp any 10.33.103.136/32 eq 5201 
  710 permit tcp any 10.35.112.170/32 eq 10051 
  715 permit tcp any 10.32.231.131/32 eq 10051 
  720 permit tcp any 10.19.46.53/32 eq 3389 
  730 permit tcp any 10.32.0.168/32 eq 8443 
  740 permit tcp any 10.20.48.17/32 eq 3389 
  750 permit tcp any 10.39.128.80/32 eq 10001 
  751 permit tcp any 10.39.128.80/32 eq 10002 
  755 permit tcp any 10.143.160.162/32 eq 5901 
  760 permit ip any 10.32.98.78/32 
  765 permit tcp any 10.129.32.193/32 range 8081 8085 
  770 permit tcp any 10.39.128.80/32 eq 10005 
  795 permit tcp any 10.14.1.13/32 eq 1433 
  865 permit tcp any 10.48.11.114/32 eq 10000 
  870 permit tcp any 10.26.0.128/28 range 18000 19000 
  880 permit tcp any 10.26.247.0/27 range 8081 8082 
  900 deny tcp any any portgroup og_port_deny 
  910 deny tcp any addrgroup og_ip_idcnet 
  1000 permit ip any any 
policy-map type queuing test
  class type queuing c-out-8q-q7
    bandwidth remaining percent 0
  class type queuing c-out-8q-q6
    bandwidth remaining percent 0
  class type queuing c-out-8q-q5
    bandwidth remaining percent 0
  class type queuing c-out-8q-q4
    bandwidth remaining percent 0
  class type queuing c-out-8q-q3
    bandwidth remaining percent 0
  class type queuing c-out-8q-q2
    bandwidth remaining percent 0
  class type queuing c-out-8q-q1
    bandwidth remaining percent 0
  class type queuing c-out-8q-q-default
    bandwidth remaining percent 100'''

    # 测试解析器
    from lib_config import get_parser
    import json

    print("=" * 60)
    print("Cisco ACL 解析测试")
    print("=" * 60)

    # 获取解析器
    parser = get_parser('cisco_nx', cisco_config)
    print(f"\n{parser}\n")

    # 只解析 ACL
    print("=== parse(sections=['access_lists']) ===")
    result = parser.parse(sections=['access_lists'])

    print(f"\n解析结果:")
    print(f"  ACL 数量: {len(result.access_lists)}")

    for acl in result.access_lists:
        print(f"\n  ACL: {acl.acl_name}  type={acl.acl_type}  kind={acl.acl_kind}  number={acl.acl_number}")
        print(f"    规则数: {len(acl.entries)}")
        for entry in acl.entries:
            print(f"      {json.dumps(entry.to_dict(), ensure_ascii=False)}")
