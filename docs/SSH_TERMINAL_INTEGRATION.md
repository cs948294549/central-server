# SSH 终端功能集成指南

## 概述

SSH 终端功能已完全集成到 WebSocket 服务器中，无需修改主应用代码。

## 架构说明

```
┌─────────────┐                                    
│   前端      │ ─── WebSocket (订阅消息) ──────────┐
│  (xterm.js) │                                    │
│             │ ─── HTTP API (发送命令) ─────────┐ │
└─────────────┘                                  │ │
                                                 ↓ ↓
                                        ┌──────────────────┐
                                        │  WebSocket       │
                                        │  Server          │
                                        │  (port 8081)     │
                                        │                  │
                                        │ 包含:            │
                                        │ - SSH Manager    │
                                        │ - HTTP Routes    │
                                        │ - SocketIO       │
                                        └──────────────────┘
                                                 │
                                        ┌────────┴────────┐
                                        │                 │
                                ┌───────↓──────┐   ┌─────↓──────┐
                                │ SSH Session  │   │ SSH Session│
                                │ (device 1)   │   │ (device 2) │
                                └──────────────┘   └────────────┘
                                        │                 │
                                        ↓                 ↓
                                ┌──────────────┐   ┌────────────┐
                                │  Network     │   │  Network   │
                                │  Device 1    │   │  Device 2  │
                                └──────────────┘   └────────────┘
```

## 已完成的集成

### 1. WebSocket 服务器 (`core/websocket_server.py`)

✅ 已集成 `InteractiveSSHManager`
✅ 已添加 SSH 相关的 HTTP 路由：
- `POST /ssh/create_session` - 创建 SSH 会话
- `POST /ssh/send_command` - 发送命令
- `POST /ssh/close_session` - 关闭会话
- `GET /ssh/session_status` - 查询状态

### 2. SSH 会话管理 (`function_ssh/interactive_ssh.py`)

✅ `InteractiveSSHSession` - 单个 SSH 交互式会话
✅ `InteractiveSSHManager` - 多会话管理器
✅ 自动清理死亡会话
✅ 实时输出通过 WebSocket 推送

### 3. 主应用 (`main.py`)

✅ 无需修改！WebSocket 服务器已经在主应用启动时初始化

## 工作流程

1. **前端创建会话**（可选，首次发送命令时自动创建）
   ```
   POST http://your-server:8081/ssh/create_session
   {
     "ip": "10.220.17.122",
     "user": "admin"
   }
   ```

2. **前端订阅 WebSocket 频道**
   ```javascript
   const session_id = `${user}_${ip}`
   this.sockets.subscribe(session_id, (data) => {
     this.term.write(data)  // 写入 xterm 终端
   })
   ```

3. **前端发送命令**
   ```
   POST http://your-server:8081/ssh/send_command
   {
     "ip": "10.220.17.122",
     "cmd": "show version",
     "padding": "0a",  // 回车
     "user": "admin"
   }
   ```

4. **后端处理**
   - SSH Manager 发送命令到设备
   - 设备返回输出
   - 通过 WebSocket 推送到前端（频道：`admin_10.220.17.122`）

5. **前端显示**
   - 前端收到 WebSocket 消息
   - 更新 xterm 终端显示

## API 接口说明

### 1. 创建 SSH 会话
- **URL**: `POST /ssh/create_session`
- **端口**: 8081 (WebSocket 服务器)
- **请求体**:
  ```json
  {
    "ip": "10.220.17.122",
    "user": "admin",
    "username": "ssh_user",  // 可选，默认使用 Config.ssh_username
    "password": "ssh_pass"   // 可选，默认使用 Config.ssh_password
  }
  ```
- **响应**:
  ```json
  {
    "status": "success",
    "session_id": "admin_10.220.17.122",
    "message": "SSH 会话已创建"
  }
  ```

### 2. 发送命令
- **URL**: `POST /ssh/send_command`
- **端口**: 8081
- **请求体**:
  ```json
  {
    "ip": "10.220.17.122",
    "cmd": "show version",
    "padding": "0a",  // 控制字符（十六进制）
    "user": "admin"
  }
  ```
