"""
配置模板的 Jinja 渲染与参数提取

模板语法限制为三种写法：
    {{ 参数 }}              取值，支持 {{ 集合里的字段 }} 与登记过的过滤器
    {% for x in 集合 %}     遍历（可嵌套）
    {% if 参数 %}           条件取舍（可带 else / elif）

不允许 set / macro / include / extends / block / with 以及函数调用，
目的是让模板里出现的名字就是需要人工填写的参数，一眼能对上。

参数提取走 Jinja 自己的 AST，不用正则：
    - 顶层标量参数    -> variables
    - 需要遍历的集合  -> collections，并记录集合内被引用到的字段
这样模板改了哪一段，参数清单就跟着变。
"""
import logging

from jinja2 import Environment, StrictUndefined, Undefined
from jinja2 import nodes as jnodes
from jinja2.exceptions import TemplateSyntaxError, UndefinedError

from function_poap.jinja_filters import (
    CUSTOM_FILTERS,
    ALLOWED_FILTERS,
    ALLOWED_TESTS,
)

logger = logging.getLogger(__name__)


# ==================== 语法白名单 ====================
# 允许出现的 AST 节点名。其余节点一律拒绝，错误信息里直接报节点名。
# 按名字取类：不同 jinja2 版本的节点类有增减，缺失的跳过，避免导入期报错。
_ALLOWED_NODE_NAMES = [
    "Template", "Output", "TemplateData",
    "For", "If",
    "Name", "Getattr", "Getitem", "Const",
    "Tuple", "List", "Dict", "Pair",
    "Filter", "Test", "Keyword",
    "And", "Or", "Not", "Compare", "Operand",
    "CondExpr", "Slice",
    "Add", "Sub", "Mul", "Div", "FloorDiv",
    "Mod", "Pos", "Neg", "Concat",
]

ALLOWED_NODES = tuple(
    cls for cls in (getattr(jnodes, n, None) for n in _ALLOWED_NODE_NAMES)
    if isinstance(cls, type)
)

# 明确禁止的节点 -> 给用户看的说明
FORBIDDEN_HINT = {
    "Assign": "{% set %}",
    "AssignBlock": "{% set %}…{% endset %}",
    "Macro": "{% macro %}",
    "CallBlock": "{% call %}",
    "FilterBlock": "{% filter %}",
    "Include": "{% include %}",
    "Extends": "{% extends %}",
    "Import": "{% import %}",
    "FromImport": "{% from %}",
    "Block": "{% block %}",
    "With": "{% with %}",
    "Scope": "{% with %}",
    "ExprStmt": "{% do %}",
    "Break": "{% break %}",
    "Continue": "{% continue %}",
    "Call": "函数调用",
}

# 循环内置变量，不算参数
LOOP_BUILTIN = "loop"


