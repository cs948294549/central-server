from daos.database import mysqldb_netops
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

'''
Wi-Fi 地图数据库操作
对应表：wifi_ac、wifi_ap、wifi_radio、wifi_ssid、wifi_client、wifi_map、wifi_map_ap
建表见 scripts/db_wifi.sql，设计见 docs/wifi_map_design.md

AP / 射频 / SSID / 终端四张快照表由 projects/collector 采集写入，这里只读；
AC 与地图相关的表在这里维护。SQL 一律参数化，不再经过 waf 转义。
连接在 finally 中关闭，每个实例只能调用一次方法。
'''


class WifiDB(mysqldb_netops):
    """Wi-Fi 数据库操作类"""

    # ==================== AC ====================

    def getAcList(self):
        """
        AC 列表，带 AP 数
        :return: 列表数据或"failed"
        """
        try:
            fields = ["ac_id", "ac_name", "vendor", "model", "mgmt_ip", "community", "last_status", "ap_count"]
            sql = """SELECT a.ac_id, a.ac_name, a.vendor, a.model, a.mgmt_ip, a.community, a.last_status,
                     COUNT(p.ap_mac)
                     FROM wifi_ac a LEFT JOIN wifi_ap p ON p.ac_id = a.ac_id
                     GROUP BY a.ac_id ORDER BY a.ac_id"""
            self.cursor.execute(sql)
            return [dict(zip(fields, row)) for row in self.cursor.fetchall()]

        except Exception as err:
            logger.error("======WifiDB getAcList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getAcById(self, ac_id):
        """
        按 ID 取单个 AC（含 community 明文）
        :return: 字典 / None / "failed"
        """
        try:
            fields = ["ac_id", "ac_name", "vendor", "model", "mgmt_ip", "community", "last_status"]
            sql = """SELECT ac_id, ac_name, vendor, model, mgmt_ip, community, last_status
                     FROM wifi_ac WHERE ac_id = %s"""
            self.cursor.execute(sql, (ac_id,))
            row = self.cursor.fetchone()
            return dict(zip(fields, row)) if row else None

        except Exception as err:
            logger.error("======WifiDB getAcById error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def checkAcExists(self, ac_name, mgmt_ip, exclude_id=0):
        """
        检查 AC 名称 / 管理 IP 是否已被其它 AC 占用
        :return: "name" / "ip" / "" / "failed"
        """
        try:
            sql = "SELECT ac_name, mgmt_ip FROM wifi_ac WHERE (ac_name = %s OR mgmt_ip = %s) AND ac_id <> %s"
            self.cursor.execute(sql, (ac_name, mgmt_ip, exclude_id or 0))
            for row in self.cursor.fetchall():
                if row[0] == ac_name:
                    return "name"
                if row[1] == mgmt_ip:
                    return "ip"
            return ""

        except Exception as err:
            logger.error("======WifiDB checkAcExists error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def createAc(self, data):
        """
        新增 AC
        :param data: {ac_name, vendor, mgmt_ip, model, community}
        :return: 新 ac_id 或"failed"
        """
        try:
            sql = """INSERT INTO wifi_ac (ac_name, vendor, mgmt_ip, model, community, last_status)
                     VALUES (%s, %s, %s, %s, %s, 'unknown')"""
            self.cursor.execute(sql, (data["ac_name"], data["vendor"], data["mgmt_ip"],
                                      data.get("model", ""), data.get("community", "")))
            self.conn.commit()
            return self.cursor.lastrowid

        except Exception as err:
            logger.error("======WifiDB createAc error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateAc(self, data):
        """
        修改 AC；data 不带 community 时保留原值
        :param data: {ac_id, ac_name, vendor, mgmt_ip, model, community?}
        :return: 影响行数或"failed"
        """
        try:
            sets = ["ac_name = %s", "vendor = %s", "mgmt_ip = %s", "model = %s"]
            params = [data["ac_name"], data["vendor"], data["mgmt_ip"], data.get("model", "")]
            if "community" in data.keys():
                sets.append("community = %s")
                params.append(data["community"])
            params.append(data["ac_id"])

            sql = "UPDATE wifi_ac SET " + ", ".join(sets) + " WHERE ac_id = %s"
            self.cursor.execute(sql, tuple(params))
            self.conn.commit()
            return self.cursor.rowcount

        except Exception as err:
            logger.error("======WifiDB updateAc error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def deleteAc(self, ac_id):
        """
        删除 AC，级联删除地图图标、终端、SSID、射频、AP（同一事务）
        :return: 删除的 AC 行数或"failed"
        """
        try:
            self.cursor.execute("""DELETE FROM wifi_map_ap
                                   WHERE ap_mac IN (SELECT ap_mac FROM wifi_ap WHERE ac_id = %s)""", (ac_id,))
            self.cursor.execute("DELETE FROM wifi_client WHERE ac_id = %s", (ac_id,))
            self.cursor.execute("DELETE FROM wifi_ssid WHERE ac_id = %s", (ac_id,))
            self.cursor.execute("DELETE FROM wifi_radio WHERE ac_id = %s", (ac_id,))
            self.cursor.execute("DELETE FROM wifi_ap WHERE ac_id = %s", (ac_id,))
            self.cursor.execute("DELETE FROM wifi_ac WHERE ac_id = %s", (ac_id,))
            count = self.cursor.rowcount
            self.conn.commit()
            return count

        except Exception as err:
            logger.error("======WifiDB deleteAc error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateAcStatus(self, ac_id, status):
        """
        回写 AC 采集状态
        :return: 影响行数或"failed"
        """
        try:
            sql = "UPDATE wifi_ac SET last_status = %s WHERE ac_id = %s"
            self.cursor.execute(sql, (status, ac_id))
            self.conn.commit()
            return self.cursor.rowcount

        except Exception as err:
            logger.error("======WifiDB updateAcStatus error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getApCountByAc(self, ac_id):
        """
        AC 下 AP 数
        :return: 整数或"failed"
        """
        try:
            self.cursor.execute("SELECT COUNT(*) FROM wifi_ap WHERE ac_id = %s", (ac_id,))
            return self.cursor.fetchone()[0]

        except Exception as err:
            logger.error("======WifiDB getApCountByAc error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== 地图 ====================

    def getMapList(self):
        """
        地图列表，不带底图，按建筑 + 排序号排序
        :return: 列表数据或"failed"
        """
        try:
            fields = ["map_id", "map_name", "building", "sort_num", "ap_count", "has_image"]
            sql = """SELECT m.map_id, m.map_name, m.building, m.sort_num,
                     (SELECT COUNT(*) FROM wifi_map_ap a WHERE a.map_id = m.map_id),
                     m.image_base64 <> ''
                     FROM wifi_map m ORDER BY m.building, m.sort_num, m.map_id"""
            self.cursor.execute(sql)
            rows = []
            for row in self.cursor.fetchall():
                item = dict(zip(fields, row))
                item["has_image"] = bool(item["has_image"])
                rows.append(item)
            return rows

        except Exception as err:
            logger.error("======WifiDB getMapList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getMapDetail(self, map_id):
        """
        单张地图，带底图 base64
        :return: 字典 / None / "failed"
        """
        try:
            fields = ["map_id", "map_name", "building", "sort_num", "image_base64",
                      "image_width", "image_height", "version"]
            sql = """SELECT map_id, map_name, building, sort_num, image_base64,
                     image_width, image_height, version
                     FROM wifi_map WHERE map_id = %s"""
            self.cursor.execute(sql, (map_id,))
            row = self.cursor.fetchone()
            return dict(zip(fields, row)) if row else None

        except Exception as err:
            logger.error("======WifiDB getMapDetail error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def checkMapName(self, map_name, exclude_id=0):
        """
        地图名称是否已被其它地图占用（map_name 全局唯一）
        :return: True / False / "failed"
        """
        try:
            sql = "SELECT COUNT(*) FROM wifi_map WHERE map_name = %s AND map_id <> %s"
            self.cursor.execute(sql, (map_name, exclude_id or 0))
            return self.cursor.fetchone()[0] > 0

        except Exception as err:
            logger.error("======WifiDB checkMapName error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def createMap(self, data):
        """
        新增地图
        :param data: {map_name, building, sort_num, image_base64, image_width, image_height}
        :return: 新 map_id 或"failed"
        """
        try:
            sql = """INSERT INTO wifi_map (map_name, building, sort_num, image_base64, image_width, image_height, version)
                     VALUES (%s, %s, %s, %s, %s, %s, 1)"""
            self.cursor.execute(sql, (data["map_name"], data.get("building", ""), data.get("sort_num", 0),
                                      data["image_base64"], data.get("image_width", 0), data.get("image_height", 0)))
            self.conn.commit()
            return self.cursor.lastrowid

        except Exception as err:
            logger.error("======WifiDB createMap error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def updateMapInfo(self, data):
        """
        修改地图属性，版本号 +1；data 带 image_base64 时同时替换底图与宽高
        :param data: {map_id, map_name, building, sort_num, image_base64?, image_width?, image_height?}
        :return: 影响行数或"failed"
        """
        try:
            sets = ["map_name = %s", "building = %s", "sort_num = %s", "version = version + 1"]
            params = [data["map_name"], data.get("building", ""), data.get("sort_num", 0)]
            if data.get("image_base64"):
                sets += ["image_base64 = %s", "image_width = %s", "image_height = %s"]
                params += [data["image_base64"], data.get("image_width", 0), data.get("image_height", 0)]
            params.append(data["map_id"])

            sql = "UPDATE wifi_map SET " + ", ".join(sets) + " WHERE map_id = %s"
            self.cursor.execute(sql, tuple(params))
            self.conn.commit()
            return self.cursor.rowcount

        except Exception as err:
            logger.error("======WifiDB updateMapInfo error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def saveMapLayout(self, map_id, version, markers, image_width=0, image_height=0):
        """
        保存布局（version 乐观锁）：整图替换 wifi_map_ap，版本号 +1；宽高都大于 0 时一并更新
        :param markers: [{ap_mac, x_ratio, y_ratio, display_name}]
        :return: 新版本号 / "notfound" / "conflict" / "failed"
        """
        try:
            self.cursor.execute("SELECT version FROM wifi_map WHERE map_id = %s FOR UPDATE", (map_id,))
            row = self.cursor.fetchone()
            if not row:
                self.conn.rollback()
                return "notfound"
            if int(row[0]) != int(version):
                self.conn.rollback()
                return "conflict"

            self.cursor.execute("DELETE FROM wifi_map_ap WHERE map_id = %s", (map_id,))
            if markers:
                sql = """INSERT INTO wifi_map_ap (map_id, ap_mac, x_ratio, y_ratio, display_name)
                         VALUES (%s, %s, %s, %s, %s)"""
                self.cursor.executemany(sql, [(map_id, m["ap_mac"], m["x_ratio"], m["y_ratio"],
                                               m.get("display_name", "")) for m in markers])

            if image_width > 0 and image_height > 0:
                self.cursor.execute("""UPDATE wifi_map SET version = version + 1, image_width = %s, image_height = %s
                                       WHERE map_id = %s""", (image_width, image_height, map_id))
            else:
                self.cursor.execute("UPDATE wifi_map SET version = version + 1 WHERE map_id = %s", (map_id,))
            self.conn.commit()
            return int(row[0]) + 1

        except Exception as err:
            logger.error("======WifiDB saveMapLayout error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def deleteMap(self, map_id):
        """
        删除地图及其图标（同一事务，不删 AP 数据）
        :return: 删除的地图行数或"failed"
        """
        try:
            self.cursor.execute("DELETE FROM wifi_map_ap WHERE map_id = %s", (map_id,))
            self.cursor.execute("DELETE FROM wifi_map WHERE map_id = %s", (map_id,))
            count = self.cursor.rowcount
            self.conn.commit()
            return count

        except Exception as err:
            logger.error("======WifiDB deleteMap error========\n{}".format(str(err)))
            self.conn.rollback()
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getMapMarkers(self, map_id):
        """
        地图上的图标，带 AP 当前状态；AP 已不存在时状态记为 unknown
        :return: 列表数据或"failed"
        """
        try:
            fields = ["ap_mac", "display_name", "x_ratio", "y_ratio", "ap_name",
                      "online_status", "client_count", "last_seen_at"]
            sql = """SELECT m.ap_mac, m.display_name, m.x_ratio, m.y_ratio,
                     COALESCE(a.ap_name, ''), COALESCE(a.online_status, 'unknown'),
                     COALESCE(a.client_count, 0), COALESCE(a.last_seen_at, '')
                     FROM wifi_map_ap m LEFT JOIN wifi_ap a ON a.ap_mac = m.ap_mac
                     WHERE m.map_id = %s ORDER BY m.ap_mac"""
            self.cursor.execute(sql, (map_id,))
            rows = []
            for row in self.cursor.fetchall():
                item = dict(zip(fields, row))
                item["x_ratio"] = float(item["x_ratio"]) if isinstance(item["x_ratio"], Decimal) else item["x_ratio"]
                item["y_ratio"] = float(item["y_ratio"]) if isinstance(item["y_ratio"], Decimal) else item["y_ratio"]
                rows.append(item)
            return rows

        except Exception as err:
            logger.error("======WifiDB getMapMarkers error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # ==================== AP ====================

    def getApList(self, data=None):
        """
        AP 列表，带所属 AC 名称，支持条件筛选
        :param data: {
            "ap_name" / "ap_mac" / "ap_ip" / "sn" / "model" / "ap_group" / "sw_version": 模糊匹配,
            "ac_id": 所属 AC,
            "online_status": online / offline / unknown,
        }
        :return: 列表数据或"failed"
        """
        try:
            data = data or {}
            conditions = []
            params = []

            # 文本字段统一模糊匹配，字段名白名单拼进 SQL，值走参数
            for field in ["ap_name", "ap_mac", "ap_ip", "sn", "model", "ap_group", "sw_version"]:
                value = str(data.get(field) or "").strip()
                if value:
                    conditions.append("a." + field + " LIKE %s")
                    params.append("%" + value + "%")

            ac_id = int(data.get("ac_id") or 0)
            if ac_id:
                conditions.append("a.ac_id = %s")
                params.append(ac_id)

            online_status = str(data.get("online_status") or "").strip().lower()
            if online_status in ["online", "offline", "unknown"]:
                conditions.append("a.online_status = %s")
                params.append(online_status)

            fields = ["ap_mac", "ap_name", "sn", "online_status", "ap_ip", "model", "sw_version",
                      "ap_group", "client_count", "lldp_name", "lldp_port", "ac_id", "last_seen_at", "ac_name"]
            sql = """SELECT a.ap_mac, a.ap_name, a.sn, a.online_status, a.ap_ip, a.model, a.sw_version,
                     a.ap_group, a.client_count, a.lldp_name, a.lldp_port, a.ac_id, a.last_seen_at,
                     COALESCE(c.ac_name, '')
                     FROM wifi_ap a LEFT JOIN wifi_ac c ON c.ac_id = a.ac_id"""
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY a.ac_id, a.ap_name, a.ap_mac"

            self.cursor.execute(sql, params)
            return [dict(zip(fields, row)) for row in self.cursor.fetchall()]

        except Exception as err:
            logger.error("======WifiDB getApList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getClientList(self, data=None):
        """
        终端列表，带所属 AC 名称，支持条件筛选
        :param data: {
            "ip" / "username" / "client_mac" / "ap_name" / "ssid" / "band": 模糊匹配,
            "ac_id": 所属 AC,
            "status": online / offline,
        }
        :return: 列表数据或"failed"
        """
        try:
            data = data or {}
            conditions = []
            params = []

            # 文本字段统一模糊匹配，字段名白名单拼进 SQL，值走参数
            for field in ["ip", "username", "client_mac", "ap_name", "ssid", "band"]:
                value = str(data.get(field) or "").strip()
                if not value:
                    continue
                if field == "ap_name":
                    # ap_name 为空时界面展示的是按 ap_mac 关联出来的名称，两个来源都匹配
                    conditions.append("(c.ap_name LIKE %s OR EXISTS (SELECT 1 FROM wifi_ap p "
                                      "WHERE p.ac_id = c.ac_id AND p.ap_mac = c.ap_mac AND p.ap_name LIKE %s))")
                    params.append("%" + value + "%")
                    params.append("%" + value + "%")
                else:
                    conditions.append("c." + field + " LIKE %s")
                    params.append("%" + value + "%")

            ac_id = int(data.get("ac_id") or 0)
            if ac_id:
                conditions.append("c.ac_id = %s")
                params.append(ac_id)

            status = str(data.get("status") or "").strip().lower()
            if status in ["online", "offline"]:
                conditions.append("c.status = %s")
                params.append(status)

            fields = ["client_mac", "username", "ip", "ap_mac", "ap_name", "ssid", "band", "channel",
                      "radio_id", "status", "vlan_id", "up_rate", "down_rate", "rssi", "ac_id", "ac_name"]
            # 终端上报的 ap_mac 可能是 Hex-STRING 解析出的乱码，以 ap_name 关联 AP 表取准确值；
            # 反过来 ap_name 为空时用 ap_mac 兜底。用标量子查询避免 JOIN 出重复行
            sql = """SELECT c.client_mac, c.username, c.ip,
                     COALESCE(
                         (SELECT p.ap_mac FROM wifi_ap p
                          WHERE p.ac_id = c.ac_id AND p.ap_name = c.ap_name AND c.ap_name <> '' LIMIT 1),
                         c.ap_mac, '') AS ap_mac,
                     COALESCE(NULLIF(c.ap_name, ''),
                         (SELECT p.ap_name FROM wifi_ap p
                          WHERE p.ac_id = c.ac_id AND p.ap_mac = c.ap_mac AND c.ap_mac <> '' LIMIT 1), '') AS ap_name,
                     c.ssid, c.band, c.channel,
                     c.radio_id, c.status, c.vlan_id, c.up_rate, c.down_rate, c.rssi, c.ac_id,
                     COALESCE(a.ac_name, '')
                     FROM wifi_client c
                     LEFT JOIN wifi_ac a ON a.ac_id = c.ac_id"""
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY ap_name, c.client_mac"

            self.cursor.execute(sql, params)
            return [dict(zip(fields, row)) for row in self.cursor.fetchall()]

        except Exception as err:
            logger.error("======WifiDB getClientList error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getRadiosByAps(self, ap_macs):
        """
        批量取多个 AP 的射频，用于地图标签汇总
        :return: 列表数据或"failed"
        """
        try:
            if not ap_macs:
                return []
            fields = ["ap_mac", "radio_id", "band", "channel", "utilization", "client_count", "tx_power"]
            sql = """SELECT ap_mac, radio_id, band, channel, utilization, client_count, tx_power
                     FROM wifi_radio WHERE ap_mac IN (""" + ",".join(["%s"] * len(ap_macs)) + """)
                     ORDER BY ap_mac, radio_id"""
            self.cursor.execute(sql, tuple(ap_macs))
            rows = []
            for row in self.cursor.fetchall():
                item = dict(zip(fields, row))
                item["utilization"] = float(item["utilization"]) if item["utilization"] is not None else None
                item["client_count"] = int(item["client_count"] or 0)
                rows.append(item)
            return rows

        except Exception as err:
            logger.error("======WifiDB getRadiosByAps error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getApPool(self):
        """
        可摆放 AP 池，带所属 AC 名称
        :return: 列表数据或"failed"
        """
        try:
            fields = ["ac_name", "ap_mac", "ap_name", "ap_group", "online_status", "client_count"]
            sql = """SELECT c.ac_name, a.ap_mac, a.ap_name, a.ap_group, a.online_status, a.client_count
                     FROM wifi_ap a INNER JOIN wifi_ac c ON c.ac_id = a.ac_id
                     ORDER BY a.ac_id, a.ap_name"""
            self.cursor.execute(sql)
            return [dict(zip(fields, row)) for row in self.cursor.fetchall()]

        except Exception as err:
            logger.error("======WifiDB getApPool error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getPlacements(self):
        """
        全部摆放关系（AP 在哪些地图上）
        :return: 列表数据或"failed"
        """
        try:
            fields = ["ap_mac", "map_id", "map_name"]
            sql = """SELECT p.ap_mac, m.map_id, m.map_name
                     FROM wifi_map_ap p INNER JOIN wifi_map m ON m.map_id = p.map_id
                     ORDER BY m.building, m.sort_num, m.map_id"""
            self.cursor.execute(sql)
            return [dict(zip(fields, row)) for row in self.cursor.fetchall()]

        except Exception as err:
            logger.error("======WifiDB getPlacements error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getApBase(self, ap_mac):
        """
        AP 基础信息，带所属 AC 名称
        :return: 字典 / None / "failed"
        """
        try:
            fields = ["ap_mac", "ap_name", "sn", "ap_group", "online_status", "ap_ip", "model", "sw_version",
                      "client_count", "lldp_name", "lldp_port", "ac_id", "last_seen_at", "ac_name"]
            sql = """SELECT a.ap_mac, a.ap_name, a.sn, a.ap_group, a.online_status, a.ap_ip, a.model, a.sw_version,
                     a.client_count, a.lldp_name, a.lldp_port, a.ac_id, a.last_seen_at, COALESCE(c.ac_name, '')
                     FROM wifi_ap a LEFT JOIN wifi_ac c ON c.ac_id = a.ac_id
                     WHERE a.ap_mac = %s"""
            self.cursor.execute(sql, (ap_mac,))
            row = self.cursor.fetchone()
            return dict(zip(fields, row)) if row else None

        except Exception as err:
            logger.error("======WifiDB getApBase error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getRadios(self, ap_mac):
        """
        单个 AP 的射频明细
        :return: 列表数据或"failed"
        """
        try:
            fields = ["ap_mac", "radio_id", "wlan_type", "band", "channel_status", "channel", "bandwidth",
                      "utilization", "interference_rate", "client_count", "tx_power", "max_power"]
            sql = """SELECT ap_mac, radio_id, wlan_type, band, channel_status, channel, bandwidth,
                     utilization, interference_rate, client_count, tx_power, max_power
                     FROM wifi_radio WHERE ap_mac = %s ORDER BY radio_id"""
            self.cursor.execute(sql, (ap_mac,))
            rows = []
            for row in self.cursor.fetchall():
                item = dict(zip(fields, row))
                item["utilization"] = float(item["utilization"]) if item["utilization"] is not None else None
                item["interference_rate"] = float(item["interference_rate"]) if item["interference_rate"] is not None else None
                rows.append(item)
            return rows

        except Exception as err:
            logger.error("======WifiDB getRadios error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getSsids(self, ap_mac):
        """
        单个 AP 的开放 SSID
        :return: 列表数据或"failed"
        """
        try:
            fields = ["radio_id", "seq", "ssid", "client_count", "ssid_status"]
            sql = """SELECT radio_id, seq, ssid, client_count, ssid_status
                     FROM wifi_ssid WHERE ap_mac = %s ORDER BY radio_id, seq"""
            self.cursor.execute(sql, (ap_mac,))
            return [dict(zip(fields, row)) for row in self.cursor.fetchall()]

        except Exception as err:
            logger.error("======WifiDB getSsids error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getClients(self, ap_mac):
        """
        单个 AP 下的在线终端
        :return: 列表数据或"failed"
        """
        try:
            fields = ["client_mac", "username", "ap_mac", "ap_name", "radio_id", "band", "channel", "ssid",
                      "status", "vlan_id", "ip", "up_rate", "down_rate", "rssi", "ac_id"]
            sql = """SELECT client_mac, username, ap_mac, ap_name, radio_id, band, channel, ssid,
                     status, vlan_id, ip, up_rate, down_rate, rssi, ac_id
                     FROM wifi_client WHERE ap_mac = %s ORDER BY client_mac"""
            self.cursor.execute(sql, (ap_mac,))
            return [dict(zip(fields, row)) for row in self.cursor.fetchall()]

        except Exception as err:
            logger.error("======WifiDB getClients error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()
