from lib_ssh.sshClient import run_ssh_command
from utils.threadPool import execAllFunctions

from core.logger import setup_logger
logger = setup_logger()

iplist = ["172.19.1.21","172.19.1.22",]
tasks = []
for ip in iplist:
    tasks.append({"name":"{}".format(ip), "func": run_ssh_command, "args":None, "kwargs": {"host":ip, "vendor":"cisco_nx", "commands": ["conf t",'ntp server 10.1.1.9', 'end', "copy run start"]}})

all_results = execAllFunctions(tasks, max_workers=8)

for item in all_results:
    print(item)
    print(all_results[item])