import redis

# 定义redis连接池
pool = redis.ConnectionPool(host='192.168.56.10', port=6379, db=1)
red = redis.Redis(connection_pool=pool)