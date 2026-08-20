"""
IPAM地址更新定时任务

功能：从采集数据库中读取网关和ARP信息，更新到IPAM地址表
- 从网关表(gates)提取网关IP地址
- 从ARP表(arps)提取已使用的IP地址
- 批量写入IPAM地址表(ipam_ipaddr)

参照 snmpcollector/cron_ipam_address_update.py 实现

使用方式：
1. 作为定时任务：在 tasks/task_manager.py 中配置 cron 表达式
2. 单独运行：python3 tasks/update_ipam_address.py
"""
import logging
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tables.CollectDB import CollectDB
from tables.IpamDB import IpamDB
from utils.ipaddr import ip2decimalism

logger = logging.getLogger(__name__)


# 任务配置
TASK_CONFIG = {
    "batch_size": 200,  # 批量写入大小
    "enabled": True,    # 是否启用任务
}


def list_split(items, n):
    """将列表分割成每n个元素一组"""
    return [items[i:i + n] for i in range(0, len(items), n)]


def run():
    """
    主执行函数 - 更新IPAM地址信息

    执行流程：
    1. 从采集数据库读取网关信息
    2. 从采集数据库读取ARP信息
    3. 转换为IPAM地址格式
    4. 批量写入IPAM数据库
    """
    if not TASK_CONFIG["enabled"]:
        logger.info("IPAM地址更新任务已禁用")
        return

    logger.info("开始执行IPAM地址更新任务")

    try:
        # 使用字典按ip_deci去重，记录所有来源
        # ip_dict: {ip_deci: {"ip_addr": "x.x.x.x", "sources": [{"type": "gateway/arp", "device": "x.x.x.x", "mac": "xx:xx:xx:xx:xx:xx"}]}}
        ip_dict = {}

        # 1. 处理网关信息
        logger.info("读取网关信息...")
        db_collector = CollectDB()
        gate_data = db_collector.get_gate_v4_list({})

        if gate_data == "failed":
            logger.error("读取网关信息失败")
            gate_data = []

        for gate_item in gate_data:
            gateway = gate_item.get("gateway", "")
            device_ip = gate_item.get("ip", "")  # 设备IP
            if not gateway or not device_ip:
                continue

            try:
                ip_deci = ip2decimalism(gateway)

                # 初始化或获取已有记录
                if ip_deci not in ip_dict:
                    ip_dict[ip_deci] = {
                        "ip_addr": gateway,
                        "sources": []
                    }

                # 添加网关来源信息
                ip_dict[ip_deci]["sources"].append({
                    "type": "gateway",
                    "device": device_ip
                })
            except Exception as e:
                logger.error(f"处理网关 {gateway} 失败: {e}")

        logger.info(f"处理网关信息完成，共 {len([s for s in ip_dict.values() if any(src['type']=='gateway' for src in s['sources'])])} 个网关IP")

        # 2. 处理ARP信息
        logger.info("读取ARP信息...")
        db_collector = CollectDB()
        arp_data = db_collector.get_arp_list({})

        if arp_data == "failed":
            logger.error("读取ARP信息失败")
            arp_data = []

        arp_count = 0
        for arp_item in arp_data:
            arp_ip = arp_item.get("arp_ip", "")
            arp_mac = arp_item.get("arp_mac", "")
            device_ip = arp_item.get("ip", "")  # 设备IP

            # 过滤无效MAC地址
            if arp_mac == "00:00:00:00:00:00" or not arp_mac or not device_ip:
                continue

            try:
                ip_deci = ip2decimalism(arp_ip)

                # 初始化或获取已有记录
                if ip_deci not in ip_dict:
                    ip_dict[ip_deci] = {
                        "ip_addr": arp_ip,
                        "sources": []
                    }

                # 添加ARP来源信息
                ip_dict[ip_deci]["sources"].append({
                    "type": "arp",
                    "device": device_ip,
                    "mac": arp_mac
                })
                arp_count += 1
            except Exception as e:
                logger.error(f"处理ARP记录 {arp_ip} 失败: {e}")

        logger.info(f"处理ARP信息完成，共 {arp_count} 条ARP记录")

        # 3. 转换为待写入格式
        log_ipaddrs = []
        for ip_deci, ip_info in ip_dict.items():
            ip_addr = ip_info["ip_addr"]
            sources = ip_info["sources"]

            # 分类统计来源
            gateway_sources = [s for s in sources if s["type"] == "gateway"]
            arp_sources = [s for s in sources if s["type"] == "arp"]

            # 确定主要类型
            if gateway_sources:
                collect_type = "gateway"
            else:
                collect_type = "arp"

            # 构建comment信息，确保不超过300字符
            comment_parts = []

            # 添加网关来源信息
            if gateway_sources:
                devices = [s["device"] for s in gateway_sources]
                if len(devices) == 1:
                    comment_parts.append(f"gw:{devices[0]}")
                elif len(devices) <= 3:
                    comment_parts.append(f"gw:{','.join(devices)}")
                else:
                    comment_parts.append(f"gw:{','.join(devices[:2])}...(+{len(devices)-2})")

            # 添加ARP来源信息
            if arp_sources:
                if len(arp_sources) == 1:
                    s = arp_sources[0]
                    comment_parts.append(f"arp:{s['device']}({s['mac']})")
                elif len(arp_sources) <= 2:
                    devices_info = [f"{s['device']}({s['mac']})" for s in arp_sources]
                    comment_parts.append(f"arp:{','.join(devices_info)}")
                else:
                    # ARP来源过多时只显示数量和第一个
                    s = arp_sources[0]
                    comment_parts.append(f"arp:{s['device']}({s['mac']})...(+{len(arp_sources)-1})")

            comment = "; ".join(comment_parts)

            # 确保不超过300字符
            if len(comment) > 300:
                comment = comment[:297] + "..."

            log_ipaddrs.append({
                "ip_deci": ip_deci,
                "ip_addr": ip_addr,
                "collect_type": collect_type,
                "comment": comment
            })

        logger.info(f"合并处理完成，共 {len(log_ipaddrs)} 个唯一IP地址")

        # 3. 批量写入IPAM数据库
        total_count = len(log_ipaddrs)
        if total_count == 0:
            logger.warning("没有需要更新的IP地址")
            return

        logger.info(f"准备写入IPAM数据库，共 {total_count} 条记录")

        # 分批写入
        batch_size = TASK_CONFIG["batch_size"]
        split_datas = list_split(log_ipaddrs, batch_size)
        success_batches = 0
        failed_batches = 0

        for i, batch in enumerate(split_datas, 1):
            try:
                db_ipam = IpamDB()
                result = db_ipam.add_ipaddr_batch(batch)
                if result == "success":
                    success_batches += 1
                    logger.info(f"批次 {i}/{len(split_datas)}: 成功写入 {len(batch)} 条记录")
                else:
                    failed_batches += 1
                    logger.error(f"批次 {i}/{len(split_datas)}: 写入失败")
            except Exception as e:
                failed_batches += 1
                logger.error(f"批次 {i}/{len(split_datas)}: 写入异常 - {e}")

        logger.info(f"IPAM地址更新任务完成 - 总记录数: {total_count}, 成功批次: {success_batches}, 失败批次: {failed_batches}")

    except Exception as e:
        logger.error(f"IPAM地址更新任务执行失败: {e}")
        raise


if __name__ == "__main__":
    # 单独运行时的配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/ipam_update.log')
        ]
    )

    logger.info("=" * 60)
    logger.info("手动触发IPAM地址更新任务")
    logger.info("=" * 60)

    try:
        run()
        logger.info("=" * 60)
        logger.info("任务执行成功")
        logger.info("=" * 60)
    except KeyboardInterrupt:
        logger.info("\n任务被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        logger.info("=" * 60)
        sys.exit(1)

