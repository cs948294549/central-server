# 数据库初始化说明

## 📋 概述

本文档说明如何初始化 Central-Server 项目的 MySQL 数据库。

---

## 🗄️ 数据库结构

### 用户认证相关表

| 表名 | 说明 |
|------|------|
| `users` | 用户表，存储用户信息和认证凭证 |
| `roles` | 角色表，定义角色和权限级别 |
| `role_pages` | 角色页面权限关联表 |

### 页面和权限管理表

| 表名 | 说明 |
|------|------|
| `pages` | 页面/目录表，前端路由配置 |
| `pages_uri` | 页面 URI 表，API 接口权限配置 |

### Syslog 日志管理表

| 表名 | 说明 |
|------|------|
| `syslog_black_list` | Syslog 黑名单规则表 |
| `syslog_merge_list` | Syslog 合并规则表 |

### 告警管理表

| 表名 | 说明 |
|------|------|
| `alarm_list` | 告警列表 |
| `alarm_log` | 告警处理日志 |

---

## 🚀 初始化步骤

### 方法一：使用 SQL 脚本（推荐）

```bash
# 1. 进入项目目录
cd /path/to/central-server

# 2. 执行初始化脚本
mysql -u root -p < scripts/db_init.sql

# 3. 验证
mysql -u root -p netops -e "SHOW TABLES;"
```

### 方法二：手动执行

```bash
# 1. 登录 MySQL
mysql -u root -p

# 2. 执行以下命令
mysql> source /path/to/central-server/scripts/db_init.sql;

# 3. 验证
mysql> USE netops;
mysql> SHOW TABLES;
mysql> SELECT * FROM roles;
mysql> SELECT username, subname, rid FROM users;
```

---

## 👤 默认账户

### 系统管理员

初始化脚本会创建一个默认管理员账户：

```
用户名: admin
密码: admin123
角色: system (系统管理员)
```

**⚠️ 安全提醒**：
- 生产环境部署后，请立即修改默认密码
- 建议创建专用管理员账户，禁用默认 admin 账户

### 修改密码方法

**方法 1：通过 Web 界面**
1. 登录系统
2. 进入个人设置
3. 修改密码

**方法 2：直接更新数据库**
```sql
-- 计算新密码的 identify
-- identify = md5(原始密码) 或根据实际算法计算

UPDATE users 
SET identify = 'new_password_hash', 
    update_time = UNIX_TIMESTAMP() 
WHERE username = 'admin';
```

---

## 🔐 密码 Hash 说明

### Web 用户登录

用户表 `identify` 字段存储密码 hash。登录时：

1. 客户端计算签名：
   ```
   secret = md5(username + identify + "netops" + timestamp)
   ```

2. 发送到服务端验证

### 生成密码 Hash 示例

**Python**:
```python
import hashlib

username = "admin"
password = "admin123"

# 方法1: 简单 md5
identify = hashlib.md5(password.encode()).hexdigest()

# 方法2: 根据实际算法调整
# identify = hashlib.sha256(password.encode()).hexdigest()

print(f"username: {username}")
print(f"identify: {identify}")
```

**命令行**:
```bash
echo -n "admin123" | md5sum
```

---

## 🔑 创建 API 用户

API 用户的 `identify` 字段存储随机 secret 字符串，用于 API Key/Secret 认证。

### 生成 API Secret

```bash
# 使用项目提供的工具
python3 scripts/generate_secret_key.py
```

### 创建 API 用户示例

```sql
-- 插入 API 用户
INSERT INTO users (username, identify, subname, rid, update_time, last_login) 
VALUES (
    'collector_service',                                    -- API Key
    'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4',  -- API Secret (identify)
    '数据采集服务',                                          -- 中文名
    'system',                                                -- 角色
    UNIX_TIMESTAMP(),                                        -- 创建时间
    '0'                                                      -- 最后登录
);
```

