docker run -d \
  --name librenms-ex \
  --network librenms-network \
  --restart always \
  -p 8001:8000 \
  -p 5514:514 \
  -e DB_HOST=192.168.110.153 \
  -e DB_NAME=librenms \
  -e DB_USER=root \
  -e DB_PASSWORD=root \
  -e DB_PORT=33060 \
  -e REDIS_HOST=librenms_redis \
  -e REDIS_PORT=6379 \
  -e TZ=Asia/Shanghai \
  -v /opt/librenms:/opt/librenms \
  -v /data/logs:/data/logs \
  librenms/librenms:latest


mkdir -p /opt/librenms/{logs,rrd,storage}

# 1. 先启动临时容器（不挂载卷），仅用于复制内容
docker run --name temp-librenms -d librenms/librenms

# 2. 复制内容
docker cp temp-librenms:/opt/librenms/storage/ /opt/librenms/

# 3. 停止并删除临时容器
docker stop temp-librenms && docker rm temp-librenms

docker run -d \
  --name librenms-ex \
  --network librenms-network \
  --restart always \
  -p 8001:8000 \
  -p 5514:514 \
  -e DB_HOST=192.168.110.153 \
  -e DB_NAME=librenms \
  -e DB_USER=root \
  -e DB_PASSWORD=root \
  -e DB_PORT=33060 \
  -e REDIS_HOST=librenms_redis \
  -e REDIS_PORT=6379 \
  -e TZ=Asia/Shanghai \
  -v /opt/librenms/logs:/data/logs \
  -v /opt/librenms/rrd:/opt/librenms/rrd \
  -v /opt/librenms/storage:/opt/librenms/storage \
  librenms/librenms:latest