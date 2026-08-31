from flask import Blueprint, request, jsonify
from functools import wraps
from function_mcp.mcp_interface import MCP_TOOLS, MCP_TOOLS_prompt
from api.api_response import APIResponse
import logging

logger = logging.getLogger(__name__)

# 创建 MCP 蓝图
mcp_bp = Blueprint("mcp", __name__, url_prefix='/mcp')

# ======================
# OAuth2 认证装饰器（可选，用于独立的 MCP 认证）
# ======================
# 注意：如果使用 central-server 的统一认证，可以不需要这个装饰器
# 这里保留是为了兼容独立的 MCP 客户端访问
VALID_MCP_TOKENS = {
    "mcp-token-1": {"username": "mcp_admin1", "user_id": 1},
    "mcp-token-2": {"username": "mcp_admin2", "user_id": 2},
}

def mcp_auth_required(f):
    """
    MCP 专用的 OAuth2 认证装饰器
    如果请求带有 Bearer token，则使用 MCP 专用认证
    否则依赖 central-server 的统一认证（before_request）
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        # 如果带有 Bearer token，使用 MCP 专用认证
        if auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[-1].strip()
            user = VALID_MCP_TOKENS.get(token)

            if not user:
                return jsonify({"error": "Unauthorized - invalid MCP token"}), 401

            # 把用户信息传到视图函数
            request.mcp_user = user
            logger.info(f"MCP 独立认证成功: {user['username']}")
        else:
            # 否则依赖 central-server 的统一认证
            # 由 before_request 中间件处理
            pass

        return f(*args, **kwargs)
    return decorated


# --------------------------
# 核心端点
# --------------------------
@mcp_bp.route("", methods=["GET", "POST"])
@mcp_auth_required
def mcp_endpoint():
    """
    MCP 协议端点
    支持 GET 和 POST 请求
    """
    if request.method == "POST":
        try:
            req_data = request.get_json(force=True)
        except Exception as e:
            logger.error(f"MCP 请求解析失败: {str(e)}")
            return jsonify({"error": "Invalid JSON"}), 400

        resp_data = handle_mcp_request(req_data)
        logger.info(f"MCP 请求处理完成: {resp_data}")
        return jsonify(resp_data)

    # GET 请求返回服务信息
    return jsonify({
        "service": "MCP Server",
        "version": "1.0.0",
        "status": "running"
    })


# --------------------------
# MCP 逻辑纯手写实现
# --------------------------
def handle_mcp_request(req):
    """
    处理 MCP 协议请求
    :param req: MCP 请求数据
    :return: MCP 响应数据
    """
    method = req.get("method")
    req_id = req.get("id")
    logger.info(f"收到 MCP 请求: method={method}, id={req_id}")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "prompts": {},
                    "resources": {}
                },
                "serverInfo": {
                    "name": "central-server-mcp",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {}
        }

    elif method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"prompts": []}
        }

    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": []}
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOLS_prompt}
        }

    elif method == "tools/call":
        func_params = req.get("params", {})
        func_name = func_params.get("name", "")

        if func_name in MCP_TOOLS:
            try:
                result = MCP_TOOLS[func_name](**func_params.get("arguments", {}))
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": str(result)}
                        ]
                    }
                }
            except Exception as e:
                logger.error(f"MCP 工具调用失败: {func_name}, 错误: {str(e)}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
        else:
            logger.warning(f"MCP 工具未找到: {func_name}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": "Tool not found"
                }
            }

    logger.warning(f"MCP 方法未找到: {method}")
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": "Method not found"
        }
    }


# --------------------------
# 额外的辅助端点（可选）
# --------------------------
@mcp_bp.route("/tools", methods=["GET"])
def list_tools():
    """
    列出所有可用的 MCP 工具
    """
    return APIResponse.success(
        data={"tools": MCP_TOOLS_prompt},
        message="MCP 工具列表"
    )


@mcp_bp.route("/health", methods=["GET"])
def health_check():
    """
    健康检查端点
    """
    return APIResponse.success(
        data={
            "status": "healthy",
            "service": "MCP Server",
            "tools_count": len(MCP_TOOLS)
        },
        message="MCP 服务正常"
    )
