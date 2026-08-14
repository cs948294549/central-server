# Docker 部署目录

本目录包含 Central-Server 项目的 Docker 相关文件和脚本。

## 📁 目录结构

```
docker/
├── Dockerfile              # Docker 镜像构建文件
├── .dockerignore          # Docker 构建排除文件
├── app_build.sh           # 镜像构建脚本
├── app_start.sh           # 容器启动脚本
├── logs.sh                # 日志查看脚本
└── README.md              # 本文件
```

## 🚀 快速开始

### 单容器部署（使用外部依赖服务）

Central-Server 应用独立部署，MySQL、Redis、Kafka 等依赖服务使用已有的外部服务。

```bash
# 1. 构建镜像
./docker/app_build.sh

# 2. 配置环境变量
export MYSQL_HOST=192.168.1.100
export MYSQL_PASSWORD=your_password
export REDIS_HOST=192.168.1.101
export KAFKA_SERVER=192.168.1.102:9092

# 3. 启动容器
./docker/app_start.sh

# 4. 查看日志
./docker/logs.sh
```

---

## 🔧 脚本说明

### app_build.sh - 镜像构建脚本

构建 Central-Server 的 Docker 镜像。

**用法**:
```bash
./docker/app_build.sh [版本标签]

# 示例
./docker/app_build.sh          # 构建 v1 版本（默认）
./docker/app_build.sh v2.0     # 构建 v2.0 版本
```

**功能**:
- 检查必要文件是否存在
- 使用 `--no-cache` 和 `--pull` 确保最新构建
- 自动标记 latest 标签
- 显示构建结果和后续步骤

---

### app_start.sh - 容器启动脚本

启动 Central-Server 容器。

**用法**:
```bash
./docker/app_start.sh [版本标签]

# 示例
./docker/app_start.sh          # 启动 v1 版本（默认）
./docker/app_start.sh v2.0     # 启动 v2.0 版本
```

**环境变量配置**:
```bash
# 服务端口
API_PORT=8080                  # API 服务端口（默认 8080）
WEBSOCKET_PORT=8081            # WebSocket 端口（默认 8081）

# MySQL 配置
MYSQL_HOST=localhost           # MySQL 主机（默认 localhost）
MYSQL_PORT=3306                # MySQL 端口（默认 3306）
MYSQL_USER=root                # MySQL 用户（默认 root）
MYSQL_PASSWORD=root            # MySQL 密码（默认 root）
MYSQL_DATABASE=netops          # 数据库名（默认 netops）

# Redis 配置
REDIS_HOST=localhost           # Redis 主机（默认 localhost）
REDIS_PORT=6379                # Redis 端口（默认 6379）
REDIS_DB=0                     # Redis 数据库（默认 0）

# Kafka 配置
KAFKA_SERVER=localhost:9092    # Kafka 服务器（默认 localhost:9092）

# 数据目录
CENTRAL_DATA_DIR=/data         # 数据根目录（默认为当前目录）
```

**功能**:
- 自动检查镜像是否存在
- 清理旧容器（如果存在）
- 创建必要的数据目录（logs、files）
- 自动复制配置文件模板
- 挂载日志和文件目录
- 配置健康检查
- 启动后检查服务状态

---

### logs.sh - 日志查看脚本

快速查看和分析容器日志。

**用法**:
```bash
./docker/logs.sh [选项]

# 选项说明
follow, -f        实时跟踪 Docker 日志（默认）
tail [N]          查看最后 N 行日志（默认 100）
app               查看应用日志文件列表
server            实时跟踪主服务日志
error             查看错误日志
search [keyword]  搜索包含关键字的日志
clear             清空应用日志文件
health            检查服务健康状态
help, -h          显示帮助信息
```

**示例**:
```bash
./docker/logs.sh                    # 实时查看日志
./docker/logs.sh tail 200           # 查看最后 200 行
./docker/logs.sh error              # 查看错误日志
./docker/logs.sh search "API"       # 搜索包含 API 的日志
./docker/logs.sh health             # 检查服务健康状态
```

---

### start.sh - 交互式启动脚本

使用 Docker Compose 启动完整服务栈的交互式脚本。

