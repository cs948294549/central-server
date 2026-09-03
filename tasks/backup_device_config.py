"""
设备配置备份定时任务

功能：定时备份网络设备配置
- 从设备列表(devices)获取设备信息
- 通过SSH连接设备执行 show run / display current 命令
- 计算配置MD5哈希值，与上次备份对比
- 配置有变化：插入新记录
- 配置无变化：更新最后采集时间

使用方式：
1. 作为定时任务：在 tasks/task_manager.py 中配置 cron 表达式（每晚22点执行）
2. 单独运行：python3 tasks/backup_device_config.py
"""
import logging
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tables.CollectDB import CollectDB
from tables.ConfigDB import ConfigDB
from function_ssh.sshClient import run_ssh_command, SSHClientFactory
from function_snmp.snmp_collector import identify_device_vendor
from config.config import Config

logger = logging.getLogger(__name__)

# 任务配置
TASK_CONFIG = {
    "enabled": True,  # 是否启用任务
    "max_workers": 10,  # 并发线程数
    "timeout": 60,  # SSH连接超时时间（秒）
}

# 不同厂商的配置查询命令映射
VENDOR_CONFIG_COMMANDS = {
    'h3c': ['display current-configuration'],
    'huawei': ['display current-configuration'],
    'cisco_nx': ['show running-config'],
    'cisco_ios': ['show running-config'],
    'cisco_xr': ['show running-config'],
    'juniper': ['show configuration'],
    'arista': ['show running-config'],
    'ruijie': ['show running-config'],
}


def get_device_list():
    """
    从数据库获取设备列表

    Returns:
        list: 设备列表，每个设备包含 ip, sysname, sys_type, sysdesc 等信息
    """
    try:
        logger.info("开始获取设备列表...")
        db = CollectDB()
        # 获取所有非屏蔽设备（admin_status <> '1'）
        devices = db.get_device_list()

        if not devices:
            logger.warning("获取设备列表失败或为空")
            return []

        logger.info(f"成功获取 {len(devices)} 台设备")
        return devices

    except Exception as e:
        logger.error(f"获取设备列表异常: {e}")
        return []




def get_device_config(ip, sysname, vendor):
    """
    通过SSH获取设备配置

    Args:
        ip: 设备IP
        sysname: 设备名称
        vendor: 设备厂商

    Returns:
        str: 配置内容，失败返回None
    """
    try:
        # 获取配置命令
        commands = VENDOR_CONFIG_COMMANDS.get(vendor)
        if not commands:
            logger.warning(f"设备 {ip}({sysname}) 不支持的厂商: {vendor}")
            return None

        # 执行SSH命令
        logger.debug(f"连接设备 {ip}({sysname}) - {vendor}")
        result = run_ssh_command(host=ip, commands=commands, vendor=vendor)

        if result.get("status") == "success":
            data = result.get("data", {})
            if data and len(data) > 0:
                # 合并多个命令的输出
                config_content = '\n'.join(data.values())
                logger.info(f"设备 {ip}({sysname}) 配置获取成功，大小: {len(config_content)} 字节")
                return config_content
            else:
                logger.error(f"设备 {ip}({sysname}) 配置获取失败，命令无输出")
                return None
        else:
            logger.error(f"设备 {ip}({sysname}) SSH执行失败: {result.get('msg')}")
            return None

    except Exception as e:
        logger.error(f"设备 {ip}({sysname}) 配置获取异常: {e}")
        return None


