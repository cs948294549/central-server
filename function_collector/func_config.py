import difflib
import re
import logging
from tables.ConfigDB import ConfigDB

logger = logging.getLogger(__name__)


def get_config_list_by_device(data):
    """
    获取设备的配置备份列表
    :param data: {"ip": "xxx"} 或 {"sysname": "xxx"}
    :return: 配置列表
    """
    try:
        db = ConfigDB()
        config_list = db.get_config_list(data)

        if config_list == "failed":
            return []

        # 处理返回数据，添加格式化字段
        for config in config_list:
            # 格式化时间
            if config.get("created_at"):
                import time
                timestamp = int(config["created_at"])
                config["backup_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
            else:
                config["backup_time"] = ""

            # 计算文件大小（如果有detail字段）
            if "detail" in config:
                size_bytes = len(config["detail"].encode('utf-8'))
                config["file_size"] = format_file_size(size_bytes)
                # 移除detail字段，减少数据传输
                del config["detail"]
            else:
                config["file_size"] = "-"

            # 备份类型（可以根据change_id判断）
            if config.get("change_id"):
                config["backup_type"] = "变更"
                config["note"] = f"变更单号: {config['change_id']}"
            else:
                config["backup_type"] = "自动"
                config["note"] = "定期自动备份"

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


def format_file_size(size_bytes):
    """
    格式化文件大小
    :param size_bytes: 字节数
    :return: 格式化后的大小字符串
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


