# 认证机制说明

## 📋 概述

Central-Server 实现了**统一用户表的双模式认证体系**，所有用户数据存储在同一张 `users` 表中，支持两种使用方式：

1. **JWT Token 认证**（Web 用户登录）- 适用于浏览器、移动应用等交互式场景
2. **API Key/Secret 认证**（API 直接调用）- 适用于脚本、服务间调用等自动化场景

**核心特性**：
- ✅ 同一个用户账户，可以选择任意一种方式使用
- ✅ 统一的用户管理和权限控制
- ✅ 统一的角色体系（rid）
- ✅ 无需维护两套用户数据

---

## 📊 用户表结构

```sql
CREATE TABLE users (
    username VARCHAR(40) COLLATE utf8_bin NOT NULL COMMENT '用户名',
    identify VARCHAR(64) COLLATE utf8_bin NOT NULL COMMENT '密码hash或API认证凭证',
    subname VARCHAR(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '中文名',
    phone VARCHAR(20) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '电话',
    mail VARCHAR(50) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '邮箱',
    rid VARCHAR(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '角色ID',
    update_time VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '最近更新时间',
    last_login VARCHAR(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '最近登陆时间',
    PRIMARY KEY (username)
);
```

**字段说明**：
- `username`: 用户唯一标识，同时用作 JWT 登录账号和 API Key
- `identify`: 存储密码 hash（用于 JWT 登录）或 API 认证凭证
- `rid`: 角色 ID，决定用户权限（system/admin 拥有全部权限）

---

## 🔐 认证流程

### 排除路由（无需认证）

以下路由不需要认证：
- `/system/login` - 用户登录
- `/system/health` - 健康检查
- `/tools/ip` - IP 工具

### 认证流程图

```
请求到达
    ↓
检查路径是否在排除列表
    ↓ (否)
检查是否提供 Apptime 头（时间戳）
    ↓ (是)
判断认证方式：
    ├─ 存在 key + secret 头 → API Key 认证
    │   ↓
    │   验证 API Secret
    │   ↓
    │   通过 → 允许访问
    │
    └─ 存在 Authorization 头 → JWT Token 认证
        ↓
        提取 Bearer Token
        ↓
        检查 Sessionid 头
        ↓
        验证 JWT Token
        ↓
        验证 Session 签名 (md5(sign + timestamp) == Sessionid)
        ↓
        检查用户角色权限
        ↓
        通过 → 允许访问
```

---

## 🔑 方式一：JWT Token 认证

### 1. 用户登录

**请求**:
```bash
curl -X POST http://localhost:8080/system/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "secret": "password_hash",
    "timestamp": 1234567890
  }'
```

**响应**:
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "username": "admin",
    "rid": "admin",
    "sign": "abc123def456"
  }
}
```

### 2. 使用 Token 访问 API

**请求头要求**:
```
Authorization: Bearer <token>
Sessionid: <md5(sign + timestamp)>
Apptime: <timestamp>
```

**示例**:
```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
SIGN="abc123def456"
TIMESTAMP=$(date +%s)
SESSION_ID=$(echo -n "${SIGN}${TIMESTAMP}" | md5sum | cut -d' ' -f1)

curl -X GET http://localhost:8080/api/scheduler/jobs \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Sessionid: ${SESSION_ID}" \
  -H "Apptime: ${TIMESTAMP}"
```

### 3. 认证验证步骤

1. **检查 Authorization 头**
   - 必须以 `Bearer ` 开头
   - 提取 Token

2. **检查 Sessionid 头**
   - 必须提供会话 ID

3. **验证 JWT Token**
   - 使用 `jwt_secret_key` 验证签名
   - 检查 Token 是否过期
   - 提取用户信息

4. **验证 Session 签名**
   - 计算: `md5(sign + timestamp)`
   - 对比请求头中的 Sessionid
   - **目的**: 防止 Token 重放攻击

5. **权限检查**
   - `system` 和 `admin` 角色：全部权限
   - 其他角色：检查 URL 权限表

---

## 🔧 方式二：API Key/Secret 认证

### 1. 认证原理

**使用用户表中的数据直接进行 API 认证**：
- `key`: 用户的 `username`
- `secret`: `md5(identify + timestamp)` 计算得出

**优势**：
- 无需先登录获取 Token
- 适合自动化脚本和服务间调用
- 同一个用户账户，两种方式都能用

### 2. 使用 API Key 访问

**请求头要求**:
```
key: <username>
secret: <md5(identify + timestamp)>
Apptime: <timestamp>
```

**Python 示例**:
```python
import hashlib
import time
import requests

