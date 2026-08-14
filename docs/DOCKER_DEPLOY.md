# Docker 部署指南

## 📦 快速开始

### 使用启动脚本（推荐）

```bash
# 给脚本添加执行权限
chmod +x start.sh

# 运行启动脚本
./start.sh
```

启动脚本提供了交互式菜单，包括：
1. 首次启动（构建镜像）
2. 启动服务
3. 停止服务
4. 重启服务
5. 查看日志
6. 查看服务状态
7. 仅启动 Central Server
8. 清理所有数据

### 手动启动

```bash
# 首次启动（构建镜像并启动所有服务）
docker-compose up --build -d

# 后续启动
docker-compose up -d

# 停止服务
docker-compose down

# 查看日志
docker-compose logs -f central-server

# 查看所有服务状态
docker-compose ps
```

---

## 🏗️ 架构说明

### 服务组件

Docker Compose 会启动以下服务：

| 服务名 | 端口 | 说明 |
|--------|------|------|
| central-server | 8080, 8081 | 主应用（API + WebSocket） |
| redis | 6379 | 缓存和消息队列 |
| mysql | 3306 | 数据库 |
| kafka | 9092 | 消息队列 |
| zookeeper | 2181 | Kafka 依赖 |
| elasticsearch | 9200, 9300 | 日志存储（可选） |

### 端口映射

- **8080**: API 服务（HTTP REST API）
- **8081**: WebSocket 服务（实时推送）
- **6379**: Redis
- **3306**: MySQL
- **9092**: Kafka
- **9200**: Elasticsearch HTTP API

---

## ⚙️ 配置说明

### 环境变量

在 `docker-compose.yml` 中可以配置以下环境变量：

```yaml
environment:
  # 服务配置
  - SERVICE_IP=0.0.0.0
  - SERVICE_PORT=8080
  - WEBSOCKET_PORT=8081
  - LOG_LEVEL=INFO

  # 功能开关
  - WEBSOCKET_ENABLE=true
  - COLLECT_ENABLE=true
  - SYSLOG_ENABLE=true

  # Kafka 配置
  - KAFKA_SERVER=kafka:9092
  
  # Redis 配置
  - REDIS_HOST=redis
  
  # MySQL 配置
  - MYSQL_HOST=mysql
  - MYSQL_USER=root
  - MYSQL_PASSWORD=root
```

### 使用 .env 文件

创建 `.env` 文件覆盖默认配置：

```bash
# .env
SERVICE_PORT=8080
WEBSOCKET_PORT=8081
LOG_LEVEL=DEBUG
MYSQL_PASSWORD=your_secure_password
```

---

## 🔧 常用操作

### 查看服务状态

```bash
docker-compose ps
```

### 查看实时日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 仅查看 central-server 日志
docker-compose logs -f central-server

# 查看最近 100 行日志
docker-compose logs --tail=100 central-server
```

### 进入容器

```bash
# 进入 central-server 容器
docker-compose exec central-server bash

# 进入 MySQL 容器
docker-compose exec mysql mysql -uroot -proot netops

# 进入 Redis 容器
docker-compose exec redis redis-cli
```

### 重启单个服务

```bash
# 重启 central-server
docker-compose restart central-server

# 重启 MySQL
docker-compose restart mysql
```

### 重新构建镜像

```bash
# 重新构建并启动
docker-compose up --build -d

# 强制重新构建（不使用缓存）
docker-compose build --no-cache central-server
docker-compose up -d
```

### 扩展服务实例

```bash
# 运行 3 个 central-server 实例
docker-compose up -d --scale central-server=3
```

---

## 📊 健康检查

### 检查服务健康状态

```bash
# 查看健康状态
docker-compose ps

# API 健康检查
curl http://localhost:8080/health

# WebSocket 健康检查
curl http://localhost:8081/
```

### 健康检查配置

在 Dockerfile 中配置：

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
```

---

## 💾 数据持久化

### 数据卷

Docker Compose 会自动创建以下数据卷：

- `redis-data`: Redis 数据
- `mysql-data`: MySQL 数据
- `kafka-data`: Kafka 数据
- `zookeeper-data`: Zookeeper 数据
- `es-data`: Elasticsearch 数据

### 备份数据

