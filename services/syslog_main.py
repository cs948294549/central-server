import time

from services.syslog.filter_blacklist import BlacklistManager
from services.syslog.log_merge import MergelistManager
from function_messaging.kafka_client import readDataFromSyslog, sendDataToCollector
import threading
import logging

logger = logging.getLogger(__name__)


class SyslogService:
    def __init__(self, refresh_interval:int=300, time_window:int=300):
        self._refresh_interval = refresh_interval
        self._time_window = time_window
        self.messages = readDataFromSyslog()
        self._handle_thread = None
        self._running = False

    def start(self):
        self._running = True
        self._handle_thread = threading.Thread(
            target=self._handle_syslog,
            args=(),
            daemon=True
        )
        self._handle_thread.start()

    def _handle_syslog(self):
        """
        处理日志，先黑名单筛选，再通过规则聚合
        """
        _blacklist_manager = BlacklistManager(refresh_interval=self._refresh_interval)
        _mergelist_manager = MergelistManager(refresh_interval=self._refresh_interval, time_window=self._time_window)
        for message in self.messages:
            if self._running:
                try:
                    filter_flag = _blacklist_manager.is_blacklisted(message.value)
                    if not filter_flag:
                        new_log = _mergelist_manager.mergeLog(message.value)
                        kafka_msg = {
                            "ip": new_log["ip"],
                            "metric_name": "syslog_data",
                            "status": "ok",
                            "message": "处理成功",
                            "timestamp": int(time.time()),
                            "data": new_log
                        }
                        sendDataToCollector(messages=kafka_msg, key=new_log["ip"])
                except Exception as e:
                    logger.error("failed to handle data to syslog {}; reason:{}".format(str(message), str(e)))
            else:
                break

    def stop(self):
        self._running = False


if __name__ == '__main__':
    pass
    from core.logger import setup_logger
    import random

    logger = setup_logger()
    bl = BlacklistManager(refresh_interval=60)


    ml = MergelistManager(refresh_interval=60, time_window=20)


    log_dict = {}
    with open("syslog/义桥S125完整日志记录.txt", "r") as f:
        while True:
            line = f.readline()
            if not line:
                break
            if line.strip() == "":
                continue
            filter_flag = bl.is_blacklisted({"message": line.strip(), "ip": "1.1.1.1"})
            if not filter_flag:
                new_log = ml.mergeLog({"message": line.strip(), "ip": "1.1.1.1"})
                if new_log["group_label"] not in log_dict:
                    log_dict[new_log["group_label"]] = []
                log_dict[new_log["group_label"]].append(new_log)

    for group_name, logs in log_dict.items():
        print(group_name)
        for log in logs:

            print(log["group_name"],log["keyword"],log["alarm_object"],log["message"])
