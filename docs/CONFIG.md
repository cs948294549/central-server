# 配置文件说明

本文档详细说明 Central-Server 的配置项及其用途。

## 📄 配置文件位置

- `config.py` - 实际使用的配置文件
- `config_example.py` - 配置文件模板

## 🔧 配置项说明

### 1. API 服务配置

```python
# API 服务监听地址和端口
service_ip = "0.0.0.0"      # 监听地址，0.0.0.0 表示监听所有网卡
service_port = 8080         # API 服务端口

# 日志级别
log_level = "INFO"          # 可选：DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### 2. WebSocket 服务配置

```python
websocket_enable = True     # 是否启用 WebSocket 服务
websocket_ip = "0.0.0.0"    # WebSocket 监听地址
websocket_port = 8081       # WebSocket 服务端口
```

### 3. JWT 认证配置

```python
jwt_secret_key = "your_secret_key_here"  # JWT 签名密钥（生产环境必须修改）
jwt_algorithm = "HS256"                   # JWT 加密算法
jwt_expire_hours = 24                     # JWT Token 有效期（小时）
```

**⚠️ 重要说明**:
- **JWT Secret Key 是后端专用密钥**，仅用于服务端签名和验证 Token
- **不要将此密钥分发给客户端或前端**
- **修改密钥的影响**：
  - 所有已签发的 JWT Token 将立即失效
  - 所有已登录用户需要重新登录
  - 建议在维护窗口期间进行密钥更换
- **密钥轮换策略**：
  - 定期更换密钥（建议 3-6 个月）
  - 更换前通知用户
  - 选择低峰时段操作

**安全建议**:
- 生产环境务必修改 `jwt_secret_key` 为随机字符串
- 使用 `scripts/generate_secret_key.py` 生成安全的密钥
- 密钥长度至少 64 字节
- 不要将密钥提交到版本控制系统

### 4. API Key 认证配置

```python
api_secrets = {
    "agent1": "secret_string_here",  # API Key 和对应的 Secret
    "agent2": "another_secret",
}
```

**用途**: 用于机器间 API 调用认证

**使用方式**:
```bash
curl -X POST http://localhost:8080/api/endpoint \
  -H "key: agent1" \
  -H "secret: secret_string_here" \
  -H "Apptime: $(date +%s)"
```

### 5. 数据采集配置

```python
collect_enable = True                # 是否启用数据采集服务
collect_kafka_topic = "collect_data" # Kafka 数据采集主题
```

### 6. Syslog 配置

```python
syslog_enable = True                # 是否启用 Syslog 服务
syslog_kafka_topic = "syslog_data"  # Kafka Syslog 主题
```

### 7. 消息队列配置

#### Kafka 配置
```python
kafka_server = ["localhost:9092"]   # Kafka 服务器列表
```

**集群配置示例**:
```python
kafka_server = [
    "kafka1.example.com:9092",
    "kafka2.example.com:9092",
    "kafka3.example.com:9092"
]
```

#### Redis 队列配置
```python
queue_key_collect = "queue:collect_data"  # Redis 采集队列 Key
queue_key_syslog = "queue:syslog_data"    # Redis Syslog 队列 Key
```

**说明**: Redis 队列可作为 Kafka 的轻量级替代方案

### 8. Redis 配置

```python
redis_host = "localhost"    # Redis 主机地址
redis_port = 6379          # Redis 端口
redis_db = 0               # Redis 数据库编号
```

### 9. MySQL 配置

```python
mysql_config = {
    "db_host": "localhost",  # MySQL 主机地址
    "db_user": "root",       # MySQL 用户名
    "db_token": "root",      # MySQL 密码
    "db_port": 3306,         # MySQL 端口
}
```

**安全建议**:
- 生产环境使用强密码
- 创建专用数据库用户，不要使用 root
- 限制数据库用户权限

---

## 🔐 生成安全密钥

### 使用密钥生成工具

```bash
# 运行密钥生成脚本
python scripts/generate_secret_key.py
```

输出示例：
```
============================================================
Central-Server 密钥生成工具
============================================================

JWT Secret Key (用于 jwt_secret_key):
  aG9zdGxvY2FsaG9zdGxvY2FsaG9zdGxvY2FsaG9zdGxvY2Fs...

API Secrets (用于 api_secrets):
  "agent1": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
  "agent2": "b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7"
  "agent3": "c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8"
```

### 手动生成密钥

#### Python 方式
```python
import secrets
import base64

