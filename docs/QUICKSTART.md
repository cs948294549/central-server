# 快速启动指南

## 🚀 5分钟快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆代码
git clone <repository-url>
cd central-server

# 2. 一键启动
./start.sh

# 选择选项 1 (首次启动)
```

就这么简单！所有服务（API、WebSocket、数据库、消息队列）都会自动启动。

**访问地址**:
- API 服务: http://localhost:8080
- WebSocket: ws://localhost:8081
- 健康检查: http://localhost:8080/system/health

---

### 方式二：本地开发部署

#### 1. 安装依赖

```bash
# Python 3.9+
pip install -r requirements.txt
```

#### 2. 配置文件

```bash
# 复制配置模板
cp config_example.py config.py

# 编辑配置（修改数据库连接等）
vim config.py
```

#### 3. 初始化数据库

```bash
scripts/db_create.sql
```

#### 4. 启动服务

```bash
# 前台运行（开发调试）
python main.py

# 后台运行（生产环境）
nohup python3 -u main.py > central-server.log 2>&1 &
```

---

## 📋 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| API 服务 | 8080 | HTTP REST API |
| WebSocket | 8081 | 实时消息推送 |
| MySQL | 3306 | 数据库 |
| Redis | 6379 | 缓存/队列 |
| Kafka | 9092 | 消息队列 |
| Elasticsearch | 9200 | 日志存储 |

---

## ✅ 验证部署

### 1. 检查服务状态

```bash
# Docker 方式
docker-compose ps

# 本地方式
ps aux | grep main.py
```

### 2. 健康检查

```bash
# API 健康检查
curl http://localhost:8080/system/health

# WebSocket 健康检查
curl http://localhost:8081/
```

### 3. 查看日志

```bash
# Docker 方式
docker-compose logs -f central-server

# 本地方式
tail -f central-server.log
```

---

## 🔧 基本配置

### 最小配置（仅 API + WebSocket）

```python
# config.py
class Config:
    # API 配置
    service_port = 8080
    
    # WebSocket 配置
    websocket_enable = True
    websocket_port = 8081
    
    # 禁用其他服务（可选）
    collect_enable = False
    syslog_enable = False
```

### 完整配置

参考 `config_example.py` 文件。

---

## 🌐 API 使用示例

### 1. 用户登录

```bash
curl -X POST http://localhost:8080/system/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "secret": "password",
    "timestamp": 1234567890
  }'
```

### 2. 查看任务列表

```bash
curl http://localhost:8080/api/scheduler/jobs \
  -H "Authorization: Bearer <your_token>" \
  -H "Sessionid: <session_id>" \
  -H "Apptime: <timestamp>"
```

### 3. 发送 WebSocket 消息

```bash
curl -X POST http://localhost:8081/send_msg \
  -H "Content-Type: application/json" \
  -d '{
    "target": "alarm_channel",
    "msg": {"type": "alert", "content": "System alert"}
  }'
```

---

## 🐛 常见问题

### 端口被占用

```bash
# 查找占用端口的进程
lsof -i :8080

# 修改配置使用其他端口
# config.py
service_port = 8090
websocket_port = 8091
```

### 依赖安装失败

```bash
# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Docker 启动失败

```bash
# 查看详细日志
docker-compose logs central-server

# 重新构建镜像
docker-compose build --no-cache
docker-compose up -d
```

---

## 📚 下一步

- 📖 阅读 [完整架构文档](../README.md)
- 🐳 查看 [Docker 部署指南](DOCKER_DEPLOY.md)
- 🔄 了解 [迁移指南](MIGRATION.md)（从旧版本升级）
- 🔐 配置生产环境安全策略

---

## 💡 提示

1. **开发环境**: 建议使用本地部署，方便调试
2. **生产环境**: 强烈推荐使用 Docker 部署，便于管理
3. **性能测试**: 启动后建议进行压力测试
4. **监控告警**: 配置监控系统监控服务状态

---

**最后更新**: 2026-08-14