```bash
# 备份 MySQL
docker-compose exec mysql mysqldump -uroot -proot netops > backup.sql

# 备份 Redis
docker-compose exec redis redis-cli SAVE
docker cp central-redis:/data/dump.rdb ./redis-backup.rdb

# 查看所有数据卷
docker volume ls | grep central
```

### 恢复数据

```bash
# 恢复 MySQL
docker-compose exec -T mysql mysql -uroot -proot netops < backup.sql

# 恢复 Redis
docker cp ./redis-backup.rdb central-redis:/data/dump.rdb
docker-compose restart redis
```

---

## 🚨 故障排查

### 容器无法启动

1. 查看容器日志：
```bash
docker-compose logs central-server
```

2. 检查端口占用：
```bash
# macOS/Linux
lsof -i :8080
lsof -i :8081

# 或使用
netstat -tlnp | grep 8080
```

3. 检查依赖服务：
```bash
docker-compose ps
```

### 连接数据库失败

1. 检查 MySQL 是否就绪：
```bash
docker-compose exec mysql mysqladmin ping -h localhost -uroot -proot
```

2. 等待 MySQL 初始化完成（首次启动需要 30-60 秒）

3. 手动测试连接：
```bash
docker-compose exec mysql mysql -uroot -proot -e "SHOW DATABASES;"
```

### Kafka 连接问题

1. 检查 Kafka 和 Zookeeper：
```bash
docker-compose logs kafka
docker-compose logs zookeeper
```

2. 验证 Kafka 主题：
```bash
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### 内存不足

如果遇到内存问题，可以调整 Elasticsearch 的内存限制：

```yaml
# docker-compose.yml
elasticsearch:
  environment:
    - "ES_JAVA_OPTS=-Xms256m -Xmx256m"  # 降低内存使用
```

---

## 🔒 生产环境部署建议

### 1. 使用环境变量管理敏感信息

```bash
# 不要在 docker-compose.yml 中硬编码密码
export MYSQL_ROOT_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)
```

### 2. 启用网络隔离

```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # 后端网络不对外
```

### 3. 限制资源使用

```yaml
services:
  central-server:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 4. 配置日志轮转

```yaml
services:
  central-server:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 5. 使用 HTTPS

在前端配置 Nginx 反向代理：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
    }
    
    location /socket.io/ {
        proxy_pass http://localhost:8081;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 6. 定期备份

设置 cron 任务自动备份：

```bash
# 每天凌晨 2 点备份
0 2 * * * cd /path/to/central-server && docker-compose exec mysql mysqldump -uroot -proot netops > /backup/mysql-$(date +\%Y\%m\%d).sql
```

---

## 🔄 更新部署

### 更新应用代码

```bash
# 1. 拉取最新代码
git pull

# 2. 重新构建镜像
docker-compose build central-server

# 3. 滚动更新（无停机）
docker-compose up -d --no-deps central-server
```

### 更新依赖服务

```bash
# 更新所有服务镜像
docker-compose pull

# 重启服务
docker-compose up -d
```

---

## 🧹 清理

### 停止并删除容器

```bash
# 停止并删除容器（保留数据卷）
docker-compose down

# 停止并删除容器和数据卷（危险操作！）
docker-compose down -v
```

### 清理未使用的资源

```bash
# 清理停止的容器
docker container prune -f

# 清理未使用的镜像
docker image prune -a -f

# 清理未使用的数据卷
docker volume prune -f

# 清理所有未使用的资源
docker system prune -a --volumes -f
```

---

## 📝 开发环境 vs 生产环境

### 开发环境

```bash
# 使用开发配置
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

创建 `docker-compose.dev.yml`：

```yaml
version: '3.8'

services:
  central-server:
    volumes:
      - .:/app  # 挂载代码目录，支持热重载
    environment:
      - LOG_LEVEL=DEBUG
      - FLASK_DEBUG=1
```

### 生产环境

```bash
# 使用生产配置
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

创建 `docker-compose.prod.yml`：

```yaml
version: '3.8'

services:
  central-server:
    restart: always
    environment:
      - LOG_LEVEL=WARNING
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

---

## 🔗 相关链接

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Flask-SocketIO 文档](https://flask-socketio.readthedocs.io/)

---

**最后更新**: 2026-08-14
