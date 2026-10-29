"""
设备配置备份定时任务

功能：定时备份网络设备配置
- 从设备列表(devices)获取设备信息
- 通过SSH连接设备执行 show run / display current 命令
- 计算配置MD5哈希值，与上次备份对比
- 配置有变化：插入新记录
- 配置无变化：更新最后采集时间

使用方式：
1. 作为定时任务：在 config/task_config.yaml 中配置任务和参数
2. 单独运行（备份所有设备）：python3 tasks/backup_device_config.py
3. 单独运行（备份指定设备）：通过 kwargs 传递 filter_ips 参数
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
from function_collector.func_config import backup_config_by_ip

logger = logging.getLogger(__name__)

# ============================================
# 任务配置
# ============================================

# 任务配置
TASK_CONFIG = {
    "enabled": True,  # 是否启用任务
    "max_workers": 10,  # 并发线程数
    "timeout": 60,  # SSH连接超时时间（秒）
}


def get_device_list(filter_ips=None):
    """
    从数据库获取设备列表

    Args:
        filter_ips: IP地址列表，如果提供则只返回这些IP的设备

    Returns:
        list: 设备列表，每个设备包含 ip, sysname, sys_type, sysdesc 等信息
    """
    try:
        logger.info("开始获取设备列表...")
        db = CollectDB()
        # 获取所有非屏蔽设备（admin_status <> '1'）
        all_devices = db.get_device_list()

        if not all_devices:
            logger.warning("获取设备列表失败或为空")
            return []

        # 如果指定了过滤IP，则只返回匹配的设备
        if filter_ips:
            filtered_devices = [d for d in all_devices if d.get('ip') in filter_ips]
            logger.info(f"根据IP过滤后，获取 {len(filtered_devices)} 台设备（总共 {len(all_devices)} 台）")

            # 检查哪些IP没有找到
            found_ips = {d.get('ip') for d in filtered_devices}
            not_found_ips = set(filter_ips) - found_ips
            if not_found_ips:
                logger.warning(f"以下IP在设备列表中未找到: {', '.join(not_found_ips)}")

            return filtered_devices
        else:
            logger.info(f"成功获取 {len(all_devices)} 台设备")
            return all_devices

    except Exception as e:
        logger.error(f"获取设备列表异常: {e}")
        return []

def backup_device(device):
    """
    备份单台设备配置

    Args:
        device: 设备信息字典

    Returns:
        dict: 备份结果 {"ip": "", "sysname": "", "status": "success/failed", "message": "", "changed": bool}
    """
    ip = device.get("ip")
    sysname = device.get("sysname", "")

    result = {
        "ip": ip,
        "sysname": sysname,
        "status": "failed",
        "message": "",
        "changed": False
    }

    try:
        # 调用通用备份方法
        backup_result = backup_config_by_ip(ip)

        result["message"] = backup_result.get("message", "")
        if backup_result.get("success"):
            result["status"] = "success"
            result["changed"] = backup_result.get("data", {}).get("changed", False)

    except Exception as e:
        result["message"] = f"备份异常: {str(e)}"
        logger.error(f"设备 {ip}({sysname}) 备份异常: {e}")

    return result

def run(filter_ips=None):
    """
    主执行函数 - 并发备份所有设备配置

    Args:
        filter_ips: IP地址列表，如果提供则只备份这些IP的设备，否则备份所有设备

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
    devices = get_device_list(filter_ips)
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
                    if result["changed"]:
                        changed_count += 1
                    else:
                        no_change_count += 1
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
        filter_ips = ["172.25.1.104","172.25.1.114"]

        run(filter_ips=filter_ips)
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("\n任务被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        sys.exit(1)
