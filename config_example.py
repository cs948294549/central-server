class Config:
    """中心服务配置"""
    # API服务配置
    service_ip = "0.0.0.0"
    service_port = 8080
    log_level = "INFO"

    # WebSocket服务配置
    websocket_enable = True
    websocket_ip = "0.0.0.0"
    websocket_port = 8081

    # JWT 认证配置
    # 注意：JWT Secret Key 是后端专用密钥，用于签名和验证 Token
    # ⚠️ 重要：修改此密钥后，所有已签发的 Token 将立即失效，用户需重新登录
    # 生产环境请使用强随机密钥，运行: python scripts/generate_secret_key.py
    jwt_secret_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFkbWlu"
    jwt_algorithm = "HS256"
    jwt_expire_hours = 24  # JWT Token 有效期（小时）

    # 时间戳验证配置
    # Apptime 时间戳允许的最大偏差（秒），用于防止重放攻击
    timestamp_tolerance = 300  # 默认 5 分钟

    # ⚠️ 统一认证说明：
    # 所有用户数据存储在 users 表中，支持两种认证方式：
    # 1. Web 用户登录：POST /system/login 获取 JWT Token，后续请求使用 Authorization: Bearer <token>
    # 2. API 调用：直接使用 username 作为 key，md5(identify+timestamp) 作为 secret
    # 详细文档请查看: docs/AUTHENTICATION.md

    # 数据采集配置
    collect_enable = True
    collect_kafka_topic = "collect_data"

    # Syslog服务器配置
    syslog_enable = True
    syslog_kafka_topic = "syslog_data"

    # 消息队列配置
    kafka_server = ["localhost:9092"]

    # Redis配置
    redis_host = "localhost"
    redis_port = 6379
    redis_db = 0

    # Redis队列配置（用于替代Kafka）
    queue_key_collect = "queue:collect_data"
    queue_key_syslog = "queue:syslog_data"

    # MySQL配置
    mysql_config = {
        "db_host": "localhost",
        "db_user": "root",
        "db_token": "root",
        "db_port": 3306,
    }