def build_env(strict=True):
    """
    构造受限的 Jinja 环境
    :param strict: True 时未提供的参数直接报错；False 时渲染成占位标记，便于预览
    """
    env = Environment(
        undefined=StrictUndefined if strict else _MarkerUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters.update(CUSTOM_FILTERS)
    return env


class _MarkerUndefined(Undefined):
    """
    预览用：缺失的参数渲染成 <<未填:名字>>，而不是空字符串，
    避免生成出看着正常、实际少了值的配置。
    """

    def __str__(self):
        return "<<未填:{}>>".format(self._undefined_name or "?")

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __len__(self):
        return 0


# ==================== AST 遍历 ====================

def _node_name(node):
    return type(node).__name__


def _resolve_path(node, scope):
    """
    把取值表达式还原成点号路径，循环变量替换成它遍历的集合路径。

    {{ vlan_server }}                      -> "vlan_server"
    {% for link in links %}{{ link.a_ip }} -> "links.a_ip"
    {% for pp in link.port_pairs %}{{ pp.a_port }}
                                           -> "links.port_pairs.a_port"
    取不出路径（如对常量取属性）返回 None。
    返回 (path: str, depth: int)，depth 是点号层数（hostname 为 1，link.a_ip 为 2）。
    """
    if isinstance(node, jnodes.Name):
        return (scope.get(node.name, node.name), 1)

    if isinstance(node, jnodes.Getattr):
        parent_result = _resolve_path(node.node, scope)
        if not parent_result or not parent_result[0]:
            return (None, 0)
        parent_path, parent_depth = parent_result
        return ("{}.{}".format(parent_path, node.attr), parent_depth + 1)

    if isinstance(node, jnodes.Getitem):
        parent_result = _resolve_path(node.node, scope)
        if not parent_result or not parent_result[0]:
            return (None, 0)
        parent_path, parent_depth = parent_result
        arg = node.arg
        # ["字段"] 与 .字段 等价
        if isinstance(arg, jnodes.Const):
            # jinja2 2.x 用 const，3.x 用 value
            val = getattr(arg, 'value', None) or getattr(arg, 'const', None)
            if isinstance(val, str):
                return ("{}.{}".format(parent_path, val), parent_depth + 1)
        # [下标] 取的是数组元素，字段归属仍算在这个集合上
        return (parent_path, parent_depth)

    return (None, 0)


class _Collector(object):
    """
    一次遍历同时做两件事：校验语法白名单、收集参数引用
    """

    def __init__(self):
        self.errors = []
        self.paths = set()        # 解析后的完整路径
        self.iterated = set()     # 被 for 遍历过的集合路径
        self.loop_vars = []       # 循环变量名，按出现顺序
        self.filters = set()
        self.tests = set()
        self.block_count = {"for": 0, "if": 0}
        self.for_depth = 0        # 当前 for 嵌套深度

    def err(self, msg, node=None):
        lineno = getattr(node, "lineno", None)
        self.errors.append({"lineno": lineno, "message": msg})

    def walk(self, node, scope):
        name = _node_name(node)

        if name in FORBIDDEN_HINT:
            self.err("不支持 {}，模板只允许 {{{{ 参数 }}}}、{{% for %}}、{{% if %}}".format(
                FORBIDDEN_HINT[name]), node)
            return

        if not isinstance(node, ALLOWED_NODES):
            self.err("不支持的语法：{}".format(name), node)
            return

        if isinstance(node, jnodes.For):
            self._walk_for(node, scope)
            return

        if isinstance(node, jnodes.If):
            self.block_count["if"] += 1

        if isinstance(node, jnodes.Filter):
            if node.name not in ALLOWED_FILTERS:
                self.err("过滤器 {} 未开放，可用：{}".format(
                    node.name, "、".join(sorted(ALLOWED_FILTERS))), node)
            else:
                self.filters.add(node.name)

        if isinstance(node, jnodes.Test):
            if node.name not in ALLOWED_TESTS:
                self.err("测试 {} 未开放，可用：{}".format(
                    node.name, "、".join(sorted(ALLOWED_TESTS))), node)
            else:
                self.tests.add(node.name)

        # 取值表达式：记录引用，不再往下钻（下标里的表达式单独处理）
        if isinstance(node, (jnodes.Name, jnodes.Getattr, jnodes.Getitem)):
            self._note(node, scope)
            if isinstance(node, jnodes.Getitem):
                self.walk(node.arg, scope)
            return

        for child in node.iter_child_nodes():
            self.walk(child, scope)

    def _walk_for(self, node, scope):
        self.block_count["for"] += 1
        self.for_depth += 1

        if self.for_depth > 2:
            self.err("for 循环最多二层嵌套，不允许三层及以上", node)
            self.for_depth -= 1
            return

        # 被遍历的集合先在外层作用域里解析
        coll_result = _resolve_path(node.iter, scope)
        coll_path = None
        if coll_result and coll_result[0]:
            coll_path = coll_result[0]
            self.iterated.add(coll_path)
            self.paths.add(coll_path)
        else:
            self.walk(node.iter, scope)

        if node.recursive:
            self.err("不支持 recursive 循环", node)

        # 循环变量绑定到集合路径，供块内解析字段
        inner = dict(scope)
        targets = node.target.items if isinstance(node.target, jnodes.Tuple) else [node.target]
        for t in targets:
            if isinstance(t, jnodes.Name):
                inner[t.name] = coll_path or t.name
                if t.name not in self.loop_vars:
                    self.loop_vars.append(t.name)
            else:
                self.err("循环变量只能是简单名字", node)

        if node.test is not None:
            self.walk(node.test, inner)
        for child in node.body:
            self.walk(child, inner)
        for child in node.else_:
            self.walk(child, inner)

        self.for_depth -= 1

    def _note(self, node, scope):
        result = _resolve_path(node, scope)
        if not result or not result[0]:
            return
        path, depth = result

        # 参数取值最多二层：hostname（1层）、link.a_ip（2层）
        if depth > 2:
            self.err("参数取值最多二层（a.b），不允许更深嵌套：{}".format(path), node)
            return

        root = path.split(".")[0]
        if root == LOOP_BUILTIN:
            return
        self.paths.add(path)


# ==================== 对外接口 ====================

def extract_params(source):
    """
    从模板里提取参数清单

    :param source: 模板文本
    :return: {
        ok: bool,
        errors: [{lineno, message}],        语法不合规之处
        variables: [str],                   顶层标量参数（取根名）
        collections: {集合名: [字段…]},      需要遍历的集合及其被引用的字段
        paths: [str],                       所有引用的完整路径，不丢 a.b.c 这类层级
        loop_vars: [str],                   循环变量名（不是参数，仅供参考）
        filters: [str], tests: [str],
        blocks: {for: n, if: n}
      }
    """
    out = {
        "ok": False, "errors": [],
        "variables": [], "collections": {}, "paths": [], "loop_vars": [],
        "filters": [], "tests": [], "blocks": {"for": 0, "if": 0},
    }

    env = build_env(strict=True)
    try:
        ast = env.parse(source or "")
    except TemplateSyntaxError as err:
        out["errors"].append({"lineno": err.lineno, "message": "模板语法错误：{}".format(err.message)})
        return out
    except Exception as err:
        logger.error("解析模板失败: {}".format(err))
        out["errors"].append({"lineno": None, "message": "解析模板失败：{}".format(err)})
        return out

    c = _Collector()
    c.walk(ast, {})

    # 路径归类：被 for 遍历过的算集合，其余算标量
    collections = {name: set() for name in c.iterated}
    variables = set()
    for path in c.paths:
        if path in collections:
            continue
        # 找出这条路径属于哪个集合（取最长匹配，兼容嵌套集合）
        owner = None
        for name in collections:
            if path.startswith(name + "."):
                if owner is None or len(name) > len(owner):
                    owner = name
        if owner:
            field = path[len(owner) + 1:]
            # 嵌套集合本身不算字段，它的字段已经单独记过
            if field and ("{}.{}".format(owner, field) not in collections):
                collections[owner].add(field)
        else:
            variables.add(path.split(".")[0])

    out["errors"] = c.errors
    out["ok"] = not c.errors
    out["variables"] = sorted(variables)
    out["collections"] = {k: sorted(v) for k, v in sorted(collections.items())}
    out["paths"] = sorted(c.paths)
    out["loop_vars"] = c.loop_vars
    out["filters"] = sorted(c.filters)
    out["tests"] = sorted(c.tests)
    out["blocks"] = c.block_count
    return out


def validate_template(source):
    """
    只校验语法是否合规
    :return: {ok: bool, errors: [...]}
    """
    r = extract_params(source)
    return {"ok": r["ok"], "errors": r["errors"]}


def _flatten_present(context, prefix=""):
    """
    把上下文摊平成点号路径集合，用于比对模板引用了但没给值的参数
    """
    found = set()
    if isinstance(context, dict):
        for k, v in context.items():
            path = "{}.{}".format(prefix, k) if prefix else str(k)
            found.add(path)
            found |= _flatten_present(v, path)
    elif isinstance(context, (list, tuple)):
        # 列表元素的字段挂在列表路径上，与提取结果的表达方式一致
        for item in context:
            found |= _flatten_present(item, prefix)
    return found


def find_missing(source, context):
    """
    找出模板引用了、但上下文里没有的参数路径
    :return: [str]
    """
    info = extract_params(source)
    present = _flatten_present(context or {})
    missing = []

    for name in info["variables"]:
        if name not in present:
            missing.append(name)

    for coll, fields in info["collections"].items():
        if coll not in present:
            missing.append(coll)
            continue
        for f in fields:
            path = "{}.{}".format(coll, f)
            if path not in present:
                missing.append(path)

    return sorted(set(missing))


def render_template(source, context=None, strict=True):
    """
    渲染配置模板

    :param source: 模板文本
    :param context: 参数字典
    :param strict: True 时缺参数直接失败；False 时缺的渲染成 <<未填:名字>>，用于页面预览
    :return: {ok: bool, text: str, missing: [str], errors: [{lineno, message}]}
    """
    out = {"ok": False, "text": "", "missing": [], "errors": []}
    ctx = context or {}

    check = validate_template(source)
    if not check["ok"]:
        out["errors"] = check["errors"]
        return out

    out["missing"] = find_missing(source, ctx)

    env = build_env(strict=strict)
    try:
        out["text"] = env.from_string(source or "").render(**ctx)
    except UndefinedError as err:
        out["errors"].append({"lineno": None, "message": "参数缺失：{}".format(err.message)})
        return out
    except TemplateSyntaxError as err:
        out["errors"].append({"lineno": err.lineno, "message": "模板语法错误：{}".format(err.message)})
        return out
    except Exception as err:
        logger.error("渲染模板失败: {}".format(err))
        out["errors"].append({"lineno": None, "message": "渲染失败：{}".format(err)})
        return out

    out["ok"] = True
    return out
