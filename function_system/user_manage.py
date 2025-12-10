import json
import logging
import jwt
import time
from tables.UsersDB import UsersDB
from tables.PagesDB import PagesDB
from tables.RolesDB import RolesDB
from utils.utils import decorator_checkparams

from function_messaging.redis_client import get_redis_client

from hashlib import md5


# 配置日志
logger = logging.getLogger(__name__)

# 配置（生产环境建议从环境变量读取，避免硬编码）
SECRET_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFkbWlu"  # 对称密钥，需高强度
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24  # 访问令牌有效期

# jwt认证相关
def create_access_token(data: dict):
    """生成访问令牌"""
    to_encode = data.copy()
    # 设置过期时间（UTC时间，避免时区问题）
    expire = int(time.time()) + ACCESS_TOKEN_EXPIRE_HOURS*3600
    to_encode.update({"exp": expire})
    # 加密生成令牌
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 验证token
def verify_access_token(token: str):
    """验证令牌，返回载荷数据"""
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": True}  # 强制验证过期时间
        )
        return payload  # 格式：{"sub": "user123", "role": "admin", "exp": 1716888888}
    except jwt.ExpiredSignatureError:
        raise Exception("令牌已过期")
    except jwt.InvalidTokenError:
        raise Exception("无效令牌")

# 验证user
def authenticate_user(username: str, secret: str, timestamp: int):
    current_time = int(time.time())
    if current_time-timestamp >= 30:
        return {"status": "failed", "data": None, "message": "认证失败, timestamp超时"}
    db = UsersDB()
    user_infos = db.getUser({"username": username})
    if len(user_infos) == 0:
        return {"status": "failed", "data":None, "message": "用户不存在"}
    else:
        if len(user_infos) == 1:
            user_info = user_infos[0]
            sign_content = user_info["username"] + user_info["identify"] + "netops" + str(timestamp)
            sign = md5(sign_content.encode("utf-8")).hexdigest()
            if sign == secret:
                token = create_access_token(data={"username": username, 'rid': user_info["rid"]})
                del user_info["identify"]
                return {
                    "status": "success",
                    "data": {
                        "user_info": user_info,
                        "token":token,
                    },
                    "message": "认证成功"
                }
            else:
                return {"status": "failed", "data": None, "message": "认证失败"}

        else:
            return {"status": "failed", "data": None, "message": "用户冲突"}

# 获取user基本信息
def get_user_info(username: str):
    db = UsersDB()
    user_infos = db.getUser({"username": username})
    if len(user_infos) == 0:
        return {"status": "failed", "data":None, "message": "用户不存在"}
    else:
        if len(user_infos) == 1:
            user_info = user_infos[0]
            del user_info["identify"]
            return {"status": "success", "data":user_info, "message": "查询成功"}
        else:
            return {"status": "failed", "data": None, "message": "查询到用户冲突"}

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

# 角色数据表增删改查
@decorator_checkparams(key_array=["rid", "name", "descr"])
def add_role(data):
    try:
        db = RolesDB()
        ret = db.addRole(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rid"])
def update_role(data):
    try:
        db = RolesDB()
        ret = db.updateRole(data)
        if ret != "failed":
            return {"status":"success","message": "更新成功", "data": ret}
        else:
            return {"status": "failed", "message": "更新失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["rid"])
def del_role(data):
    try:
        if data["rid"] in ["system", "admin"]:
            return {"status": "failed", "message": "系统管理权限，不能删除", "data": None}
        else:
            db = RolesDB()
            ret = db.delRole(data)

            db = RolesDB()
            ret = db.delRolePage(data)

            if ret != "failed":
                return {"status":"success","message": "删除成功", "data": ret}
            else:
                return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_role_list(data):
    try:
        db = RolesDB()
        ret = db.getRoleList(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

# 新增完角色，用户可以添加了
@decorator_checkparams(key_array=["username", "identify", "subame", "phone", "mail", "rid"])
def add_user(data):
    try:
        db = UsersDB()
        ret = db.addUser(data)
        if ret != "failed":
            return {"status":"success","message": "添加成功", "data": ret}
        else:
            return {"status": "failed", "message": "添加失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["username"])
def update_user(data):
    try:
        db = UsersDB()
        ret = db.updateUser(data)
        if ret != "failed":
            return {"status": "success", "message": "更新成功", "data": ret}
        else:
            return {"status": "failed", "message": "更新失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=["username"])
def del_user(data):
    try:
        db = UsersDB()
        ret = db.delUser(data)
        if ret != "failed":
            return {"status":"success","message": "删除成功", "data": ret}
        else:
            return {"status": "failed", "message": "删除失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}

@decorator_checkparams(key_array=[])
def get_user_list(data):
    try:
        db = UsersDB()
        ret = db.getUser(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
        else:
            return {"status": "failed", "message": "查询失败", "data": None}
    except Exception as e:
        return {"status": "failed", "message": "内部错误{}".format(str(e)), "data": None}


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
        ret = db.delPage(data)
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
        ret = db.getPageList(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
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
        ret = db.getPageListByRole(data)
        if ret != "failed":
            return {"status":"success","message": "查询成功", "data": ret}
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


if __name__ == '__main__':
    # token = create_access_token(data={"username":"admin1", "role":"admin", "host": ""})
    # print(token)

    # old_t = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzY1NDE4ODQzfQ.Hm9RvsGYvbVahEpRJr6pCZDYFmp2J3tpBFixoCKxcJA"
    # sd = verify_access_token(old_t)
    # print(sd)

    # ret = authenticate_user(username="admin", identify="20d6ba810a3185f4207bac8588824da3")
    # print(ret)

    # aa = verify_url_privilege("admin", "/system/getuser")
    # print(aa)

    aa = get_role_list(data={})
    print(aa)