#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU指标处理策略
"""

from services.dataStrategy import DataStrategy
import logging
from tables.AlarmDB import AlarmDB
import time

logger = logging.getLogger(__name__)

class SyslogStrategy(DataStrategy):
    """
    CPU指标处理策略
    """
    
    # 指标名称
    metric_name = "syslog_data"
    
    def process_data(self, data):
        """
        处理日志数据
        {
            "ip": new_log["ip"],
            "metric_name": "syslog_data",
            "status": "ok",
            "message": "处理成功",
            "timestamp": int(time.time()),
            "data": new_log
        }
        new_log: {
            "message": message["message"],
            "ip": ip,
            "hostname": hostname,
            "keyword": keyword,
            "alarm_object": alarmObject,
            "group_name": group_name,
            "group_label": hash_group_key
        }
        Args:
            data: 日志数据
            
        Returns:
            处理后的CPU指标数据
        """
        try:
            logger.info(f"开始处理syslog指标数据: {data}")
            
            # 数据预处理
            syslog_dt = data.get("data", {})
            timestamp = data.get("timestamp", int(time.time()))
            db = AlarmDB()
            ret = db.addAlarmList({
                "ip": syslog_dt["ip"],
                "hostname": syslog_dt["hostname"],
                "alarm_type": syslog_dt["alarm_type"],
                "group_label": syslog_dt["group_label"],
                "msg": syslog_dt["message"],
                "group_name": syslog_dt["group_name"],
                "alarm_object": syslog_dt["alarm_object"],
                "keyword": syslog_dt["keyword"],
                "create_time":timestamp
            })
            if ret!="failed":
                logger.info(f"syslog指标数据处理完成: {ret}")
                return True
            else:
                logger.error("failed to handle syslog {}; reason:{}".format(str(ret), str(data)))
                return False
            
        except Exception as e:
            logger.error(f"处理syslog指标数据失败: {e}")
            return False