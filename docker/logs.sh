#!/bin/bash

# Central-Server 日志查看脚本
# 快速查看和排查 Docker 容器日志

set -e

CONTAINER_NAME="central-server"
DATA_BASE_DIR="${CENTRAL_DATA_DIR:-$(pwd)}"
LOGS_DIR="${DATA_BASE_DIR}/logs"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 显示帮助信息
show_help() {
    echo -e "${GREEN}Central-Server 日志查看工具${NC}"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  follow, -f        实时跟踪 Docker 日志（默认）"
    echo "  tail [N]          查看最后 N 行日志（默认 100）"
    echo "  app               查看应用日志文件列表"
    echo "  server            实时跟踪主服务日志"
    echo "  error             查看错误日志"
    echo "  search [keyword]  搜索包含关键字的日志"
    echo "  clear             清空应用日志文件"
    echo "  health            检查服务健康状态"
    echo "  help, -h          显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 实时查看 Docker 日志"
    echo "  $0 tail 200           # 查看最后 200 行"
    echo "  $0 app                # 列出应用日志文件"
    echo "  $0 server             # 实时查看主服务日志"
    echo "  $0 error              # 查看错误日志"
    echo "  $0 search \"API\"      # 搜索包含关键字的日志"
    echo "  $0 health             # 检查服务健康状态"
    echo ""
}

# 检查容器是否运行
check_container() {
    if ! docker ps | grep -q "${CONTAINER_NAME}"; then
        echo -e "${RED}错误: 容器 ${CONTAINER_NAME} 未运行${NC}"
        echo -e "${YELLOW}提示: 使用 ./docker/app_start.sh 启动容器${NC}"
        exit 1
    fi
}

# 实时跟踪 Docker 日志
follow_docker_logs() {
    check_container
    echo -e "${GREEN}实时跟踪 Docker 日志 (Ctrl+C 退出)${NC}"
    echo -e "${YELLOW}容器: ${CONTAINER_NAME}${NC}"
    echo ""
    docker logs -f "${CONTAINER_NAME}"
}

# 查看最后 N 行日志
tail_docker_logs() {
    local lines=${1:-100}
    check_container
    echo -e "${GREEN}查看最后 ${lines} 行 Docker 日志${NC}"
    echo ""
    docker logs --tail "${lines}" "${CONTAINER_NAME}"
}

# 列出应用日志文件
list_app_logs() {
    echo -e "${GREEN}应用日志文件列表${NC}"
    echo -e "${YELLOW}日志目录: ${LOGS_DIR}${NC}"
    echo ""

    if [ ! -d "${LOGS_DIR}" ]; then
        echo -e "${RED}错误: 日志目录不存在${NC}"
        exit 1
    fi

    if [ -z "$(ls -A ${LOGS_DIR} 2>/dev/null)" ]; then
        echo -e "${YELLOW}日志目录为空${NC}"
    else
        ls -lh "${LOGS_DIR}"
    fi
}

# 实时跟踪主服务日志
tail_server_log() {
    local logpath="${LOGS_DIR}/central-server.log"

    if [ ! -f "${logpath}" ]; then
        echo -e "${YELLOW}警告: 主服务日志文件不存在: ${logpath}${NC}"
        echo -e "${YELLOW}尝试查看 Docker 日志...${NC}"
        echo ""
        follow_docker_logs
        return
    fi

    echo -e "${GREEN}实时跟踪主服务日志 (Ctrl+C 退出)${NC}"
    echo -e "${YELLOW}文件: ${logpath}${NC}"
    echo ""
    tail -f "${logpath}"
}

# 查看错误日志
show_error_logs() {
    check_container
    echo -e "${GREEN}查看错误日志${NC}"
    echo ""
    docker logs "${CONTAINER_NAME}" 2>&1 | grep -iE "error|exception|fail|traceback|warning" --color=always | tail -50
}

# 搜索日志
search_logs() {
    local keyword="$1"

    if [ -z "$keyword" ]; then
        echo -e "${RED}错误: 请提供搜索关键字${NC}"
        exit 1
    fi

    check_container
    echo -e "${GREEN}搜索包含 '${keyword}' 的日志${NC}"
    echo ""
    docker logs "${CONTAINER_NAME}" 2>&1 | grep -i "${keyword}" --color=always
}

# 清空应用日志
clear_logs() {
    echo -e "${YELLOW}确认要清空应用日志吗? (y/N)${NC}"
    read -r confirm

    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        rm -f "${LOGS_DIR}"/*.log
        echo -e "${GREEN}✓ 应用日志已清空${NC}"
    else
        echo -e "${YELLOW}已取消${NC}"
    fi
}

# 检查服务健康状态
check_health() {
    check_container

    echo -e "${GREEN}检查服务健康状态${NC}"
    echo ""

    # 检查容器状态
    echo -e "${YELLOW}1. 容器状态:${NC}"
    docker ps | grep "${CONTAINER_NAME}" || echo -e "${RED}容器未运行${NC}"
    echo ""

    # 检查容器健康状态
    echo -e "${YELLOW}2. 健康检查:${NC}"
    health_status=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
    if [ "$health_status" = "healthy" ]; then
        echo -e "${GREEN}✓ 容器健康状态: ${health_status}${NC}"
    else
        echo -e "${YELLOW}⚠ 容器健康状态: ${health_status}${NC}"
    fi
    echo ""

    # 检查 API 端口
    echo -e "${YELLOW}3. API 服务 (端口 8080):${NC}"
    if curl -f -s http://localhost:8080/system/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API 服务正常${NC}"
        curl -s http://localhost:8080/system/health | python3 -m json.tool 2>/dev/null || echo ""
    else
        echo -e "${RED}✗ API 服务无响应${NC}"
    fi
    echo ""

    # 检查 WebSocket 端口
    echo -e "${YELLOW}4. WebSocket 服务 (端口 8081):${NC}"
    if curl -f -s http://localhost:8081/ > /dev/null 2>&1; then
        echo -e "${GREEN}✓ WebSocket 服务正常${NC}"
    else
        echo -e "${RED}✗ WebSocket 服务无响应${NC}"
    fi
    echo ""

    # 显示最近日志
    echo -e "${YELLOW}5. 最近日志 (最后 10 行):${NC}"
    docker logs --tail 10 "${CONTAINER_NAME}"
    echo ""
}

# 主逻辑
case "${1:-follow}" in
    follow|-f)
        follow_docker_logs
        ;;
    tail)
        tail_docker_logs "$2"
        ;;
    app)
        list_app_logs
        ;;
    server)
        tail_server_log
        ;;
    error)
        show_error_logs
        ;;
    search)
        search_logs "$2"
        ;;
    clear)
        clear_logs
        ;;
    health)
        check_health
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        echo -e "${RED}未知选项: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
