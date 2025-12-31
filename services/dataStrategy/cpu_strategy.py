#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU指标处理策略
"""

from services.dataStrategy import DataStrategy
import logging

logger = logging.getLogger(__name__)

class CpuStrategy(DataStrategy):
    """
    CPU指标处理策略
    """
    
    # 指标名称
    metric_name = "cpu_usage"
    
    def process_data(self, data):
        """
        处理CPU指标数据
        
        Args:
            data: CPU指标数据
            
        Returns:
            处理后的CPU指标数据
        """
        try:
            logger.info(f"开始处理CPU指标数据: {data}")
            
            # 数据预处理
            cpu_data = data.get("data", {})
            
            # 计算CPU使用率（示例处理逻辑）
            if "total" in cpu_data and "idle" in cpu_data:
                total = cpu_data["total"]
                idle = cpu_data["idle"]
                usage = 100 - (idle / total * 100) if total > 0 else 0
                cpu_data["usage_percent"] = round(usage, 2)
            
            # 检查CPU使用是否过高
            if cpu_data.get("usage_percent", 0) > 80:
                logger.warning(f"CPU使用率过高: {cpu_data['usage_percent']}%")
                cpu_data["alert"] = "high_cpu_usage"
            
            logger.info(f"CPU指标数据处理完成: {cpu_data}")
            return cpu_data
            
        except Exception as e:
            logger.error(f"处理CPU指标数据失败: {e}")
            return data