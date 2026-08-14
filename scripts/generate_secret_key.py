#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密钥生成工具

用于生成安全的 JWT Secret Key 和用户 identify 字段
"""

import secrets
import base64


def generate_secret_key(length=64):
    """
    生成随机的 JWT Secret Key

    Args:
        length: 密钥长度（字节数），默认 64 字节

    Returns:
        str: Base64 编码的密钥字符串
    """
    random_bytes = secrets.token_bytes(length)
    secret_key = base64.b64encode(random_bytes).decode('utf-8')
    return secret_key


def generate_identify_secret(length=32):
    """
    生成用户 identify 字段（用于 API 认证）

    Args:
        length: 密钥长度（字节数），默认 32 字节

    Returns:
        str: 十六进制格式的密钥
    """
    return secrets.token_hex(length)


if __name__ == "__main__":
    print("=" * 70)
    print("Central-Server 密钥生成工具")
    print("=" * 70)
    print()

    # 生成 JWT Secret Key
    jwt_secret = generate_secret_key(64)
    print("【1】JWT Secret Key（配置文件使用）")
    print("-" * 70)
    print(f"jwt_secret_key = \"{jwt_secret}\"")
    print()
    print("用途: 用于 JWT Token 签名和验证")
    print("配置位置: config.py 中的 jwt_secret_key")
    print("⚠️  重要: 这是后端专用密钥，不要分发给客户端")
    print()

    # 生成用户 identify 示例
    print("【2】用户 identify 字段（数据库 users 表使用）")
    print("-" * 70)
    print("用途: 用于 API Key/Secret 认证")
    print()

    print("API 专用用户示例:")
    for i in range(3):
        username = f"api_service_{i+1}"
        identify = generate_identify_secret(32)
        print(f"  username: {username}")
        print(f"  identify: {identify}")
        print()

    print("说明:")
    print("  - username: 作为 API 认证的 key")
    print("  - identify: 用于计算 API 认证的 secret")
    print("  - 认证时: secret = md5(identify + timestamp)")
    print()

    print("=" * 70)
    print("统一认证说明")
    print("=" * 70)
    print()
    print("Central-Server 使用统一用户表 (users) 支持两种认证方式:")
    print()
    print("【方式 1】JWT Token 认证（Web 用户）")
    print("  - 用途: Web 界面登录、移动 App")
    print("  - 流程: POST /system/login 获取 Token → 使用 Token 访问 API")
    print("  - 计算: secret = md5(username + identify + 'netops' + timestamp)")
    print()
    print("【方式 2】API Key/Secret 认证（脚本/服务）")
    print("  - 用途: 自动化脚本、服务间调用")
    print("  - 流程: 直接使用 username + identify 计算签名访问 API")
    print("  - 计算: secret = md5(identify + timestamp)")
    print()
    print("同一个用户账户可以选择任意一种方式使用！")
    print()

    print("=" * 70)
    print("配置步骤")
    print("=" * 70)
    print()
    print("1. 配置 JWT Secret Key")
    print("   编辑 config.py，替换 jwt_secret_key 为上面生成的值")
    print()
    print("2. 创建 API 用户（可选）")
    print("   INSERT INTO users (username, identify, subname, rid)")
    print(f"   VALUES ('api_service_1', '{generate_identify_secret(32)}', '采集服务', 'system');")
    print()
    print("3. 重启服务使配置生效")
    print("   docker restart central-server")
    print()

    print("=" * 70)
    print("安全建议")
    print("=" * 70)
    print("✓ 生产环境务必更换默认密钥")
    print("✓ JWT Secret Key 是后端专用，不要分发给客户端")
    print("✓ 修改 JWT 密钥后，所有已登录用户需重新登录")
    print("✓ identify 字段等同于密码，需妥善保管")
    print("✓ 为不同服务创建独立的 API 用户账户")
    print("✓ 定期轮换 JWT 密钥（建议每 3-6 个月）")
    print("✓ 密钥不要提交到版本控制系统")
    print("✓ 生产环境使用 HTTPS")
    print()
    print("详细文档: docs/AUTHENTICATION.md")
    print("=" * 70)
