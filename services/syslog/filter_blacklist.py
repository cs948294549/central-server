from typing import Dict, Any, List, Optional, Set
import re
import logging
import threading
import json
import time

logger = logging.getLogger(__name__)


class BlacklistEntry:
    """
    黑名单条目
    """

    def __init__(self, entry_id: str, pattern: str, description: str = None):
        """
        初始化黑名单条目

        Args:
            entry_id: 条目ID
            pattern: 匹配模式（正则表达式）
            description: 描述
        """
        self.id = entry_id
        self.pattern = pattern
        self.description = description
        self._matched_sum = 0
        self._compiled_pattern = None

        try:
            self._compiled_pattern = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern}': {e}")

    def matches(self, text: str) -> bool:
        """
        检查文本是否匹配该黑名单条目

        Args:
            text: 要检查的文本

        Returns:
            是否匹配
        """
        if not text:
            return False
        return bool(self._compiled_pattern.search(text))

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            字典表示
        """
        return {
            'id': self.id,
            'pattern': self.pattern,
            'description': self.description,
            'matched_sum': self._matched_sum,
        }

    def increase(self):
        self._matched_sum += 1

def get_blacklisted_entries() -> List[BlacklistEntry]:
    with open("services/syslog/syslog_config.json", "r") as f:
        config = json.loads(f.read())
        black_list = config.get("black_list", [])
        blacklisted_entries = []
        for blacklisted_entry in black_list:
            entry = BlacklistEntry(
                entry_id=blacklisted_entry.get('id', ''),
                pattern=blacklisted_entry.get('pattern', ''),
                description=blacklisted_entry.get('description', '')
            )
            blacklisted_entries.append(entry)
        return blacklisted_entries

class BlacklistManager:
    def __init__(self, refresh_interval: int=300) -> None:
        self._blacklist = []  # 黑名单条目列表
        self._blacklist_lock = threading.RLock()
        self._last_refresh_time = None
        self._refresh_thread = None
        self._stop_event = threading.Event()
        self._refresh_interval=refresh_interval

        # 初始化方法
        self._initialize()


    def _initialize(self):
        try:
            self._refresh_blacklist()
            if self._refresh_interval > 0:
                self._start_blacklist_refresh_thread(self._refresh_interval)
            logger.info(f"Blacklist manager initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize blacklist manager: {e}")
            return False

    def _refresh_blacklist(self):
        blacklisted_entries = get_blacklisted_entries()

        # 更新黑名单
        with self._blacklist_lock:
            self._blacklist = blacklisted_entries
            self._last_refresh_time = int(time.time())

        logger.info(f"Blacklist refreshed, loaded {len(blacklisted_entries)} entries")

    def _start_blacklist_refresh_thread(self, interval: int):
        """
        启动黑名单刷新线程

        Args:
            interval: 刷新间隔（秒）
        """
        self._stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=self._blacklist_refresh_loop,
            args=(interval,),
            daemon=True
        )
        self._refresh_thread.start()

    def _blacklist_refresh_loop(self, interval: int):
        """
        黑名单刷新循环

        Args:
            interval: 刷新间隔（秒）
        """
        while not self._stop_event.is_set():
            try:
                # 等待指定的间隔时间
                if self._stop_event.wait(timeout=interval):
                    break

                # 刷新黑名单
                self._refresh_blacklist()

            except Exception as e:
                logger.error(f"Error in blacklist refresh loop: {e}")
                # 出错后等待较短时间再重试
                time.sleep(min(interval, 60))

    def is_blacklisted(self, message: Dict[str, Any]) -> bool:
        """
        检查消息是否在黑名单中

        Args:
            message: 要检查的消息

        Returns:
            是否在黑名单中
        """
        with self._blacklist_lock:
            blacklist_entries = self._blacklist.copy()

        # 要检查的字段
        check_fields = ['message', 'host', 'program', 'raw']

        for entry in blacklist_entries:
            if entry.matches(str(message["message"])):
                entry.increase()
                logger.debug(
                    f"Message blacklisted by pattern '{entry.pattern}'")
                return True

        return False

    def get_blacklisted_entries(self) -> List[BlacklistEntry]:
        return self._blacklist



if __name__ == '__main__':
    from core.logger import setup_logger
    logger = setup_logger()


    bl = BlacklistManager()

    log_list = [
        {"message": "2025-12-23 15:49:02 - core.app - INFO - Request: OPTIONS /system/change_passwd Status: 200"},
        {"message": '2025-12-23 15:49:02 - werkzeug - INFO - 183.159.48.32 - - [23/Dec/2025 15:49:02] [INFO] [IP: 183.159.48.32] "OPTIONS /system/change_passwd HTTP/HTTP/1.0" 200 -'},
        {"message": '2025-12-23 15:49:02 - core.app - INFO - 用户demo demo访问接口/system/change_passwd'},
        {"message": '2025-12-23 15:49:02 - core.app - INFO - Request: POST /system/change_passwd Status: 200'},
        {"message": '2025-12-23 15:49:02 - werkzeug - INFO - 183.159.48.32 - - [23/Dec/2025 15:49:02] [INFO] [IP: 183.159.48.32] "POST /system/change_passwd HTTP/HTTP/1.0" 200 -'},
        {"message": '2025-12-23 15:49:13 - core.app - INFO - Request: OPTIONS /system/login Status: 200'},
        {"message": '2025-12-23 15:49:13 - werkzeug - INFO - 183.159.48.32 - - [23/Dec/2025 15:49:13] [INFO] [IP: 183.159.48.32] "OPTIONS /system/login HTTP/HTTP/1.0" 200 -'},
        {"message": '2025-12-23 15:49:13 - core.app - INFO - Request: POST /system/login Status: 200'},
        {"message": '2025-12-23 15:49:13 - werkzeug - INFO - 183.159.48.32 - - [23/Dec/2025 15:49:13] [INFO] [IP: 183.159.48.32] "POST /system/login HTTP/HTTP/1.0" 200 -'},
        {"message": '2025-12-23 15:49:13 - core.app - INFO - Request: OPTIONS /system/get_route_list Status: 200'},
    ]
    for msg in log_list:
        if bl.is_blacklisted(msg):
            logger.info(f"Message blacklisted by pattern '{msg}'")

    for entry in bl.get_blacklisted_entries():
        print(entry.to_dict())
    # while True:
    #
    #     for msg in log_list:
    #         if bl.is_blacklisted(msg):
    #             print("日志内容:", msg['message'])
    #             print("状态:", bl.is_blacklisted(msg))
    #
    #     for entry in bl.get_blacklisted_entries():
    #         print(entry.to_dict())
    #     time.sleep(10)
