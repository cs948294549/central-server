import difflib
import re
import logging
from tables.ConfigDB import ConfigDB
from tables.CollectDB import CollectDB
from function_ssh.sshClient import run_ssh_command, SSHClientFactory
from function_snmp.snmp_collector import identify_device_vendor

logger = logging.getLogger(__name__)

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

# 部分厂商输出的配置头部包含采集时间等动态内容（例如NX-OS的
# "!Time: ..."），每次采集都会变化，需要从固定不变的行开始截取，
# 避免配置实际未变化时被误判为有变更
VENDOR_CONFIG_STABLE_START = {
    'cisco_nx': re.compile(r'^version\s'),
}


def _strip_unstable_header(config_content, vendor):
    """
    去除配置头部的动态内容（如采集时间戳），避免配置未变化时被误判为变更
    :param config_content: 原始配置内容
    :param vendor: 设备厂商
    :return: 处理后的配置内容
    """
    pattern = VENDOR_CONFIG_STABLE_START.get(vendor)
    if not pattern:
        return config_content

    lines = config_content.split("\n")
    for idx, line in enumerate(lines):
        if pattern.match(line):
            return "\n".join(lines[idx:])

    # 未找到稳定起始行，原样返回
    return config_content


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
                # 去除部分厂商配置头部的动态内容（如采集时间戳）
                config_content = _strip_unstable_header(config_content, vendor)
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

def save_config_by_opid(ip, op_id):
    """
    根据变更单号采集并保存单台设备的配置（用于变更前后的配置采集）
    :param ip: 设备IP
    :param op_id: 变更单号
    :return: dict {"status": "success/failed", "message": ""}
    """
    result = {"status": "failed", "message": ""}
    try:
        db_collect = CollectDB()
        all_devices = db_collect.get_device_list()

        device = next((d for d in all_devices if d.get("ip") == ip), None)
        if not device:
            result["message"] = f"设备 {ip} 不在设备列表中"
            logger.warning(result["message"])
            return result

        sysname = device.get("sysname", "")
        sysdesc = device.get("sysdesc", "")

        vendor = identify_device_vendor(sysdesc)
        if not vendor or vendor == 'unknown' or vendor not in SSHClientFactory.VENDOR_CLASS_MAP:
            result["message"] = f"无法识别设备厂商或厂商不支持: {vendor}"
            logger.warning(f"设备 {ip}({sysname}) 识别厂商为 {vendor}，不支持采集")
            return result

        config_content = get_device_config(ip, sysname, vendor)
        if not config_content:
            result["message"] = "配置获取失败"
            return result

        db_config = ConfigDB()
        add_result = db_config.add_config({
            "ip": ip,
            "sysname": sysname,
            "dev_type": vendor,
            "detail": config_content,
            "change_id": op_id
        })

        if add_result == "success":
            result["status"] = "success"
            result["message"] = "配置采集成功"
            logger.info(f"设备 {ip}({sysname}) 变更单 {op_id} 配置采集成功")
        else:
            result["message"] = "保存配置失败"
            logger.error(f"设备 {ip}({sysname}) 变更单 {op_id} 保存配置失败")

        return result

    except Exception as e:
        result["message"] = f"配置采集异常: {str(e)}"
        logger.error(f"设备 {ip} 变更单 {op_id} 配置采集异常: {e}")
        return result

def get_config_list_by_device(data):
    """
    获取设备的配置备份列表
    :param data: {"ip": "xxx"} 或 {"sysname": "xxx"}
    :return: 配置列表，字段直接来自数据库，格式化(时间/备份类型等)交由前端处理
    """
    try:
        db = ConfigDB()
        config_list = db.get_config_list(data)

        if config_list == "failed":
            return []

        return config_list

    except Exception as e:
        logger.error(f"获取配置列表失败: {e}")
        return []