# 用户凭证（从 users 表获取）
USERNAME = "api_user"
IDENTIFY = "your_identify_value_from_db"  # 用户表中的 identify 字段

# 生成认证信息
timestamp = str(int(time.time()))
secret = hashlib.md5((IDENTIFY + timestamp).encode()).hexdigest()

# 发起请求
response = requests.post(
    "http://localhost:8080/api/endpoint",
    headers={
        "key": USERNAME,
        "secret": secret,
        "Apptime": timestamp,
        "Content-Type": "application/json"
    },
    json={"data": "value"}
)

print(response.json())
```

**Bash 示例**:
```bash
USERNAME="api_user"
IDENTIFY="your_identify_value_from_db"
TIMESTAMP=$(date +%s)
SECRET=$(echo -n "${IDENTIFY}${TIMESTAMP}" | md5sum | cut -d' ' -f1)

curl -X POST http://localhost:8080/api/endpoint \
  -H "key: ${USERNAME}" \
  -H "secret: ${SECRET}" \
  -H "Apptime: ${TIMESTAMP}" \
  -H "Content-Type: application/json" \
  -d '{"data": "value"}'
```

### 3. 认证验证步骤

1. **检查 key 和 secret 头**
   - 必须同时提供

2. **从数据库查询用户**
   - 根据 key（username）查询 users 表
   - 获取 identify 和 rid

3. **验证签名**
   - 计算预期签名: `md5(identify + timestamp)`
   - 对比请求中的 secret

4. **权限检查**
   - 获取用户角色 (rid)
   - API Key 认证同样受权限控制（除 system/admin 外需检查 URL 权限）

---

## 🆚 两种方式对比

| 特性 | JWT Token 认证 | API Key/Secret 认证 |
|------|----------------|---------------------|
| **使用场景** | Web 应用、移动 App | 脚本、服务间调用 |
| **认证步骤** | 先登录获取 Token → 使用 Token 访问 | 直接使用 username + identify 计算签名 |
| **有效期** | Token 有过期时间（默认 24 小时） | 无过期时间（只要用户存在即可用） |
| **会话管理** | 需要维护 Session 签名 | 每次请求独立计算 |
| **安全性** | Token + Session 双重防护 | 时间戳防重放 |
| **权限控制** | 完整的角色权限检查 | 完整的角色权限检查 |
| **适用角色** | 所有用户类型 | 所有用户类型 |
| **撤销方式** | 等待 Token 过期或更换密钥 | 删除用户或修改 identify |

---

## 💡 使用建议

### 选择 JWT Token 认证的场景：
- ✅ Web 前端应用
- ✅ 移动 App
- ✅ 需要用户登录/登出功能
- ✅ 需要频繁访问 API（Token 有效期内无需重复认证）

### 选择 API Key/Secret 认证的场景：
- ✅ 自动化脚本
- ✅ 定时任务
- ✅ 服务间调用
- ✅ 无交互式的后台程序
- ✅ 需要长期有效的访问凭证

### 同一用户两种方式都用：
完全支持！例如：
- 运维人员通过 Web 界面登录管理（JWT Token）
- 同时编写脚本批量操作设备（API Key/Secret）
- 使用同一个账户，共享同一套权限

---

## ⚠️ 安全注意事项

### JWT Token 认证

**优点**:
- ✅ 用户级别的权限控制
- ✅ Token 有过期时间
- ✅ Session 签名防重放

**注意**:
- ⚠️ Token 无法单独撤销（只能等待过期或更换密钥）
- ⚠️ 修改 `jwt_secret_key` 后所有 Token 失效
- ⚠️ `sign` 字段在整个 Token 生命周期内保持不变

**Session 签名机制**:
```
登录时: 后端生成随机 sign，返回给客户端
请求时: 客户端计算 md5(sign + 当前时间戳) 作为 Sessionid
验证时: 后端从 Token 中获取 sign，重新计算并对比
目的: 每次请求的 Sessionid 都不同，防止重放攻击
```

### API Key/Secret 认证

**优点**:
- ✅ 简单直接，适合机器间调用
- ✅ 无需维护 Session
- ✅ 统一的用户管理和权限控制

**注意**:
- ⚠️ identify 字段是敏感信息，需妥善保管
- ⚠️ identify 泄露需立即修改（等同于密码泄露）
- ⚠️ 建议为 API 专用账户设置独立的 identify 值
- ⚠️ API Key 认证同样受角色权限限制（除 system/admin 外）

---

## 🛡️ 安全建议

### 1. JWT Secret Key 管理

**关键点**:
- JWT Secret Key 是后端专用，**绝不**分发给客户端
- 修改密钥后所有已登录用户需重新登录
- 定期轮换密钥（3-6 个月）

详细说明请查看：[JWT 安全文档](JWT_SECURITY.md)

### 2. 用户账户管理

**Web 用户**:
- identify 字段存储密码 hash（如 md5、sha256 等）
- 登录时验证: `md5(username + identify + "netops" + timestamp) == secret`
- 定期要求用户修改密码

**API 专用用户**:
```sql
-- 创建 API 专用账户示例
INSERT INTO users (username, identify, subname, rid) 
VALUES (
    'collector_service',           -- API Key
    'random_secret_string_here',   -- API Secret（identify字段）
    '数据采集服务',
    'system'                        -- 根据需要分配角色
);
```

**推荐做法**:
- 为每个服务/脚本创建独立的 API 账户
- 使用描述性的 username（如 `monitor_agent`, `backup_script`）
- identify 字段使用强随机字符串（可用 `scripts/generate_secret_key.py` 生成）
- 根据实际需要分配最小权限角色

### 3. identify 字段保护

**存储建议**:
- Web 用户: 存储密码 hash，不要存储明文密码
- API 用户: 使用强随机字符串作为 identify

**更新 identify**:
```sql
-- Web 用户修改密码
UPDATE users SET identify = 'new_password_hash' WHERE username = 'web_user';

