"""
Cisco 配置编码器

将标准化模型转换为 Cisco NX-OS/IOS/IOS-XR 配置文本
"""
import logging
from typing import Any, Dict, List, Optional
from lib_config.encoders.encode_base import BaseEncoder, register_encoder
from lib_config.models import (
    PrefixListConfig,
    PrefixListEntry,
    AclConfig,
    AclEntry,
    AddrGroupConfig,
    AddrGroupEntry,
    PortGroupConfig,
    PortGroupEntry,
    Action,
)

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
        self.available_sections = {
            'prefix_lists',
            'access_lists',
            'address_groups',
            'port_groups',
        }

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

    # ==================== 地址 / 端口文本渲染 ====================

    def _encode_addr(self, spec: Optional[Dict[str, Any]]) -> str:
        """
        渲染 AddressSpec 为 Cisco 地址文本（与 parser._parse_addr 互逆）

        any / host x / addrgroup x / x/n
        """
        if not spec:
            return 'any'

        addr_type = spec.get('type')

        if addr_type == 'addrgroup':
            return f"addrgroup {spec.get('name')}"

        if addr_type == 'any':
            return 'any'

        address = spec.get('address', '')

        if addr_type == 'host':
            # 归一化的单主机带 /32 /128, Cisco 写法去掉长度
            return f"host {address.split('/')[0]}"

        return address

    def _encode_port(self, spec: Optional[Dict[str, Any]]) -> str:
        """
        渲染 PortSpec 为 Cisco 端口文本（与 parser._parse_port 互逆）

        portgroup x / <op> <端口号> [<端口号>]
        """
        if not spec:
            return ''

        if spec.get('type') == 'portgroup':
            return f"portgroup {spec.get('name')}"

        ports = " ".join(str(p) for p in spec.get('ports') or [])

        return f"{spec.get('op')} {ports}".strip()

    # ==================== ACL ====================

    def encode_access_lists(self, access_lists: List[AclConfig], operation: str = 'add') -> str:
        """
        编码 ACL 为 Cisco 配置

        Cisco 格式:
        ip access-list <标识>
          <seq> <action> <protocol> <src> [src_port] <dst> [dst_port]
        删除格式:
        ip access-list <标识>
          no <seq>

        Args:
            access_lists: ACL 模型列表
            operation: 操作类型，'add' 表示添加配置，'delete' 表示删除配置

        Returns:
            str: Cisco 配置文本
        """
        config_lines = []

        for acl in access_lists:
            # 删除同样需要进入 ACL 上下文, 块内 no <seq>
            config_lines.append(self._encode_acl_header(acl))

            for entry in sorted(acl.entries, key=lambda e: e.seq):
                config_lines.extend(self._encode_acl_entry(entry, operation))

            config_lines.append("")

        if config_lines and config_lines[-1] == "":
            config_lines.pop()

        return "\n".join(config_lines)

    def _encode_acl_header(self, acl: AclConfig) -> str:
        """编码 ACL 块头"""
        return f"{'ipv6' if acl.acl_type == 'ipv6' else 'ip'} access-list {acl.acl_name}"

    def _encode_acl_entry(self, entry: AclEntry, operation: str = 'add') -> List[str]:
        """
        编码单条 ACL 规则

        Args:
            entry: 规则条目
            operation: 操作类型，'add' 或 'delete'
        """
        if operation == 'delete':
            # 删除操作: 块内 no <seq>, 块上下文由调用方输出
            return [f"  no {entry.seq}"]

        action = "permit" if entry.action == Action.PERMIT else "deny"
        line = (
            f"  {entry.seq} {action} {entry.protocol} "
            f"{self._encode_addr(entry.src)}"
        )

        # 源端口跟在源地址之后
        src_port = self._encode_port(entry.src_port)
        if src_port:
            line += f" {src_port}"

        line += f" {self._encode_addr(entry.dst)}"

        # 目的端口跟在目的地址之后
        dst_port = self._encode_port(entry.dst_port)
        if dst_port:
            line += f" {dst_port}"

        # 规则选项（只写 true 键）
        for option, value in (entry.options or {}).items():
            if value:
                line += f" {option}"

        return [line]

    # ==================== 地址组（地址簿）====================

    def encode_address_groups(self, address_groups: List[AddrGroupConfig], operation: str = 'add') -> str:
        """
        编码地址组为 Cisco 配置

        Cisco 格式:
        object-group ip address <组名>
          <seq> host <IP>
          <seq> <IP>/<LEN>
        删除格式:
        object-group ip address <组名>
          no <seq>

        Args:
            address_groups: 地址组模型列表
            operation: 操作类型，'add' 表示添加配置，'delete' 表示删除配置

        Returns:
            str: Cisco 配置文本
        """
        config_lines = []

        for group in address_groups:
            # 对象组的删除必须先进入组上下文, 组内执行 no <seq>
            config_lines.append(self._encode_addr_group_header(group))

            for entry in sorted(group.entries, key=lambda e: e.seq):
                config_lines.extend(self._encode_addr_group_entry(entry, operation))

            config_lines.append("")

        if config_lines and config_lines[-1] == "":
            config_lines.pop()

        return "\n".join(config_lines)

    def _encode_addr_group_header(self, group: AddrGroupConfig) -> str:
        """编码地址组块头"""
        family = 'ipv6' if group.addr_type == 'ipv6' else 'ip'
        return f"object-group {family} address {group.name}"

    def _encode_addr_group_entry(self, entry: AddrGroupEntry, operation: str = 'add') -> List[str]:
        """
        编码单个地址组条目

        条目地址可多个, 分组写法上每行一个; 一个条目对应多行时首行带 seq, 后续行省略

        Args:
            entry: 地址组条目
            operation: 操作类型，'add' 或 'delete'
        """
        if operation == 'delete':
            # 删除操作: 组内 no <seq>, 组上下文由调用方输出
            return [f"  no {entry.seq}"]

        lines = []
        for index, address in enumerate(entry.addresses):
            # 首行带 seq, 后续行省略
            prefix = f"  {entry.seq} " if index == 0 else "  "

            if entry.kind == 'host':
                # host 写法去掉归一化的 /32 /128
                body = f"host {address.split('/')[0]}"
            else:
                body = address

            lines.append(prefix + body)

        # 如果有描述，添加到最后一行行尾
        if lines and entry.description:
            lines[-1] += f"  ! {entry.description}"

        return lines

    # ==================== 端口组（端口簿）====================

    def encode_port_groups(self, port_groups: List[PortGroupConfig], operation: str = 'add') -> str:
        """
        编码端口组为 Cisco 配置

        Cisco 格式:
        object-group ip port <组名>
          <seq> eq 80
          <seq> range 8080 8090
        删除格式:
        object-group ip port <组名>
          no <seq>

        Args:
            port_groups: 端口组模型列表
            operation: 操作类型，'add' 表示添加配置，'delete' 表示删除配置

        Returns:
            str: Cisco 配置文本
        """
        config_lines = []

        for group in port_groups:
            # 对象组的删除必须先进入组上下文, 组内执行 no <seq>
            config_lines.append(self._encode_port_group_header(group))

            for entry in sorted(group.entries, key=lambda e: e.seq):
                config_lines.extend(self._encode_port_group_entry(entry, operation))

            config_lines.append("")

        if config_lines and config_lines[-1] == "":
            config_lines.pop()

        return "\n".join(config_lines)

    def _encode_port_group_header(self, group: PortGroupConfig) -> str:
        """编码端口组块头"""
        return f"object-group ip port {group.name}"

    def _encode_port_group_entry(self, entry: PortGroupEntry, operation: str = 'add') -> List[str]:
        """
        编码单个端口组条目

        Args:
            entry: 端口组条目
            operation: 操作类型，'add' 或 'delete'
        """
        if operation == 'delete':
            # 删除操作: 组内 no <seq>, 组上下文由调用方输出
            return [f"  no {entry.seq}"]

        ports = " ".join(str(p) for p in entry.ports or [])
        line = f"  {entry.seq} {entry.op} {ports}".rstrip()

        if entry.description:
            line += f"  ! {entry.description}"

        return [line]

