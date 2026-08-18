"""
SSH 终端 WebSocket 蓝图
提供交互式 SSH 终端功能的 HTTP API
通过 WebSocket 服务器推送终端输出
"""
from flask import Blueprint, request, jsonify
import logging
import requests
import json

logger = logging.getLogger(__name__)

# 创建蓝图
websocket_ssh_bp = Blueprint('websocket_ssh', __name__, url_prefix='/webssh')

# 全局变量，在主应用中初始化
ssh_manager = None
websocket_url = None


def init_websocket_ssh(manager, ws_url):
    """
    初始化 SSH 终端蓝图

    Args:
        manager: InteractiveSSHManager 实例
        ws_url: WebSocket 服务器地址（如 http://localhost:8081）
    """
    global ssh_manager, websocket_url
    ssh_manager = manager
    websocket_url = ws_url
    logger.info(f"SSH 终端蓝图已初始化，WebSocket 服务器: {ws_url}")


def send_to_websocket(session_id, message):
    """
    通过 WebSocket 服务器发送消息

    Args:
        session_id: 会话 ID（作为 target 频道名）
        message: 消息内容（SSH 终端输出）
    """
    if not websocket_url:
        logger.error("WebSocket 服务器地址未配置")
        return False

    try:
        # 按照实际的 WebSocket 消息格式发送
        response = requests.post(
            f"{websocket_url}/send_msg",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "target": session_id,  # session_id 作为频道名
                "msg": message         # SSH 终端输出内容
            }),
            timeout=5
        )

        if response.status_code == 200:
            logger.debug(f"消息已发送到 WebSocket 频道: {session_id}")
            return True
        else:
            logger.error(f"发送到 WebSocket 失败: {response.text}")
            return False
    except Exception as e:
        logger.error(f"调用 WebSocket 服务器异常: {str(e)}")
        return False


@websocket_ssh_bp.route('/create_session', methods=['POST'])
def create_session():
    """
    创建 SSH 会话

    请求体:
    {
        "ip": "10.220.17.122",
        "user": "admin",
        "username": "ssh_user",  // 可选
        "password": "ssh_pass"   // 可选
    }

    返回:
    {
        "status": "success",
        "session_id": "admin_10.220.17.122",
        "message": "SSH 会话已创建"
    }
    """
    try:
        data = request.get_json()

        if not data or 'ip' not in data:
            return jsonify({
                "status": "error",
                "message": "缺少必要参数 ip"
            }), 400

        host = data['ip']

        # 从配置获取默认凭证
        from config import Config
        username = data.get('username', Config.ssh_username)
        password = data.get('password', Config.ssh_password)

        # 生成会话 ID（格式：user_ip）
        user = data.get('user', 'admin')
        session_id = f"{user}_{host}"

        # 创建 SSH 会话
        success = ssh_manager.create_session(
            session_id=session_id,
            host=host,
            username=username,
            password=password
        )

        if success:
            logger.info(f"SSH 会话已创建: {session_id}")
            return jsonify({
                "status": "success",
                "session_id": session_id,
                "message": "SSH 会话已创建"
            })
        else:
            logger.error(f"SSH 会话创建失败: {session_id}")
            return jsonify({
                "status": "error",
                "message": "SSH 会话创建失败，请检查网络连接和凭证"
            }), 500

    except Exception as e:
        logger.error(f"创建 SSH 会话异常: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"创建会话失败: {str(e)}"
        }), 500


@websocket_ssh_bp.route('/send_command', methods=['POST'])
def send_command():
    """
    发送命令到 SSH 会话

    请求体:
    {
        "ip": "10.220.17.122",
        "user": "admin",
        "cmd": "show version",
        "padding": "0a"  // 可选，控制字符（十六进制）
    }

    控制字符说明:
    - "0a": 回车 (Enter)
    - "03": Ctrl+C
    - "15": Ctrl+U
    - "18": Ctrl+X
    - "7f": 退格 (Backspace)
    - "09": Tab
    - "00": 无控制字符

    返回:
    {
        "status": "success",
        "message": "命令已发送"
    }
    """
    try:
        data = request.get_json()

        if not data or 'ip' not in data:
            return jsonify({
                "status": "error",
                "message": "缺少必要参数 ip"
            }), 400

        host = data['ip']
        command = data.get('cmd', '')
        padding = data.get('padding', '')

        # 命令白名单检查：只允许 show 和 display 开头的命令
        # 注意：空格、Tab 等控制字符用于交互式操作（如翻页），不应被拦截
        command_stripped = command.strip()
        if command_stripped:
            # 转换为小写进行比较
            command_lower = command_stripped.lower()

            # 检查是否以允许的命令开头
            allowed_prefixes = ['show', 'display']
            is_allowed = any(command_lower.startswith(prefix) for prefix in allowed_prefixes)

            if not is_allowed:
                logger.warning(f"拒绝执行不允许的命令: {command_stripped} (来自 {data.get('user', 'unknown')})")
                return jsonify({
                    "status": "error",
                    "message": "只允许执行 show 或 display 开头的查询命令"
                }), 403

        # 生成会话 ID
        user = data.get('user', 'admin')
        session_id = f"{user}_{host}"

        # 发送命令
        ssh_manager.send_command(session_id, command, padding)

        logger.info(f"命令已发送到会话 {session_id}: {command}")
        return jsonify({
            "status": "success",
            "message": "命令已发送"
        })

    except Exception as e:
        logger.error(f"发送命令异常: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"发送命令失败: {str(e)}"
        }), 500


@websocket_ssh_bp.route('/close_session', methods=['POST'])
def close_session():
    """
    关闭 SSH 会话

    请求体:
    {
        "ip": "10.220.17.122",
        "user": "admin"
    }

    返回:
    {
        "status": "success",
        "message": "SSH 会话已关闭"
    }
    """
    try:
        data = request.get_json()

        if not data or 'ip' not in data:
            return jsonify({
                "status": "error",
                "message": "缺少必要参数 ip"
            }), 400

        host = data['ip']

        # 生成会话 ID
        user = data.get('user', 'admin')
        session_id = f"{user}_{host}"

        # 关闭会话
        ssh_manager.close_session(session_id)

        logger.info(f"SSH 会话已关闭: {session_id}")
        return jsonify({
            "status": "success",
            "message": "SSH 会话已关闭"
        })

    except Exception as e:
        logger.error(f"关闭会话异常: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"关闭会话失败: {str(e)}"
        }), 500


@websocket_ssh_bp.route('/session_status', methods=['GET'])
def session_status():
    """
    获取会话状态

    查询参数:
    - ip: 设备 IP
    - user: 用户名

    返回:
    {
        "status": "success",
        "alive": true,
        "total_sessions": 5
    }
    """
    try:
        host = request.args.get('ip')

        if not host:
            return jsonify({
                "status": "error",
                "message": "缺少参数 ip"
            }), 400

        user = request.args.get('user', 'admin')
        session_id = f"{user}_{host}"

        # 检查会话状态
        with ssh_manager.lock:
            session = ssh_manager.sessions.get(session_id)
            alive = session.is_alive() if session else False

        return jsonify({
            "status": "success",
            "alive": alive,
            "session_id": session_id,
            "total_sessions": ssh_manager.get_session_count()
        })

    except Exception as e:
        logger.error(f"获取会话状态异常: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"获取状态失败: {str(e)}"
        }), 500


# 导出蓝图
__all__ = ['websocket_ssh_bp', 'init_websocket_ssh', 'send_to_websocket']
