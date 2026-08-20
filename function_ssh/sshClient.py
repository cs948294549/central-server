from function_snmp.snmp_collector import common_identify_vendor
import logging
import threading
import time
from typing import Dict, Optional, List, Any

# 导入所有厂商设备类
try:
    from function_ssh.SSHDeviceBase import SSHDeviceBase
    from function_ssh.H3CDevice import H3CDevice
    from function_ssh.HuaweiDevice import HuaweiDevice
    from function_ssh.CiscoNXDevice import CiscoNXDevice
    from function_ssh.CiscoXRDevice import CiscoXRDevice
    from function_ssh.JuniperDevice import JuniperDevice
    from function_ssh.AristaDevice import AristaDevice
    from function_ssh.RuijieDevice import RuijieDevice
    from function_ssh.HillstoneDevice import HillStoneDevice
    from function_ssh.DebianDevice import DebianDevice
except ImportError as e:
    logging.error(f"导入厂商设备类失败: {e}")

from config.config import Config

COMMON_COMMUNITY = Config.snmp_community

logger = logging.getLogger(__name__)

class SSHClientFactory:
    """
    SSH客户端工厂类
    负责创建不同厂商的SSH设备连接实例
    """
    
    # 厂商设备类映射
    VENDOR_CLASS_MAP = {
        'h3c': H3CDevice,
        'huawei': HuaweiDevice,
        'cisco_nx': CiscoNXDevice,
        'cisco_ios': CiscoNXDevice,
        'cisco_xr': CiscoXRDevice,
        'juniper': JuniperDevice,
        'arista': AristaDevice,
        'ruijie': RuijieDevice,
        'hillstone': HillStoneDevice,
        "debian": DebianDevice,
    }
    
    @classmethod
    def create_client(cls, host: str, username: str, password: str, vendor: str='') -> Optional[SSHDeviceBase]:
        """
        创建SSH设备连接实例
        
        Args:
            host: 设备IP地址
            username: 用户名
            password: 密码
            vendor: 厂商
            
        Returns:
            SSHDeviceBase: 设备连接实例，如果创建失败则返回None
        """
        try:
            if vendor == '':
                # 自动识别厂商
                logger.info(f"自动识别设备 {host} 的厂商")
                vendor = cls._identify_vendor(host)
                if not vendor:
                    logger.error(f"无法识别设备 {host} 的厂商")
                    return None

                vendor = vendor.lower()
                logger.info(f"为设备 {host} 创建 {vendor} 连接实例")
            
            # 根据厂商选择对应的设备类
            if vendor in cls.VENDOR_CLASS_MAP:
                device_class = cls.VENDOR_CLASS_MAP[vendor]
                # 只使用3个必要参数初始化
                # time.sleep(10)
                return device_class(host, username, password)
            else:
                logger.error(f"不支持的厂商: {vendor}")
                return None
                
        except Exception as e:
            logger.error(f"创建设备 {host} 连接实例失败: {e}")
            return None
    
    @classmethod
    def _identify_vendor(cls, host: str) -> Optional[str]:
        """
        自动识别设备厂商
        
        Args:
            host: 设备IP地址
            
        Returns:
            str: 厂商名称，如果识别失败则返回None
        """
        try:
            # 使用common_identify_vendor函数识别厂商，只传入ip参数
            vendor = common_identify_vendor(host, COMMON_COMMUNITY)
            return vendor
        except Exception as e:
            logger.error(f"自动识别厂商失败 {host}: {e}")
            return None

# 移除了SSHConnection类，直接在连接池中使用字典存储连接和元数据

