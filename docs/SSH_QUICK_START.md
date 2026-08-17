# SSH 终端功能 - 快速集成指南

## 架构概述

```
前端 (xterm.js)
    │
    ├─→ HTTP API (8080) ────→ websocket_ssh_bp ────→ InteractiveSSHManager
    │                              │                        │
    │                              │                   SSH Session
    │                              │                        │
    │                              ↓                        ↓
    │                         send_to_websocket      SSH 输出数据
    │                              │                        │
    │                              └────────────────────────┘
    │                                     │
    └─← WebSocket (8081) ←───── /send_msg ←─────────────────┘
         订阅 session_id
```

## 核心流程

1. **前端发送命令** → API (8080端口) `/api/ssh/send_command`
2. **SSH Manager** → 通过 SSH 连接发送命令到设备
3. **设备返回输出** → SSH Session 接收数据
4. **调用回调函数** → `send_to_websocket(session_id, data)`
5. **发送到 WebSocket** → POST `http://localhost:8081/send_msg`
   ```json
   {
     "target": "admin_10.220.17.122",  // session_id
     "msg": "设备输出内容..."           // SSH 输出
   }
   ```
6. **前端接收** → 订阅 `admin_10.220.17.122` 频道，实时显示输出

## 已创建的文件

1. ✅ `function_ssh/interactive_ssh.py` - SSH 会话管理核心
2. ✅ `api/websocket_ssh_bp.py` - Flask 蓝图，提供 HTTP API

## 集成步骤

### 1. 在 `main.py` 中添加导入

```python
from function_ssh.interactive_ssh import InteractiveSSHManager
from api.websocket_ssh_bp import websocket_ssh_bp, init_websocket_ssh, send_to_websocket
```

### 2. 在 `main()` 函数中初始化（WebSocket 服务器启动后，Flask 应用创建后）

```python
def main():
    # ... 启动 WebSocket 服务器 ...
    
    websocket_server = None
    if Config.websocket_enable:
        websocket_server = WebSocketServer(
            host=Config.websocket_ip,
            port=Config.websocket_port
        )
        websocket_server.start()
        logger.info(f"✓ WebSocket 服务器已启动")
    
    # ... 其他服务 ...
    
    # 创建 Flask 应用
    app = create_app()
    
    # ========== 集成 SSH 终端功能 ==========
    if websocket_server:
        try:
            # 1. 创建 SSH 会话管理器
            ssh_manager = InteractiveSSHManager(output_sender=send_to_websocket)
            
            # 2. WebSocket 服务器地址
            ws_url = f"http://{Config.websocket_ip}:{Config.websocket_port}"
            
            # 3. 初始化蓝图
            init_websocket_ssh(ssh_manager, ws_url)
            
            # 4. 注册蓝图
            app.register_blueprint(websocket_ssh_bp)
            
            logger.info(f"✓ SSH 终端功能已启用")
        except Exception as e:
            logger.error(f"✗ SSH 终端功能启动失败: {str(e)}")
    # ======================================
    
    # 运行 Flask 应用
    app.run(host=Config.service_ip, port=Config.service_port, ...)
```

## API 接口

所有接口在主应用端口 (8080) 上，路径前缀：`/api/ssh`

### 1. 创建 SSH 会话（可选，首次发送命令时自动创建）
```
POST /api/ssh/create_session

请求体:
{
  "ip": "10.220.17.122",
  "user": "admin"
}

响应:
{
  "status": "success",
  "session_id": "admin_10.220.17.122"
}
```

### 2. 发送命令
```
POST /api/ssh/send_command

请求体:
{
  "ip": "10.220.17.122",
  "user": "admin",
  "cmd": "show version",
  "padding": "0a"  // 回车
}

响应:
{
  "status": "success",
  "message": "命令已发送"
}
```

### 3. 关闭会话
```
POST /api/ssh/close_session

请求体:
{
  "ip": "10.220.17.122",
  "user": "admin"
}
```

### 4. 查询会话状态
```
GET /api/ssh/session_status?ip=10.220.17.122&user=admin

响应:
{
  "status": "success",
  "alive": true,
  "session_id": "admin_10.220.17.122",
  "total_sessions": 3
}
```

