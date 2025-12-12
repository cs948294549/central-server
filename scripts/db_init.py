from tables.PagesDB import PagesDB
from tables.RolesDB import RolesDB
from tables.UsersDB import UsersDB

page_cfg = [
]


def step1():
    print("=======角色部分=========")
    aa = RolesDB()
    ret = aa.addRole({"rid": "system", "name": "系统管理员", "descr": '管理员权限'})
    print("新增系统管理员角色")
    aa = RolesDB()
    ret = aa.addRole({"rid": "default", "name": "默认角色", "descr": '默认角色'})
    print("新增系统默认角色")


def step2():
    print("=======账户部分=========")
    user_info = {
        "username":"admin",
        "identify": "b2fd3bace4778f19918ffbf7a42bb4b8",
        "subname": "初始化管理员",
        "phone": "",
        "mail": "",
        "rid": "system",
    }
    aa = UsersDB()
    ret = aa.addUser(user_info)
    print("新增系统管理账号 admin 密码 123456")


def step3():
    print("=======页面配置=========")
    "name", "classify", "sort_num", "path", "p_type", "descr", "hide", "parent_id", "icon"
    db = PagesDB()

