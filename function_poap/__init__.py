"""
设备自动化上线（POAP）相关功能模块

当前提供配置模板能力：
    - Jinja 渲染（语法限制为 {{ 参数 }} / {% for %} / {% if %}）
    - 从模板里提取参数清单，供前端生成填写表单
"""

from function_poap.jinja_template import (
    render_template,
    extract_params,
    validate_template,
    find_missing,
)
from function_poap.jinja_filters import ALLOWED_FILTERS, ALLOWED_TESTS
from function_poap.func_arch_template import (
    get_template_list,
    get_template_detail,
    create_template,
    update_template,
    delete_template,
    duplicate_template,
    get_snapshot_list,
    get_snapshot_detail,
)

__all__ = [
    'render_template',
    'extract_params',
    'validate_template',
    'find_missing',
    'ALLOWED_FILTERS',
    'ALLOWED_TESTS',
    'get_template_list',
    'get_template_detail',
    'create_template',
    'update_template',
    'delete_template',
    'duplicate_template',
    'get_snapshot_list',
    'get_snapshot_detail',
]
