from lib_ssh.sshClient import run_ssh_command
from utils.threadPool import execAllFunctions

from core.logger import setup_logger
logger = setup_logger()

def exec_task():
    iplist = ["172.19.2.21","172.19.2.22","172.19.2.23","172.19.2.24","172.19.2.25","172.19.2.26","172.19.2.27","172.19.2.28","172.19.2.31","172.19.2.32","172.19.2.33","172.19.2.34","172.19.2.35","172.19.2.36","172.19.2.37","172.19.2.38",]


    tasks = []
    for ip in iplist:
        tasks.append({"name":"{}".format(ip), "func": run_ssh_command, "args":None, "kwargs": {"host":ip, "vendor":"cisco_nx", "commands": ["conf t",'errdisable recovery interval 300', 'errdisable recovery cause link-flap','end', "copy run start"]}})

    all_results = execAllFunctions(tasks, max_workers=8)

    for item in all_results:
        print(item)
        print(all_results[item])


if __name__ == '__main__':
    exec_task()