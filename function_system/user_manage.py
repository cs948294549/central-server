import logging
import jwt
import time
from tables.UsersDB import UsersDB
from tables.RolesDB import RolesDB
from utils.utils import decorator_checkparams
from utils.aes_util import decrypt_aes_payload
from function_system.ldap_manage import authenticate_ldap_user

from hashlib import md5

# 从配置文件导入
from config.config import Config


# 配置日志
logger = logging.getLogger(__name__)

# JWT 配置（从配置文件读取）
SECRET_KEY = Config.jwt_secret_key
ALGORITHM = Config.jwt_algorithm
ACCESS_TOKEN_EXPIRE_HOURS = Config.jwt_expire_hours

# 验证API Key/Secret（从数据库用户表读取）
def verify_secret_token(key: str, secret: str, timestamp: str):
    """
    验证 API Key/Secret 认证
    key: username（用户名）
    secret: 计算后的签名 md5(identify + timestamp)
    timestamp: 请求时间戳
    返回: True/False 或用户信息字典
    """
    try:
        db = UsersDB()
        user_infos = db.getUser({"username": key})

        if len(user_infos) != 1:
            logger.warning(f"API Key认证失败: 用户 {key} 不存在或重复")
            return False

        user_info = user_infos[0]
        # 计算签名: md5(identify + timestamp)
        expected_signature = md5((user_info["identify"] + timestamp).encode("utf-8")).hexdigest()

        if expected_signature == secret:
            logger.info(f"API Key认证成功: 用户 {key}")
            # 返回用户信息供后续使用
            return {
                "username": user_info["username"],
                "rid": user_info["rid"],
                "subname": user_info.get("subname", ""),
                "auth_type": "api_key"
            }
        else:
            logger.warning(f"API Key认证失败: 用户 {key} 签名不匹配")
            return False

    except Exception as e:
        logger.error(f"API Key认证异常: {str(e)}")
        return False

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

#修改用户密码
def changePasswdByUser(username: str, old_pass: str, new_pass: str):
    db = UsersDB()
    user_infos = db.getUser({"username": username})
    if len(user_infos) == 0:
        return {"status": "failed", "data": None, "message": "用户不存在"}
    else:
        if len(user_infos) == 1:
            user_info = user_infos[0]
            if user_info["identify"] == old_pass:
                db1 = UsersDB()
                ret = db1.updateUser({"username": username, "identify": new_pass})
                if ret != "failed":
                    return {"status": "success", "data": None, "message": "密码更新成功"}
                else:
                    return {"status": "failed", "data": None, "message": "密码更新失败"}
            else:
                return {"status": "failed", "data": None, "message": "密码错误"}
        else:
            return {"status": "failed", "data": None, "message": "用户冲突"}

# 管理员重置用户凭证（无需验证旧密码）
@decorator_checkparams(key_array=["username", "new_identify"])
def resetUserIdentify(data):
    """
    管理员重置用户凭证
    参数:
        username: 用户名
        new_identify: 新凭证（已加密的密码）
    返回:
        {"status": "success/failed", "data": None, "message": "提示信息"}
    """
    try:
        username = data["username"]
        new_identify = data["new_identify"]

        # 先检查用户是否存在
        db_check = UsersDB()
        user_infos = db_check.getUser({"username": username})

        if len(user_infos) == 0:
            return {"status": "failed", "data": None, "message": "用户不存在"}
        elif len(user_infos) > 1:
            return {"status": "failed", "data": None, "message": "用户冲突"}

        # 执行重置（使用新的数据库连接）
        db_update = UsersDB()
        ret = db_update.updateUser({"username": username, "identify": new_identify})

        if ret != "failed":
            logger.info(f"管理员重置用户凭证: {username}")
            return {"status": "success", "data": None, "message": "凭证重置成功"}
        else:
            return {"status": "failed", "data": None, "message": "凭证重置失败"}

    except Exception as e:
        logger.error(f"重置用户凭证异常: {str(e)}")
        return {"status": "failed", "data": None, "message": f"内部错误: {str(e)}"}

# 验证user
def authenticate_user(username: str, secret: str, timestamp: int, auth_type: str = "local"):
    current_time = int(time.time())
    if current_time-timestamp >= 30:
        return {"status": "failed", "data": None, "message": "认证失败, timestamp超时"}
    db = UsersDB()
    user_infos = db.getUser({"username": username})

    if auth_type == "ldap":
        # LDAP 认证：secret 为前端 AES 加密后的明文密码，需先解密再向 LDAP 发起 bind 校验
        try:
            plain_password = decrypt_aes_payload(secret, Config.aes_secret)
        except Exception as e:
            logger.error(f"LDAP密码解密失败: {str(e)}")
            return {"status": "failed", "data": None, "message": "认证失败"}

        if not authenticate_ldap_user(username, plain_password):
            return {"status": "failed", "data": None, "message": "认证失败"}

        if len(user_infos) == 0:
            # LDAP 认证通过但本地无该用户，自动创建，默认分组为 default
            db_add = UsersDB()
            add_ret = db_add.addUser({
                "username": username,
                "identify": "",
                "subname": username,
                "phone": "",
                "mail": "",
                "rid": "default"
            })
            if add_ret == "failed":
                logger.error(f"LDAP自动创建用户失败: {username}")
                return {"status": "failed", "data": None, "message": "认证失败"}
            user_infos = db.getUser({"username": username})

        if len(user_infos) != 1:
            return {"status": "failed", "data": None, "message": "用户冲突"}

        user_info = user_infos[0]
    else:
        if len(user_infos) == 0:
            return {"status": "failed", "data": None, "message": "用户不存在"}
        if len(user_infos) != 1:
            return {"status": "failed", "data": None, "message": "用户冲突"}

        user_info = user_infos[0]
        sign_content = user_info["username"] + user_info["identify"] + "netops" + str(timestamp)
        sign = md5(sign_content.encode("utf-8")).hexdigest()
        if sign != secret:
            return {"status": "failed", "data": None, "message": "认证失败"}

    # sign 直接沿用请求携带的 secret（本地哈希或 LDAP 密文均可），仅作为后续请求签名的凭据
    token = create_access_token(data={"username": username, 'rid': user_info["rid"], 'sign': secret})
    del user_info["identify"]
    try:
        db_user = UsersDB()
        db_user.updateUser({"username": username, "last_login": int(time.time())})
    except Exception as e:
        logger.error("更新last_login失败,原因{}".format(str(e)))
    return {
        "status": "success",
        "data": {
            "user_info": user_info,
            "token": token,
        },
        "message": "认证成功"
    }

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
        if data["rid"] in ["system", "default"]:
            return {"status": "failed", "message": "系统权限，不能删除", "data": None}
        else:
            db = RolesDB()
            ret = db.delRole(data)

            db = RolesDB()
            ret = db.delRolePage(data)

            db = UsersDB()
            ret = db.defaultRoleByRole(data)

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
@decorator_checkparams(key_array=["username", "identify", "subname", "phone", "mail", "rid"])
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


if __name__ == '__main__':
    # token = create_access_token(data={"username":"admin1", "role":"admin", "host": ""})
    # print(token)
    print(md5("chens_dasdasd".encode("utf-8")).hexdigest())