# 生成 JWT Secret Key
jwt_secret = base64.b64encode(secrets.token_bytes(64)).decode('utf-8')
print(jwt_secret)

# 生成 API Secret
api_secret = secrets.token_hex(16)
print(api_secret)
```

#### OpenSSL 方式
```bash
# 生成 JWT Secret Key
openssl rand -base64 64

# 生成 API Secret
openssl rand -hex 16
```

---

## 🌍 环境变量支持

配置文件支持通过环境变量覆盖（Docker 部署时特别有用）。

### 环境变量映射

| 配置项 | 环境变量 | 示例 |
|--------|----------|------|
| service_port | SERVICE_PORT | 8080 |
| websocket_port | WEBSOCKET_PORT | 8081 |
| mysql_config.db_host | MYSQL_HOST | localhost |
| mysql_config.db_user | MYSQL_USER | root |
| mysql_config.db_token | MYSQL_PASSWORD | password |
| redis_host | REDIS_HOST | localhost |
| kafka_server | KAFKA_SERVER | localhost:9092 |

### Docker 使用示例

```bash
docker run -d \
  -e MYSQL_HOST=mysql.example.com \
  -e MYSQL_PASSWORD=secure_password \
  -e REDIS_HOST=redis.example.com \
  central-server:latest
```

### Docker Compose 示例

```yaml
services:
  central-server:
    environment:
      - MYSQL_HOST=mysql
      - MYSQL_PASSWORD=${MYSQL_PASSWORD}
      - REDIS_HOST=redis
      - KAFKA_SERVER=kafka:9092
```

---

## 📝 配置最佳实践

### 1. 开发环境配置

```python
# config.py (开发环境)
class Config:
    service_port = 8080
    log_level = "DEBUG"
    
    # 使用本地服务
    mysql_config = {
        "db_host": "localhost",
        "db_user": "dev",
        "db_token": "dev123",
        "db_port": 3306,
    }
    
    redis_host = "localhost"
    kafka_server = ["localhost:9092"]
```

### 2. 生产环境配置

```python
# config.py (生产环境)
import os

class Config:
    service_port = int(os.getenv("SERVICE_PORT", 8080))
    log_level = "WARNING"
    
    # 使用环境变量
    mysql_config = {
        "db_host": os.getenv("MYSQL_HOST", "localhost"),
        "db_user": os.getenv("MYSQL_USER", "root"),
        "db_token": os.getenv("MYSQL_PASSWORD", ""),
        "db_port": int(os.getenv("MYSQL_PORT", 3306)),
    }
    
    redis_host = os.getenv("REDIS_HOST", "localhost")
    kafka_server = os.getenv("KAFKA_SERVER", "localhost:9092").split(",")
    
    # 使用强密钥
    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "your-production-secret-key")
```

### 3. 配置文件版本控制

```bash
# .gitignore
config.py           # 不提交实际配置
*.secret            # 不提交密钥文件
.env               # 不提交环境变量文件
```

只提交 `config_example.py` 作为模板。

---

## 🔍 配置验证

### 启动时检查

服务启动时会自动验证配置：
- 检查必要的配置项是否存在
- 验证端口是否可用
- 测试数据库连接

### 手动验证配置

```python
# 验证配置脚本
from config import Config

print("API 端口:", Config.service_port)
print("WebSocket 端口:", Config.websocket_port)
print("MySQL 主机:", Config.mysql_config["db_host"])
print("Redis 主机:", Config.redis_host)
print("Kafka 服务器:", Config.kafka_server)
```

---

## 🚨 常见问题

### Q1: 修改配置后不生效？

**解决**: 重启服务
```bash
# Docker 方式
docker restart central-server

# 本地方式
pkill -f main.py
python main.py
```

### Q2: JWT Token 验证失败？

**原因**: `jwt_secret_key` 不一致

**解决**: 确保所有服务使用相同的 `jwt_secret_key`

### Q3: 数据库连接失败？

**检查步骤**:
1. 验证 MySQL 配置是否正确
2. 测试数据库连接
   ```bash
   mysql -h localhost -u root -p
   ```
3. 检查防火墙规则
4. 查看日志文件

---

## 📚 相关文档

- [快速启动指南](QUICKSTART.md)
- [Docker 部署指南](DOCKER_DEPLOY.md)
- [安全配置指南](SECURITY.md)（待补充）

---

**最后更新**: 2026-08-14
