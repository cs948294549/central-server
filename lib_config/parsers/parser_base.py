"""
配置解析器基类（整合优化版本）

参考 switchcli 项目的设计，优化点：
1. 保留按需解析机制（parse sections）
2. 统一返回标准化模型
3. 支持节点树解析（便于处理层级配置）
4. 动态方法查找机制
5. 更好的日志和错误处理
"""

import re
import logging
from abc import ABC
from typing import List, Optional, Dict, Any, Set, Callable
from lib_config.models import ParseResult
from utils.config_tree import build_config_tree

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """配置解析器基类"""

    def __init__(self, vendor: str, raw_cfg: str):
        """
        初始化解析器

        Args:
            vendor: 厂商类型（h3c, huawei, cisco_nx等）
        """
        self.vendor = vendor
        self.raw_config: str = raw_cfg
        self.config_tree: Optional[List[Dict[str, Any]]] = []
        self.available_sections: Set[str] = set()
        self._init_available_sections()

    def _init_available_sections(self) -> None:
        """初始化支持的配置项（由子类实现）"""
        pass

    def parse(self, sections: Optional[List[str]] = None) -> ParseResult:
        """
        解析设备备份配置（主入口）

        Args:
            sections: 需要解析的配置项列表，None表示解析所有支持的配置项

        Returns:
            ParseResult: 解析结果
        """
        # 构建配置树
        try:
            self.config_tree = build_config_tree(self.raw_config)
            if self.config_tree:
                logger.debug(f"[{self.vendor}] 配置树构建完成")
                self._print_config_tree()
        except Exception as e:
            logger.debug(f"[{self.vendor}] 配置树构建失败: {e}")
            self.config_tree = []

        # 验证请求的配置项
        target_sections = self._validate_sections(sections)

        result = ParseResult()

        # 动态调用解析方法
        for section in target_sections:
            parse_method = self._get_parse_method(section)
            if parse_method:
                try:
                    parsed_data = parse_method()
                    setattr(result, section, parsed_data)
                    logger.info(f"[{self.vendor}] 已解析配置项: {section} ({len(parsed_data)} 条)")
                except Exception as e:
                    logger.error(f"[{self.vendor}] 解析 {section} 失败: {e}", exc_info=True)
            else:
                logger.debug(f"[{self.vendor}] 跳过未实现的配置项: {section}")

        return result

    def _print_config_tree(self):
        """打印配置树结构用于调试"""
        if not self.config_tree:
            logger.debug(f"[{self.vendor}] 配置树为空")
            return

        logger.debug(f"[{self.vendor}] 配置树结构 (共 {len(self.config_tree)} 个根节点):")
        for i, node in enumerate(self.config_tree):  # 只打印前20个节点
            indent_str = "  " * node['indent']
            content_preview = node['content'][:100]  # 截取前100字符
            logger.debug(f"  [{i}] indent={node['indent']} {indent_str}{content_preview}")

            # 如果有子节点，打印前几个
            if node['child']:
                for j, child in enumerate(node['child'][:3]):
                    child_indent_str = "  " * child['indent']
                    child_preview = child['content'][:80]
                    logger.debug(f"      └─ [{j}] indent={child['indent']} {child_indent_str}{child_preview}")
                if len(node['child']) > 3:
                    logger.debug(f"      └─ ... 还有 {len(node['child']) - 3} 个子节点")

    def _validate_sections(self, sections: Optional[List[str]]) -> List[str]:
        """
        验证并返回有效的配置项列表

        Args:
            sections: 用户请求的配置项列表

        Returns:
            List[str]: 有效的配置项列表
        """
        if not sections:
            # 未指定，返回所有支持的配置项
            return list(self.available_sections)

        # 检查请求的配置项是否都受支持
        invalid_sections = [s for s in sections if s not in self.available_sections]
        if invalid_sections:
            logger.warning(
                f"[{self.vendor}] 不支持的配置项: {invalid_sections}，已忽略。"
                f"支持的配置项: {sorted(self.available_sections)}"
            )

        return [s for s in sections if s in self.available_sections]

    def _get_parse_method(self, section: str) -> Optional[Callable]:
        """
        获取指定配置项对应的解析方法

        通过命名约定查找方法：parse_{section}

        Args:
            section: 配置项名称

        Returns:
            解析方法或 None
        """
        method_name = f"parse_{section}"
        return getattr(self, method_name, None)

    # ==================== 解析方法（由子类实现）====================
    # 子类根据需要实现 parse_{section}() 方法
    # 例如：
    #   def parse_prefix_lists(self, config_text: str) -> List[PrefixListConfig]
    #   def parse_acls(self, config_text: str) -> List[AclConfig]
    #   def parse_address_objects(self, config_text: str) -> List[AddressObjectConfig]
    #   def parse_service_objects(self, config_text: str) -> List[ServiceObjectConfig]

    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"解析器: {self.__class__.__name__}\n"
            f"厂商: {self.vendor}\n"
            f"支持的配置项: {sorted(self.available_sections)}"
        )


# ==================== 解析器工厂 ====================

_PARSER_REGISTRY: Dict[str, type] = {}


def register_parser(vendor: str):
    """
    解析器注册装饰器

    Usage:
        @register_parser('h3c')
        class H3CParser(BaseParser):
            ...
    """
    def decorator(parser_class):
        _PARSER_REGISTRY[vendor] = parser_class
        logger.debug(f"注册解析器: {vendor} -> {parser_class.__name__}")
        return parser_class
    return decorator


def get_parser(vendor: str, raw_cfg: str) -> BaseParser:
    """
    获取解析器实例

    Args:
        vendor: 厂商类型

    Returns:
        BaseParser: 解析器实例

    Raises:
        ValueError: 不支持的厂商类型
    """
    parser_class = _PARSER_REGISTRY.get(vendor)
    if not parser_class:
        raise ValueError(
            f"不支持的厂商: {vendor}。"
            f"支持的厂商: {list(_PARSER_REGISTRY.keys())}"
        )

    return parser_class(vendor, raw_cfg)


def get_supported_vendors() -> List[str]:
    """
    获取支持的厂商列表

    Returns:
        List[str]: 厂商列表
    """
    return list(_PARSER_REGISTRY.keys())
