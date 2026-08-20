# Central-Server 项目架构文档

> **🎉 特性**: 单进程统一管理 API + WebSocket，支持 Docker 一键部署！  
> 详见：[快速启动](docs/QUICKSTART.md) | [Docker 部署](docs/DOCKER_DEPLOY.md)

## 🚀 快速开始

### Docker 部署（推荐）

```bash
# 1. 构建镜像
./docker/app_build.sh

# 2. 配置外部依赖服务（MySQL、Redis、Kafka）
export MYSQL_HOST=your_mysql_host
export REDIS_HOST=your_redis_host
export KAFKA_SERVER=your_kafka_host:9092

# 3. 启动容器
./docker/app_start.sh
```

更多 Docker 部署选项请参考 [docker/README.md](docker/README.md)

### 本地开发部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置文件
cp config_example.py config.py
# 编辑 config.py，修改数据库连接等配置

# ⚠️ 重要：生产环境请务必修改 JWT 密钥
python scripts/generate_secret_key.py
# 详细说明请查看：docs/JWT_SECURITY.md

# 3. 启动服务（单进程，包含 API + WebSocket）
python main.py
```

更多详情请参考 [快速启动指南](docs/QUICKSTART.md) | [配置说明](docs/CONFIG.md) | [JWT 安全](docs/JWT_SECURITY.md)

---

## 📋 项目概述

这是一个基于 Flask 的网络运维平台控制中心，用于处理网络设备的 syslog 日志和采集数据，提供告警管理、任务调度、数据处理等功能。

**项目规模**: 约 8945 行 Python 代码

**主要功能**:
- 网络设备 Syslog 日志收集与处理
- 设备数据采集与存储
- 告警规则管理（黑名单、日志聚合）
- 任务调度系统
- RESTful API 接口
- WebSocket 实时消息推送
- 用户认证与权限管理

**核心特性**:
- ✅ 单进程统一管理（API + WebSocket）
- ✅ Docker 一键部署
- ✅ 健康检查支持
- ✅ 时区自动配置 (UTC+8)
- ✅ 优雅启动和关闭

---

## 🏗️ 核心架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Flask Web 应用                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  API 层 (RESTful Endpoints)                          │  │
│  │  - 告警管理 - 任务管理 - 用户系统 - 工具接口        │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  认证中间件 (JWT + API Key)                          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    任务调度系统 (APScheduler)                │
│  - 定时任务管理  - 动态注册/取消  - 执行监控                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────┐          ┌────────────────────────┐
│   Syslog 处理服务    │          │   数据采集处理服务      │
│  ┌─────────────────┐ │          │  ┌──────────────────┐  │
│  │ 黑名单过滤      │ │          │  │ 策略模式分发     │  │
│  │ 日志聚合        │ │          │  │ CPU/Memory/...   │  │
│  └─────────────────┘ │          │  └──────────────────┘  │
└──────────────────────┘          └────────────────────────┘
         ↓                                    ↓
┌─────────────────────────────────────────────────────────────┐
│              消息队列 (Kafka / Redis Queue)                  │
│  - syslog_data 通道  - collect_data 通道                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              数据持久化 (MySQL + Elasticsearch)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 目录结构

```
central-server/
├── main.py                    # 应用入口
├── config.py                  # 配置文件
├── requirements.txt           # 依赖列表
├── socket_main.py            # Socket 服务
├── file_server.py            # 文件服务
│
├── core/                     # 核心组件
│   ├── app.py               # Flask 应用创建
│   ├── logger.py            # 日志系统
│   └── scheduler.py         # APScheduler 调度器
│
├── api/                      # API 接口层
│   ├── api_routes.py        # 调度器任务管理 API
│   ├── api_system.py        # 系统用户管理 API
│   ├── api_tools.py         # 工具类 API
│   ├── api_alarm.py         # 告警管理 API
│   ├── api_agent.py         # Agent 任务上报 API
│   ├── api_kafka_data.py    # 数据查询 API
│   └── api_response.py      # 统一响应格式
│
├── task_core/               # 任务调度核心
│   ├── task_base.py         # 任务基类
│   ├── task_factory.py      # 任务工厂
│   └── task_manager.py      # 任务管理器
│
├── task_implements/         # 任务实现
│   └── HeartbeatTask.py    # 心跳任务
│
├── services/                # 后台服务
│   ├── syslog_main.py      # Syslog 处理服务
│   ├── data_main.py        # 数据采集服务
│   ├── syslog/             # Syslog 处理模块
│   │   ├── filter_blacklist.py  # 黑名单过滤
│   │   └── log_merge.py         # 日志聚合
│   └── dataStrategy/       # 数据处理策略
│       ├── __init__.py     # 策略工厂
│       ├── cpu_strategy.py
│       ├── memory_strategy.py
│       └── syslog_strategy.py
│
├── function_messaging/      # 消息队列
│   ├── kafka_client.py     # Kafka 客户端
│   ├── queue_client.py     # Redis 队列客户端
│   └── redis_client.py     # Redis 连接
│
├── function_alarm/          # 告警功能
│   └── syslog_manage.py    # 告警规则管理
│
├── function_system/         # 系统功能
│   └── user_manage.py      # 用户认证与权限
│
├── function_tools/          # 工具函数
│   ├── ipprefix_tools.py   # IP 地址工具
│   └── text_diff_tool.py   # 文本对比工具
│
├── daos/                    # 数据访问层
│   ├── database.py         # MySQL 连接
│   └── elasticsearch_DB.py # Elasticsearch 连接
│
├── tables/                  # 数据表模型
│   ├── AlarmDB.py          # 告警表
│   ├── SyslogDB.py         # 日志表
│   ├── CollectDB.py        # 采集表
│   ├── UsersDB.py          # 用户表
│   ├── RolesDB.py          # 角色表
│   └── PagesDB.py          # 页面权限表
│
├── utils/                   # 工具类
│   ├── ipaddr.py           # IP 地址处理
│   ├── threadPool.py       # 线程池
│   └── utils.py            # 通用工具
│
├── scripts/                 # 脚本工具
│   ├── db_init.py          # 数据库初始化
│   └── cron_health_check.py # 健康检查
│
├── docs/                    # 文档
└── docker/                  # Docker 配置
```

---

## 🔧 核心模块详解

### 1. 应用层（Flask Web）

#### main.py - 应用入口
```python
# 启动流程
1. 初始化日志系统
2. 启动 APScheduler 调度器
3. 启动 Syslog 处理服务（可选）
4. 启动数据采集服务（可选）
5. 创建 Flask 应用
6. 配置 ProxyFix 中间件（处理反向代理）
7. 启动 Flask 服务（端口 8080）
```

**关键特性**:
- 自定义 WSGI 请求处理器，记录真实客户端 IP
- 支持优雅关闭（KeyboardInterrupt）
- 自动停止所有任务和调度器

#### core/app.py - Flask 应用核心
- **认证中间件** (`before_request`):
  - 排除路由：`/system/login`, `/tools/ip`
  - JWT Token + Session ID 双重验证
  - API Key/Secret 认证（机器调用）
  - 基于角色的 URL 权限控制

- **响应处理** (`after_request`):
  - CORS 跨域配置
  - 自定义响应头
  - 请求日志记录

- **蓝图注册**:
  - `api_bp` - 调度器管理
  - `system_bp` - 系统管理
  - `tools_bp` - 工具接口
  - `data_bp` - 数据查询
  - `alarm_bp` - 告警管理
  - `agent_bp` - Agent 管理

---

### 2. 任务调度系统

#### 架构设计
```
TaskManager (任务管理器)
    ↓
