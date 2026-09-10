"""
配置编码器基类

将标准化模型转换为厂商特定的配置文本
"""

import logging
from abc import ABC
from typing import List, Optional, Dict, Any, Callable
from lib_config.models import PrefixListConfig

logger = logging.getLogger(__name__)


class BaseEncoder(ABC):
    """
    配置编码器基类

    负责将标准化的配置模型转换为厂商特定的配置文本

    子类需要实现:
    - _init_available_sections(): 初始化支持的配置项
    - encode_prefix_lists(): 编码地址前缀列表
    """

    def __init__(self, vendor: str):
        """
        初始化编码器

        Args:
            vendor: 厂商类型
        """
        self.vendor = vendor
        self.available_sections = set()
        self._init_available_sections()
        logger.debug(f"[{self.vendor}] 编码器初始化，支持: {self.available_sections}")

    def _init_available_sections(self) -> None:
        """初始化支持的配置项（由子类实现）"""
        pass

    def _validate_sections(self, sections: Optional[List[str]]) -> List[str]:
        """
        验证并返回有效的配置项列表

        Args:
            sections: 要编码的配置项列表，None 表示全部

        Returns:
            List[str]: 有效的配置项列表
        """
        if sections is None:
            return list(self.available_sections)

        invalid = set(sections) - self.available_sections
        if invalid:
            logger.warning(f"[{self.vendor}] 不支持的配置项: {invalid}")

        return [s for s in sections if s in self.available_sections]

    def encode(self, data: Dict[str, Any], sections: Optional[List[str]] = None) -> str:
        """
        主编码入口

        Args:
            data: 配置数据字典，格式: {'prefix_lists': [...], ...}
            sections: 要编码的配置项列表，None 表示全部

        Returns:
            str: 生成的配置文本
        """
        logger.debug(f"[{self.vendor}] 开始编码配置")

        # 验证配置项
        target_sections = self._validate_sections(sections)
        if not target_sections:
            logger.warning(f"[{self.vendor}] 没有可编码的配置项")
            return ""

        # 存储生成的配置行
        config_lines = []

        # 动态调用编码方法
        for section in target_sections:
            encode_method = self._get_encode_method(section)
            if encode_method and section in data:
                try:
                    logger.debug(f"[{self.vendor}] 编码 {section}")
                    # 从字典重建模型对象
                    models = self._dict_to_models(section, data[section])
                    if models:
                        section_config = encode_method(models)
                        if section_config:
                            config_lines.append(section_config)
                            logger.info(f"[{self.vendor}] 已编码配置项: {section} ({len(models)} 条)")
                except Exception as e:
                    logger.error(f"[{self.vendor}] 编码 {section} 失败: {e}", exc_info=True)
            else:
                logger.debug(f"[{self.vendor}] 跳过未实现或无数据的配置项: {section}")

        # 合并配置文本
        result = "\n".join(config_lines)
        logger.debug(f"[{self.vendor}] 编码完成，共 {len(config_lines)} 个配置块")
        return result

    def _dict_to_models(self, section: str, data: List[Dict[str, Any]]) -> List[Any]:
        """
        将字典数据转换为模型对象

        Args:
            section: 配置项名称
            data: 字典数据列表

        Returns:
            List[Any]: 模型对象列表
        """
        if section == 'prefix_lists':
            return [PrefixListConfig.from_dict(d) for d in data]
        # 后续扩展其他类型
        return []

    def _get_encode_method(self, section: str) -> Optional[Callable]:
        """
        获取指定配置项对应的编码方法

        通过命名约定查找方法：encode_{section}

        Args:
            section: 配置项名称

        Returns:
            编码方法或 None
        """
        method_name = f"encode_{section}"
        return getattr(self, method_name, None)

    # ==================== 编码方法（由子类实现）====================
    # 子类需要实现以下方法：
    #   def encode_prefix_lists(self, prefix_lists: List[PrefixListConfig]) -> str

    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"编码器: {self.__class__.__name__}\n"
            f"厂商: {self.vendor}\n"
            f"支持的配置项: {sorted(self.available_sections)}"
        )


# ==================== 编码器工厂 ====================

_ENCODER_REGISTRY: Dict[str, type] = {}


def register_encoder(vendor: str):
    """
    编码器注册装饰器

    Usage:
        @register_encoder('cisco_nx')
        class CiscoEncoder(BaseEncoder):
            ...
    """
    def decorator(encoder_class):
        _ENCODER_REGISTRY[vendor] = encoder_class
        logger.debug(f"注册编码器: {vendor} -> {encoder_class.__name__}")
        return encoder_class
    return decorator


def get_encoder(vendor: str) -> BaseEncoder:
    """
    获取编码器实例

    Args:
        vendor: 厂商类型

    Returns:
        BaseEncoder: 编码器实例

    Raises:
        ValueError: 不支持的厂商类型
    """
    encoder_class = _ENCODER_REGISTRY.get(vendor)
    if not encoder_class:
        raise ValueError(
            f"不支持的厂商: {vendor}。"
            f"支持的厂商: {list(_ENCODER_REGISTRY.keys())}"
        )

    return encoder_class(vendor)


def get_supported_vendors() -> List[str]:
    """
    获取支持的厂商列表

    Returns:
        List[str]: 厂商列表
    """
    return list(_ENCODER_REGISTRY.keys())
