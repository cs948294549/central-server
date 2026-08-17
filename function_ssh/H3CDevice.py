from function_ssh.SSHDeviceBase import SSHDeviceBase
import re
import logging

logger = logging.getLogger(__name__)

class H3CDevice(SSHDeviceBase):
    def __init__(self, host, username, password):
        init_prompt = re.compile(r"<(.+?)>$")

        self.error_prompts = [
            "found at '^' position",
            "Permission denied"
        ]
        self.next_prompts = [
            "[Y/N]"
        ]

        super().__init__(host, username, password, port=22, connect_timeout=15, timeout=10, init_prompt=init_prompt)

    def _set_terminal(self):
        ret = self._send_command(f"screen disable")
        if ret:
            prompt, detail = ret
            if prompt is False:
                raise ValueError("{} 执行screen disable 失败, 回显{}".format(self.host, detail))

    def _new_terminal(self):
        status = self.init_prompt.findall(self.current_prompt)
        while len(status) == 0:
            logger.debug("设备{} 当前游标位置{}".format(self.host, self.current_prompt))
            self._send_command("return")
            status = self.init_prompt.findall(self.current_prompt)


    def _send_command(self, command):
        logger.info("设备{} 配置-执行命令{}".format(self.host, command))
        self.ssh_shell.sendall((command + "\n").encode('utf-8'))
        reg_prompt = re.compile(r"(?:^<.*?>$)|(?:^\[.*?]$)")
        cmd_cache = ''
        while True:
            try:
                line = self.ssh_shell.recv(30000)
                if line:
                    cmd_cache += line.decode("utf-8", "ignore").replace("\r", "")
                    last_line = cmd_cache.strip().split("\n")[-1]
                    prompt = reg_prompt.findall(last_line)
                    if len(prompt) > 0:
                        self.current_prompt = prompt[0]
                        cmd_cache = cmd_cache.replace(self.current_prompt, "")
                        for error_prompt in self.error_prompts:
                            if error_prompt in cmd_cache:
                                return False, cmd_cache.strip()
                        return prompt[0], cmd_cache.strip()
                    else:
                        for next_prompt in self.next_prompts:
                            if next_prompt in cmd_cache:
                                if command in ["quit", "return"]:
                                    self.ssh_shell.sendall("n\n".encode("utf-8", "ignore"))
                                else:
                                    self.ssh_shell.sendall("y\n".encode("utf-8", "ignore"))
                else:
                    break
            except Exception as e:
                logger.warning("设备{} 执行失败, 执行命令 {}， 失败原因{}".format(self.host, command, str(e)))
                break