- **响应**:
  ```json
  {
    "status": "success",
    "message": "命令已发送"
  }
  ```

### 3. 关闭会话
- **URL**: `POST /ssh/close_session`
- **端口**: 8081
- **请求体**:
  ```json
  {
    "ip": "10.220.17.122",
    "user": "admin"
  }
  ```

### 4. 查询会话状态
- **URL**: `GET /ssh/session_status?ip=10.220.17.122&user=admin`
- **端口**: 8081
- **响应**:
  ```json
  {
    "status": "success",
    "alive": true,
    "total_sessions": 3
  }
  ```

## 控制字符说明

| 十六进制 | 说明 | 用途 |
|---------|------|------|
| `0a` | 回车 (\\n) | 执行命令 |
| `03` | Ctrl+C | 中断命令 |
| `15` | Ctrl+U | 删除行 |
| `18` | Ctrl+X | 删除行 |
| `7f` | 退格 | 删除字符 |
| `09` | Tab | 自动补全 |
| `00` | 无控制字符 | 仅发送命令 |

## 前端对接

### 修改 `xterm_window.vue`

```javascript
import collector_api from "@/api/mapis/collector_interface.js"

export default {
  mounted() {
    // 1. 订阅 WebSocket 频道
    let user = this.$store.getters.info.emailPrefix
    this.ssh_session = user + "_" + this.target_ip
    
    this.sockets.subscribe(this.ssh_session, (data) => {
      this.cmd_show = this.cmd_show + data
      this.term.write(data)
    })
    
    // 2. 可选：显式创建会话
    this.createSession()
  },
  
  methods: {
    createSession() {
      collector_api.createSSHSession({
        ip: this.target_ip,
        user: this.$store.getters.info.emailPrefix
      }).then(response => {
        console.log('SSH 会话已创建')
      }).catch(error => {
        console.error('创建会话失败:', error)
      })
    },
    
    sendCMD(cmd, padding) {
      let post_data = {
        ip: this.target_ip,
        cmd: cmd,
        user: this.$store.getters.info.emailPrefix
      }
      
      if(padding) {
        post_data.padding = padding
      }
      
      collector_api.sendSSH(post_data).then(response => {
        // 命令已发送
      }).catch(error => {
        this.$message({
          type: 'error',
          message: '命令发送失败'
        })
      })
    },
    
    beforeDestroy() {
      // 关闭会话
      collector_api.closeSSHSession({
        ip: this.target_ip,
        user: this.$store.getters.info.emailPrefix
      })
      
      this.sockets.unsubscribe(this.ssh_session)
    }
  }
}
```

### 添加 API 方法到 `collector_interface.js`

```javascript
export default {
  // ... 现有方法 ...
  
  // SSH 终端相关接口
  createSSHSession(data, params) {
    return axios.post("/ssh/create_session", data, params)
  },
  sendSSH(data, params) {
    return axios.post("/ssh/send_command", data, params)
  },
  closeSSHSession(data, params) {
    return axios.post("/ssh/close_session", data, params)
  },
  getSSHSessionStatus(data, params) {
    return axios.get("/ssh/session_status", { params: data })
  },
}
```

### Nginx 代理配置（如果需要）

如果使用 Nginx 代理，需要配置 WebSocket 支持：

```nginx
# WebSocket 服务器代理
location /ssh/ {
    proxy_pass http://localhost:8081/ssh/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# WebSocket 连接代理
location /socket.io/ {
    proxy_pass http://localhost:8081/socket.io/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

## 测试方法

### 1. 测试 WebSocket 服务器

```bash
curl http://localhost:8081/
```

应返回：
```json
{"status": "ok", "service": "websocket"}
```

### 2. 测试创建 SSH 会话

```bash
curl -X POST http://localhost:8081/ssh/create_session \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "10.220.17.122",
    "user": "test_user"
  }'
