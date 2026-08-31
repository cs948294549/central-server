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

即可看到登录页面，使用默认账号 `admin` / `123456` 登录。

**默认管理员账号**:
- 用户名: `admin`
- 密码: `123456`

⚠️ **安全提示**: 
- 首次登录后必须立即修改默认密码
- 新建用户的默认密码也是 `123456`，需要在首次登录后修改

**登录方式**:
- 通过前端页面登录（推荐）
- 通过 API 登录需要提交密码的 hash 值
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

## 🤖 MCP 集成

Central-Server 内置了 MCP（Model Context Protocol）服务，将网络运维能力以工具（Tools）的形式暴露给支持 MCP 的 AI 客户端（如 Claude Code），可直接通过对话完成设备命令执行、设备信息检索等操作。

### 认证方式

MCP 接口使用独立的认证方式，与主站认证机制分离，不校验时间戳，仅校验 `key:secret`：

```
Authorization: Bearer <key>:<secret>
```

其中 `key` 对应用户的 `username`，`secret` 对应用户的 `identify` 字段（数据库中存储的 API 密钥）。

### 接入 Claude Code

```bash
claude mcp add --header "Authorization: Bearer <key>:<secret>" --transport http <name> http://<netops.vdian.net>/api/mcp
```

- `<key>:<secret>` 替换为实际分配的账号密钥
- `<name>` 为自定义的 MCP 服务名称
- `<netops.vdian.net>` 替换为实际部署域名或 IP

### 相关接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/mcp` | POST | MCP 协议主入口（JSON-RPC 2.0），支持 `initialize`、`ping`、`tools/list`、`tools/call` 等方法 |
| `/api/mcp/tools` | GET | 获取当前可用工具列表 |
| `/api/mcp/health` | GET | MCP 服务健康检查 |

### 可用工具（Tools）

| 工具 | 说明 |
|------|------|
| `run_cmd` | 登录交换机设备执行命令（出于安全策略，仅允许 `display`/`show` 等查询类命令） |
| `get_vendor` | 通过 SNMP 获取设备厂商信息 |
| `search_device_list` | 通过设备名（sysname）、描述（sysdesc）搜索并返回完整设备列表 |
| `location_device` | 通过设备名/SN/IP 等关键字定位设备，返回设备详情、ARP/LLDP/MAC 表等多维数据 |
| `send_message` | 发送点对点或群组消息通知 |
**最后更新**: 2026-08-20