TaskFactory (任务工厂) ← 注册 TaskClass
    ↓
BaseTask (任务基类) ← 继承实现
    ↓
APScheduler (调度器执行)
```

#### task_core/task_base.py - 任务基类
**核心属性**:
- `TASK_ID`: 任务类唯一标识
- `TASK_NAME`: 任务名称
- `TASK_DESCRIPTION`: 任务描述

**执行框架**:
```python
def run():
    # 1. 记录开始时间
    # 2. 执行 execute() 方法
    # 3. 记录执行结果（成功/失败）
    # 4. 统计执行时间
    # 5. 返回结果字典
```

**统计信息**:
- `run_count`: 总执行次数
- `success_count`: 成功次数
- `failure_count`: 失败次数
- `last_run_time`: 最后执行时间
- `run_time`: 最后执行耗时

#### task_core/task_manager.py - 任务管理器
**核心功能**:
- `register_task()`: 注册任务到调度器
- `unregister_task()`: 取消任务
- `update_task_config()`: 更新任务配置
- `update_task_schedule()`: 更新调度配置
- `execute_task_now()`: 立即执行任务
- `get_all_tasks()`: 获取所有任务状态

**调度类型**:
- `interval`: 固定间隔执行（秒/分/小时）
- `cron`: Cron 表达式定时执行

**设计特点**:
- 任务实例 ID 与任务类 ID 分离
- 支持动态注册/取消任务
- 自动清理旧任务（replace_existing）

---

### 3. 数据处理服务

#### Syslog 日志处理流程
```
1. Kafka/Redis 消费 syslog_data 主题
   ↓
