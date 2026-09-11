"""
策略管理相关功能模块
包含地址前缀列表管理等策略配置功能
"""

from function_policy.func_prefix import (
    calculate_prefix_list_fingerprint,
    get_device_statistics_for_standard,
    get_device_list_for_standard,
    compare_configurations,
    group_records_by_fingerprint,
    batch_create_issue_records,
    collect_and_update_prefix_lists
)

__all__ = [
    'calculate_prefix_list_fingerprint',
    'get_device_statistics_for_standard',
    'get_device_list_for_standard',
    'compare_configurations',
    'group_records_by_fingerprint',
    'batch_create_issue_records',
    'collect_and_update_prefix_lists'
]
