# Central-Server

基于 Flask 的网络运维平台控制中心，提供设备日志收集、数据采集、告警管理、任务调度等功能。

> **💡 提示**: 本项目是完整网络运维平台的后端组件，需配合前端和数据采集器一起部署才能实现完整功能。  
> 快速开始请查看 [完整平台部署指南](#-完整平台部署指南)

---

## 🏗️ 完整平台部署指南

完整的网络运维平台由三个独立组件构成，需要配合部署才能实现完整功能。

### 项目组件

| 组件 | 仓库地址 | 说明 |
|------|---------|------|
| **前端** | `git@github.com:cs948294549/chen_vue.git` | 集成用户权限管理，支持在框架下自由增减页面，灵活开发自定义功能页面 |
| **后端**（本项目） | `git@github.com:cs948294549/central-server.git` | 对接数据库，提供 API 接口，统一管理 WebSocket 接入 |
| **数据采集** | `git@github.com:cs948294549/collector.git` | 独立功能模块，定时任务采集设备数据，直接写入数据库 |

**数据流向**: 数据采集器定时采集设备数据 → 写入数据库 → 后端从数据库读取数据，提供 API → 前端调用 API 展示数据

### 整体架构

```
                    ┌─────────────┐
                    │    Nginx    │  统一入口（本例端口 9090）
                    └──────┬──────┘
              ┌────────────┼────────────┐
              │            │            │
        location /   location /api/  location /sock/
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  前端静态  │  │ 后端 API │  │ WebSocket│
        │  资源文件  │  │  :28000  │  │  :28001  │
        └──────────┘  └────┬─────┘  └────┬─────┘
                            └──────┬───────┘
                                   ▼
                            ┌──────────┐       ┌──────────┐
                            │  MySQL   │◄──────│ 数据采集器 │
                            │ (netops) │       │ (独立部署) │
                            └──────────┘       └──────────┘
```

### 1. 配置 Nginx 统一入口

本例使用如下端口分配：
- Nginx 入口: `9090`
- 后端 API: `28000`
- 后端 WebSocket: `28001`

```nginx
upstream api {
    server 127.0.0.1:28000;
}

upstream websock {
    server 127.0.0.1:28001;
}

server {
    listen 9090;                    # Nginx 监听端口
    server_name your_domain_or_ip;  # 替换为实际域名或服务器 IP

    # WebSocket 转发
    location ^~ /sock/ {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_pass http://websock/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # API 转发
    location ^~ /api/ {
        proxy_pass http://api/;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host              $http_host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_send_timeout 180;
        proxy_read_timeout 180;
    }

    # 前端静态资源
    location / {
        root   /var/www/netops;   # 前端 dist 目录实际路径
        index  index.html index.htm;
        error_page 404 /index.html;
    }
}
```

> ⚠️ 前端、API、WebSocket 的转发路径必须与前端项目实际请求的路径（`/`、`/api/`、`/sock/`）保持一致，否则会出现跨域或 404 问题。

### 2. 部署前端

**方式一：直接使用项目自带的编译产物（推荐，无需 Node 环境）**

```bash
# chen_vue 项目已包含编译好的 dist 目录
cd chen_vue
sh deploy.sh   # 将 dist 目录内容部署到 /var/www/netops
```

**方式二：自行开发后重新编译**

```bash
# 需要 Node v16.20.2
cd chen_vue
npm install
npm run build
sh deploy.sh
```

### 3. 初始化数据库

三个组件共用同一个数据库 `netops`，需要分别执行两处的初始化脚本：

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS netops DEFAULT CHARACTER SET utf8mb4;"

# 后端初始化脚本（central-server 项目）
mysql -u root -p netops < central-server/scripts/db_create.sql
mysql -u root -p netops < central-server/scripts/db_page.sql
mysql -u root -p netops < central-server/scripts/db_user_init.sql

# 采集器初始化脚本（collector 项目）
mysql -u root -p netops < collector/sql/init.sql
```

### 4. 启动后端（central-server）

```bash
cd central-server
# 修改 config/config.py 中的数据库、Redis、Kafka 等配置
sh docker/app_build.sh
sh docker/app_start.sh
```

### 5. 启动数据采集器（collector）

```bash
cd collector
# 修改采集器自身的配置文件（数据库连接等）
sh docker/app_build.sh
sh docker/app_start.sh
```

### 6. 开放访问

确保 Nginx 配置的端口（本例 `9090`）已在防火墙/安全组中开放，浏览器访问：

```
http://your_domain_or_ip:9090
```

即可看到登录页面，使用默认账号 `admin` / `123456` 登录（见 [首次登录](#首次登录) 说明）。

---

## 🚀 快速开始（单独部署后端）

以下内容仅针对 **central-server 后端组件** 单独部署调试的场景。如需部署完整平台（前端 + 后端 + 数据采集器），请参考上方 [完整平台部署指南](#-完整平台部署指南)。

### 方式一：Docker 部署（推荐）

适合生产环境和快速体验，无需手动配置 Python 环境。

```bash
# 1. 修改配置文件
cd /path/to/central-server
cp config/config_example.py config/config.py
vim config/config.py  # 修改数据库、Redis、Kafka 等配置

# 2. 构建镜像
./docker/app_build.sh

# 3. 启动容器（可选指定版本和端口）
./docker/app_start.sh v1 28000 28001
# 参数说明：v1=镜像版本，28000=API端口，28001=WebSocket端口
```

容器启动后访问：
- API 服务: `http://localhost:28000`
- WebSocket 服务: `ws://localhost:28001`
- 健康检查: `curl http://localhost:28000/health`

**Docker 部署详细说明**: [docker/README.md](docker/README.md)

---

### 方式二：本地开发部署

适合开发调试和功能测试。

#### 1. 环境准备

```bash
# Python 版本要求: 3.8+
python3 --version

# 克隆项目（如果还没有）
git clone <repository_url>
cd central-server
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

<details>
<summary>依赖列表（点击展开）</summary>

- `flask==2.2.5` - Web 框架
- `flask-socketio==5.3.6` - WebSocket 支持
- `eventlet==0.33.3` - 异步网络库
- `pyjwt` - JWT 认证
- `apscheduler` - 任务调度
- `kafka-python` - Kafka 客户端
- `redis` - Redis 客户端
- `pymysql` - MySQL 客户端
- `paramiko==2.10.4` - SSH 客户端
- `puresnmp==1.11.0` - SNMP 客户端
- `pyyaml` - YAML 配置解析

</details>

#### 3. 配置文件

```bash
# 复制配置模板
cp config/config_example.py config/config.py

# 编辑配置文件，修改关键配置项
vim config/config.py
```

**必须修改的配置项**:

```python
# MySQL 数据库配置
mysql_config = {
    "db_host": "localhost",      # 数据库地址
    "db_user": "root",            # 数据库用户
    "db_token": "your_password",  # 数据库密码
    "db_port": 3306,
    "db_name": "netops"           # 数据库名称
}

# Redis 配置
redis_host = "localhost"
redis_port = 6379
redis_password = ""  # 如有密码请填写

# Kafka 配置（可选，如不使用可关闭）
kafka_server = ["localhost:9092"]
```

#### 4. 数据库初始化

```bash
# 执行数据库初始化脚本（首次部署）
mysql -u root -p < scripts/db_create.sql
```

#### 5. JWT 密钥配置（生产环境必做）

```bash
# 生成安全的 JWT 密钥
python scripts/generate_secret_key.py

# 将生成的密钥复制到 config/config.py 中的 jwt_secret_key
```

⚠️ **安全警告**: 默认密钥仅供测试使用，生产环境必须更换！详见 [docs/JWT_SECURITY.md](docs/JWT_SECURITY.md)

#### 6. 启动服务

```bash
# 前台启动（适合开发调试）
python main.py

# 后台启动（适合生产环境）
nohup python3 -u main.py > logs/central-server.log 2>&1 &

# 查看日志
tail -f logs/central-server.log
```

#### 7. 验证服务

```bash
# 健康检查
curl http://localhost:8080/health

# 预期返回
{"status": "healthy", "timestamp": "2026-08-20T10:30:00"}
```

---

### 首次登录

**默认管理员账号**:
- 用户名: `admin`
- 密码: `123456`

⚠️ **安全提示**: 
- 首次登录后必须立即修改默认密码
- 新建用户的默认密码也是 `123456`，需要在首次登录后修改

**登录方式**:
- 通过前端页面登录（推荐）
- 通过 API 登录需要提交密码的 hash 值，请参考前端实现或 [API 文档](docs/API.md)

---

## 📋 项目介绍

### 项目定位

Central-Server 是一个专为网络运维场景设计的数据处理和管理平台，核心功能包括：

1. **日志收集与处理**：接收网络设备 Syslog 日志，支持黑名单过滤和日志聚合
2. **数据采集与存储**：处理来自监控 Agent 的设备性能数据（CPU、内存、接口等）
3. **告警管理**：基于规则的告警触发、分组、处理和历史查询
4. **任务调度**：支持定时任务和周期任务的动态管理
5. **API 服务**：提供 RESTful API 供前端和第三方系统调用
6. **WebSocket 推送**：实时消息推送和 SSH 终端交互

### 技术架构

**核心技术栈**:
- **Web 框架**: Flask 2.2.5 + Flask-SocketIO 5.3.6
- **任务调度**: APScheduler（支持 interval 和 cron 两种调度方式）
- **消息队列**: Kafka / Redis Queue（双实现，可切换）
- **数据存储**: MySQL（业务数据）+ Elasticsearch（日志存储）
- **网络协议**: Paramiko（SSH）、PureSNMP（SNMP）
- **认证授权**: JWT Token + Session 双重认证

**架构特点**:
- ✅ 单进程多线程架构（API + WebSocket + 任务调度统一管理）
- ✅ 策略模式设计（数据处理可扩展）
- ✅ 双消息队列支持（Kafka 高性能 / Redis 轻量级）
- ✅ 反向代理透明支持（自动识别 X-Forwarded-For）
- ✅ 优雅启停机制（信号处理 + 资源清理）

### 项目规模

```
代码统计（Python）:
- 总行数: ~8945 行
- 核心模块: 18 个
- API 接口: 40+ 个
- 任务类型: 可扩展（基于工厂模式）
```

### 核心功能模块

| 模块 | 说明 | 关键文件 |
|------|------|---------|
| **API 服务** | RESTful 接口，支持认证、权限控制 | `core/app.py`, `api/*` |
| **任务调度** | 基于 APScheduler 的动态任务管理 | `tasks/task_manager.py` |
| **日志处理** | Syslog 黑名单过滤、日志聚合 | `services/syslog_main.py` |
| **数据采集** | 设备性能数据处理（CPU、内存等） | `services/data_main.py` |
| **告警管理** | 告警规则、分组处理、历史查询 | `api/api_alarm.py` |
| **用户系统** | JWT 认证、角色权限、API Key 管理 | `function_system/user_manage.py` |
| **WebSocket** | 实时消息推送、SSH 终端交互 | `core/websocket_server.py` |
| **SSH 管理** | 交互式 SSH 终端、命令执行 | `function_ssh/interactive_ssh.py` |

### 应用场景

- **网络设备管理**: 批量管理交换机、路由器、防火墙等网络设备
- **日志分析**: 实时收集和分析设备 Syslog 日志，快速定位故障
- **性能监控**: 采集设备 CPU、内存、接口流量等性能指标
- **告警响应**: 根据规则自动触发告警，支持告警分组和批量处理
- **运维自动化**: 通过 API 集成到运维平台，实现设备配置自动化

---

## 📚 深入了解

### 快速导航

- [架构设计](#-架构设计) - 了解系统整体架构和数据流
- [目录结构](#-目录结构) - 快速定位代码模块
- [API 接口](#-api-接口文档) - 查看可用的 API 接口
- [开发指南](#-开发指南) - 贡献代码和开发新功能
- [部署运维](#-部署与运维) - 生产环境部署建议
- [常见问题](docs/FAQ.md) - 常见问题解答

---

## 🏗️ 架构设计

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

### 生产环境部署建议

#### 1. 环境准备

**硬件要求**:
- CPU: 4 核心以上
- 内存: 8GB 以上
- 磁盘: 100GB 以上（日志和数据存储）

**软件依赖**:
- Python 3.8+
- MySQL 5.7+ / 8.0+
- Redis 5.0+
- Kafka 2.8+（可选，可用 Redis 替代）

#### 2. 安全配置

**必须修改的配置**:
```python
# config/config.py

# 1. 修改 JWT 密钥（使用脚本生成）
jwt_secret_key = "YOUR_GENERATED_SECRET_KEY"

# 2. 修改默认管理员密码
# 首次登录后立即修改

# 3. 配置数据库强密码
mysql_config = {
    "db_token": "STRONG_PASSWORD_HERE"
}

# 4. Redis 密码保护
redis_password = "REDIS_PASSWORD"
```

**网络安全**:
- 使用防火墙限制访问端口（仅开放必要端口）
- 配置 HTTPS（使用 Nginx 反向代理）
- 启用 API 访问频率限制

#### 3. 反向代理配置（Nginx）

```nginx
upstream central_server {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name central-server.example.com;
    
    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name central-server.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://central_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket 支持
    location /socket.io/ {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 4. Systemd 服务配置

```ini
# /etc/systemd/system/central-server.service
[Unit]
Description=Central Server
After=network.target mysql.service redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/central-server
Environment="PATH=/opt/central-server/venv/bin"
ExecStart=/opt/central-server/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**启动服务**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable central-server
sudo systemctl start central-server
sudo systemctl status central-server
```

#### 5. 日志管理

**日志轮转配置** (`/etc/logrotate.d/central-server`):
```
/opt/central-server/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 www-data www-data
    sharedscripts
    postrotate
        systemctl reload central-server > /dev/null 2>&1 || true
    endscript
}
```

#### 6. 监控与健康检查

**健康检查端点**:
```bash
# 基础健康检查
curl http://localhost:8080/health

# 详细健康检查（包含依赖服务状态）
curl http://localhost:8080/health/detailed
```

**监控脚本** (`scripts/cron_health_check.py`):
```bash
# 添加到 crontab
*/5 * * * * /opt/central-server/venv/bin/python /opt/central-server/scripts/cron_health_check.py
```

**Prometheus 监控**（推荐）:
```python
# 安装依赖
pip install prometheus-flask-exporter

# 在 main.py 中添加
from prometheus_flask_exporter import PrometheusMetrics
metrics = PrometheusMetrics(app)
```

#### 7. 备份策略

**数据库备份**:
```bash
#!/bin/bash
# backup_mysql.sh
BACKUP_DIR="/backup/mysql"
DATE=$(date +%Y%m%d_%H%M%S)
mysqldump -u root -p netops > $BACKUP_DIR/netops_$DATE.sql
# 保留最近 30 天的备份
find $BACKUP_DIR -name "netops_*.sql" -mtime +30 -delete
```

**配置文件备份**:
```bash
# 定期备份配置文件
tar -czf /backup/config_$(date +%Y%m%d).tar.gz config/
```

#### 8. 性能优化

**数据库优化**:
- 为高频查询字段添加索引
- 定期执行 `ANALYZE TABLE` 更新统计信息
- 配置合理的连接池大小

**Redis 优化**:
- 配置持久化策略（RDB + AOF）
- 设置合理的内存限制和淘汰策略
- 监控慢查询日志

**应用层优化**:
- 使用连接池管理数据库连接
- 启用 Redis 缓存热点数据
- 配置合理的线程池大小

---

## 🐛 故障排查

### 常见问题

#### 1. 服务无法启动

**检查端口占用**:
```bash
lsof -i:8080
netstat -tunlp | grep 8080
```

**检查日志**:
```bash
tail -f logs/central-server.log
```

#### 2. 数据库连接失败

**测试数据库连接**:
```bash
mysql -h localhost -u root -p -e "SELECT 1"
```

**检查配置**:
```python
# config/config.py 中的数据库配置是否正确
mysql_config = {
    "db_host": "localhost",
    "db_user": "root",
    "db_token": "password",
    ...
}
```

#### 3. Kafka/Redis 连接失败

**测试 Redis 连接**:
```bash
redis-cli -h localhost -p 6379 ping
```

**测试 Kafka 连接**:
```bash
kafka-topics.sh --bootstrap-server localhost:9092 --list
```

#### 4. 任务不执行

**检查任务状态**:
```bash
curl http://localhost:8080/api/scheduler/jobs \
  -H "Authorization: Bearer <token>"
```

**查看调度器日志**:
```bash
grep "APScheduler" logs/central-server.log
```

#### 5. 内存占用过高

**检查进程内存**:
```bash
ps aux | grep python | grep main.py
```

**优化建议**:
- 减少 APScheduler 线程池大小
- 限制消息队列消费者数量
- 增加服务器内存或启用 swap

---

## 📦 技术栈

### 核心依赖
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

## 🔌 API 接口文档

### 认证机制

**用户登录认证**:
```bash
# 1. 登录获取 Token
curl -X POST http://localhost:8080/system/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 返回示例
{
  "code": 200,
  "message": "success",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "session_id": "abc123def456",
    "user_info": {...}
  }
}

