import pymysql
from config import Config

mysql_cfg = Config.mysql_config

class mysqldb_netops:
    def __init__(self):
        self.conn = pymysql.connect(host=mysql_cfg["db_host"], user=mysql_cfg["db_user"],
                                    password=mysql_cfg["db_token"],
                                    port=mysql_cfg["db_port"],
                                    database="netops", charset="utf8")
        self.cursor = self.conn.cursor()

    def ping(self):
        self.conn.ping(reconnect=True)
        self.cursor = self.conn.cursor()


