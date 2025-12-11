from daos.database import mysqldb_netops
from utils.utils import waf
import time
import logging


# 配置日志
logger = logging.getLogger(__name__)
'''
drop table IF EXISTS pages;
create table pages(
page_id bigint COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '页面或目录ID',
name varchar(40) COLLATE utf8_bin NOT NULL COMMENT '页面名称',
classify varchar(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '页面分类',
sort_num varchar(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '同层排序',
path varchar(100) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '路径',
p_type varchar(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '目录0or路由1',
descr varchar(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '页面描述',
hide varchar(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '0是否隐藏，仅注册',
parent_id bigint COLLATE utf8_bin NOT NULL DEFAULT 0 COMMENT '归属',
icon varchar(40) COLLATE utf8_bin NOT NULL COMMENT '图标',
primary key(page_id)
);

drop table IF EXISTS pages_uri;
create table pages_uri(
uri_id bigint COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '页面接口ID',
page_id bigint COLLATE utf8_bin NOT NULL COMMENT '页面ID',
uri varchar(60) COLLATE utf8_bin NOT NULL COMMENT '接口地址',
descr varchar(64) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '接口描述',
privilege varchar(1) COLLATE utf8_bin NOT NULL DEFAULT '0'  COMMENT '页面权限 0 只读 1读写',
primary key(uri_id)
);

'''
class PagesDB(mysqldb_netops):
    #页面管理
    def addPage(self, data):
        try:
            check_params = ["name", "classify", "sort_num", "path", "p_type", "descr", "hide", "parent_id", "icon"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["name"], data["classify"], data["sort_num"], data["path"],
                             data["p_type"], data["descr"], data["hide"], data["parent_id"], data["icon"]))
            sql = 'insert into pages(name,classify,sort_num,path,p_type,descr,hide,parent_id,icon)values(%s,%s,%s,%s,%s,%s,%s,%s,%s);'
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======PagesDB addpage error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delPage(self, data):
        data = waf(data)
        if "page_id" in data.keys():
            sql = "delete from pages where page_id='{}'".format(int(data["page_id"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======PagesDB delpage error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def updatePage(self, data):
        data = waf(data)
        # name,classify,sort_num,path,p_type,descr,hide,parent_id,icon
        if "page_id" in data.keys():
            conditions = []
            params = []

            update_key = ["name", "classify", "sort_num", "path", "p_type", "descr", "hide", "parent_id", "icon"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])

            if len(conditions) > 0:
                sql = "update pages set " + ",".join(conditions) + " where page_id='{}'".format(int(data["page_id"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======PagesDB update-page error========\n{}".format(str(err)))
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"

    def getPageList(self, data):
        data = waf(data)
        conditions = []
        serach_reg_key = [
            {"key": "name_reg", "value": "name"},
        ]
        for key_item in serach_reg_key:
            if key_item["key"] in data.keys():
                conditions.append(key_item["value"] + " regexp '" + str(data[key_item["key"]]) + "'")

        serach_eq_key = ["classify", "parent_id"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = '''select page_id,name,classify,sort_num,path,p_type,descr,hide,parent_id,icon from pages '''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["page_id", "name", "classify", "sort_num", "path", "p_type", "descr", "hide", "parent_id", "icon"]
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
            logger.error("======PagesDB get page list error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # 页面接口
    def addPageUri(self, data):
        try:
            check_params = ["page_id", "uri", "descr", "privilege"]
            for i in check_params:
                if i not in data.keys():
                    print("参数不足", i)
                    return "failed"
            sqlParam = []
            data = waf(data)
            sqlParam.append((data["page_id"], data["uri"], data["descr"], data["privilege"]))
            sql = 'insert into pages_uri(page_id,uri,descr,privilege)values(%s,%s,%s,%s);'
            self.cursor.executemany(sql, sqlParam)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as err:
            self.conn.rollback()
            logger.error("======PagesDB addpage uri error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def delPageUri(self, data):
        data = waf(data)
        if "uri_id" in data.keys():
            sql = "delete from pages_uri where uri_id='{}'".format(int(data["uri_id"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======PagesDB delpage uri error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def delPageUriByPageId(self, data):
        data = waf(data)
        if "page_id" in data.keys():
            sql = "delete from pages_uri where page_id='{}'".format(int(data["page_id"]))
            try:
                self.cursor.execute(sql)
                self.conn.commit()
                return "success"
            except Exception as err:
                self.conn.rollback()
                logger.error("======PagesDB delpage uri by page_id error========\n{}".format(str(err)))
                return "failed"
            finally:
                self.cursor.close()
                self.conn.close()
        else:
            return "failed"

    def updatePageUri(self, data):
        data = waf(data)
        # page_id,uri,descr,privilege
        if "uri_id" in data.keys():
            conditions = []
            params = []

            update_key = ["uri", "descr", "privilege"]
            for key in update_key:
                if key in data.keys():
                    conditions.append(key + " = %s")
                    params.append(data[key])

            if len(conditions) > 0:
                sql = "update pages_uri set " + ",".join(conditions) + " where uri_id='{}'".format(int(data["uri_id"]))
                try:
                    self.cursor.execute(sql, params)
                    self.conn.commit()
                    return "success"
                except Exception as err:
                    self.conn.rollback()
                    logger.error("======PagesDB update-page uri error========\n{}".format(str(err)))
                    return "failed"
                finally:
                    self.cursor.close()
                    self.conn.close()
            else:
                return "failed"
        else:
            return "failed"

    def getPageUri(self, data):
        data = waf(data)
        conditions = []

        serach_eq_key = ["page_id"]
        for key in serach_eq_key:
            if key in data.keys():
                conditions.append(key + "='" + str(data[key]) + "'")

        sql = '''select uri_id,page_id,uri,descr,privilege from pages_uri '''
        if len(conditions) > 0:
            sql = sql + " where " + " and ".join(conditions)
        proper = ["uri_id", "page_id", "uri", "descr", "privilege"]
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
            logger.error("======PagesDB get page list error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    # 特殊用法,通过角色获取所有接口
    def getPageUriListByRole(self, data):
        data = waf(data)
        conditions = []
        if "rid" in data.keys():
            conditions.append("role_pages.rid='" + str(data["rid"]) + "'")
            sql = '''
            select 
                role_pages.rid,role_pages.page_id,role_pages.privilege,
                pages_uri.uri_id,pages_uri.uri,pages_uri.privilege from role_pages 
            join pages_uri on pages_uri.page_id=role_pages.page_id
            '''
            sql = sql + " where " + " and ".join(conditions)
        else:
            return "failed"

        proper = ["rid", "page_id", "page_pri", "uri_id", "uri", "uri_pri"]
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
            logger.error("======PagesDB get PageUriListByRole error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

    def getPageListByRole(self, data):
        data = waf(data)
        conditions = []
        if "rid" in data.keys():
            conditions.append("role_pages.rid='" + str(data["rid"]) + "'")
            sql = '''
            select 
                role_pages.rid,role_pages.page_id,role_pages.privilege,
                pages.name,pages.classify,pages.sort_num,pages.path,
                pages.descr,pages.hide,pages.parent_id,pages.icon from role_pages 
            join pages on pages.page_id=role_pages.page_id
            '''
            sql = sql + " where " + " and ".join(conditions)
        else:
            return "failed"

        proper = ["rid", "page_id", "page_pri", "name", "group", "order", "path", "descr", "hide", "parent_id", "icon"]
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
            logger.error("======PagesDB get PageListByRole error========\n{}".format(str(err)))
            return "failed"
        finally:
            self.cursor.close()
            self.conn.close()

