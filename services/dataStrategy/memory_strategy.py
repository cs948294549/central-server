#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存指标处理策略
"""

from services.dataStrategy import DataStrategy
import logging

logger = logging.getLogger(__name__)

class MemoryStrategy(DataStrategy):
    """
    内存指标处理策略
    """
    
    # 指标名称
    metric_name = "memory_usage"
    
    def process_data(self, data):
        """
        处理内存指标数据
        
        Args:
            data: 内存指标数据
            
        Returns:
            处理后的内存指标数据
        """
        try:
            logger.info(f"开始处理内存指标数据: {data}")
            
            # 数据预处理
            memory_data = data.get("data", {})
            
            # 计算内存使用率（示例处理逻辑）
            if "total" in memory_data and "used" in memory_data:
                total = memory_data["total"]
                used = memory_data["used"]
                usage = (used / total * 100) if total > 0 else 0
                memory_data["usage_percent"] = round(usage, 2)
                memory_data["free_percent"] = round(100 - usage, 2)
            
            # 转换为人类可读的格式
            for key in ["total", "used", "free", "cached"]:
                if key in memory_data and isinstance(memory_data[key], (int, float)):
                    memory_data[f"{key}_human"] = self._bytes_to_human(memory_data[key])
            
            # 检查内存使用是否过高
            if memory_data.get("usage_percent", 0) > 85:
                logger.warning(f"内存使用率过高: {memory_data['usage_percent']}%")
                memory_data["alert"] = "high_memory_usage"
            
            logger.info(f"内存指标数据处理完成: {memory_data}")
            return memory_data
            
        except Exception as e:
            logger.error(f"处理内存指标数据失败: {e}")
            return data
    
    def _bytes_to_human(self, bytes_value):
        """
        将字节数转换为人类可读的格式
        
        Args:
            bytes_value: 字节数
            
        Returns:
            人类可读的格式字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024
        return f"{bytes_value:.2f} PB"