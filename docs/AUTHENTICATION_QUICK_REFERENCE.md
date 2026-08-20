# 认证快速参考

## 🚀 快速开始

### 用户表结构
```sql
users (
    username,   -- 用户名/API Key
    identify,   -- 密码hash/API Secret凭证
    rid,        -- 角色ID
    ...
)
```

---

## 认证方式选择

| 场景 | 使用方式 | 请求头 |
|------|---------|--------|
| Web登录 | JWT Token | `Authorization: Bearer <token>` + `Sessionid` + `Apptime` |
| API调用 | Key/Secret | `key: <username>` + `secret: <md5(identify+timestamp)>` + `Apptime` |

---

## JWT Token 认证（Web用户）

### 1. 登录
```bash
POST /system/login
{
  "username": "admin",
  "secret": "md5(username + identify + 'netops' + timestamp)",
  "timestamp": 1234567890
}
```

### 2. 访问API
```bash
Authorization: Bearer <token>
Sessionid: md5(sign + timestamp)
Apptime: <timestamp>
```

---

## API Key/Secret 认证（脚本/服务）

### 请求头
```bash
key: <username>
secret: md5(identify + timestamp)
Apptime: <timestamp>
```

### Python示例
```python
import hashlib, time

USERNAME = "api_user"
IDENTIFY = "from_users_table"  # users.identify字段
timestamp = str(int(time.time()))
secret = hashlib.md5((IDENTIFY + timestamp).encode()).hexdigest()

headers = {
    "key": USERNAME,
    "secret": secret,
    "Apptime": timestamp
}
```

### Bash示例
```bash
USERNAME="api_user"
IDENTIFY="from_users_table"
TIMESTAMP=$(date +%s)
SECRET=$(echo -n "${IDENTIFY}${TIMESTAMP}" | md5sum | cut -d' ' -f1)

curl -H "key: ${USERNAME}" \
     -H "secret: ${SECRET}" \
     -H "Apptime: ${TIMESTAMP}" \
     http://localhost:8080/api/endpoint
```

---

## 创建用户

### Web用户
```sql
INSERT INTO users (username, identify, subname, rid) 
VALUES ('web_user', 'password_hash', '张三', 'admin');
```

### API用户
```sql
INSERT INTO users (username, identify, subname, rid) 
VALUES ('collector', 'random_secret_abc123', '采集服务', 'system');
```

---

## 权限控制

- `system` / `admin`: 全部权限
- 其他角色: 检查 URL 权限表

---

## 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| 401 未提供时间戳 | 缺少 Apptime 头 | 添加 `Apptime: $(date +%s)` |
| 401 时间戳过期 | 时间差超过5分钟 | 同步服务器时间 |
| 401 API认证失败 | secret计算错误 | 检查: `md5(identify + timestamp)` |
| 401 认证签名异常 | Sessionid错误 | 检查: `md5(sign + timestamp)` |
| 403 权限不足 | 角色权限不够 | 检查用户 rid 和 URL 权限配置 |

---

## 安全检查清单

- [ ] 生产环境使用 HTTPS
- [ ] 妥善保管 identify 字段（等同于密码）
- [ ] 定期轮换 JWT Secret Key（`../config/config.py`）
- [ ] API用户按需分配最小权限
- [ ] 定期审计访问日志
- [ ] 服务器时间使用 NTP 同步

---

**详细文档**: [AUTHENTICATION.md](AUTHENTICATION.md)
