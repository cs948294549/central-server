"""
配置模板可用的过滤器

模板只允许 if / for 两种逻辑，不允许写表达式运算。
地址换算这类纯格式转换由过滤器提供，避免把 split、位运算写进模板。

过滤器名即白名单，未登记的过滤器在校验阶段会被拒绝。
"""
import ipaddress
import logging

logger = logging.getLogger(__name__)


def _parse_interface(value):
    """
    把 10.0.0.1/30 解析成 ip_interface；失败返回 None
    """
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return ipaddress.ip_interface(text)
    except ValueError:
        return None


def ip_only(value):
    """
    10.0.0.1/30 -> 10.0.0.1；无掩码时原样返回
    """
    return str(value or "").strip().split("/")[0]


def prefix_len(value):
    """
    10.0.0.1/30 -> 30
    """
    itf = _parse_interface(value)
    return itf.network.prefixlen if itf else ""


def netmask(value):
    """
    10.0.0.1/30 -> 255.255.255.252
    """
    itf = _parse_interface(value)
    return str(itf.netmask) if itf else ""


def wildcard(value):
    """
    10.0.0.0/24 -> 0.0.0.255（Cisco ACL 反掩码）
    """
    itf = _parse_interface(value)
    return str(itf.hostmask) if itf else ""


def network(value):
    """
    10.0.0.1/30 -> 10.0.0.0
    """
    itf = _parse_interface(value)
    return str(itf.network.network_address) if itf else ""


def dotted(value):
    """
    10.0.0.1/30 -> 10.0.0.1 255.255.255.252（H3C/华为的点分写法）
    """
    itf = _parse_interface(value)
    if not itf:
        return str(value or "").strip()
    return "{} {}".format(itf.ip, itf.netmask)


# 自定义过滤器：名字 -> 实现
CUSTOM_FILTERS = {
    "ip_only": ip_only,
    "prefix_len": prefix_len,
    "netmask": netmask,
    "wildcard": wildcard,
    "network": network,
    "dotted": dotted,
}

# 允许使用的 Jinja 内置过滤器。只放不改变语义、不隐藏参数的格式化类。
ALLOWED_BUILTIN_FILTERS = {
    "default", "join", "length", "count",
    "lower", "upper", "trim", "replace",
    "int", "string", "first", "last",
}

# 允许使用的 Jinja 测试（配合 if 用）
ALLOWED_TESTS = {
    "defined", "undefined", "none", "equalto", "eq", "ne",
    "in", "number", "string", "sameas", "even", "odd",
}

ALLOWED_FILTERS = set(CUSTOM_FILTERS.keys()) | ALLOWED_BUILTIN_FILTERS