-- API 用户重新生成凭证
UPDATE users SET identify = 'new_random_secret' WHERE username = 'api_user';
```

**泄露处理**:
1. 立即修改 identify 字段
2. 检查访问日志，确认是否有异常访问
3. 通知相关人员更新凭证

### 4. 时间戳验证

**当前配置**:
- 时间戳容差: 5 分钟（300 秒）
- 验证时间差: `abs(服务器时间 - 请求时间) <= 300`

**注意事项**:
- 确保服务器时间准确（使用 NTP 同步）
- 客户端时间偏差过大会导致认证失败
- 可在 `../config/config.py` 中调整 `timestamp_tolerance`

### 5. HTTPS 强制

**生产环境必须使用 HTTPS**:
- Token、identify、secret 在 HTTP 下明文传输
- 容易被中间人攻击截获
- 建议使用 Nginx 反向代理并配置 SSL

**Nginx 配置示例**:
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 6. 权限最小化原则

**角色分配**:
- `system`: 系统管理员，完全权限
- `admin`: 普通管理员，完全权限
- `其他角色`: 按需分配 URL 权限

**API 用户建议**:
- 不要默认分配 system/admin 角色
- 根据服务实际需要创建专用角色
- 定期审计 API 用户的访问日志

---

## 📝 使用示例

### 示例 1: Web 用户登录并访问

```python
import requests
import hashlib
import time

# 1. 登录获取 Token
username = "admin"
password_hash = "hashed_password"  # 实际是 users 表中的 identify
timestamp = int(time.time())

# 计算登录签名
secret = hashlib.md5(
    f"{username}{password_hash}netops{timestamp}".encode()
).hexdigest()

login_response = requests.post(
    "http://localhost:8080/system/login",
    json={
        "username": username,
        "secret": secret,
        "timestamp": timestamp
    }
)

data = login_response.json()["data"]
token = data["token"]
sign = data["sign"]

# 2. 使用 Token 访问 API
timestamp = int(time.time())
sessionid = hashlib.md5(f"{sign}{timestamp}".encode()).hexdigest()

api_response = requests.get(
    "http://localhost:8080/api/scheduler/jobs",
    headers={
        "Authorization": f"Bearer {token}",
        "Sessionid": sessionid,
        "Apptime": str(timestamp)
    }
)

print(api_response.json())
```

### 示例 2: API 直接调用

```python
import requests
import hashlib
import time

# 用户凭证（从 users 表获取）
API_KEY = "collector_service"
API_IDENTIFY = "your_identify_from_db"

# 生成签名
timestamp = str(int(time.time()))
secret = hashlib.md5((API_IDENTIFY + timestamp).encode()).hexdigest()

