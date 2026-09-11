"""
前缀列表配置采集定时任务

功能：定时采集网络设备的前缀列表配置
- 从设备列表(devices)获取设备信息
- 获取设备最新配置并解析前缀列表
- 计算配置指纹并更新到数据库
- 支持增量更新（先删除旧记录再插入新记录）

使用方式：
1. 作为定时任务：在 config/task_config.yaml 中配置任务和参数
2. 单独运行（采集所有设备）：python3 tasks/collect_prefix_lists.py
3. 单独运行（采集指定设备）：通过 kwargs 传递 filter_ips 参数
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
from function_policy.func_prefix import collect_and_update_prefix_lists

logger = logging.getLogger(__name__)

# ============================================
# 任务配置
# ============================================

TASK_CONFIG = {
    "enabled": True,  # 是否启用任务
    "max_workers": 10,  # 并发线程数
    "timeout": 120,  # 单个设备处理超时时间（秒）
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


def collect_device_prefix_lists(device):
    """
    采集单台设备的前缀列表配置

    Args:
        device: 设备信息字典

    Returns:
        dict: 采集结果 {"ip": "", "sysname": "", "status": "success/failed", "message": "", "data": {}}
    """
    ip = device.get("ip")
    sysname = device.get("sysname", "")

    result = {
        "ip": ip,
        "sysname": sysname,
        "status": "failed",
        "message": "",
        "data": {}
    }

    try:
        logger.info(f"开始采集设备 {ip}({sysname}) 的前缀列表配置")

        # 调用采集和更新方法
        collect_result = collect_and_update_prefix_lists(ip)

        if collect_result.get("success"):
            result["status"] = "success"
            result["message"] = collect_result.get("message", "采集成功")
            result["data"] = collect_result.get("data", {})

            # 提取统计信息
            prefix_lists_info = collect_result.get("data", {}).get("prefix_lists", {})
            inserted = prefix_lists_info.get("inserted", 0)
            failed = prefix_lists_info.get("failed", 0)

            logger.info(f"设备 {ip}({sysname}) 采集成功: 插入 {inserted} 条，失败 {failed} 条")
        else:
            result["message"] = collect_result.get("message", "采集失败")
            logger.warning(f"设备 {ip}({sysname}) 采集失败: {result['message']}")

    except Exception as e:
        result["message"] = f"采集异常: {str(e)}"
        logger.error(f"设备 {ip}({sysname}) 采集异常: {e}")

    return result


def run(filter_ips=None):
    """
    主执行函数 - 并发采集所有设备的前缀列表配置

    Args:
        filter_ips: IP地址列表，如果提供则只采集这些IP的设备，否则采集所有设备

    执行流程：
    1. 从数据库获取设备列表
    2. 使用线程池并发采集设备
    3. 统计采集结果
    """
    if not TASK_CONFIG["enabled"]:
        logger.info("前缀列表采集任务已禁用")
        return

    logger.info("=" * 60)
    logger.info("开始执行前缀列表配置采集任务")
    logger.info("=" * 60)

    start_time = time.time()

    # 获取设备列表
    devices = get_device_list(filter_ips)
    if not devices:
        logger.warning("没有需要采集的设备")
        return

    total_count = len(devices)
    logger.info(f"准备采集 {total_count} 台设备，并发数: {TASK_CONFIG['max_workers']}")

    # 使用线程池并发采集
    success_count = 0
    failed_count = 0
    total_inserted = 0
    total_failed = 0
    failed_devices = []  # 记录失败的设备详情

    with ThreadPoolExecutor(max_workers=TASK_CONFIG["max_workers"]) as executor:
        futures = {executor.submit(collect_device_prefix_lists, device): device for device in devices}

        for future in as_completed(futures):
            device = futures[future]
            try:
                result = future.result(timeout=TASK_CONFIG["timeout"])
                if result["status"] == "success":
                    success_count += 1
                    # 累计统计信息
                    prefix_info = result.get("data", {}).get("prefix_lists", {})
                    total_inserted += prefix_info.get("inserted", 0)
                    total_failed += prefix_info.get("failed", 0)
                else:
                    failed_count += 1
                    # 记录失败设备的详细信息
                    failed_devices.append({
                        "ip": result["ip"],
                        "sysname": result["sysname"],
                        "reason": result["message"]
                    })
                    logger.warning(f"设备采集失败: {result['ip']}({result['sysname']}) - {result['message']}")

            except Exception as e:
                failed_count += 1
                device_ip = device.get('ip', 'unknown')
                device_name = device.get('sysname', 'unknown')
                failed_devices.append({
                    "ip": device_ip,
                    "sysname": device_name,
                    "reason": f"执行超时或异常: {str(e)}"
                })
                logger.error(f"设备 {device_ip}({device_name}) 采集任务异常: {e}")

    # 计算耗时
    elapsed_time = time.time() - start_time

    # 输出统计结果
    logger.info("=" * 60)
    logger.info("前缀列表配置采集任务完成")
    logger.info(f"总设备数: {total_count}")
    logger.info(f"成功: {success_count} 台")
    logger.info(f"失败: {failed_count} 台")
    logger.info(f"插入前缀列表配置: {total_inserted} 条")
    logger.info(f"插入失败: {total_failed} 条")
    logger.info(f"总耗时: {elapsed_time:.2f} 秒")
    logger.info("=" * 60)

    # 如果有失败设备，输出详细信息
    if failed_devices:
        logger.warning("以下设备采集失败：")
        for fd in failed_devices:
            logger.warning(f"  - {fd['ip']}({fd['sysname']}): {fd['reason']}")


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 执行任务
    # 示例1：采集所有设备
    run()

    # 示例2：采集指定设备
    # run(filter_ips=['172.24.250.11'])
