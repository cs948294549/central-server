"""
企业微信智能机器人消息推送

不直接连接企业微信：同一个 bot_id 只能保持一条 WebSocket 长连接，已被 network_bot 占用。
这里调用 network_bot 暴露的 POST /api/send，由它通过现有长连接执行 aibot_send_msg 主动推送。

接收方 chatid：单聊填用户 userid，群聊填群 chatid（机器人需已在群内）。
"""
import logging
import requests
from config.config import Config

logger = logging.getLogger(__name__)


def _post(payload):
    """
    调用 network_bot 推送接口

    Args:
        payload: 请求体 { chatid, msgtype, content / template_card }

    Returns:
        dict: {"code": 0, "message": "success"} 或 {"code": -1, "message": 错误信息}
    """
    conf = getattr(Config, "wecom_bot_config", None) or {}
    api_url = conf.get("api_url")
    if not api_url:
        return {"code": -1, "message": "wecom_bot_config 未配置 api_url"}

    try:
        resp = requests.post(api_url, json=payload, timeout=conf.get("timeout", 10))
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code == 200 and data.get("success"):
            return {"code": 0, "message": "success"}
        err = data.get("error") or resp.text
        logger.error(f"企业微信消息发送失败: chatid={payload.get('chatid')}, status={resp.status_code}, error={err}")
        return {"code": -1, "message": f"发送失败: {err}"}
    except Exception as e:
        logger.error(f"企业微信消息发送异常: chatid={payload.get('chatid')}, {e}")
        return {"code": -1, "message": f"发送失败: {str(e)}"}


def send_markdown(chatid, content):
    """
    发送 Markdown 消息

    Args:
        chatid: 单聊为 userid，群聊为 chatid
        content: markdown 文本

    Returns:
        dict: {"code": 0/-1, "message": ...}
    """
    return _post({"chatid": chatid, "msgtype": "markdown", "content": content})


def send_text(chatid, content):
    """
    发送文本消息（aibot 主动推送不支持纯 text，按 markdown 发送）
    """
    return _post({"chatid": chatid, "msgtype": "text", "content": content})


def send_template_card(chatid, template_card):
    """
    发送模板卡片消息

    Args:
        chatid: 单聊为 userid，群聊为 chatid
        template_card: 模板卡片结构，如 {"card_type": "text_notice", "main_title": {...}, ...}
    """
    return _post({"chatid": chatid, "msgtype": "template_card", "template_card": template_card})


def send_message(chatids, content, msg_type="markdown"):
    """
    批量发送消息

    Args:
        chatids: 单个 chatid 或 chatid 列表
        content: 消息内容（template_card 时为卡片 dict）
        msg_type: markdown / text / template_card

    Returns:
        dict: {"code": 0 全部成功 / -1 存在失败, "message": ..., "data": {chatid: 结果}}
    """
    if isinstance(chatids, str):
        chatids = [chatids]

    senders = {
        "markdown": send_markdown,
        "text": send_text,
        "template_card": send_template_card,
    }
    sender = senders.get(msg_type)
    if not sender:
        return {"code": -1, "message": f"不支持的消息类型: {msg_type}"}

    results = {chatid: sender(chatid, content) for chatid in chatids}
    failed = [c for c, r in results.items() if r["code"] != 0]
    if failed:
        return {"code": -1, "message": f"部分发送失败: {', '.join(failed)}", "data": results}
    return {"code": 0, "message": "success", "data": results}
