from flask import Blueprint, request, g
from api.api_response import APIResponse
from function_system import user_manage

# 创建蓝图
system_bp = Blueprint('system', __name__, url_prefix='/system')


@system_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录接口
    """
    try:
        data = request.json
        username = data.get('username')
        secret = data.get('secret')  # 使用password代替identify，更符合常规命名
        timestamp = data.get('timestamp')


        # 验证参数
        if not username or not secret:
            return APIResponse.error("用户名和密码不能为空", 400)

        ret = user_manage.authenticate_user(username=username, secret=secret, timestamp=int(timestamp))
        if ret["status"] == "success":
            return APIResponse.success(ret["data"], message=ret["message"])
        else:
            return APIResponse.auth_error(ret["message"])
            
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/getuser', methods=['POST'])
def getuser():
    """
    获取当前用户基本信息
    """
    try:
        ret = user_manage.get_user_info(username=g.user["username"])
        return APIResponse.success(data=ret["data"], message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/change_passwd', methods=['POST'])
def changePasswd():
    """
    获取当前用户基本信息
    """
    try:
        data = request.json
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        ret = user_manage.changePasswdByUser(username=g.user["username"], old_pass=old_password, new_pass=new_password)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

# 角色表相关接口
@system_bp.route('/add_role', methods=['POST'])
def addRole():
    try:
        data = request.json
        ret = user_manage.add_role(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/update_role', methods=['POST'])
def updateRole():
    try:
        data = request.json
        ret = user_manage.update_role(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/delete_role', methods=['POST'])
def deleteRole():
    try:
        data = request.json
        ret = user_manage.del_role(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/get_role_list', methods=['POST'])
def getRoleList():
    try:
        data = request.json
        ret = user_manage.get_role_list(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

# 用户增删改查
@system_bp.route('/add_user', methods=['POST'])
def addUser():
    try:
        data = request.json
        ret = user_manage.add_user(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/update_user', methods=['POST'])
def updateUser():
    try:
        data = request.json
        ret = user_manage.update_user(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/delete_user', methods=['POST'])
def deleteUser():
    try:
        data = request.json
        ret = user_manage.del_user(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/get_user_list', methods=['POST'])
def getUserList():
    try:
        data = request.json
        ret = user_manage.get_user_list(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

# 页面增删改查
@system_bp.route('/add_page', methods=['POST'])
def addPage():
    try:
        data = request.json
        ret = user_manage.add_page(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/update_page', methods=['POST'])
def updatePage():
    try:
        data = request.json
        ret = user_manage.update_page(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/delete_page', methods=['POST'])
def deletePage():
    try:
        data = request.json
        ret = user_manage.del_page(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/get_page_list', methods=['POST'])
def getPageList():
    try:
        data = request.json
        ret = user_manage.get_page_list(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

# 页面uri增删改查
@system_bp.route('/add_uri', methods=['POST'])
def addUri():
    try:
        data = request.json
        ret = user_manage.add_page_uri(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/update_uri', methods=['POST'])
def updateUri():
    try:
        data = request.json
        ret = user_manage.update_page_uri(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/delete_uri', methods=['POST'])
def deleteUri():
    try:
        data = request.json
        ret = user_manage.del_page_uri(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/get_uri_list', methods=['POST'])
def getUriList():
    try:
        data = request.json
        ret = user_manage.get_page_uri_list(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

# 角色对应页面关系增删改查
@system_bp.route('/add_role_page', methods=['POST'])
def addRolePage():
    try:
        data = request.json
        ret = user_manage.add_role_page(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/update_role_page', methods=['POST'])
def updateRolePage():
    try:
        data = request.json
        ret = user_manage.update_role_page(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/delete_role_page', methods=['POST'])
def deleteRolePage():
    try:
        data = request.json
        ret = user_manage.del_role_page(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/get_role_page_list', methods=['POST'])
def getRolePageList():
    try:
        data = request.json
        ret = user_manage.get_role_page_list(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

@system_bp.route('/get_role_uri_list', methods=['POST'])
def getRoleUriList():
    try:
        data = request.json
        ret = user_manage.get_role_uri_list(data)
        if ret["status"] == "success":
            return APIResponse.success(data=ret["data"], message=ret["message"])
        else:
            return APIResponse.error(message=ret["message"])
    except Exception as e:
        return APIResponse.server_error(message="接口异常，异常原因:{}".format(str(e)))

# 导出蓝图和设置函数
__all__ = ['system_bp']