2. BlacklistManager - 黑名单过滤
   ↓
3. MergelistManager - 日志聚合（相似日志合并）
   ↓
4. 发送到 collect_data 主题
```

**特性**:
- 独立守护线程运行
- 定期刷新过滤规则（默认 300s）
- 时间窗口聚合（默认 300s）

#### 数据采集处理流程
```
1. Kafka/Redis 消费 collect_data 主题
   ↓
2. 提取 metric_name 字段
   ↓
3. StrategyFactory 获取对应策略
   ↓
4. Strategy.process_data() 处理数据
   ↓
5. 存储到数据库
```

**策略模式**:
```python
class DataStrategy(ABC):
    @abstractmethod
    def process_data(self, data):
        pass

# 注册策略
strategy_factory.register_strategy("cpu_data", CpuStrategy())
strategy_factory.register_strategy("memory_data", MemoryStrategy())
strategy_factory.register_strategy("syslog_data", SyslogStrategy())
```

---

### 4. 消息队列层

#### 双实现支持
**Kafka 模式** (`kafka_client.py`):
- 高吞吐量
- 分布式部署
- 适合生产环境

**Redis 队列模式** (`queue_client.py`):
- 轻量级部署
- 简单易用
- 适合小规模或测试环境

#### 数据通道
| 通道名称 | 用途 | 数据源 |
|---------|------|--------|
| `syslog_data` | 设备 Syslog 日志 | 网络设备 |
| `collect_data` | 采集数据 | 监控 Agent |

#### 使用方式
```python
# 发送数据
from function_messaging.queue_client import sendDataToCollector
sendDataToCollector(messages=data, key=device_ip)

# 消费数据
from function_messaging.queue_client import readDataFromCollect
for message in readDataFromCollect():
    process(message)
```

---

### 5. API 接口层

#### 认证机制
**用户认证流程**:
```
1. POST /system/login (username + password)
   ↓
2. 返回 JWT Token + Session ID
   ↓
3. 后续请求携带 Headers:
   - Authorization: Bearer <token>
   - Sessionid: <md5(sign+timestamp)>
   - Apptime: <timestamp>