if __name__ == '__main__':
    import json

    dat = '{"prefix_lists": [], "access_lists": [{"acl_name": "2999", "acl_number": 2999, "acl_type": "ipv4", "acl_kind": "advanced", "entries": [{"seq": 10, "action": "permit", "protocol": "ip", "src": {"type": "network", "address": "10.143.170.0/24"}, "src_port": null, "dst": {"type": "any"}, "dst_port": null, "options": {}}, {"seq": 100, "action": "permit", "protocol": "ip", "src": {"type": "host", "address": "10.33.103.136/32"}, "src_port": null, "dst": {"type": "any"}, "dst_port": null, "options": {}}, {"seq": 10000, "action": "deny", "protocol": "ip", "src": {"type": "any"}, "src_port": null, "dst": {"type": "any"}, "dst_port": null, "options": {}}]}, {"acl_name": "acl_office_to_idc", "acl_number": null, "acl_type": "ipv4", "acl_kind": "named", "entries": [{"seq": 100, "action": "permit", "protocol": "tcp", "src": {"type": "any"}, "src_port": null, "dst": {"type": "any"}, "dst_port": null, "options": {"established": true}}, {"seq": 200, "action": "permit", "protocol": "tcp", "src": {"type": "any"}, "src_port": null, "dst": {"type": "addrgroup", "name": "og_ip_idcnet"}, "dst_port": {"type": "portgroup", "name": "og_port_per"}, "options": {}}, {"seq": 210, "action": "permit", "protocol": "tcp", "src": {"type": "any"}, "src_port": null, "dst": {"type": "addrgroup", "name": "og_ip_relay"}, "dst_port": {"type": "direct", "op": "eq", "ports": [22]}, "options": {}}, {"seq": 340, "action": "permit", "protocol": "tcp", "src": {"type": "any"}, "src_port": null, "dst": {"type": "addrgroup", "name": "og_ip_bigdata_proxy"}, "dst_port": {"type": "portgroup", "name": "og_port_bigdata_proxy"}, "options": {}}, {"seq": 900, "action": "deny", "protocol": "tcp", "src": {"type": "any"}, "src_port": null, "dst": {"type": "any"}, "dst_port": {"type": "portgroup", "name": "og_port_deny"}, "options": {}}, {"seq": 910, "action": "deny", "protocol": "tcp", "src": {"type": "any"}, "src_port": null, "dst": {"type": "addrgroup", "name": "og_ip_idcnet"}, "dst_port": null, "options": {}}, {"seq": 1000, "action": "permit", "protocol": "ip", "src": {"type": "any"}, "src_port": null, "dst": {"type": "any"}, "dst_port": null, "options": {}}]}], "address_groups": [{"name": "og_ip_idcnet", "addr_type": "ipv4", "description": null, "entries": [{"seq": 10, "kind": "network", "addresses": ["10.32.0.0/14"], "description": null}, {"seq": 20, "kind": "network", "addresses": ["10.36.0.0/16"], "description": null}, {"seq": 30, "kind": "network", "addresses": ["10.16.0.0/16"], "description": null}, {"seq": 40, "kind": "network", "addresses": ["10.128.0.0/12"], "description": null}]}, {"name": "og_ip_relay", "addr_type": "ipv4", "description": null, "entries": [{"seq": 10, "kind": "host", "addresses": ["10.33.144.129/32"], "description": null}, {"seq": 20, "kind": "host", "addresses": ["10.32.19.83/32"], "description": null}, {"seq": 30, "kind": "host", "addresses": ["10.33.102.136/32"], "description": null}, {"seq": 40, "kind": "host", "addresses": ["10.39.128.29/32"], "description": null}, {"seq": 50, "kind": "host", "addresses": ["10.39.128.30/32"], "description": null}, {"seq": 60, "kind": "host", "addresses": ["10.33.144.157/32"], "description": null}]}, {"name": "og_ip_security_source", "addr_type": "ipv4", "description": null, "entries": [{"seq": 10, "kind": "host", "addresses": ["172.24.33.97/32"], "description": null}, {"seq": 20, "kind": "host", "addresses": ["172.24.33.126/32"], "description": null}]}, {"name": "og_ip_vdds", "addr_type": "ipv4", "description": null, "entries": [{"seq": 10, "kind": "host", "addresses": ["10.39.160.8/32"], "description": null}]}], "port_groups": [{"name": "og_port_bigdata_proxy", "description": null, "entries": [{"seq": 10, "op": "eq", "ports": [7777], "description": null}, {"seq": 20, "op": "eq", "ports": [8042], "description": null}, {"seq": 30, "op": "eq", "ports": [8080], "description": null}, {"seq": 40, "op": "eq", "ports": [8088], "description": null}, {"seq": 50, "op": "eq", "ports": [16010], "description": null}, {"seq": 60, "op": "eq", "ports": [16030], "description": null}, {"seq": 70, "op": "eq", "ports": [18080], "description": null}, {"seq": 80, "op": "eq", "ports": [18088], "description": null}, {"seq": 90, "op": "eq", "ports": [19888], "description": null}, {"seq": 100, "op": "eq", "ports": [50070], "description": null}, {"seq": 110, "op": "eq", "ports": [10002], "description": null}]}, {"name": "og_port_db", "description": null, "entries": [{"seq": 10, "op": "eq", "ports": [27017], "description": null}]}, {"name": "og_port_deny", "description": null, "entries": [{"seq": 10, "op": "eq", "ports": [23], "description": null}, {"seq": 20, "op": "eq", "ports": [22], "description": null}, {"seq": 30, "op": "eq", "ports": [2181], "description": null}]}, {"name": "og_port_oa", "description": null, "entries": [{"seq": 10, "op": "range", "ports": [8080, 8090], "description": null}, {"seq": 20, "op": "eq", "ports": ["domain"], "description": null}, {"seq": 30, "op": "gt", "ports": [1024], "description": null}, {"seq": 40, "op": "lt", "ports": [1024], "description": null}, {"seq": 50, "op": "neq", "ports": [80], "description": null}]}]}'

    json_dat = json.loads(dat)





    a = CiscoEncoder("cisco_nx")

    # 段级方法收模型对象, 字典需先 from_dict 转换（encode() 主入口内部会做这一步）
    res = a.encode_access_lists([AclConfig.from_dict(d) for d in json_dat['access_lists']], 'delete')
    print(res)

    print("=" * 60)
    print(a.encode_address_groups([AddrGroupConfig.from_dict(d) for d in json_dat['address_groups']], 'add'))

    print("=" * 60)
    print(a.encode_port_groups([PortGroupConfig.from_dict(d) for d in json_dat['port_groups']], 'add'))

    print("=" * 60)
    print("--- delete ---")
    print(a.encode_port_groups([PortGroupConfig.from_dict(d) for d in json_dat['port_groups']], 'delete'))