class SSHConnectionPool:
    """
    SSH连接池类
    管理设备的SSH连接，限制同一IP最多4个连接
    直接使用字典存储连接和元数据，不再使用SSHConnection中间类
    """
    
    def __init__(self, username:str, password:str, max_connections_per_host: int = 4):
        """
        初始化连接池
        
        Args:
            max_connections_per_host: 每台设备最大连接数
        """
        self.username = username
        self.password = password
        self.max_connections_per_host = max_connections_per_host
        # 使用字典直接存储连接和元数据
        # 格式: {host: [{client: SSHDeviceBase, created_at: float, last_used: float, in_use: bool, usage_count: int, error_count: int}]}
        self.lock = threading.Lock()  # 使用锁
        self.hosts: Dict[str, Optional[Dict[str, Any]]] = {}
    
    def get_connection(self, host: str, vendor: str='', timeout: int = 5) -> Optional[SSHDeviceBase]:
        """
        获取设备连接
        
        Args:
            host: 设备IP地址
            vendor: 厂商型号
            timeout: 获取连接的超时时间（秒）
            
        Returns:
            SSHDeviceBase: 设备连接实例，如果获取失败则返回None
        """
        # 为每个主机创建单独的锁
        conn_name = ""
        is_exsisted = False
        # 新建时，需要锁到属性添加进去
        with self.lock:
            if host not in self.hosts:
                self.hosts[host] = {}
                conn_name = "conn_{}".format(len(self.hosts[host]))
                client_info = {
                    "tid": conn_name,
                    "client": None,
                    "lock": threading.Lock(),
                    "timestamp": int(time.time())
                }
                client_info["lock"].acquire()
                self.hosts[host][conn_name] = client_info
            else:
                is_exsisted = True

        # 当字典存在时，循环读取时，只需要读取时加锁
        if is_exsisted:
            retry = 30
            is_create = False
            while retry > 0:
                retry = retry - 1
                for idx in range(0, self.max_connections_per_host):
                    conn_name = "conn_{}".format(idx)
                    with self.lock:
                        logger.info("循环等待获取连接{}".format(conn_name))
                        if conn_name in self.hosts[host]:
                            if self.hosts[host][conn_name]["lock"].locked():
                                continue
                            else:
                                self.hosts[host][conn_name]["lock"].acquire()
                                return self.hosts[host][conn_name]
                        else:
                            client_info = {
                                "tid": conn_name,
                                "client": None,
                                "lock": threading.Lock(),
                                "timestamp": int(time.time())
                            }
                            client_info["lock"].acquire()
                            self.hosts[host][conn_name] = client_info
                            is_create = True
                            break
                if is_create is True:
                    break
                time.sleep(1)

            if is_create is False:
                return None


        logger.info("更新pool数据完成====user: {} passwd:{}".format(self.username, self.password))
        client = SSHClientFactory.create_client(
            host, self.username, self.password, vendor=vendor
        )
        if client and conn_name != "":
            with self.lock:
                self.hosts[host][conn_name]["client"] = client
                logger.info("新建连接==={} {}".format(str(client), conn_name))
                return self.hosts[host][conn_name]
        else:
            # 创建客户端失败，需要释放锁并清理连接信息
            logger.error(f"创建设备 {host} 的SSH客户端失败，释放锁并清理连接")
            with self.lock:
                if host in self.hosts and conn_name in self.hosts[host]:
                    try:
                        self.hosts[host][conn_name]["lock"].release()
                    except Exception as e:
                        logger.warning(f"释放锁失败: {e}")
                    # 删除失败的连接信息
                    del self.hosts[host][conn_name]
            return None

    def release_connection(self, host: str, conn_name: str):
        with self.lock:
            if host not in self.hosts:
                pass
            else:
                if conn_name in self.hosts[host]:
                    try:
                        self.hosts[host][conn_name]["lock"].release()
                        logger.info("释放连接==={}".format(conn_name))
                    except Exception as e:
                        logger.warning("{}释放连接失败，失败原因{}".format(host, str(e)))

    def disconnect(self, host: str, conn_name: str):
        with self.lock:
            if host not in self.hosts:
                pass
            else:
                if conn_name in self.hosts[host]:
                    try:
                        del self.hosts[host][conn_name]
                        logger.info("删除连接==={}".format(conn_name))
                    except Exception as e:
                        logger.warning("{}删除连接失败，失败原因{}".format(host, str(e)))

    def execute_command(self, host, commands: List[str], vendor: str='') -> Dict[str, str]:
        if not isinstance(commands, list):
            return {"status": "failed", "msg": "命令列表不正确", "data": {}}
        else:
            retry = 0
            while retry<3:
                retry = retry + 1
                client_info = self.get_connection(host=host, vendor=vendor)
                if client_info:
                    # { "tid": conn_name, "client": None, "lock": threading.Lock(),"timestamp": int(time.time())}
                    logger.info("获取连接==={}".format(str(client_info)))
                    client = client_info["client"]
                    logger.info("{}执行命令{}===尝试次数{}= 连接ID=={} {}".format(host, str(commands), retry, str(client), client_info["tid"]))
                    if client:
                        # 过滤空命令
                        filter_commands = []
                        for command in commands:
                            if command.strip() == "":
                                continue
                            filter_commands.append(command.strip())

                        if len(filter_commands) == 0:
                            logger.info("{}执行命令{}为空===尝试次数{}=".format(host, str(commands), retry))
                            self.release_connection(host=host, conn_name=client_info["tid"])
                            return {"status": "success", "msg": "命令列表为空", "data": {}}

                        result = client.exec_commands(filter_commands)
                        if result is None:
                            logger.warning("{}执行命令{}失败,原因未知===尝试次数{}=".format(host, str(filter_commands), retry))
                            self.disconnect(host=host, conn_name=client_info["tid"])
                        elif result == "failed":
                            logger.warning("{}执行命令{}失败,原因数据格式不匹配===尝试次数{}=".format(host, str(filter_commands), retry))
                            self.release_connection(host=host, conn_name=client_info["tid"])
                        else:
                            logger.info("{}执行命令{}成功===尝试次数{}=".format(host, str(filter_commands), retry))
                            if "\n".join(result.values()).strip() == "":
                                logger.info("{}执行命令{}返回结果为空, 重置连接===尝试次数{}=".format(host, str(filter_commands), retry))
                                self.disconnect(host=host, conn_name=client_info["tid"])
                            else:
                                self.release_connection(host=host, conn_name=client_info["tid"])
                                return {"status": "success", "msg": "命令执行成功", "data": result}
                    else:
                        self.disconnect(host=host, conn_name=client_info["tid"])
                time.sleep(1)
            return {"status": "failed", "msg": "命令执行失败", "data": {}}


