import redis
from typing import Optional
from config import Config

# 定义redis连接池
_pool = redis.ConnectionPool(host=Config.redis_host, port=6379, db=1)

def get_redis_client() -> redis.Redis:
    red = redis.Redis(connection_pool=_pool)
    return red