**用法**:
```bash
./docker/start.sh
```

**功能菜单**:
1. 启动所有服务（首次启动）
2. 启动服务（后台运行）
3. 停止服务
4. 重启服务
5. 查看日志
6. 查看服务状态
7. 仅启动 Central Server
8. 清理所有数据（危险操作）

---

## 📊 依赖服务配置

Central-Server 依赖以下外部服务：

| 服务 | 默认端口 | 说明 |
|------|---------|------|
| MySQL | 3306 | 数据库 |
| Redis | 6379 | 缓存和消息队列 |
| Kafka | 9092 | 消息队列（可选） |
| Elasticsearch | 9200 | 日志存储（可选） |

**确保外部服务已部署并可访问**。

---

## 🔍 验证部署

### 1. 检查容器状态

```bash
docker ps | grep central-server
```

### 2. 健康检查

```bash
# 使用日志脚本
./docker/logs.sh health

# 或手动检查
curl http://localhost:8080/system/health
curl http://localhost:8081/
```

### 3. 查看日志

```bash
# 实时日志
./docker/logs.sh

# 错误日志
./docker/logs.sh error
```

---

## 🛠️ 常用操作

```bash
# 停止容器
docker stop central-server

# 重启容器
docker restart central-server

# 删除容器
docker rm central-server

# 进入容器
docker exec -it central-server bash

# 查看容器详情
docker inspect central-server
```

---

## 🐛 故障排查

### 问题：容器启动失败

**检查步骤**:
```bash
# 1. 查看容器日志
docker logs central-server

# 2. 检查端口占用
lsof -i :8080
lsof -i :8081

# 3. 检查配置文件
cat config.py

# 4. 检查依赖服务
docker-compose ps
```

### 问题：无法连接数据库

**解决方案**:
```bash
# 1. 检查 MySQL 是否运行
docker-compose ps mysql

# 2. 测试数据库连接
docker-compose exec mysql mysql -uroot -proot -e "SHOW DATABASES;"

# 3. 检查网络连接
docker network ls
docker network inspect central-network
```

### 问题：时区不正确

**解决方案**:
```bash
# 检查容器时区
docker exec central-server date

# 时区已在 Dockerfile 中配置为 Asia/Shanghai (UTC+8)
# 如需修改，编辑 Dockerfile 中的 TZ 环境变量
```

---

## 📝 配置说明

### 单容器模式配置

编辑 `config.py` 文件：

```python
class Config:
    # API 服务配置
    service_ip = "0.0.0.0"
    service_port = 8080
    
    # WebSocket 配置
    websocket_enable = True
    websocket_port = 8081
    
    # MySQL 配置
    mysql_config = {
        "db_host": "localhost",
        "db_user": "root",
        "db_token": "your_password",
        "db_port": 3306,
    }
    
    # Redis 配置
    redis_host = "localhost"
    redis_port = 6379
    
    # Kafka 配置
    kafka_server = ["localhost:9092"]
```

### Docker Compose 模式配置

编辑 `docker-compose.yml` 中的环境变量：

```yaml
services:
  central-server:
    environment:
      - MYSQL_HOST=mysql
      - MYSQL_PASSWORD=your_secure_password
      - REDIS_HOST=redis
      - KAFKA_SERVER=kafka:9092
```

---

## 🔐 生产环境建议

1. **修改默认密码**
   ```yaml
   MYSQL_ROOT_PASSWORD=your_strong_password
   ```

2. **使用环境变量文件**
   ```bash
   # 创建 .env 文件
   cp .env.example .env
   # 编辑敏感信息
   vim .env
   ```

3. **限制资源使用**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 2G
   ```

4. **配置日志轮转**
   ```yaml
   logging:
     driver: "json-file"
     options:
       max-size: "10m"
       max-file: "3"
   ```

5. **启用 HTTPS**
   - 在前端配置 Nginx 反向代理
   - 配置 SSL 证书

---

## 📚 相关文档

- [快速启动指南](../docs/QUICKSTART.md)
- [完整部署指南](../docs/DOCKER_DEPLOY.md)
- [项目架构文档](../README.md)

---

**最后更新**: 2026-08-14
