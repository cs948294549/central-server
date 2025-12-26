import time

from services.syslog.filter_blacklist import BlacklistManager
from services.syslog.log_merge import MergelistManager
from function_messaging.kafka_client import readDataFromSyslog, sendDataToCollector
import json
import threading



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
                            "data": [new_log]
                        }
                        sendDataToCollector(messages=kafka_msg, key=new_log["ip"])
                except Exception as e:
                    logger.error("failed to handle data to syslog {}; reason:{}".format(str(message), str(e)))
            else:
                break

    def stop(self):
        self._running = False


if __name__ == '__main__':
    from core.logger import setup_logger
    import random

    logger = setup_logger()
    bl = BlacklistManager(refresh_interval=60)


    ml = MergelistManager(refresh_interval=60, time_window=20)


    # log_dict = {}
    # with open("义桥S125完整日志记录.txt", "r") as f:
    #     while True:
    #         line = f.readline()
    #         if not line:
    #             break
    #         if line.strip() == "":
    #             continue
    #         filter_flag = bl.is_blacklisted({"message": line.strip(), "ip": "1.1.1.1"})
    #         if not filter_flag:
    #             status, new_log = ml.mergeLog({"message": line.strip(), "ip": "1.1.1.1"})
    #             if new_log["group_name"] not in log_dict:
    #                 log_dict[new_log["group_name"]] = []
    #             log_dict[new_log["group_name"]].append(new_log)
    #
    # for group_name, logs in log_dict.items():
    #     print(group_name)
    #     for log in logs:
    #         print(log["message"])
    messages=[
        "%Jan  1 08:42:00:457 2011 vrrp-test-2 %%IFNET/3/PHY_UPDOWN: Bridge-Aggregation51 link status is up.",
        "%Jan  1 08:42:00:460 2011 vrrp-test-2 %%IFNET/5/LINK_UPDOWN: Line protocol on the interface Bridge-Aggregation51 is up.",
        "%Jan  1 08:42:00:542 2011 vrrp-test-2 %%IFNET/3/PHY_UPDOWN: Bridge-Aggregation51 link status is down.",
        "%Jan  1 08:42:00:543 2011 vrrp-test-2 %%IFNET/5/LINK_UPDOWN: Line protocol on the interface Bridge-Aggregation51 is down.",
        "%Jan  1 08:42:01:791 2011 vrrp-test-2 %%IFNET/3/PHY_UPDOWN: Bridge-Aggregation51 link status is up.",
        "%Jan  1 08:42:01:792 2011 vrrp-test-2 %%IFNET/5/LINK_UPDOWN: Line protocol on the interface Bridge-Aggregation51 is up.",
        "%Jan  1 08:43:25:522 2011 vrrp-test-2 %%IFNET/3/PHY_UPDOWN: Bridge-Aggregation51 link status is down.",
        "%Jan  1 08:43:25:524 2011 vrrp-test-2 %%IFNET/5/LINK_UPDOWN: Line protocol on the interface Bridge-Aggregation51 is down.",
        "%Jan  1 08:43:32:025 2011 vrrp-test-2 %%IFNET/3/PHY_UPDOWN: Bridge-Aggregation51 link status is up.",
        "%Jan  1 08:43:32:028 2011 vrrp-test-2 %%IFNET/5/LINK_UPDOWN: Line protocol on the interface Bridge-Aggregation51 is up."
    ]
    log_dict = {}
    while True:
        for message in messages:
            filter_flag = bl.is_blacklisted({"message": message.strip(), "ip": "1.1.1.1"})
            if not filter_flag:
                new_log = ml.mergeLog({"message": message.strip(), "ip": "1.1.1.1"})
                if new_log["group_name"] not in log_dict:
                    log_dict[new_log["group_name"]] = []
                log_dict[new_log["group_name"]].append(new_log)
        print(log_dict.keys())
        time.sleep(random.randint(15, 30))