```

### 3. 测试发送命令

```bash
curl -X POST http://localhost:8081/ssh/send_command \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "10.220.17.122",
    "cmd": "show version",
    "padding": "0a",
    "user": "test_user"
  }'
```

### 4. 测试 WebSocket 订阅

使用浏览器开发者工具查看 WebSocket 消息，或使用 Socket.IO 客户端测试：

```javascript
const socket = io('http://localhost:8081')
socket.on('test_user_10.220.17.122', (data) => {
  console.log('收到终端输出:', data)
})
```

## 配置说明

确保 `../config/config.py` 中有以下配置：

```python
class Config:
    # WebSocket 配置
    websocket_enable = True
    websocket_ip = '0.0.0.0'
    websocket_port = 8081
    
    # SSH 默认凭证
    ssh_username = 'admin'
    ssh_password = 'your_password'
```

## 故障排查

### 问题 1: WebSocket 连接失败
- 检查 WebSocket 服务器是否启动：`netstat -tuln | grep 8081`
- 检查防火墙规则
- 查看日志：`tail -f logs/app.log`

### 问题 2: SSH 连接超时
- 检查网络设备是否可达：`ping 10.220.17.122`
- 验证 SSH 凭证是否正确
- 检查设备 SSH 端口是否开放：`telnet 10.220.17.122 22`

### 问题 3: 收不到终端输出
- 检查 WebSocket 订阅的频道名是否正确（格式：`user_ip`）
- 使用浏览器开发者工具查看 WebSocket 消息
- 检查后端日志确认消息是否发送

### 问题 4: 会话创建失败
- 查看后端日志：`SSH 连接失败` 相关错误
- 确认 `paramiko` 模块已安装：`pip list | grep paramiko`
- 检查 Config 中的默认 SSH 凭证是否正确

## 性能优化建议

1. **会话复用**：同一用户对同一设备的多个操作复用 SSH 会话
2. **超时清理**：自动清理超过 30 分钟无活动的会话（已实现）
3. **连接池限制**：限制单个用户的最大会话数（建议 5 个）
4. **输出缓存**：缓存最近的输出，支持断线重连后恢复

## 安全建议

1. **身份验证**：在 WebSocket 连接时验证用户身份
2. **权限控制**：验证用户是否有权限访问目标设备
3. **审计日志**：记录所有 SSH 会话和执行的命令
4. **加密传输**：生产环境使用 HTTPS 和 WSS
5. **会话隔离**：确保用户只能访问自己的会话（已通过 `user_ip` 实现）

## 总结

✅ **无需修改主应用** - 所有功能已集成到 WebSocket 服务器
✅ **自动初始化** - WebSocket 服务器启动时自动创建 SSH Manager
✅ **独立运行** - SSH 功能在独立线程中运行，不影响主应用
✅ **即插即用** - 前端只需调用 WebSocket 服务器的 API

---

如有问题，请查看日志文件或联系开发团队。


```
┌─────────────┐         WebSocket          ┌──────────────────┐
│             │ <──────────────────────────>│  WebSocket       │
│   前端      │                             │  Server          │
│  (xterm.js) │                             │  (port 8081)     │
│             │ <──────────────────────────>│                  │
└─────────────┘         HTTP API            └──────────────────┘
                                                     │
                                                     │ emit
                                                     ↓
                                            ┌──────────────────┐
                                            │ Interactive      │
                                            │ SSH Manager      │
                                            └──────────────────┘
                                                     │
                                            ┌────────┴────────┐
                                            │                 │
                                    ┌───────↓──────┐   ┌─────↓──────┐
                                    │ SSH Session  │   │ SSH Session│
                                    │ (device 1)   │   │ (device 2) │
                                    └──────────────┘   └────────────┘
                                            │                 │
                                            ↓                 ↓
                                    ┌──────────────┐   ┌────────────┐
                                    │  Network     │   │  Network   │
                                    │  Device 1    │   │  Device 2  │
                                    └──────────────┘   └────────────┘