def get_config_detail_by_id(log_id):
    """
    根据log_id获取配置详情
    :param log_id: 配置记录ID
    :return: 配置详情
    """
    try:
        db = ConfigDB()
        config_detail = db.get_config_detail(log_id)

        if config_detail:
            # 格式化时间
            if config_detail.get("created_at"):
                import time
                timestamp = int(config_detail["created_at"])
                config_detail["backup_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

            return config_detail
        else:
            return None

    except Exception as e:
        logger.error(f"获取配置详情失败: {e}")
        return None


def compare_configs_by_id(src_id, tar_id, full_diff=False):
    """
    对比两个配置文件
    :param src_id: 源配置ID
    :param tar_id: 目标配置ID
    :param full_diff: 是否显示完整对比（True）还是上下文对比（False）
    :return: HTML格式的diff结果
    """
    try:
        # 获取两个配置
        db_src = ConfigDB()
        src_config = db_src.get_config_detail(src_id)

        db_tar = ConfigDB()
        tar_config = db_tar.get_config_detail(tar_id)

        if not src_config or not tar_config:
            logger.error("配置不存在")
            return {"html": "", "stats": {"added": 0, "deleted": 0, "modified": 0}}

        src_content = src_config.get("detail", "")
        tar_content = tar_config.get("detail", "")

        # 执行对比
        diff_result = check_diff(src_content, tar_content, full_diff)

        # 统计变更
        stats = calculate_diff_stats(src_content, tar_content)

        return {
            "html": diff_result,
            "stats": stats,
            "src_info": {
                "log_id": src_config.get("log_id"),
                "ip": src_config.get("ip"),
                "sysname": src_config.get("sysname"),
                "created_at": src_config.get("backup_time", "")
            },
            "tar_info": {
                "log_id": tar_config.get("log_id"),
                "ip": tar_config.get("ip"),
                "sysname": tar_config.get("sysname"),
                "created_at": tar_config.get("backup_time", "")
            }
        }

    except Exception as e:
        logger.error(f"配置对比失败: {e}")
        return {"html": "", "stats": {"added": 0, "deleted": 0, "modified": 0}}


def check_diff(text_src, text_target, full_diff=False):
    """
    生成配置文件的diff HTML
    :param text_src: 源配置文本
    :param text_target: 目标配置文本
    :param full_diff: 是否显示完整对比
    :return: HTML字符串
    """
    try:
        # 按行分割
        src_lines = text_src.split("\n")
        tar_lines = text_target.split("\n")

        # 使用difflib生成HTML diff
        hd = difflib.HtmlDiff()

        if full_diff:
            # 完整对比
            diff = hd.make_file(src_lines, tar_lines,
                              fromdesc='源配置', todesc='目标配置',
                              context=False)
        else:
            # 上下文对比，只显示变更附近的5行
            diff = hd.make_file(src_lines, tar_lines,
                              fromdesc='源配置', todesc='目标配置',
                              context=True, numlines=5)

        # 优化样式
        diff = diff.replace(
            "table.diff {font-family:Courier; border:medium;}",
            "table.diff {font-family:Courier; border:medium; width: 100%; font-size: 13px;}"
        ).replace(
            "td.diff_header {text-align:right}",
            "td.diff_header {text-align:right; width: 50px; background-color: #f5f5f5;}\n"
            "td {word-break:break-all; text-align: left; padding: 2px 5px;}"
        ).replace(
            " nowrap=\"nowrap\"", ""
        )

        return diff

    except Exception as e:
        logger.error(f"生成diff失败: {e}")
        return "<p>对比失败</p>"


def calculate_diff_stats(text_src, text_target):
    """
    计算diff统计信息
    :param text_src: 源文本
    :param text_target: 目标文本
    :return: {"added": 新增行数, "deleted": 删除行数, "modified": 修改行数}
    """
    try:
        src_lines = text_src.split("\n")
        tar_lines = text_target.split("\n")

        # 使用SequenceMatcher计算差异
        matcher = difflib.SequenceMatcher(None, src_lines, tar_lines)

        added = 0
        deleted = 0
        modified = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                # 修改的行
                modified += max(i2 - i1, j2 - j1)
            elif tag == 'delete':
                # 删除的行
                deleted += i2 - i1
            elif tag == 'insert':
                # 新增的行
                added += j2 - j1

        return {
            "added": added,
            "deleted": deleted,
            "modified": modified
        }

    except Exception as e:
        logger.error(f"计算diff统计失败: {e}")
        return {"added": 0, "deleted": 0, "modified": 0}


def delete_config_by_id(log_id):
    """
    根据log_id删除配置记录
    :param log_id: 配置记录ID
    :return: "success" 或 "failed"
    """
    try:
        db = ConfigDB()
        result = db.delete_config(log_id)
        return result
    except Exception as e:
        logger.error(f"删除配置记录失败: {e}")
        return "failed"