## 前端集成

### 1. 在 `collector_interface.js` 添加 API 方法

```javascript
export default {
  // ... 现有方法 ...
  
  // SSH 终端
  createSSHSession(data, params) {
    return axios.post("/api/ssh/create_session", data, params)
  },
  sendSSH(data, params) {
    return axios.post("/api/ssh/send_command", data, params)
  },
  closeSSHSession(data, params) {
    return axios.post("/api/ssh/close_session", data, params)
  },
}
```

### 2. 在 `xterm_window.vue` 中使用

```javascript
mounted() {
  // 订阅 WebSocket 频道
  let user = this.$store.getters.info.emailPrefix
  this.ssh_session = user + "_" + this.target_ip
  
  this.sockets.subscribe(this.ssh_session, (data) => {
    this.cmd_show = this.cmd_show + data
    this.term.write(data)  // 写入 xterm 终端
  })
},

methods: {
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
      console.log('命令已发送')
    }).catch(error => {
      this.$message({
        type: 'error',
        message: '命令发送失败'
      })
    })
  }
},

beforeDestroy() {
  // 关闭会话
  collector_api.closeSSHSession({
    ip: this.target_ip,
    user: this.$store.getters.info.emailPrefix
  })
  
  this.sockets.unsubscribe(this.ssh_session)
}
```

## 控制字符说明

| padding | 说明 | 用途 |
|---------|------|------|
| `0a` | 回车 | 执行命令 |
| `03` | Ctrl+C | 中断命令 |
| `15` | Ctrl+U | 清除行 |
| `18` | Ctrl+X | 清除行 |
| `7f` | 退格 | 删除字符 |
| `09` | Tab | 自动补全 |
| `00` | 无控制字符 | 仅发送命令文本 |

## 测试方法

### 1. 测试创建会话

```bash
curl -X POST http://localhost:8080/api/ssh/create_session \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "10.220.17.122",
    "user": "test_user"
  }'
```

### 2. 测试发送命令

```bash
curl -X POST http://localhost:8080/api/ssh/send_command \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "10.220.17.122",
    "user": "test_user",
    "cmd": "show version",
    "padding": "0a"
  }'
```

### 3. 测试 WebSocket 接收

使用浏览器控制台或 Socket.IO 客户端：

```javascript
const socket = io('http://localhost:8081')
socket.on('test_user_10.220.17.122', (data) => {
  console.log('收到终端输出:', data)
})
```

## 配置要求

确保 `config.py` 中有：

```python
class Config:
    # WebSocket 服务器
    websocket_enable = True
    websocket_ip = '0.0.0.0'
    websocket_port = 8081
    
    # 主应用服务器
    service_ip = '0.0.0.0'
    service_port = 8080
    
    # SSH 默认凭证
    ssh_username = 'admin'
    ssh_password = 'your_password'
```

## 工作原理

1. **session_id 关联**：`user_ip` 格式（如 `admin_10.220.17.122`）
2. **命令发送**：前端 → 主应用 API (8080) → SSH Manager → 设备
3. **输出推送**：设备 → SSH Session → `send_to_websocket()` → WebSocket Server (8081) → 前端
4. **频道订阅**：前端订阅 `session_id` 频道，实时接收输出

## 故障排查

### 问题：收不到终端输出
- 检查 WebSocket 服务器是否运行：`curl http://localhost:8081/`
- 检查前端是否正确订阅：`session_id` 格式为 `user_ip`
- 查看后端日志：搜索 "消息已发送到 WebSocket"

### 问题：SSH 连接失败
- 检查设备是否可达：`ping 10.220.17.122`
- 验证 SSH 凭证：`ssh admin@10.220.17.122`
- 查看日志：搜索 "SSH 连接失败"

### 问题：蓝图未注册
- 确认在 `create_app()` 之后注册蓝图
- 检查日志是否有 "SSH 终端功能已启用"

## 下一步

1. ✅ 已创建核心文件
2. ⏳ 在 `main.py` 中集成（按上述步骤）
3. ⏳ 前端添加 API 方法
4. ⏳ 测试完整流程
5. ⏳ 部署到生产环境

---

如有问题，请查看日志或联系开发团队。
