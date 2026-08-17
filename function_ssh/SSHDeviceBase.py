import time

import paramiko
import re
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

def _remove_control_characters(text):
    """移除字符串中的控制字符和ANSI转义序列"""
    # 移除ANSI转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', re.I)
    text = ansi_escape.sub('', text)
    # 移除其他控制字符（保留换行符）
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
    return text

class SSHDeviceBase(ABC):
    """
    SSH设备抽象基类
    提供SSH连接和命令执行的通用功能
    必须被继承才能使用，不能单独实例化
    """
    
    def __init__(self, host, username, password, port=22, connect_timeout=15, timeout=10, init_prompt=None):
        """
        初始化SSH连接
        
        Args:
            host: 设备IP地址
            username: 用户名
            password: 密码
            port: SSH端口，默认为22
            connect_timeout: 登陆超时时间，部分华为设备会卡30s
            timeout: 连接超时时间，默认为10秒
        """
        if self.__class__ is SSHDeviceBase:
            raise TypeError("抽象基类SSHDeviceBase不能直接实例化，请使用具体的子类")
            
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.connect_timeout = connect_timeout
        self.timeout = timeout
        self.client = None
        self.ssh_shell = None
        self.current_prompt = None
        
        # 先设置init_prompt属性，再调用_establish()
        if init_prompt:
            self.init_prompt = init_prompt
            logger.info("初始化参数===={}".format(str(init_prompt)))
            self._establish()
        else:
            raise ValueError("缺失初始化提示词匹配规则")
    
    def _establish(self):
        """
        建立SSH连接
        内部方法，由子类继承使用
        """
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.client.connect(hostname=self.host, port=self.port, username=self.username,
                               password=self.password, allow_agent=False, look_for_keys=False,
                               timeout=self.connect_timeout)
            
            # 创建交互式shell
            self.ssh_shell = self.client.invoke_shell(width=300)
            self.ssh_shell.settimeout(self.timeout)
            
            # 读取初始提示符
            self._init_terminal()
            
        except Exception as e:
            print(f"SSH连接失败: {e}")
            self.close()
            raise
    
    def _init_terminal(self):
        """
        初始化终端，读取提示符
        内部方法，由子类继承使用
        """
        line_data = ""
        retry = 1
        while True:
            try:
                line = self.ssh_shell.recv(1024)

                line_data += line.decode('utf-8', 'ignore').replace("\r", "")
                logger.debug("回显\n{}: {}".format(self.host, str(line_data)))
                last_line = line_data.strip().split("\n")[-1]
                logger.debug("最后一行\n{}".format(str(last_line)))
                if len(self.init_prompt.findall(last_line))>0:
                    self.current_prompt = self.init_prompt.findall(last_line)[0]
                    break
            except Exception as e:
                logger.warning("{}: 超时重试{}，异常原因{}".format(self.host, retry, str(e)))
                retry += 1
                if retry >= 3:
                    break
                else:
                    self.ssh_shell.sendall("\n".encode("utf-8", "ignore"))

        if self.current_prompt:
            logger.info("登陆设备 {} 成功, 当前prompt为{}".format(self.host, self.current_prompt))
            self._set_terminal()
        else:
            logger.info("登陆设备 {} 失败, 回显为{}".format(self.host, line_data))
            self.close()

    @abstractmethod
    def _set_terminal(self):
        """
        执行terminal length命令，不同厂家命令不同，有的不需要该命令
        """
        pass

    @abstractmethod
    def _send_command(self, command):
        """
        内部方法，由子类继承使用
        Args:
            command: 要执行的命令
            
        Returns:
            tuple: (提示符, 命令输出) 或者 None（命令执行失败）
        """
        pass

    @abstractmethod
    def _new_terminal(self):
        """
        内部方法，由子类继承使用
        将视图恢复到初始状态
        """
        pass

    def exec_commands(self, commands):
        """
        统一方法，执行命令列表返回结果
        Args:
            commands: 命令列表
            
        Returns:
            dict: 命令执行结果字典
        """
        if not isinstance(commands, list):
            return "failed"
        try:
            self._new_terminal()
            result = {}
            error_flag = False
            for idx, i in enumerate(commands):
                i = i.strip()
                if error_flag:
                    result["[{}]{}".format(idx, i)] = "failed"
                    break

                respond = self._send_command(i)
                # time.sleep(10)
                if respond:
                    prompt, detail = respond
                    if prompt is False:
                        result["[{}]{}".format(idx, i)] = "failed: {}".format(_remove_control_characters(detail.strip()))
                        error_flag = True
                        break
                    else:
                        result["[{}]{}".format(idx, i)] = _remove_control_characters(detail.strip())
                else:
                    result["[{}]{}".format(idx, i)] = "failed"
                    error_flag = True
                    break
            return result
        except Exception as e:
            logger.error("设备{} 执行命令{}失败,失败原因{}".format(self.host, str(commands), str(e)))
    
    def close(self):
        """
        关闭SSH连接
        """
        try:
            if hasattr(self, 'ssh_shell') and self.ssh_shell is not None:
                self.ssh_shell.close()
                self.ssh_shell = None
            if hasattr(self, 'client') and self.client is not None:
                self.client.close()
                self.client = None
        except Exception as e:
            logger.warning("{}关闭连接异常, 异常原因{}".format(self.host, str(e)))

    def ping(self):
        if self.ssh_shell:
            ret = self._send_command("  ")
            if not ret:
                self._establish()
        else:
            self._establish()