def backup_device(device):
    """
    备份单台设备配置

    Args:
        device: 设备信息字典

    Returns:
        dict: 备份结果 {"ip": "", "status": "success/failed", "message": ""}
    """
    ip = device.get("ip")
    sysname = device.get("sysname", "")
    sysdesc = device.get("sysdesc", "")

    result = {
        "ip": ip,
        "sysname": sysname,
        "status": "failed",
        "message": ""
    }

    try:
        # 通过 sysdesc 识别厂商
        vendor = identify_device_vendor(sysdesc)

        if not vendor or vendor == 'unknown' or vendor not in SSHClientFactory.VENDOR_CLASS_MAP:
            result["message"] = f"无法识别设备厂商或厂商不支持: {vendor}"
            logger.warning(f"设备 {ip}({sysname}) 识别厂商为 {vendor}，不支持备份")
            return result

        # 获取设备配置
        config_content = get_device_config(ip, sysname, vendor)
        if not config_content:
            result["message"] = "配置获取失败"
            return result

        # 计算配置哈希值
        config_hash = ConfigDB.calculate_config_hash(config_content)

        # 查询最新配置记录
        db_config = ConfigDB()
        latest_config = db_config.get_latest_config(ip)

        if latest_config:
            # 计算上次配置的哈希值
            latest_hash = ConfigDB.calculate_config_hash(latest_config.get("detail", ""))

            if config_hash == latest_hash:
                # 配置无变化，只更新时间（需要新建数据库对象）
                db_config_update = ConfigDB()
                update_result = db_config_update.update_config_time(latest_config["log_id"])
                if update_result == "success":
                    result["status"] = "success"
                    result["message"] = "配置无变化，已更新时间"
                    logger.info(f"设备 {ip}({sysname}) 配置无变化")
                else:
                    result["message"] = "更新时间失败"
                    logger.error(f"设备 {ip}({sysname}) 更新时间失败")
            else:
                # 配置有变化，插入新记录（需要新建数据库对象）
                db_config_add = ConfigDB()
                add_result = db_config_add.add_config({
                    "ip": ip,
                    "sysname": sysname,
                    "dev_type": vendor,
                    "detail": config_content,
                    "change_id": None
                })
                if add_result == "success":
                    result["status"] = "success"
                    result["message"] = "配置有变化，已保存新记录"
                    logger.info(f"设备 {ip}({sysname}) 配置已变化，保存新记录")
                else:
                    result["message"] = "保存配置失败"
                    logger.error(f"设备 {ip}({sysname}) 保存配置失败")
        else:
            # 首次备份，插入新记录（需要新建数据库对象）
            db_config_new = ConfigDB()
            add_result = db_config_new.add_config({
                "ip": ip,
                "sysname": sysname,
                "dev_type": vendor,
                "detail": config_content,
                "change_id": None
            })
            if add_result == "success":
                result["status"] = "success"
                result["message"] = "首次备份成功"
                logger.info(f"设备 {ip}({sysname}) 首次备份成功")
            else:
                result["message"] = "首次备份失败"
                logger.error(f"设备 {ip}({sysname}) 首次备份失败")

    except Exception as e:
        result["message"] = f"备份异常: {str(e)}"
        logger.error(f"设备 {ip}({sysname}) 备份异常: {e}")

    return result


def run():
    """
    主执行函数 - 并发备份所有设备配置

    执行流程：
    1. 从数据库获取设备列表
    2. 使用线程池并发备份设备
    3. 统计备份结果
    """
    if not TASK_CONFIG["enabled"]:
        logger.info("配置备份任务已禁用")
        return

    logger.info("=" * 60)
    logger.info("开始执行设备配置备份任务")
    logger.info("=" * 60)

    start_time = time.time()

    # 获取设备列表
    devices = get_device_list()
    if not devices:
        logger.warning("没有需要备份的设备")
        return

    total_count = len(devices)
    logger.info(f"准备备份 {total_count} 台设备，并发数: {TASK_CONFIG['max_workers']}")

    # 使用线程池并发备份
    success_count = 0
    failed_count = 0
    no_change_count = 0
    changed_count = 0
    failed_devices = []  # 记录失败的设备详情

    with ThreadPoolExecutor(max_workers=TASK_CONFIG["max_workers"]) as executor:
        futures = {executor.submit(backup_device, device): device for device in devices}

        for future in as_completed(futures):
            device = futures[future]
            try:
                result = future.result(timeout=TASK_CONFIG["timeout"])
                if result["status"] == "success":
                    success_count += 1
                    if "无变化" in result["message"]:
                        no_change_count += 1
                    else:
                        changed_count += 1
                else:
                    failed_count += 1
                    # 记录失败设备的详细信息
                    failed_devices.append({
                        "ip": result["ip"],
                        "sysname": result["sysname"],
                        "reason": result["message"]
                    })
                    logger.warning(f"设备备份失败: {result['ip']}({result['sysname']}) - {result['message']}")

            except Exception as e:
                failed_count += 1
                device_ip = device.get('ip', 'unknown')
                device_name = device.get('sysname', 'unknown')
                failed_devices.append({
                    "ip": device_ip,
                    "sysname": device_name,
                    "reason": f"任务异常: {str(e)}"
                })
                logger.error(f"设备 {device_ip} 备份任务异常: {e}")

    elapsed_time = time.time() - start_time

    logger.info("=" * 60)
    logger.info("设备配置备份任务完成")
    logger.info(f"总设备数: {total_count}")
    logger.info(f"成功: {success_count} (配置有变化: {changed_count}, 无变化: {no_change_count})")
    logger.info(f"失败: {failed_count}")
    logger.info(f"耗时: {elapsed_time:.2f} 秒")

    # 输出失败设备详情
    if failed_devices:
        logger.info("-" * 60)
        logger.info("失败设备详情：")
        for idx, dev in enumerate(failed_devices, 1):
            logger.info(f"  {idx}. {dev['ip']} ({dev['sysname']}) - {dev['reason']}")

    logger.info("=" * 60)


if __name__ == "__main__":
    # 单独运行时的配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/config_backup.log')
        ]
    )

    try:
        run()
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("\n任务被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        sys.exit(1)
