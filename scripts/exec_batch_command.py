from lib_ssh.sshClient import run_ssh_command
from utils.threadPool import execAllFunctions

from core.logger import setup_logger
logger = setup_logger()

def exec_task():
    iplist = ["172.19.1.21","172.19.1.22",]
    tasks = []
    for ip in iplist:
        tasks.append({"name":"{}".format(ip), "func": run_ssh_command, "args":None, "kwargs": {"host":ip, "vendor":"cisco_nx", "commands": ["conf t",'ntp server 10.1.1.9', 'end', "copy run start"]}})

    all_results = execAllFunctions(tasks, max_workers=8)

    for item in all_results:
        print(item)
        print(all_results[item])


if __name__ == '__main__':
    cfgs = {'21': ['42'], '22': ['39'], '23': ['2'], '24': ['36', '37', '30', '34', '39', '33', '43', '41', '28', '45', '32', '44'], '32': ['39'], '34': ['28', '30', '34', '36', '38', '40', '42', '32']}

    for key, value in cfgs.items():
        ip = "172.19.2.{}".format(key)
        vendor = "cisco_nx"

        for p in value:
            "eth1/{}".format(p)
        "interface "
        commands = ["conf t",'ntp server 10.1.1.9', 'copy run start']