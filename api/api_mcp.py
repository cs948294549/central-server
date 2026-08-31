from flask import Blueprint, request, jsonify, g
from functools import wraps
from function_mcp.mcp_interface import MCP_TOOLS, MCP_TOOLS_prompt
from api.api_response import APIResponse
from tables.UsersDB import UsersDB
import logging

logger = logging.getLogger(__name__)

# 创建 MCP 蓝图
mcp_bp = Blueprint("mcp", __name__, url_prefix='/mcp')

# ======================
# MCP 专用认证装饰器
# ======================
# /mcp、/mcp/tools、/mcp/health 不走 before_request 的主认证流程
# （已在 core/app.py 的 excluded_routes 中排除），
# 因此需要在这里单独校验。认证信息通过 Authorization 头传递，
# 格式为 "Bearer <key>:<secret>"，不做时间戳校验，仅比对 key/secret
def mcp_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return APIResponse.error("未提供认证信息", 401)

        token = auth_header.split("Bearer ", 1)[-1].strip()
        if ":" not in token:
            return APIResponse.error("认证格式错误", 401)

        api_key, api_secret = token.split(":", 1)
        if not api_key or not api_secret:
            return APIResponse.error("未提供认证信息", 401)

        try:
            db = UsersDB()
            user_infos = db.getUser({"username": api_key})
        except Exception as e:
            logger.error(f"MCP 认证异常: {str(e)}")
            return APIResponse.error("MCP 认证失败", 401)

        if len(user_infos) != 1 or user_infos[0]["identify"] != api_secret:
            logger.warning(f"MCP 认证失败: key={api_key}")
            return APIResponse.error("MCP 认证失败", 401)

        user_info = user_infos[0]
        g.user = {
            "username": user_info["username"],
            "rid": user_info["rid"],
            "subname": user_info.get("subname", ""),
            "auth_type": "mcp_key",
        }
        logger.info(f"MCP 认证成功: 用户 {user_info['username']} ({user_info['rid']}) 访问接口 {request.path}")

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
@mcp_auth_required
def list_tools():
    """
    列出所有可用的 MCP 工具
    """
    return APIResponse.success(
        data={"tools": MCP_TOOLS_prompt},
        message="MCP 工具列表"
    )


@mcp_bp.route("/health", methods=["GET"])
@mcp_auth_required
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