# 直接调用 API
response = requests.post(
    "http://localhost:8080/api/data/collect",
    headers={
        "key": API_KEY,
        "secret": secret,
        "Apptime": timestamp,
        "Content-Type": "application/json"
    },
    json={
        "device": "switch-01",
        "data": {"interface": "GigabitEthernet0/0/1", "status": "up"}
    }
)

print(response.json())
```

### 示例 3: 同一用户两种方式都用

```python
# 用户信息（users 表）
# username: "devops_user"
# identify: "strong_random_secret_abc123"
# rid: "admin"

# 方式 1: 通过 Web 界面登录管理
# 使用 JWT Token 认证，适合交互式操作

# 方式 2: 编写自动化脚本
# 使用 API Key/Secret 认证，无需先登录
API_KEY = "devops_user"
API_IDENTIFY = "strong_random_secret_abc123"

# 脚本中直接调用
def call_api(endpoint, data):
    timestamp = str(int(time.time()))
    secret = hashlib.md5((API_IDENTIFY + timestamp).encode()).hexdigest()
    
    return requests.post(
        f"http://localhost:8080{endpoint}",
        headers={
            "key": API_KEY,
            "secret": secret,
            "Apptime": timestamp
        },
        json=data
    )
```

---

## 🔍 问题排查

### 401 认证失败

**JWT Token 认证失败可能原因**:
1. Token 格式错误或缺失
2. Token 已过期（超过 24 小时）
3. JWT Secret Key 不匹配（服务端修改了密钥）
4. Sessionid 计算错误
5. Apptime 未提供或已过期（超过 5 分钟）

**API Key/Secret 认证失败可能原因**:
1. username（key）不存在
2. identify 字段不匹配
3. secret 计算错误（应为 `md5(identify + timestamp)`）
4. Apptime 未提供或已过期

**排查步骤**:
```bash
# 1. 检查用户是否存在
mysql> SELECT username, rid, subname FROM users WHERE username = 'your_username';

# 2. 验证 API Key/Secret 认证（Python）
import hashlib
import time

username = "your_username"
identify = "your_identify_from_db"
timestamp = str(int(time.time()))
secret = hashlib.md5((identify + timestamp).encode()).hexdigest()

print(f"key: {username}")
print(f"secret: {secret}")
print(f"Apptime: {timestamp}")

# 3. 测试认证
curl -v -X POST http://localhost:8080/api/test \
  -H "key: your_username" \
  -H "secret: calculated_secret" \
  -H "Apptime: $(date +%s)"

# 4. 查看服务日志
tail -f logs/central-server.log | grep "认证"
```

### 403 权限不足

**可能原因**:
1. 用户角色不是 system/admin
2. URL 权限表中未配置该路径
3. 角色与页面的权限关联未配置

**解决方案**:
```sql
-- 检查用户角色
SELECT username, rid FROM users WHERE username = 'your_username';

-- 检查角色权限
SELECT * FROM role_pages WHERE rid = 'your_role';

-- 检查 URL 权限配置
SELECT * FROM page_uris WHERE uri = '/api/your/path';

-- 为角色添加页面权限
INSERT INTO role_pages (rid, page_id, privilege) 
VALUES ('your_role', page_id, 1);
```

### 时间戳过期

**错误信息**: `时间戳过期`

**可能原因**:
1. 客户端时间与服务器时间相差超过 5 分钟
2. 请求在网络中传输时间过长
3. 客户端使用了缓存的旧时间戳

**解决方案**:
```bash
# 1. 检查服务器时间
date

# 2. 检查客户端时间
date

# 3. 同步时间（客户端）
sudo ntpdate -u pool.ntp.org

# 4. 如果时间同步正常但仍报错，可以在 config.py 中调整容差
timestamp_tolerance = 600  # 增加到 10 分钟
```

### 用户不存在或密码错误

**Web 登录失败**:
- 检查 username 是否正确
- 检查密码 hash 计算方式
- 登录签名计算: `md5(username + identify + "netops" + timestamp)`

**API 认证失败**:
- 检查 key（username）是否存在
- 检查 identify 值是否正确
- API 签名计算: `md5(identify + timestamp)`

---

## 📚 相关文档

- [JWT 安全管理](JWT_SECURITY.md)
- [配置说明](CONFIG.md)
- [API 接口文档](待补充)

---

**最后更新**: 2026-08-14
