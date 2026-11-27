from flask import Blueprint, request
from api.api_response import APIResponse
from function_poap import (
    render_template,
    extract_params,
    validate_template,
    ALLOWED_FILTERS,
    ALLOWED_TESTS,
)

# 创建蓝图
poap_bp = Blueprint('poap', __name__, url_prefix='/poap')


@poap_bp.route('/template/params', methods=['POST'])
def getTemplateParams():
    """
    从配置模板里提取参数清单
    入参：{"source": "模板文本"} 或 {"configs": {"厂商": "模板文本"}}
    """
    try:
        data = request.json or {}
        source = data.get('source')
        configs = data.get('configs')

        if source is None and not configs:
            return APIResponse.param_error(message="缺少 source 或 configs")

        if source is not None:
            return APIResponse.success(data=extract_params(source), message="提取成功")

        result = {
            vendor: extract_params(text or "")
            for vendor, text in (configs or {}).items()
        }
        return APIResponse.success(data=result, message="提取成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@poap_bp.route('/template/validate', methods=['POST'])
def validateTemplate():
    """
    只校验模板语法是否合规（只允许 {{ 参数 }} / {% for %} / {% if %}）
    入参：{"source": "模板文本"}
    """
    try:
        data = request.json or {}
        source = data.get('source')
        if source is None:
            return APIResponse.param_error(message="缺少 source")

        result = validate_template(source)
        if result["ok"]:
            return APIResponse.success(data=result, message="校验通过")
        return APIResponse.success(data=result, message="模板存在不合规语法")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@poap_bp.route('/template/render', methods=['POST'])
def renderTemplate():
    """
    渲染配置模板
    入参：{"source": "模板文本", "context": {参数}, "strict": true}
    strict 为 false 时缺失参数渲染成 <<未填:名字>>，供页面预览
    """
    try:
        data = request.json or {}
        source = data.get('source')
        if source is None:
            return APIResponse.param_error(message="缺少 source")

        context = data.get('context') or {}
        if not isinstance(context, dict):
            return APIResponse.param_error(message="context 必须是对象")

        strict = data.get('strict', True)
        result = render_template(source, context, strict=bool(strict))
        if result["ok"]:
            return APIResponse.success(data=result, message="渲染成功")
        return APIResponse.success(data=result, message="渲染失败，详见 errors")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))


@poap_bp.route('/template/syntax', methods=['GET'])
def getTemplateSyntax():
    """
    返回模板可用的语法与过滤器，供前端在编辑器里提示
    """
    try:
        data = {
            "logic": ["{{ 参数 }}", "{% for x in 集合 %}…{% endfor %}", "{% if 参数 %}…{% endif %}"],
            "filters": sorted(ALLOWED_FILTERS),
            "tests": sorted(ALLOWED_TESTS),
        }
        return APIResponse.success(data=data, message="查询成功")
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))
