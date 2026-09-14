import json
import logging
from tables.PagesDB import PagesDB
from tables.RolesDB import RolesDB
from utils.utils import decorator_checkparams

from function_messaging.redis_client import get_redis_client


# 配置日志
logger = logging.getLogger(__name__)


# 判断角色访问权限
def verify_url_privilege(role_id: str, url: str):
    red = get_redis_client()
    url_list = red.get("privilege.{}".format(role_id))
    if url_list is None:
        url_list = []
        db = PagesDB()
        ret_uris = db.getPageUriListByRole({"rid": role_id})
        # "rid", "page_id", "page_pri", "uri_id", "uri", "uri_pri"
        for uri in ret_uris:
            if uri["page_pri"]<uri["uri_pri"]:
                continue
            else:
                if uri["uri"] not in url_list:
                    url_list.append(uri["uri"])
        red.set("privilege.{}".format(role_id), json.dumps(url_list), ex=300)
    else:
        url_list = json.loads(url_list)

    if url in url_list:
        return True
    else:
        return False

# 角色和用户就位，新增可用页面，page管理
@decorator_checkparams(key_array=["name", "classify", "sort_num", "path", "p_type", "descr", "hide", "parent_id", "icon"])
def add_page(data):
    try:
        db = PagesDB()
        ret = db.addPage(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["page_id"])
def update_page(data):
    try:
        db = PagesDB()
        ret = db.updatePage(data)
        if ret != "failed":
            return {"status": "success", "message": "更新成功", "data": ret}
        else:
            return {"status": "failed", "message": "更新失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["page_id"])
def del_page(data):
    try:
        db = PagesDB()
        ret = db.getPageList({"parent_id": data["page_id"]})
        if ret != "failed" and len(ret) > 0:
            return {"status": "failed", "message": "目录不为空", "data": None}

        db = PagesDB()
        ret = db.delPage(data)

        db = PagesDB()
        ret = db.delPageUriByPageId({"page_id": data["page_id"]})

        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_page_list(data):
    try:
        db = PagesDB()
        page_list = db.getPageList(data)
        if page_list != "failed":
            dir_map = {}
            for page in page_list:
                if page["parent_id"] == 0:
                    dir_map[page["page_id"]] = page
                    dir_map[page["page_id"]]["children"] = []

            for page in page_list:
                if page["parent_id"] != 0:
                    if page["parent_id"] in dir_map:
                        dir_map[page["parent_id"]]["children"].append(page)
            final_page_list = list(dir_map.values())

            for page in final_page_list:
                page["children"].sort(key=lambda x: x["sort_num"])

            final_page_list.sort(key=lambda x: x["sort_num"])


            return {"status":"success","message": "查询成功", "data": final_page_list}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

# 页面加好后，添加页面包含的url，方便权限控制
@decorator_checkparams(key_array=["page_id", "uri", "descr", "privilege"])
def add_page_uri(data):
    try:
        db = PagesDB()
        ret = db.addPageUri(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["uri_id"])
def update_page_uri(data):
    try:
        db = PagesDB()
        ret = db.updatePageUri(data)
        if ret != "failed":
            return {"status": "success", "message": "更新成功", "data": ret}
        else:
            return {"status": "failed", "message": "更新失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["uri_id"])
def del_page_uri(data):
    try:
        db = PagesDB()
        ret = db.delPageUri(data)
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_page_uri_list(data):
    try:
        db = PagesDB()
        ret = db.getPageUri(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

# 结合角色，对角色能够访问的页面关系进行管理
@decorator_checkparams(key_array=["rid", "page_id", "privilege"])
def add_role_page(data):
    try:
        db = RolesDB()
        ret = db.addRolePage(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["page_list"])
def add_role_page_list(data):
    try:
        db = RolesDB()
        ret = db.addRolePageList(data["page_list"])
        if ret != "failed":
            return {"status":"success","message": "批量添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "批量添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rid", "page_id"])
def update_role_page(data):
    try:
        db = RolesDB()
        ret = db.updateRolePage(data)
        if ret != "failed":
            return {"status": "success", "message": "更新成功", "data": ret}
        else:
            return {"status": "failed", "message": "更新失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rid", "page_id"])
def del_role_page(data):
    try:
        db = RolesDB()
        page_list = db.getRolePage({"rid": data["rid"]})
        page_ids = []
        for page in page_list:
            page_ids.append(page["page_id"])

        db1= PagesDB()
        sub_page_list = db1.getPageList({"parent_id": data["page_id"]})
        for page in sub_page_list:
            if page["page_id"] in page_ids:
                return {"status": "failed", "message": "目录不为空,不能删除", "data": None}

        db = RolesDB()
        ret = db.delRolePage(data)
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rid"])
def get_role_page_list(data):
    try:
        db = PagesDB()
        pri_page_list = db.getPageListByRole(data)
        if pri_page_list != "failed":

            dir_map = {}
            for page in pri_page_list:
                if page["parent_id"] == 0:
                    dir_map[page["page_id"]] = page
                    dir_map[page["page_id"]]["children"] = []

            for page in pri_page_list:
                if page["parent_id"] != 0:
                    if page["parent_id"] in dir_map:
                        dir_map[page["parent_id"]]["children"].append(page)

            final_page_list = list(dir_map.values())

            for page in final_page_list:
                page["children"].sort(key=lambda x: x["sort_num"])

            final_page_list.sort(key=lambda x: x["sort_num"])

            return {"status":"success","message": "查询成功", "data": final_page_list}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rid"])
def get_role_uri_list(data):
    try:
        db = PagesDB()
        ret = db.getPageUriListByRole(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rid"])
def get_route_list_by_role(data):
    try:
        if data["rid"] in ["system"]:
            return get_page_list({})
        else:
            return get_role_page_list(data)
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}