# 2. 后续请求携带认证信息
curl -X GET http://localhost:8080/api/scheduler/jobs \
  -H "Authorization: Bearer <token>" \
  -H "Sessionid: <session_id>" \
  -H "Apptime: $(date +%s)"
```

**API Key 认证**（用于系统间调用）:
```bash
curl -X GET http://localhost:8080/api/scheduler/jobs \
  -H "key: <your_api_key>" \
  -H "secret: <your_api_secret>" \
  -H "Apptime: $(date +%s)"
```

### 主要接口列表

#### 任务调度管理 (`/api/scheduler/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/scheduler/jobs` | GET | 获取所有任务列表 |
| `/api/scheduler/jobs` | POST | 添加新任务 |
| `/api/scheduler/jobs/<job_id>` | DELETE | 删除指定任务 |
| `/api/scheduler/jobs/<job_id>/pause` | POST | 暂停任务 |
| `/api/scheduler/jobs/<job_id>/resume` | POST | 恢复任务 |
| `/api/scheduler/jobs/<job_id>/execute` | POST | 立即执行任务 |

#### 告警管理 (`/alarm/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/alarm/blacklist` | GET | 获取黑名单列表 |
| `/alarm/blacklist` | POST | 添加黑名单规则 |
| `/alarm/blacklist/<id>` | PUT | 更新黑名单规则 |
| `/alarm/blacklist/<id>` | DELETE | 删除黑名单规则 |
| `/alarm/mergelist` | GET | 获取聚合规则列表 |
| `/alarm/mergelist` | POST | 添加聚合规则 |
| `/alarm/current` | GET | 获取当前告警 |
| `/alarm/history` | GET | 获取历史告警 |
| `/alarm/handle/<group_id>` | POST | 处理告警组 |
| `/alarm/check_blacklist` | POST | 测试黑名单规则 |
| `/alarm/check_mergelist` | POST | 测试聚合规则 |

#### 系统管理 (`/system/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/system/login` | POST | 用户登录 |
| `/system/users` | GET | 获取用户列表 |
| `/system/users` | POST | 创建用户 |
| `/system/users/<id>` | PUT | 更新用户信息 |
| `/system/users/<id>` | DELETE | 删除用户 |
| `/system/roles` | GET | 获取角色列表 |

#### 工具接口 (`/tools/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/tools/ip/prefix` | POST | IP 地址前缀计算 |
| `/tools/text/diff` | POST | 文本对比工具 |

### 统一响应格式

所有接口返回统一的 JSON 格式：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

**状态码说明**:
- `200`: 请求成功
- `400`: 请求参数错误
- `401`: 认证失败（Token 无效或过期）
- `403`: 权限不足
- `404`: 资源不存在
- `500`: 服务器内部错误

**完整 API 文档**: 详见 [docs/API.md](docs/API.md)

---

## 🛠️ 开发指南

### 添加新的任务类型

1. 在 `tasks/` 目录下创建新的任务类：

```python
# tasks/MyCustomTask.py
from tasks.task_base import BaseTask

