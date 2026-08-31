import requests
import json
from config.config import Config

def sendMessage(msg, msg_type, receiver):
    """
    发送消息接口
    :param msg: 消息内容
    :param msg_type: 消息类型 p2p/group
    :param receiver: 接收者（p2p为用户ID，group为群组ID）
    :return:
    """
    # 这里可以集成企业内部的消息系统
    # 例如：企业微信、钉钉、Slack等

    # 暂时返回模拟结果
    try:
        # 如果有配置消息推送服务，可以在这里实现
        # url = "http://your-message-service/api/send"
        # if msg_type == "p2p":
        #     body = {"msg": msg, "to": receiver}
        # else:
        #     body = {"msg": msg, "team_id": receiver}
        # resp = requests.post(url, json=body)
        # return resp.json()

        return {
            "code": 0,
            "message": "消息发送功能待配置",
            "data": {
                "msg": msg,
                "msg_type": msg_type,
                "receiver": receiver
            }
        }
    except Exception as e:
        return {"code": -1, "message": f"发送失败: {str(e)}"}