**使用该 API 用户**:
```bash
USERNAME="collector_service"
IDENTIFY="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4"
TIMESTAMP=$(date +%s)
SECRET=$(echo -n "${IDENTIFY}${TIMESTAMP}" | md5sum | cut -d' ' -f1)

curl -X POST http://localhost:8080/api/endpoint \
  -H "key: ${USERNAME}" \
  -H "secret: ${SECRET}" \
  -H "Apptime: ${TIMESTAMP}"
```

---

## 📊 数据库配置

### 修改数据库连接

编辑 `config.py`：

```python
mysql_config = {
    "db_host": "localhost",      # 数据库主机
    "db_user": "root",            # 数据库用户
    "db_token": "your_password",  # 数据库密码
    "db_port": 3306,              # 数据库端口
}
```

### 数据库字符集

数据库使用 `utf8mb4` 字符集，支持完整的 UTF-8 字符（包括 Emoji）。

如果需要修改：
```sql
ALTER DATABASE netops CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 🔄 重置数据库

### 完全重置（删除所有数据）

```bash
# 1. 删除数据库
mysql -u root -p -e "DROP DATABASE IF EXISTS netops;"

# 2. 重新初始化
mysql -u root -p < scripts/db_init.sql
```

### 仅重置用户表

```sql
-- 删除所有用户
TRUNCATE TABLE users;

-- 重新插入默认管理员
INSERT INTO users (username, identify, subname, phone, mail, rid, update_time, last_login) 
VALUES ('admin', '0192023a7bbd73250516f069df18b500', '系统管理员', '', 'admin@example.com', 'system', UNIX_TIMESTAMP(), '0');
```

---

## 🐛 常见问题

### 1. 数据库连接失败

**错误**: `Can't connect to MySQL server`

**解决方案**:
```bash
# 检查 MySQL 是否运行
systemctl status mysql

# 检查端口
netstat -an | grep 3306

# 检查配置
mysql -u root -p -e "SELECT user, host FROM mysql.user;"
```

### 2. 权限不足

**错误**: `Access denied for user`

**解决方案**:
```sql
-- 创建数据库用户
CREATE USER 'netops'@'localhost' IDENTIFIED BY 'password';

-- 授权
GRANT ALL PRIVILEGES ON netops.* TO 'netops'@'localhost';
FLUSH PRIVILEGES;
```

### 3. 表已存在

**错误**: `Table 'xxx' already exists`

**解决方案**:
```bash
# 脚本已包含 DROP TABLE IF EXISTS
# 如果仍然报错，手动删除：
mysql -u root -p netops -e "DROP TABLE IF EXISTS users;"
```

### 4. 字符集问题

**错误**: `Incorrect string value`

**解决方案**:
```sql
-- 检查字符集
SHOW VARIABLES LIKE 'character_set%';

-- 修改为 utf8mb4
ALTER DATABASE netops CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 📚 相关文档

- [认证机制说明](AUTHENTICATION.md)
- [配置文件说明](CONFIG.md)
- [API 接口文档](待补充)

---

## 🔧 维护建议

### 定期备份

```bash
# 备份整个数据库
mysqldump -u root -p netops > backup_$(date +%Y%m%d).sql

# 仅备份数据（不含表结构）
mysqldump -u root -p --no-create-info netops > data_backup_$(date +%Y%m%d).sql

# 恢复备份
mysql -u root -p netops < backup_20260814.sql
```

### 性能优化

```sql
-- 查看表大小
SELECT 
    table_name AS 'Table',
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
FROM information_schema.TABLES
WHERE table_schema = 'netops'
ORDER BY (data_length + index_length) DESC;

-- 优化表
OPTIMIZE TABLE users;
OPTIMIZE TABLE alarm_list;
```

### 索引优化

初始化脚本已创建必要的索引。如果查询性能不佳，可以添加额外索引：

```sql
-- 示例：为常用查询字段添加索引
CREATE INDEX idx_alarm_type ON alarm_list(alarm_type);
CREATE INDEX idx_hostname ON alarm_list(hostname);
```

---

**最后更新**: 2026-08-14