class MyCustomTask(BaseTask):
    TASK_ID = "my_custom_task"
    TASK_NAME = "我的自定义任务"
    TASK_DESCRIPTION = "执行某项自定义操作"
    
    def execute(self):
        """任务执行逻辑"""
        # 实现你的业务逻辑
        self.logger.info("执行自定义任务")
        return {"status": "success"}
```

2. 在 `tasks/task_factory.py` 中注册任务：

```python
from tasks.MyCustomTask import MyCustomTask

# 注册到工厂
task_factory.register_task("my_custom_task", MyCustomTask)
```

3. 通过 API 添加任务实例：

```bash
curl -X POST http://localhost:8080/api/scheduler/jobs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "task_instance_id": "my_task_1",
    "task_class_id": "my_custom_task",
    "schedule_type": "interval",
    "schedule_config": {"minutes": 5},
    "task_config": {"param1": "value1"}
  }'
```

### 添加新的数据处理策略

1. 在 `services/dataStrategy/` 创建新策略：

```python
# services/dataStrategy/my_strategy.py
from services.dataStrategy.base_strategy import DataStrategy

class MyDataStrategy(DataStrategy):
    def process_data(self, data):
        """处理数据逻辑"""
        metric_name = data.get("metric_name")
        device_ip = data.get("device_ip")
        
        # 处理数据
        processed_data = self._transform(data)
        
        # 存储到数据库
        self._save_to_db(processed_data)
