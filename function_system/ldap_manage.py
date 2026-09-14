import logging

from ldap3 import Server, Connection, ALL, SUBTREE

from config.config import Config

logger = logging.getLogger(__name__)


def _search_user_dn(username: str):
    """
    使用只读代理账号搜索用户DN
    Returns:
        用户完整DN，未找到返回None
    """
    server = Server(Config.ldap_server, port=Config.ldap_port, use_ssl=Config.ldap_use_ssl, get_info=ALL)
    conn = Connection(
        server,
        user=Config.ldap_bind_dn,
        password=Config.ldap_bind_password,
        auto_bind=True
    )
    try:
        search_filter = Config.ldap_user_search_filter.format(username=username)
        conn.search(
            search_base=Config.ldap_base_dn,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=["*"]
        )
        if len(conn.entries) == 0:
            return None
        return conn.entries[0]
    finally:
        conn.unbind()


def authenticate_ldap_user(username: str, password: str):
    """
    LDAP用户认证：先用代理账号搜索用户DN及属性，再用该DN+用户密码单独bind校验
    Args:
        username: 用户名（sAMAccountName）
        password: 明文密码
    Returns:
        认证成功: {"subname": 显示名, "mail": 邮箱, "phone": 手机号}
        认证失败: None
    """
    if not Config.ldap_server or not Config.ldap_bind_dn or not Config.ldap_base_dn:
        logger.error("LDAP 配置缺失，请检查 ldap_server / ldap_bind_dn / ldap_base_dn")
        return None

    if not password:
        return None

    try:
        user_entry = _search_user_dn(username)
    except Exception as e:
        logger.error(f"LDAP 用户搜索失败: 用户 {username}, 原因: {str(e)}")
        return None

    if not user_entry:
        logger.warning(f"LDAP 未找到用户: {username}")
        return None

    user_dn = user_entry.entry_dn

    conn = None
    try:
        server = Server(Config.ldap_server, port=Config.ldap_port, use_ssl=Config.ldap_use_ssl, get_info=ALL)
        conn = Connection(
            server,
            user=user_dn,
            password=password,
            auto_bind=True
        )
        if not conn.bound:
            return None

        return {
            "subname": str(user_entry.displayName) if "displayName" in user_entry else username,
            "mail": str(user_entry.mail) if "mail" in user_entry else "",
            "phone": str(user_entry.mobile) if "mobile" in user_entry else "",
        }
    except Exception as e:
        logger.warning(f"LDAP 认证失败: 用户 {username}, 原因: {str(e)}")
        return None
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:
                pass


if __name__ == '__main__':
    aa = authenticate_ldap_user("chensong", "Chensong")
    print(aa)
    pass
