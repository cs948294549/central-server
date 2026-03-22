# 构建
docker build --no-cache -f Dockerfile_chen -t claw:v1.0 .

# 启动
docker run -d --name my_claw -p 18789:18789 claw:v1.0  tail -f /dev/null

# 初始设置
openclaw onboard --install-daemon

# 设置远程访问
openclaw config set gateway.bind lan
openclaw config get gateway.bind
openclaw config get gateway.port


# 记录访问链接
openclaw dashboard

# 启动服务
openclaw gateway run


# 获取当前请求的ID
openclaw devices list

# 授权请求
openclaw devices approve [Request ID]