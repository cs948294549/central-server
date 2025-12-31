from typing import Dict, Any, List, Optional, Tuple
import re
import logging
import threading
import json
import time
from hashlib import sha1,md5
from function_messaging.redis_client import get_redis_client
from services.syslog import MergeRule, get_mergelisted_entries

logger = logging.getLogger(__name__)

local_red = get_redis_client()

class MergelistManager:
    def __init__(self, refresh_interval: int = 300, time_window:int=300):
        self._mergelist = []  # 黑名单条目列表
        self._mergelist_lock = threading.RLock()
        self._last_refresh_time = None
        self._refresh_thread = None
        self._stop_event = threading.Event()
        self._refresh_interval=refresh_interval
        self._timeWindow=time_window


        # 初始化方法
        status = self._initialize()
        if not status:
            raise RuntimeError("Failed to initialize mergelist")

    def _initialize(self):
        try:
            self._refresh_mergelist()
            if self._refresh_interval > 0:
                self._start_mergelist_refresh_thread(self._refresh_interval)
            logger.info(f"Mergelist manager initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize mergelist manager: {e}")
            return False

    def _refresh_mergelist(self):
        mergelisted_entries = get_mergelisted_entries()

        # 更新分组名单
        with self._mergelist_lock:
            self._mergelist = mergelisted_entries
            self._last_refresh_time = int(time.time())

        logger.info(f"Mergelist refreshed, loaded {len(mergelisted_entries)} entries")

    def _start_mergelist_refresh_thread(self, interval: int):
        """
        启动分组单刷新线程

        Args:
            interval: 刷新间隔（秒）
        """
        self._stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=self._mergelist_refresh_loop,
            args=(interval,),
            daemon=True
        )
        self._refresh_thread.start()

    def _mergelist_refresh_loop(self, interval: int):
        """
        分组名单刷新循环

        Args:
            interval: 刷新间隔（秒）
        """
        while not self._stop_event.is_set():
            try:
                # 等待指定的间隔时间
                if self._stop_event.wait(timeout=interval):
                    break

                # 刷新黑名单
                self._refresh_mergelist()

            except Exception as e:
                logger.error(f"Error in mergelist refresh loop: {e}")
                # 出错后等待较短时间再重试
                time.sleep(min(interval, 60))

    def mergeLog(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查消息是否在黑名单中
        强识别的字段 ip,message
        会补全 group_name, keyword,
        Args:
            message: 要检查的消息

        Returns:
            是否在黑名单中
        """
        with self._mergelist_lock:
            mergelist_entries = self._mergelist.copy()

        timeWindow = self._timeWindow

        timestamp = int(time.time()/timeWindow)
        ip = message.get('ip', '-')
        # 提取关键字
        reg_keyword = re.compile(r"%{1,2}(\S+):")
        keyword_find = reg_keyword.findall(str(message["message"]))
        if len(keyword_find) > 0:
            keyword = keyword_find[0]
        else:
            keyword = message.get("keyword", "-")

        # 提取设备名
        reg_hostname = re.compile(r"(\S+)\s+%{1,2}")
        hostname_find = reg_hostname.findall(str(message["message"]))
        if len(hostname_find) > 0:
            hostname = hostname_find[0]
        else:
            hostname = message.get("hostname", "-")

        # 提取识别对象
        alarmObject = message.get("alarm_object", "-")
        PROT_REGEXS = [
            "\S+(?:\d+/)+\d+",
            "\S+Aggregation\d+",
            "\S+interface\d+",
            "\S*tunnel\d+",
            "ae\d+",
            "\S+Trunk\d+",
            "Tunnel\d+",
            "Vlanif\d+",
            "vlan\d+"
        ]
        PORT_REGEX = re.compile("|".join(PROT_REGEXS))
        prot_find = PORT_REGEX.findall(str(message["message"]))
        if len(prot_find) > 0:
            alarmObject = prot_find[0]

        group_name = "-"
        # 要检查的字段
        for entry in mergelist_entries:
            if entry.matches(str(message["message"])):
                entry.increase()
                logger.debug(
                    f"Message matched by pattern '{entry.pattern}'")
                group_name = entry.group_name
                break
        if group_name == "-":
            # 识别分组
            group_key = "{}.{}.{}.{}".format(ip, timestamp, keyword, alarmObject)
            last_group_key = "{}.{}.{}.{}".format(ip, str(timestamp-1), keyword, alarmObject)
        else:
            group_key = "{}.{}.{}.{}".format(ip, timestamp, group_name, alarmObject)
            last_group_key = "{}.{}.{}.{}".format(ip, str(timestamp - 1), group_name, alarmObject)

        # 缓存及更新聚合key
        hash_group_key = md5(group_key.encode("utf-8")).hexdigest()
        hash_last_group_key = md5(last_group_key.encode("utf-8")).hexdigest()

        current_key = local_red.get(hash_group_key)
        if current_key:
            current_key_entry = current_key.decode("utf-8", "ignore")
            return {
                "message": message["message"],
                "ip": ip,
                "hostname": hostname,
                "alarm_type": "syslog",
                "keyword": keyword,
                "alarm_object": alarmObject,
                "group_name": group_name,
                "group_label": current_key_entry

            }
        else:
            last_key = local_red.get(hash_last_group_key)
            if last_key:
                last_key_entry = last_key.decode("utf-8", "ignore")
                local_red.set(hash_group_key, last_key_entry, ex=timeWindow * 2)
                return {
                    "message": message["message"],
                    "ip": ip,
                    "hostname": hostname,
                    "alarm_type": "syslog",
                    "keyword": keyword,
                    "alarm_object": alarmObject,
                    "group_name": group_name,
                    "group_label": last_key_entry
                }
            else:
                local_red.set(hash_group_key, hash_group_key, ex=timeWindow * 2)
                return {
                    "message": message["message"],
                    "ip": ip,
                    "hostname": hostname,
                    "alarm_type": "syslog",
                    "keyword": keyword,
                    "alarm_object": alarmObject,
                    "group_name": group_name,
                    "group_label": hash_group_key
                }

    def get_mergelisted_entries(self) -> List[MergeRule]:
        return self._mergelist

if __name__ == '__main__':
    from core.logger import setup_logger
    logger = setup_logger()


    bl = MergelistManager()


    log_dict = {}
    with open("义桥S125完整日志记录.txt", "r") as f:
        while True:
            line = f.readline()
            if not line:
                break
            if line.strip()=="":
                continue
            new_log = bl.mergeLog({"message": line.strip(), "ip":"1.1.1.1"})
            if new_log["group_name"] not in log_dict:
                log_dict[new_log["group_name"]] = []
            log_dict[new_log["group_name"]].append(new_log)

    with open("test.log", "w") as f:
        json.dump(log_dict, f, ensure_ascii=False, indent=4)