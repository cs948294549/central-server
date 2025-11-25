"""
具体任务实现模块

包含各种具体任务的实现类
"""
import logging
import socket
import requests
from typing import Dict, Any
from task_core.task_base import BaseTask
from config import Config

logger = logging.getLogger(__name__)


class HeartbeatTask(BaseTask):
    """
    心跳任务，定期向中心服务发送心跳
    """

    TASK_ID = "heartbeat"
    TASK_NAME = "心跳任务"
    TASK_DESCRIPTION = "定期向中心服务发送心跳，保持连接活跃"

    def __init__(self, config=None):
        super().__init__(config)
        self.status = "down"

    def _get_local_ip(self):
        """获取本地IP地址（非127.0.0.1）"""
        try:
            # 通过连接外部地址获取本地IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))  # 不实际发送数据，仅用于获取本地IP
                return s.getsockname()[0]
        except:
            return "127.0.0.1"

    def execute(self) -> Dict[str, Any]:
        """
        执行心跳任务，向中心服务发送心跳包

        Returns:
            Dict[str, Any]: 心跳执行结果
        """
        if self.status == "down":
            # 注册节点
            logger.warning("Agent未注册，重新发起注册")
            local_ip = self._get_local_ip()

            register_data = {
                "address": "{}:{}".format(local_ip, Config.agent_id),
                "name": Config.agent_name,
                "agent_id": Config.agent_id,
            }

            response = requests.post(
                "{}/api/register".format(Config.center_address),
                json=register_data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                self.status = "up"
                print(f"✅ 注册成功, {response.text}")
                return True
            else:
                print(f"❌ 注册失败: {response.text}")
                raise ValueError("注册失败")
        else:
            try:
                # 构建心跳数据
                heartbeat_data = {
                    "agent_id": Config.agent_id,
                    "agent_name": Config.agent_name,
                    "status": "up"
                }

                # 发送心跳请求
                response = requests.post(
                    "{}/api/heartbeat".format(Config.center_address),
                    json=heartbeat_data,
                    timeout=5
                )

                if response.status_code == 200:
                    logger.info("心跳发送成功: {}".format(Config.agent_id))
                    return {"status": "success", "server_response": response.json()}
                else:
                    self.status = "down"
                    logger.warning(f"心跳发送失败，状态码: {response.status_code}")
                    raise
            except Exception as e:
                logger.error(f"心跳发送异常: {str(e)}")
                self.status = "down"
                raise ValueError("网络连接异常")