```

## 集成步骤

### 1. 在主应用中初始化模块

在你的主应用文件（如 `app.py` 或 `main.py`）中添加：

```python
from core.websocket_server import WebSocketServer
from function_ssh.interactive_ssh import InteractiveSSHManager
from api.ssh_terminal_api import ssh_terminal_bp, init_ssh_terminal_api

# 初始化 WebSocket 服务器
websocket_server = WebSocketServer(host='0.0.0.0', port=8081)
websocket_server.start()

# 初始化 SSH 会话管理器
ssh_manager = InteractiveSSHManager(websocket_server)

# 初始化 SSH 终端 API
init_ssh_terminal_api(ssh_manager)

# 注册 API 蓝图到主 Flask 应用
app.register_blueprint(ssh_terminal_bp)
```

### 2. 完整的主应用示例

```python
# app.py 或 main.py

from flask import Flask
from flask_cors import CORS
from core.websocket_server import WebSocketServer
from function_ssh.interactive_ssh import InteractiveSSHManager
from api.ssh_terminal_api import ssh_terminal_bp, init_ssh_terminal_api
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__)
CORS(app)

# 初始化 WebSocket 服务器
logger.info("正在启动 WebSocket 服务器...")
websocket_server = WebSocketServer(host='0.0.0.0', port=8081)
websocket_server.start()

# 初始化 SSH 会话管理器
logger.info("正在初始化 SSH 会话管理器...")
ssh_manager = InteractiveSSHManager(websocket_server)

# 初始化 SSH 终端 API
init_ssh_terminal_api(ssh_manager)

# 注册蓝图
app.register_blueprint(ssh_terminal_bp)

# 其他路由和配置...

if __name__ == '__main__':
    logger.info("正在启动主应用...")
    app.run(host='0.0.0.0', port=5000, debug=False)
```

## 前端对接

### 前端 API 调用示例

你的前端代码（`xterm_window.vue`）需要修改 API 调用：

```javascript
// 导入 API
import axios from 'axios'

const API_BASE = 'http://your-server:5000/api/ssh_terminal'

// 1. 创建 SSH 会话（在 mounted 钩子中）
async createSession() {
  try {
    const response = await axios.post(`${API_BASE}/create_session`, {
      ip: this.target_ip,
      user: this.$store.getters.info.emailPrefix
    })
    console.log('SSH 会话已创建:', response.data)
  } catch (error) {
    console.error('创建会话失败:', error)
  }
}

// 2. 发送命令
sendCMD(cmd, padding) {
  const post_data = {
    ip: this.target_ip,
    cmd: cmd,
    user: this.$store.getters.info.emailPrefix
  }
  
  if (padding) {
    post_data.padding = padding
  }
  
  axios.post(`${API_BASE}/send_command`, post_data)
    .then(response => {
      console.log('命令已发送:', response.data)
    })
    .catch(error => {
      console.error('发送命令失败:', error)
      this.$message({
        type: 'error',
        message: '命令发送失败，请重试'
      })
    })
}

// 3. 关闭会话（在 beforeDestroy 钩子中）
async closeSession() {
  try {
    await axios.post(`${API_BASE}/close_session`, {
      ip: this.target_ip,
      user: this.$store.getters.info.emailPrefix
    })
    console.log('SSH 会话已关闭')
  } catch (error) {
    console.error('关闭会话失败:', error)
  }
}
```

### WebSocket 连接配置

前端已经在使用 `socket.io-client`，确保连接到正确的 WebSocket 服务器地址：

```javascript
// 在 main.js 或相关配置文件中
import VueSocketIO from 'vue-socket.io'
import SocketIO from 'socket.io-client'

const socketConnection = SocketIO('http://your-server:8081', {
  transports: ['websocket'],
  autoConnect: false
})

