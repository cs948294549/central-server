#!/bin/bash

# Central-Server Docker 启动脚本
# 用于启动 central-server 容器

set -e

# 配置变量
CONTAINER_NAME="central-server"
IMAGE_NAME="central-server"
IMAGE_TAG="${1:-v1}"
API_PORT="${2:-8080}"
WEBSOCKET_PORT="${3:-8081}"
CONTAINER_API_PORT="8080"
CONTAINER_WEBSOCKET_PORT="8081"

# 数据目录配置
DATA_BASE_DIR="${CENTRAL_DATA_DIR:-$(pwd)}"
LOGS_DIR="${DATA_BASE_DIR}/logs"
FILES_DIR="${DATA_BASE_DIR}/files"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Central-Server Docker 容器启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}容器名称:${NC} ${CONTAINER_NAME}"
echo -e "${YELLOW}镜像:${NC} ${IMAGE_NAME}:${IMAGE_TAG}"
echo -e "${YELLOW}端口映射:${NC}"
echo -e "  API: ${API_PORT}:${CONTAINER_API_PORT}"
echo -e "  WebSocket: ${WEBSOCKET_PORT}:${CONTAINER_WEBSOCKET_PORT}"
echo ""

# 切换到脚本所在目录的父目录（项目根目录）
cd "$(dirname "$0")/.."

# 检查镜像是否存在
if ! docker images | grep -q "${IMAGE_NAME}.*${IMAGE_TAG}"; then
    echo -e "${RED}错误: 镜像 ${IMAGE_NAME}:${IMAGE_TAG} 不存在${NC}"
    echo -e "${YELLOW}请先运行构建脚本:${NC} ./docker/app_build.sh"
    exit 1
fi

# 检查配置文件
if [ ! -f "config.py" ]; then
    echo -e "${RED}错误: 配置文件 config.py 不存在${NC}"
    echo -e "${YELLOW}请从模板创建配置文件:${NC}"
    echo -e "  cp config_example.py config.py"
    echo -e "  vim config.py  # 编辑配置"
    exit 1
fi

# 检查容器是否已存在
if docker ps -a | grep -q "${CONTAINER_NAME}"; then
    echo -e "${YELLOW}发现已存在的容器，正在停止并删除...${NC}"
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}" 2>/dev/null || true
    echo -e "${GREEN}✓${NC} 旧容器已清理"
    echo ""
fi

# 创建必要的目录
echo -e "${YELLOW}准备数据目录...${NC}"
mkdir -p "${LOGS_DIR}"
mkdir -p "${FILES_DIR}"
echo -e "${GREEN}✓${NC} 日志目录: ${LOGS_DIR}"
echo -e "${GREEN}✓${NC} 文件目录: ${FILES_DIR}"
echo ""

# 启动容器
echo -e "${GREEN}启动容器...${NC}"
echo ""

docker run -d \
    --name "${CONTAINER_NAME}" \
    -p ${API_PORT}:${CONTAINER_API_PORT} \
    -p ${WEBSOCKET_PORT}:${CONTAINER_WEBSOCKET_PORT} \
    -e PYTHONUNBUFFERED=1 \
    -v "${LOGS_DIR}:/app/logs" \
    -v "${FILES_DIR}:/app/files" \
    -v "$(pwd)/config.py:/app/config.py:ro" \
    --restart unless-stopped \
    --health-cmd="ps aux | grep -v grep | grep -q 'python.*main.py' || exit 1" \
    --health-interval=60s \
    --health-timeout=10s \
    --health-retries=3 \
    "${IMAGE_NAME}:${IMAGE_TAG}"

# 检查启动结果
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  容器启动成功!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}容器状态:${NC}"
    docker ps | grep "${CONTAINER_NAME}"
    echo ""
    echo -e "${YELLOW}服务访问地址:${NC}"
    echo -e "  API 服务: ${GREEN}http://localhost:${API_PORT}${NC}"
    echo -e "  WebSocket: ${GREEN}ws://localhost:${WEBSOCKET_PORT}${NC}"
    echo -e "  健康检查: ${GREEN}http://localhost:${API_PORT}/system/health${NC}"
    echo ""
    echo -e "${YELLOW}常用命令:${NC}"
    echo -e "  查看日志: ${GREEN}docker logs -f ${CONTAINER_NAME}${NC}"
    echo -e "  查看应用日志: ${GREEN}ls -lh ${LOGS_DIR}${NC}"
    echo -e "  停止容器: ${GREEN}docker stop ${CONTAINER_NAME}${NC}"
    echo -e "  重启容器: ${GREEN}docker restart ${CONTAINER_NAME}${NC}"
    echo -e "  进入容器: ${GREEN}docker exec -it ${CONTAINER_NAME} bash${NC}"
    echo ""
    echo -e "${YELLOW}数据位置:${NC}"
    echo -e "  配置文件: ${GREEN}$(pwd)/config.py${NC}"
    echo -e "  应用日志: ${GREEN}${LOGS_DIR}/${NC}"
    echo -e "  文件存储: ${GREEN}${FILES_DIR}/${NC}"
    echo ""

    # 等待几秒后检查服务
    echo -e "${YELLOW}等待服务启动...${NC}"
    sleep 3

    echo -e "${YELLOW}检查容器日志:${NC}"
    docker logs --tail 20 "${CONTAINER_NAME}"
    echo ""

    # 检查健康状态
    echo -e "${YELLOW}检查服务健康状态...${NC}"
    sleep 3
    if curl -f -s http://localhost:${API_PORT}/system/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API 服务健康检查通过${NC}"
    else
        echo -e "${YELLOW}⚠ API 服务尚未就绪，请稍后查看日志${NC}"
        echo -e "${YELLOW}  docker logs -f ${CONTAINER_NAME}${NC}"
    fi
    echo ""
else
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  容器启动失败!${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi
