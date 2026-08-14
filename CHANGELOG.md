# 更新日志 (CHANGELOG)

所有重要的项目更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵守 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.0.1] - 2026-08-14

### 🔐 安全改进

#### Changed
- **配置文件优化**: 将 JWT 和 API Key 配置从 `user_manage.py` 移到 `config.py`
  - `jwt_secret_key` - JWT 签名密钥
  - `jwt_algorithm` - JWT 加密算法
  - `jwt_expire_hours` - JWT Token 有效期
  - `api_secrets` - API Key 认证配置

#### Added
- **密钥生成工具**: `scripts/generate_secret_key.py`
  - 生成安全的 JWT Secret Key
  - 生成 API Secret Key
  - 提供配置指导

- **配置文档**: `docs/CONFIG.md`
  - 详细的配置项说明
  - 安全最佳实践
  - 环境变量支持说明

#### Fixed
- 修复硬编码密钥的安全隐患
- 提高配置管理的灵活性

---

## [1.0.0] - 2026-08-14

### 🎉 首次发布

#### 核心功能
- **RESTful API 服务** (端口 8080)
  - 用户认证与权限管理 (JWT + API Key)
  - 任务调度管理
  - 告警规则管理（黑名单、聚合规则）
  - 系统管理接口
  - 工具接口

- **WebSocket 实时推送** (端口 8081)
  - 实时消息推送
  - 多频道支持
  - 客户端连接管理
  - HTTP 消息发送接口

- **后台服务**
  - Syslog 日志处理（黑名单过滤、日志聚合）
  - 数据采集处理（策略模式）
  - APScheduler 任务调度
  - 定时任务管理

- **数据存储**
  - MySQL 数据持久化
  - Redis 缓存和队列
  - Elasticsearch 日志存储（可选）
  - Kafka 消息队列支持

#### 技术特性
- **单进程架构**: API + WebSocket 统一管理
- **多线程模型**: 独立线程处理不同服务
- **策略模式**: 可扩展的数据处理器
- **双消息队列**: 支持 Kafka 和 Redis 队列

#### Docker 支持
- **完整的容器化方案**
  - 多阶段构建优化镜像体积
  - 非特权用户运行（安全）
  - 时区配置 Asia/Shanghai (UTC+8)
  - 健康检查集成
  
- **Docker Compose 编排**
  - Central Server (主应用)
  - Redis (缓存/队列)
  - MySQL (数据库)
  - Kafka + Zookeeper (消息队列)
  - Elasticsearch (日志存储)
  
- **一键启动脚本** (`start.sh`)
  - 交互式菜单
  - 自动环境检查
  - 服务管理功能

#### 文档体系
- `README.md` - 完整架构文档
- `docs/QUICKSTART.md` - 5分钟快速开始
- `docs/DOCKER_DEPLOY.md` - Docker 部署完整指南
- `docs/PROJECT_SUMMARY.md` - 项目技术总结
- `CHANGELOG.md` - 本文件

#### 开发体验
- 统一配置管理 (`config.py`)
- 完整的依赖声明 (`requirements.txt`)
- Docker 构建优化 (`.dockerignore`)
- 健康检查端点 (`/system/health`)
- 结构化日志输出

### 📦 依赖
- Flask 2.2.5
- Flask-SocketIO 5.3.6
- Eventlet 0.33.3
- APScheduler
- PyJWT
- PyMySQL
- Kafka-Python
- Redis
- Elasticsearch
- Paramiko 2.10.4
- PureSNMP 1.11.0

### 🚀 快速开始

#### Docker 部署（推荐）
```bash
./start.sh
```

#### 本地部署
```bash
pip install -r requirements.txt
cp config_example.py config.py
python main.py
```

---

## 未来计划

### v1.1.0 (计划中)
- [ ] 添加单元测试覆盖
- [ ] Prometheus 监控集成
- [ ] Swagger API 文档
- [ ] CI/CD 流水线

### v1.2.0 (计划中)
- [ ] 配置热更新
- [ ] 限流和熔断
- [ ] 数据库连接池优化
- [ ] 分布式追踪

### v2.0.0 (规划中)
- [ ] 迁移到 FastAPI
- [ ] 异步 I/O 改造
- [ ] 微服务架构
- [ ] Kubernetes 部署

---

## 版本说明

### 版本号格式
使用语义化版本：`主版本号.次版本号.修订号`

- **主版本号**: 不兼容的 API 修改
- **次版本号**: 向下兼容的功能性新增
- **修订号**: 向下兼容的问题修正

### 标签说明
- `Added` - 新增功能
- `Changed` - 功能变更
- `Deprecated` - 即将移除的功能
- `Removed` - 已移除的功能
- `Fixed` - 问题修复
- `Security` - 安全修复

---

**维护者**: [待补充]  
**最后更新**: 2026-08-14
