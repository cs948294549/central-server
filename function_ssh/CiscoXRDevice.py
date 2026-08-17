from function_ssh.SSHDeviceBase import SSHDeviceBase
import re
import logging

logger = logging.getLogger(__name__)

class CiscoXRDevice(SSHDeviceBase):
    def __init__(self, host, username, password):
        init_prompt = re.compile(r"[a-zA-Z0-9_()/:.+-]+?#$")

        self.error_prompts = [
            "at '^' marker",
            "Incomplete command",
            "authorization failed"
        ]
        self.next_prompts = []

        super().__init__(host, username, password, port=22, connect_timeout=15, timeout=10, init_prompt=init_prompt)

    def _set_terminal(self):
        ret = self._send_command(f"terminal length 0")
        if ret:
            prompt, detail = ret
            if prompt is False:
                raise ValueError("{} 执行terminal length 0 失败, 回显{}".format(self.host, detail))

    def _new_terminal(self):
        reg_init = re.compile(r"[a-zA-Z0-9_()/:.+-]+?#$")
        reg_enable = re.compile(r"[a-zA-Z0-9_()/:.+-]+?\(config.*?\)#$")
        status_init = reg_init.findall(self.current_prompt)
        status_enable = reg_enable.findall(self.current_prompt)
        while len(status_init) == 1 and len(status_enable) == 1:
            logger.debug("设备{} 当前游标位置{}".format(self.host, self.current_prompt))
            self._send_command("end")
            status_init = reg_init.findall(self.current_prompt)
            status_enable = reg_enable.findall(self.current_prompt)


    def _send_command(self, command):
        logger.info("设备{} 配置-执行命令{}".format(self.host, command))
        self.ssh_shell.sendall((command + "\n").encode('utf-8'))
        reg_prompt = re.compile(r"[a-zA-Z0-9_()/:.+-]+?#$")
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
                        if cmd_cache.strip().endswith("]?"):
                            self.ssh_shell.sendall("\n".encode("utf-8", "ignore"))
                        if cmd_cache.strip().endswith("yes/no]:"):
                            if command in ["exit","end"]:
                                self.ssh_shell.sendall("no\n".encode("utf-8", "ignore"))
                            else:
                                self.ssh_shell.sendall("yes\n".encode("utf-8", "ignore"))
                else:
                    break
            except Exception as e:
                logger.warning("设备{} 执行失败, 执行命令 {}， 失败原因{}".format(self.host, command, str(e)))
                break