Vue.use(new VueSocketIO({
  connection: socketConnection
}))
```

## API 接口说明

### 1. 创建 SSH 会话
- **URL**: `POST /api/ssh_terminal/create_session`
- **请求体**:
  ```json
  {
    "ip": "10.220.17.122",
    "user": "admin",
    "username": "ssh_user",  // 可选
    "password": "ssh_pass"   // 可选
  }
  ```
- **响应**:
  ```json
  {
    "status": "success",
    "session_id": "admin_10.220.17.122",
    "message": "SSH 会话已创建"
  }
  ```

### 2. 发送命令
- **URL**: `POST /api/ssh_terminal/send_command`
- **请求体**:
  ```json
  {
    "ip": "10.220.17.122",
    "cmd": "show version",
    "padding": "0a",  // 控制字符
    "user": "admin"
  }
  ```

### 3. 关闭会话
- **URL**: `POST /api/ssh_terminal/close_session`
- **请求体**:
  ```json
  {
    "ip": "10.220.17.122",
    "user": "admin"
  }
  ```

### 4. 查询会话状态
- **URL**: `GET /api/ssh_terminal/session_status?ip=10.220.17.122&user=admin`
- **响应**:
  ```json
  {
    "status": "success",
    "alive": true,
    "total_sessions": 3
  }
  ```

## 控制字符说明

前端发送命令时，`padding` 参数用于发送特殊控制字符：

| 十六进制 | 说明 | 用途 |
|---------|------|------|
| `0a` | 回车 (\\n) | 执行命令 |
| `03` | Ctrl+C | 中断命令 |
| `15` | Ctrl+U | 删除行 |
| `18` | Ctrl+X | 删除行 |
| `7f` | 退格 | 删除字符 |
| `09` | Tab | 自动补全 |
| `00` | 无控制字符 | 仅发送命令 |

## 配置说明

确保 `../config/config.py` 中有以下配置：

```python
class Config:
    # SSH 默认凭证
    ssh_username = 'admin'
    ssh_password = 'your_password'
    
    # WebSocket 配置
    websocket_host = '0.0.0.0'
    websocket_port = 8081
```

## 测试方法

### 1. 测试 WebSocket 连接

```bash
curl http://localhost:8081/
```

应返回：
```json
{"status": "ok", "service": "websocket"}
```

### 2. 测试创建会话

```bash
curl -X POST http://localhost:5000/api/ssh_terminal/create_session \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "10.220.17.122",
    "user": "test_user"
  }'
```

### 3. 测试发送命令

```bash
curl -X POST http://localhost:5000/api/ssh_terminal/send_command \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "10.220.17.122",
    "cmd": "show version",
    "padding": "0a",
    "user": "test_user"
  }'
```

## 故障排查

### 问题 1: WebSocket 连接失败
- 检查 WebSocket 服务器是否启动：`netstat -tuln | grep 8081`
- 检查防火墙规则
- 确认前端配置的 WebSocket 地址正确

### 问题 2: SSH 连接超时
- 检查网络设备是否可达：`ping 10.220.17.122`
- 验证 SSH 凭证是否正确
- 查看日志：`tail -f logs/app.log`

### 问题 3: 收不到终端输出
- 检查 WebSocket 订阅的频道名是否正确（应为 `user_ip` 格式）
- 查看 WebSocket 日志确认消息是否发送
- 使用浏览器开发者工具检查 WebSocket 消息

## 性能优化建议

1. **连接池管理**：限制单个用户的最大会话数
2. **超时清理**：自动清理超过 30 分钟无活动的会话
3. **缓存历史输出**：在后端缓存最近的输出，支持断线重连后恢复
4. **压缩传输**：对大量输出数据启用压缩

## 安全建议

1. **身份验证**：在 API 层添加用户身份验证
2. **权限控制**：验证用户是否有权限访问目标设备
3. **审计日志**：记录所有 SSH 会话和执行的命令
4. **加密传输**：使用 HTTPS 和 WSS（WebSocket Secure）
5. **会话隔离**：确保用户只能访问自己的会话

## 下一步

1. 在主应用中集成上述代码
2. 修改前端 API 调用地址
3. 测试基本功能
4. 添加错误处理和用户体验优化
5. 部署到生产环境

---

如有问题，请查看日志文件或联系开发团队。
