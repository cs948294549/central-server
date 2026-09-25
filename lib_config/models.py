"""
策略配置标准化模型定义

定义所有策略类型的标准化数据结构，用于：
1. 统一不同厂商的配置格式
2. 计算配置指纹
3. 存储到数据库
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field, asdict


class PolicyType(str, Enum):
    """策略类型"""
    PREFIX_LIST = "prefix_list"
    ACL = "acl"


class Action(str, Enum):
    """动作类型"""
    PERMIT = "permit"
    DENY = "deny"


# ==================== 地址前缀列表模型 ====================

@dataclass
class PrefixListEntry:
    """前缀列表条目"""
    seq: int                          # 序列号
    action: Action                    # 动作: permit/deny
    prefix: str                       # 网络前缀，如 "172.16.0.0/12"
    ge: Optional[int] = None          # greater-equal，前缀长度下限
    le: Optional[int] = None          # less-equal，前缀长度上限
    description: Optional[str] = None # 描述信息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                # 转换枚举值为字符串
                if isinstance(v, Enum):
                    result[k] = v.value
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PrefixListEntry':
        """从字典创建对象"""
        return cls(
            seq=data['seq'],
            action=Action(data['action']),
            prefix=data['prefix'],
            ge=data.get('ge'),
            le=data.get('le'),
            description=data.get('description')
        )


@dataclass
class PrefixListConfig:
    """地址前缀列表标准化配置"""
    name: str                         # 前缀列表名称
    entries: List[PrefixListEntry]    # 条目列表
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            'name': self.name,
            'entries': [entry.to_dict() for entry in self.entries]
        }
        if self.description is not None:
            result['description'] = self.description
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PrefixListConfig':
        """从字典创建对象"""
        return cls(
            name=data['name'],
            entries=[PrefixListEntry.from_dict(e) for e in data['entries']],
            description=data.get('description')
        )

    @property
    def policy_type(self) -> str:
        """策略类型"""
        return PolicyType.PREFIX_LIST


# ==================== ACL 模型 ====================

@dataclass
class AclEntry:
    """ACL 规则条目"""
    seq: int                          # 序列号
    action: Action                    # 动作: permit/deny
    protocol: str                     # ip / tcp / udp / icmp / 数字协议号
    src: Dict[str, Any]               # 源地址 AddressSpec
    src_port: Optional[Dict[str, Any]] = None  # 源端口 PortSpec
    dst: Dict[str, Any] = None        # 目的地址 AddressSpec
    dst_port: Optional[Dict[str, Any]] = None  # 目的端口 PortSpec
    options: Dict[str, Any] = field(default_factory=dict)  # 规则选项（只写 true 键）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（所有键始终存在，不适用写 null）"""
        return {
            'seq': self.seq,
            'action': self.action.value if isinstance(self.action, Enum) else self.action,
            'protocol': self.protocol,
            'src': self.src,
            'src_port': self.src_port,
            'dst': self.dst,
            'dst_port': self.dst_port,
            'options': self.options,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AclEntry':
        """从字典创建对象"""
        return cls(
            seq=data['seq'],
            action=Action(data['action']),
            protocol=data['protocol'],
            src=data['src'],
            src_port=data.get('src_port'),
            dst=data['dst'],
            dst_port=data.get('dst_port'),
            options=data.get('options') or {},
        )


@dataclass
class AclConfig:
    """ACL 标准化配置"""
    acl_name: str                     # ACL 标识名（命名存名字，编号存编号字符串）
    entries: List[AclEntry]           # 规则条目，按 seq 升序
    acl_number: Optional[int] = None  # 仅编号定义时有值
    acl_type: str = 'ipv4'            # ipv4 / ipv6
    acl_kind: Optional[str] = None    # basic / advanced / l2 / custom / named

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（所有键始终存在）"""
        return {
            'acl_name': self.acl_name,
            'acl_number': self.acl_number,
            'acl_type': self.acl_type,
            'acl_kind': self.acl_kind,
            'entries': [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AclConfig':
        """从字典创建对象"""
        return cls(
            acl_name=data['acl_name'],
            entries=[AclEntry.from_dict(e) for e in data['entries']],
            acl_number=data.get('acl_number'),
            acl_type=data.get('acl_type', 'ipv4'),
            acl_kind=data.get('acl_kind'),
        )

    @property
    def policy_type(self) -> str:
        """策略类型"""
        return PolicyType.ACL


# ==================== 解析结果包装 ====================

@dataclass
class ParseResult:
    """配置解析结果"""
    prefix_lists: List[PrefixListConfig] = field(default_factory=list)
    access_lists: List[AclConfig] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'prefix_lists': [pl.to_dict() for pl in self.prefix_lists],
            'access_lists': [acl.to_dict() for acl in self.access_lists],
        }

    def get_total_count(self) -> int:
        """获取总数"""
        return len(self.prefix_lists) + len(self.access_lists)

    def is_empty(self) -> bool:
        """是否为空"""
        return self.get_total_count() == 0