COMMON_USER = Config.ssh_username
COMMON_PASSWD = Config.ssh_password

# 全局连接池实例
ssh_connection_pool = SSHConnectionPool(username=COMMON_USER, password=COMMON_PASSWD)


def run_ssh_command(host: str, commands: List[str], vendor: str = "") -> Dict[str, Any]:
    """
    采集单个设备的基础信息（向后兼容接口）

    Args:
        host: 设备IP地址
        commands: 待执行的命令列表
        version: SNMP版本（当前版本未使用）

    Returns:
        Dict[str, Any]: 设备基础信息
    """
    if vendor in SSHClientFactory.VENDOR_CLASS_MAP.keys():
        return ssh_connection_pool.execute_command(host=host, vendor=vendor, commands=commands)
    else:
        return ssh_connection_pool.execute_command(host=host, commands=commands)

__all__ = ["run_ssh_command"]

if __name__ == '__main__':
    from core.logger import setup_logger

    logger = setup_logger()


    # at = []
    #
    # t = threading.Thread(target=t1, args=("a1",))
    # t.start()
    # at.append(t)
    # t = threading.Thread(target=t2, args=("a2",))
    # t.start()
    # at.append(t)
    # t = threading.Thread(target=t3, args=("a3",))
    # t.start()
    # at.append(t)
    #
    #
    # for t in at:
    #     t.join()

    # print("======",ConfigLoader.config)
    # t1("a1")
    # t4("a1")
    # aa = SSHClientFactory._identify_vendor("47.98.235.241")
    # print(aa)

    a1 = run_ssh_command(host="10.92.42.60", vendor='huawei', commands=["dis ip int brie"])
    print(a1)