```

2. 在 `services/dataStrategy/__init__.py` 注册：

```python
from .my_strategy import MyDataStrategy

strategy_factory.register_strategy("my_metric", MyDataStrategy())
```

### 开发环境配置

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装开发依赖
pip install -r requirements.txt
pip install pytest pytest-cov black flake8

# 3. 代码格式化
black .

# 4. 代码检查
flake8 --max-line-length=120 .

# 5. 运行测试
pytest tests/ -v
```

### 代码规范

- **风格指南**: 遵循 [PEP 8](https://peps.python.org/pep-0008/)
- **格式化工具**: Black (line-length=120)
- **类型注解**: 推荐使用 Type Hints
- **文档字符串**: 使用 Google 风格

**Git 提交规范**:
```
feat: 新增功能
fix: 修复 bug
docs: 文档更新
refactor: 代码重构
test: 测试相关
chore: 构建/工具更新
perf: 性能优化
```

---

## 🚢 部署与运维

---

## 🎯 后续优化计划

### 短期计划（1-3 个月）

1. **测试覆盖**
   - 添加单元测试（pytest）
   - API 接口测试
   - 目标覆盖率 > 80%

2. **文档完善**
   - 补充 API 文档（Swagger/OpenAPI）
   - 添加开发者指南
   - 完善部署文档

3. **性能优化**
   - 实现数据库连接池
   - 添加 Redis 缓存层
   - 优化数据库查询

4. **监控增强**
   - 集成 Prometheus 指标
   - 添加分布式追踪（OpenTelemetry）
   - 结构化日志输出（JSON）

### 中期计划（3-6 个月）

1. **架构演进**
   - 考虑迁移到 FastAPI（异步化）
   - 实现服务容器化和编排（Kubernetes）
   - 微服务拆分（按功能模块）

2. **功能增强**
   - 实现告警规则引擎
   - 添加数据可视化面板
   - 支持多租户隔离

3. **安全加固**
   - 实现 RBAC 细粒度权限控制
   - 添加操作审计日志
   - 集成 OAuth2/OIDC

### 长期计划（6-12 个月）

1. **高可用架构**
   - 支持集群部署
   - 实现故障自动切换
   - 数据库读写分离

2. **AI 赋能**
   - 日志智能分析
   - 异常模式识别
   - 告警智能降噪

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

### 贡献流程

1. **Fork 项目**
   ```bash
   git clone https://github.com/your-username/central-server.git
   cd central-server
   ```

2. **创建特性分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **编写代码并测试**
   ```bash
   # 确保代码符合规范
   black .
   flake8 .
   
   # 运行测试
   pytest tests/
   ```

4. **提交更改**
   ```bash
   git add .
   git commit -m "feat: 添加某某功能"
   git push origin feature/your-feature-name
   ```

5. **创建 Pull Request**
   - 在 GitHub 上创建 PR
   - 详细描述改动内容
   - 等待代码审查

### 报告问题

如果发现 Bug 或有功能建议，请：
1. 在 GitHub Issues 中搜索是否已有相关问题
2. 如果没有，创建新 Issue，包含：
   - 问题描述
   - 复现步骤
   - 预期行为
   - 实际行为
   - 环境信息（操作系统、Python 版本等）

---

## 📄 许可证

本项目采用 [MIT License](LICENSE)

---

## 📞 联系方式

- **项目维护者**: NetOps Team
- **Email**: netops@example.com
- **文档**: [项目 Wiki](https://github.com/your-org/central-server/wiki)
- **问题反馈**: [GitHub Issues](https://github.com/your-org/central-server/issues)

---

## 🙏 致谢

感谢以下开源项目：
- [Flask](https://flask.palletsprojects.com/) - Web 框架
- [APScheduler](https://apscheduler.readthedocs.io/) - 任务调度
- [Paramiko](http://www.paramiko.org/) - SSH 协议实现
- 以及所有 `requirements.txt` 中列出的依赖项

---

**最后更新**: 2026-08-20
