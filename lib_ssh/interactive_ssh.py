"""
交互式 SSH 会话管理模块
用于 xterm 实时终端交互
"""
import paramiko
import logging
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class InteractiveSSHSession:
    """
    交互式 SSH 会话类
    管理单个 SSH 交互式会话，支持实时输入输出
    """

    def __init__(self, host: str, username: str, password: str,
                 output_callback=None, port: int = 22):
        """
        初始化交互式 SSH 会话

        Args:
            host: 目标主机 IP
            username: SSH 用户名
            password: SSH 密码
            output_callback: 输出回调函数，接收终端输出数据
            port: SSH 端口，默认 22
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.output_callback = output_callback

        self.client = None
        self.channel = None
        self.connected = False
        self.running = False
        self._read_thread = None

    def connect(self) -> bool:
        """
        建立 SSH 连接并创建交互式 shell

        Returns:
            bool: 连接是否成功
        """
        try:
            # 创建 SSH 客户端
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # 连接到远程主机
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )

            # 创建交互式 shell
            self.channel = self.client.invoke_shell(
                term='xterm',
                width=100,
                height=40
            )

            # 设置为非阻塞模式
            self.channel.setblocking(0)

            self.connected = True
            self.running = True

            # 启动读取线程
            self._read_thread = threading.Thread(
                target=self._read_output,
                daemon=True,
                name=f"SSH-Reader-{self.host}"
            )
            self._read_thread.start()

            logger.info(f"交互式 SSH 会话已建立: {self.host}")
            return True

        except Exception as e:
            logger.error(f"SSH 连接失败 {self.host}: {str(e)}")
            self.disconnect()
            return False

    def _read_output(self):
        """
        持续读取 SSH 输出的后台线程
        """
        buffer_size = 1024

        while self.running and self.channel:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(buffer_size)
                    if data:
                        output = data.decode('utf-8', errors='ignore')
                        if self.output_callback:
                            self.output_callback(output)
                else:
                    time.sleep(0.01)  # 避免 CPU 占用过高

            except Exception as e:
                logger.error(f"读取 SSH 输出失败 {self.host}: {str(e)}")
                break

        logger.info(f"SSH 读取线程已停止: {self.host}")

    def send_input(self, data: str):
        """
        发送输入到 SSH 会话

        Args:
            data: 要发送的数据
        """
        if not self.connected or not self.channel:
            logger.warning(f"SSH 会话未连接，无法发送数据: {self.host}")
            return

        try:
            self.channel.send(data)
        except Exception as e:
            logger.error(f"发送数据失败 {self.host}: {str(e)}")
            self.disconnect()

    def send_command(self, command: str, padding: str = ""):
        """
        发送命令到 SSH 会话

        Args:
            command: 命令内容
            padding: 控制字符（十六进制字符串）
        """
        try:
            if padding:
                # 处理控制字符
                control_char = bytes.fromhex(padding).decode('latin-1')
                self.send_input(command + control_char)
            else:
                self.send_input(command)

        except Exception as e:
            logger.error(f"发送命令失败 {self.host}: {str(e)}")

    def resize_terminal(self, width: int, height: int):
        """
        调整终端大小

        Args:
            width: 终端宽度（列数）
            height: 终端高度（行数）
        """
        if self.channel:
            try:
                self.channel.resize_pty(width=width, height=height)
            except Exception as e:
                logger.error(f"调整终端大小失败 {self.host}: {str(e)}")

    def disconnect(self):
        """
        断开 SSH 连接
        """
        self.running = False
        self.connected = False

        try:
            if self.channel:
                self.channel.close()
        except Exception as e:
            logger.warning(f"关闭 channel 失败: {str(e)}")

        try:
            if self.client:
                self.client.close()
        except Exception as e:
            logger.warning(f"关闭 SSH 客户端失败: {str(e)}")

        logger.info(f"交互式 SSH 会话已断开: {self.host}")

    def is_alive(self) -> bool:
        """
        检查会话是否仍然活跃

        Returns:
            bool: 会话是否活跃
        """
        try:
            if self.channel and self.channel.get_transport():
                return self.channel.get_transport().is_active()
        except:
            pass
        return False


class InteractiveSSHManager:
    """
    交互式 SSH 会话管理器
    管理多个用户到多个设备的 SSH 会话
    """

    def __init__(self, output_sender=None):
        """
        初始化会话管理器

        Args:
            output_sender: 输出发送函数，接收 (session_id, data) 参数
        """
        self.output_sender = output_sender
        # 存储会话：{session_id: InteractiveSSHSession}
        self.sessions: Dict[str, InteractiveSSHSession] = {}
        self.lock = threading.Lock()

        # 启动清理线程
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_dead_sessions,
            daemon=True,
            name="SSH-Session-Cleanup"
        )
        self._cleanup_thread.start()

    def create_session(self, session_id: str, host: str,
                      username: str, password: str) -> bool:
        """
        创建新的 SSH 会话

        Args:
            session_id: 会话 ID（通常是 user_ip 格式）
            host: 目标主机 IP
            username: SSH 用户名
            password: SSH 密码

        Returns:
            bool: 是否创建成功
        """
        with self.lock:
            # 如果会话已存在，先断开
            if session_id in self.sessions:
                logger.info(f"会话 {session_id} 已存在，先断开旧会话")
                self.close_session(session_id)

            # 创建输出回调函数
            def output_callback(data):
                if self.output_sender:
                    self.output_sender(session_id, data)
                else:
                    logger.warning(f"未配置 output_sender，无法发送会话 {session_id} 的输出")

            # 创建新会话
            session = InteractiveSSHSession(
                host=host,
                username=username,
                password=password,
                output_callback=output_callback
            )

            # 尝试连接
            if session.connect():
                self.sessions[session_id] = session
                logger.info(f"SSH 会话已创建: {session_id} -> {host}")
                return True
            else:
                logger.error(f"SSH 会话创建失败: {session_id} -> {host}")
                return False

    def send_command(self, session_id: str, command: str, padding: str = ""):
        """
        向指定会话发送命令

        Args:
            session_id: 会话 ID
            command: 命令内容
            padding: 控制字符（十六进制字符串）
        """
        with self.lock:
            session = self.sessions.get(session_id)
            if session and session.is_alive():
                session.send_command(command, padding)
            else:
                logger.warning(f"会话 {session_id} 不存在或已断开")

    def close_session(self, session_id: str):
        """
        关闭指定会话

        Args:
            session_id: 会话 ID
        """
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if session:
                session.disconnect()
                logger.info(f"SSH 会话已关闭: {session_id}")

    def _cleanup_dead_sessions(self):
        """
        定期清理死亡的会话（后台线程）
        """
        while True:
            try:
                time.sleep(60)  # 每分钟检查一次

                with self.lock:
                    dead_sessions = [
                        sid for sid, session in self.sessions.items()
                        if not session.is_alive()
                    ]

                    for sid in dead_sessions:
                        logger.info(f"清理死亡会话: {sid}")
                        self.close_session(sid)

            except Exception as e:
                logger.error(f"清理会话时出错: {str(e)}")

    def get_session_count(self) -> int:
        """
        获取当前活跃会话数量

        Returns:
            int: 会话数量
        """
        with self.lock:
            return len(self.sessions)


# 导出
__all__ = ['InteractiveSSHManager', 'InteractiveSSHSession']
