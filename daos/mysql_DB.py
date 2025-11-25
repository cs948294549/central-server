import pymysql
from utils.utils import waf

db_config = {
    "db_host": "192.168.56.10",
    "db_user": "netops",
    "db_token": "netops@163",
    "db_port": 3306,
    "db_name": "test"
}

class DB_op:
    def __init__(self):

        self.conn = pymysql.connect(host=db_config["db_host"], user=db_config["db_user"], password=db_config["db_token"],
                                    port=db_config["db_port"],
                                    database=db_config["db_name"], charset="utf8")
        self.cursor = self.conn.cursor()

    def ping(self):
        self.conn.ping(reconnect=True)
        self.cursor = self.conn.cursor()

    def getTables(self):
        try:
            self.cursor.execute("show tables;")
            result = self.cursor.fetchall()
            tables = []
            for i in result:
                tables.append(i[0])
            return tables
        except Exception as err:
            print("======DB_op.getTables error========\n", err)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # 分组信息
    def addGroupItem(self, data):
        # name 分组名称, op_list 成员列表 data = {"name": "test", "op_list": "chensong1,chensong2"}
        try:
            check_params = ["name", "op_list"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["name"], data["op_list"]))
            sql = 'insert into op_groups(name,op_list)values(%s,%s);'
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            print("======DB_op.addGroupItem error========\n", err)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delGroupItem(self, data):
        data = waf(data)
        if "group_id" in data.keys():
            sql = "delete from op_groups where pid='{}'".format(int(data["group_id"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                print("======DB_op.delGroupItem error========\n", err)
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def updateGroupItem(self, data):
        data = waf(data)
        # group_id, name, op_list
        if "group_id" in data.keys():
            conditions = []
            params = []

            update_key = ["name", "op_list"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])

            if len(conditions) > 0:
                sql = "update op_groups set " + ",".join(conditions) + " where pid='{}'".format(
                    int(data["group_id"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    print("======DB_op.updateGroupItem error========\n", err)
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"

    def getGroupItem(self, data):
        # group_id, name, op_list
        data = waf(data)
        conditions = []

        serach_reg_key = [
            {"key": "op_list", "value": "op_list"},
            {"key": "name_reg", "value": "name"}
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append(key_item["value"] + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["name", "pid"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = "select pid,name,op_list from op_groups "
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["pid", "name", "op_list"]
        try:
            self.cursor.execute(sql)
            result1 = self.cursor.fetchall()
            results = []
            if len(result1) > 0:
                for i in result1:
                    result = {}
                    for num in range(len(proper)):
                        result[proper[num]] = i[num] if i[num] != None else ""
                    results.append(result)
                return results
            else:
                return []
        except Exception as err:
            print("======DB_op.getGroupItem error========\n", err)
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()


if __name__ == '__main__':
    db = DB_op()
    asb = db.getTables()
    print(asb)





