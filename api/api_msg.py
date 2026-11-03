from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_msg.wecom_bot import send_message as wecom_bot_send_message
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
msg_bp = Blueprint('msg', __name__, url_prefix='/msg')


@msg_bp.route('/wecom_bot/send', methods=['POST'])
def sendWecomBotMsg():
    """
    发送企业微信智能机器人消息（经 network_bot 转发）

    Body:
        chatid: 单个 chatid 或列表；单聊为 userid，群聊为群 chatid
        msg_type: markdown（默认）/ text / template_card
        content: 消息内容；template_card 时为卡片 dict
    """
    try:
        data = request.json or {}
        chatid = data.get('chatid')
        msg_type = data.get('msg_type', 'markdown')
        content = data.get('content')

        if not chatid:
            return APIResponse.param_error(message="缺少 chatid")
        if not content:
            return APIResponse.param_error(message="缺少 content")
        if msg_type == 'template_card' and not isinstance(content, dict):
            return APIResponse.param_error(message="template_card 消息的 content 必须为对象")
        if msg_type in ('markdown', 'text') and not isinstance(content, str):
            return APIResponse.param_error(message="content 必须为字符串")

        logger.info(f"用户 {g.user['username']} 发送企业微信机器人消息: chatid={chatid}, msg_type={msg_type}")
        result = wecom_bot_send_message(chatid, content, msg_type)
        if result["code"] == 0:
            return APIResponse.success(data=result.get("data"), message="发送成功")
        return APIResponse.error(message=result["message"], data=result.get("data"))
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))
