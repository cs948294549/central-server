# 消息队列配置说明

## 📋 概述

Central-Server 支持两种消息队列实现：
- **Redis 队列**：基于 Redis List 实现，简单轻量
- **Kafka**：分布式消息队列，高吞吐量

通过配置文件可以灵活切换，无需修改业务代码。

---

## 🔧 配置方法

### 在 config.py 中配置

```python
# 消息队列类型: "kafka" 或 "redis"
queue_type = "redis"  # 使用 Redis 队列
# queue_type = "kafka"  # 切换为 Kafka
```

### 完整配置示例

```python
class Config:
    # 消息队列类型
    queue_type = "redis"  # 或 "kafka"
    
    # Kafka 配置（当 queue_type = "kafka" 时使用）
    kafka_server = ["localhost:9092"]
    collect_kafka_topic = "collect_data"
    syslog_kafka_topic = "syslog_data"
    
    # Redis 配置（当 queue_type = "redis" 时使用）
    redis_host = "localhost"
    redis_port = 6379
    redis_db = 0
    queue_key_collect = "queue:collect_data"
    queue_key_syslog = "queue:syslog_data"
```

---

## 📊 两种队列对比

| 特性 | Redis 队列 | Kafka |
|------|-----------|-------|
| **部署复杂度** | 简单（单机 Redis） | 复杂（需要 ZooKeeper） |
| **性能** | 中等（单机限制） | 高（分布式） |
| **消息持久化** | 支持（RDB/AOF） | 支持（磁盘日志） |
| **消息堆积能力** | 受内存限制 | 受磁盘限制 |
| **消费模式** | 简单队列 | 支持多消费者组 |
| **适用场景** | 小规模部署、开发测试 | 大规模生产环境 |
| **依赖** | Redis | Kafka + ZooKeeper |

---

## 🎯 使用建议

### 使用 Redis 队列的场景：
- ✅ 开发环境和测试环境
- ✅ 小规模部署（单机或少量设备）
- ✅ 消息量不大（每秒几百条以内）
- ✅ 希望简化部署（已有 Redis，不想额外部署 Kafka）

### 使用 Kafka 的场景：
- ✅ 生产环境（大规模部署）
- ✅ 高吞吐量需求（每秒数千条以上）
- ✅ 需要消息回溯和多消费者组
- ✅ 已有 Kafka 集群

---

## 💻 代码实现

### 统一适配器

项目使用 `function_messaging/message_queue.py` 作为统一适配器，自动根据配置加载对应的队列实现。

**业务代码示例**：
```python
# 使用统一接口，无需关心底层实现
from function_messaging.message_queue import (
    readDataFromSyslog,
    readDataFromCollect,
    sendDataToSyslog,
    sendDataToCollector
)

# 读取消息（统一接口）
for message in readDataFromCollect():
    data = message.value  # 统一通过 .value 访问消息内容
    print(data)

# 发送消息（统一接口）
sendDataToCollector({"key": "value"})
```

### 消息接口统一

**Kafka 消息**：
```python
# Kafka 原生消息对象
message.value  # 消息内容
message.key    # 消息键
```

**Redis 消息**：
```python
# Redis 返回的是字典，通过 MessageWrapper 包装
message.value  # 消息内容（字典）
message.key    # None（Redis 队列不支持 key）
```

**统一后**：
```python
# 业务代码统一使用 message.value 访问
for message in readDataFromCollect():
    data = message.value  # 无论 Kafka 还是 Redis，都是这样访问
```

---

## 🔄 切换步骤

### 从 Redis 切换到 Kafka

1. **部署 Kafka 集群**
   ```bash
   # 启动 ZooKeeper
   bin/zookeeper-server-start.sh config/zookeeper.properties
   
   # 启动 Kafka
   bin/kafka-server-start.sh config/server.properties
   ```

2. **创建 Topic**
   ```bash
   bin/kafka-topics.sh --create --topic collect_data --bootstrap-server localhost:9092
   bin/kafka-topics.sh --create --topic syslog_data --bootstrap-server localhost:9092
   ```

3. **修改配置**
   ```python
   # config.py
   queue_type = "kafka"
   kafka_server = ["localhost:9092"]
   ```

4. **重启服务**
   ```bash
   docker restart central-server
   ```

### 从 Kafka 切换到 Redis

1. **确保 Redis 已部署**
   ```bash
   redis-cli ping
   ```

2. **修改配置**
   ```python
   # config.py
   queue_type = "redis"
   redis_host = "localhost"
   redis_port = 6379
   ```

3. **重启服务**
   ```bash
   docker restart central-server
   ```

---

## 🐛 故障排查

### 启动时报错：不支持的消息队列类型

**错误信息**：
```
ValueError: 不支持的消息队列类型: xxx，请配置为 'kafka' 或 'redis'
```

**解决方案**：
- 检查 `../config/config.py` 中 `queue_type` 的值
- 只能是 `"kafka"` 或 `"redis"`（注意引号和小写）

### Kafka 连接失败

**错误信息**：
```
NoBrokersAvailable: NoBrokersAvailable
```

**排查步骤**：
```bash
# 1. 检查 Kafka 是否运行
ps aux | grep kafka

# 2. 检查端口是否监听
netstat -an | grep 9092

# 3. 测试连接
telnet localhost 9092

# 4. 检查配置
# config.py 中 kafka_server 地址是否正确
```

### Redis 连接失败

**错误信息**：
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**排查步骤**：
```bash
# 1. 检查 Redis 是否运行
redis-cli ping

# 2. 检查配置
# config.py 中 redis_host 和 redis_port 是否正确

# 3. 检查防火墙
telnet localhost 6379
```

### 消息丢失

**Redis 队列**：
- 检查 Redis 内存是否充足
- 检查是否配置了持久化（AOF/RDB）
- Redis 重启会导致未持久化的消息丢失

**Kafka**：
- 检查 Topic 的副本数配置
- 检查磁盘空间是否充足

---

## 📈 性能优化

### Redis 队列优化

```python
# Redis 配置优化
redis_host = "localhost"
redis_port = 6379
redis_db = 0

# Redis 持久化配置（redis.conf）
appendonly yes
appendfsync everysec
```

### Kafka 优化

```python
# Kafka 生产者配置
kafka_server = ["kafka1:9092", "kafka2:9092", "kafka3:9092"]

# 批量发送配置（kafka_client.py）
batch_size = 16384
linger_ms = 10
```

---

## 📚 相关文件

- `function_messaging/message_queue.py`: 统一适配器
- `function_messaging/kafka_client.py`: Kafka 实现
- `function_messaging/queue_client.py`: Redis 队列实现
- `services/syslog_main.py`: Syslog 数据处理服务
- `services/data_main.py`: 数据处理服务

---

**最后更新**: 2026-08-14