```

**API Key 认证**:
```
Headers:
- key: <api_key>
- secret: <api_secret>
- Apptime: <timestamp>
```

#### 主要接口

**调度器管理** (`/api/scheduler/*`):
- `GET /api/scheduler/jobs` - 获取所有任务
- `POST /api/scheduler/jobs` - 添加任务
- `DELETE /api/scheduler/jobs/<job_id>` - 删除任务
- `POST /api/scheduler/jobs/<job_id>/pause` - 暂停任务
- `POST /api/scheduler/jobs/<job_id>/resume` - 恢复任务

**告警管理** (`/alarm/*`):
- 黑名单 CRUD: `add_blacklist`, `del_blacklist`, `update_blacklist`, `get_blacklist`
- 聚合规则 CRUD: `add_mergelist`, `del_mergelist`, `update_mergelist`, `get_mergelist`
- 告警查询: `get_current_alarm`, `get_history_alarm`, `get_alarm_by_group`
- 告警处理: `handle_alarm_by_group`, `get_alarm_log`

**测试接口**:
- `POST /alarm/check_blacklist` - 测试黑名单规则
- `POST /alarm/check_mergelist` - 测试聚合规则

#### 统一响应格式
```json
{
    "code": 200,
    "message": "success",
    "data": { ... }
}
```

**错误码**:
- `200`: 成功
- `400`: 参数错误
- `401`: 认证失败
- `403`: 权限不足
- `500`: 服务器错误

---

## 🔑 关键设计特点

### 1. 多线程架构
- **Flask 线程化模式**: `app.run(threaded=True)`
- **APScheduler 线程池**: 20 个工作线程
- **后台服务线程**: Syslog/Data 服务独立守护线程
- **自定义线程池**: `utils/threadPool.py`

### 2. 策略模式（数据处理）
```python
# 可扩展的数据处理器
class CpuStrategy(DataStrategy):
    def process_data(self, data):
        # 处理 CPU 数据
        pass

# 注册到工厂
strategy_factory.register_strategy("cpu_data", CpuStrategy())
```

### 3. 双消息队列支持
- 通过配置切换 Kafka/Redis
- 统一的消费者/生产者接口
- 自动重连机制（重试 3 次）

### 4. 反向代理透明支持
```python
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,      # X-Forwarded-For
    x_proto=1,    # X-Forwarded-Proto
    x_host=1      # X-Forwarded-Host
)
```

### 5. 任务实例与类分离
```python
# 任务类 ID: "heartbeat"（任务类型）
# 任务实例 ID: "heartbeat_dc1", "heartbeat_dc2"（任务实例）
task_manager.register_task(
    task_instance_id="heartbeat_dc1",
    task_class_id="heartbeat",
    config={"target": "dc1"}
)
```

---

## 📦 技术栈

### 核心框架
- **Web**: Flask 2.2.5
- **WebSocket**: Flask-SocketIO 5.3.6 + Eventlet 0.33.3
- **调度**: APScheduler

### 消息队列
- **Kafka**: kafka-python
- **Redis**: redis-py

### 数据库
- **MySQL**: PyMySQL
- **Elasticsearch**: elasticsearch-py

### 网络协议
- **SSH**: Paramiko 2.10.4
- **SNMP**: PureSNMP 1.11.0

### 认证授权
- **JWT**: PyJWT

---

## ⚙️ 配置说明

### config.py 配置项

```python
class Config:
    # API 服务配置
    service_ip = "0.0.0.0"
    service_port = 8080
    log_level = "INFO"
    
    # 功能开关
    collect_enable = True          # 数据采集服务
    syslog_enable = True           # Syslog 服务
    
    # Kafka 配置
    kafka_server = ["localhost:9092"]
    collect_kafka_topic = "collect_data"
    syslog_kafka_topic = "syslog_data"
    
    # Redis 配置
    redis_host = "localhost"
    queue_key_collect = "queue:collect_data"
    queue_key_syslog = "queue:syslog_data"
    
    # MySQL 配置
    mysql_config = {
        "db_host": "localhost",
        "db_user": "root",
        "db_token": "root",
        "db_port": 3306,
    }
```

---

## 🚀 部署运行

### 安装依赖
```bash
pip install -r requirements.txt
```

### 数据库初始化
```bash
db_create.sql
```

### 启动服务
```bash
# 前台运行
python main.py

# 后台运行
nohup python3 -u main.py > lweb.log 2>&1 &
```

### 健康检查
```bash
curl http://localhost:8080/health
```

---

## 🎯 优化建议

### 1. 配置管理
**现状**: 配置硬编码在 `config/config.py`  
**建议**: 
- 使用环境变量（12-factor app）
- 分离 dev/test/prod 配置
- 敏感信息使用密钥管理服务

```python
# 推荐方案
import os
from dotenv import load_env

class Config:
    KAFKA_SERVER = os.getenv('KAFKA_SERVER', 'localhost:9092')
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
```

### 2. 错误处理与重试
**现状**: 部分代码缺少统一错误处理  
**建议**:
- 使用装饰器统一异常捕获
- 实现指数退避重试机制
- 添加熔断器（Circuit Breaker）

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def connect_to_kafka():
    pass
```

### 3. 连接池管理
**现状**: MySQL/Redis 连接未使用池化  
**建议**:
```python
# MySQL 连接池
from DBUtils.PooledDB import PooledDB
pool = PooledDB(
    creator=pymysql,
    maxconnections=20,
    mincached=2,
    ...
)

# Redis 连接池
from redis import ConnectionPool
pool = ConnectionPool(host='localhost', port=6379, max_connections=50)
```

### 4. 监控与可观测性
**建议添加**:
- Prometheus 指标导出
- 健康检查端点
- 分布式追踪（OpenTelemetry）
- 结构化日志（JSON 格式）

```python
from prometheus_flask_exporter import PrometheusMetrics
metrics = PrometheusMetrics(app)
```

### 5. 测试覆盖
**现状**: 缺少单元测试  
**建议**:
- pytest + pytest-cov
- 单元测试覆盖率 > 80%
- 集成测试（Docker Compose）
- API 接口测试

### 6. API 文档
**建议**:
- 使用 Flask-RESTX 或 Flasgger
- 自动生成 OpenAPI/Swagger 文档
- 接口版本管理

```python
from flask_restx import Api, Resource
api = Api(app, version='1.0', title='Central Server API')
```

### 7. 容器化部署
**建议完善**:
```dockerfile
# 多阶段构建
FROM python:3.9-slim as builder
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.9-slim
COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*
COPY . /app
WORKDIR /app
CMD ["python", "main.py"]
```

### 8. 异步化改造
**现状**: 同步阻塞 I/O  
**建议**: 
- 迁移到 FastAPI + asyncio
- 异步数据库驱动（asyncpg, motor）
- 异步消息队列客户端（aiokafka）

```python
# FastAPI 示例
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/tasks")
async def get_tasks():
    tasks = await task_manager.get_all_tasks_async()
    return tasks
```

### 9. 安全加固
- 密码加盐哈希（bcrypt）
- SQL 注入防护（ORM 或参数化查询）
- XSS 防护
- 速率限制（Flask-Limiter）
- HTTPS 强制
- 敏感信息脱敏

### 10. 性能优化
- Redis 缓存热点数据
- 数据库索引优化
- 批量操作减少 I/O
- 异步任务队列（Celery）
- 数据库读写分离

---

## 📝 开发规范

### 代码风格
- 遵循 PEP 8
- 使用 Black 格式化
- 使用 Flake8 静态检查
- 类型注解（Type Hints）

### Git 提交规范
```
feat: 新功能
fix: 修复 bug
docs: 文档更新
refactor: 重构
test: 测试相关
chore: 构建/工具链
```

### 日志规范
```python
# 使用结构化日志
logger.info(
    "任务执行完成",
    extra={
        "task_id": task_id,
        "duration": duration,
        "status": "success"
    }
)
```

---

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

[待补充]

---

## 📞 联系方式

[待补充]

---

**最后更新**: 2026-08-14
