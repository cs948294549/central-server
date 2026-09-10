"""
策略管理模块 - 用于解析和管理交换机策略配置

支持的策略类型：
- 地址前缀列表（Prefix List）
- 访问控制列表（ACL）
- 路由策略（Route Policy）
"""

__version__ = "0.1.0"

# 自动导入所有解析器和编码器，触发注册
from lib_config.parsers import parser_cisco  # noqa
from lib_config.encoders import encode_cisco  # noqa

# 导出解析器接口
from lib_config.parsers import get_parser, get_supported_vendors as get_supported_parser_vendors  # noqa

# 导出编码器接口
from lib_config.encoders import get_encoder, get_supported_vendors as get_supported_encoder_vendors  # noqa

# 导出模型
from lib_config.models import ParseResult  # noqa

__all__ = [
    'get_parser',
    'get_supported_parser_vendors',
    'get_encoder',
    'get_supported_encoder_vendors',
    'ParseResult'
]
