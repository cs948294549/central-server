# 定时任务系统使用说明

## 概述

Central-Server 实现了基于 APScheduler 的定时任务系统，支持从 YAML 配置文件动态加载和管理任务。

## 目录结构

```
central-server/
├── tasks/                          # 任务模块目录
│   ├── __init__.py
│   ├── task_manager.py            # 任务管理器
│   └── update_ipam_address.py     # IPAM地址更新任务
├── config/
│   └── task_config.yaml           # 任务配置文件
└── main.py                        # 主程序入口
```

## 配置文件说明

任务配置文件位于 `config/task_config.yaml`，支持两种任务类型：

### 1. Cron 任务

使用标准的 5 字段 cron 表达式：`分 时 日 月 周`

```yaml
tasks:
  - id: update_ipam_address
    type: cron
    module: tasks.update_ipam_address
    function: run
    schedule: "0 2 * * *"  # 每天凌晨2点执行
    description: "从采集数据更新IPAM地址表"
    enabled: true
```

**常用 Cron 表达式示例：**
- `"0 2 * * *"` - 每天凌晨2点执行
- `"*/30 * * * *"` - 每30分钟执行一次
- `"0 */2 * * *"` - 每2小时执行一次
- `"0 0 * * 0"` - 每周日凌晨执行
- `"0 0 1 * *"` - 每月1号凌晨执行

### 2. Interval 任务

按固定时间间隔执行：

```yaml
tasks:
  - id: example_interval_task
    type: interval
    module: tasks.example_task
    function: run
    schedule:
      hours: 0
      minutes: 30
      seconds: 0
    description: "示例间隔任务 - 每30分钟执行"
    enabled: true
```

## 创建新任务

### 步骤1: 编写任务脚本

在 `tasks/` 目录下创建任务文件，例如 `tasks/my_task.py`：

```python
"""
我的定时任务
"""
import logging
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

# 任务配置
TASK_CONFIG = {
    "enabled": True,
}

def run():
    """
    任务主执行函数
    """
    if not TASK_CONFIG["enabled"]:
        logger.info("任务已禁用")
        return

    logger.info("开始执行任务...")
    
    try:
        # 任务逻辑
        pass
        
        logger.info("任务执行完成")
    except Exception as e:
        logger.error(f"任务执行失败: {e}")
        raise

if __name__ == "__main__":
    # 支持单独运行
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    run()
```

### 步骤2: 添加任务配置

在 `config/task_config.yaml` 中添加任务配置：

```yaml
tasks:
  - id: my_task
    type: cron
    module: tasks.my_task
    function: run
    schedule: "0 3 * * *"
    description: "我的定时任务描述"
    enabled: true
```

### 步骤3: 重启服务

重启 Central-Server 服务，任务会自动注册并按计划执行。

## 任务管理

### 启用/禁用任务

修改配置文件中的 `enabled` 字段：

```yaml
enabled: true   # 启用任务
enabled: false  # 禁用任务
```

修改后需要重启服务。

### 查看任务状态

启动服务时会在日志中显示所有已注册的任务：

```
✓ 已注册 1 个定时任务:
  - update_ipam_address (cron) - 下次运行: 2024-08-20 02:00:00
```

### 手动执行任务

任务脚本支持单独运行：

```bash
# 进入项目目录
cd /Users/weidian/netops/projects/central-server

# 手动执行任务
python3 tasks/update_ipam_address.py
```

## 现有任务

### 1. IPAM地址更新任务

- **任务ID**: `update_ipam_address`
- **执行时间**: 每天凌晨2点
- **功能**: 从采集数据库读取网关和ARP信息，更新到IPAM地址表
- **脚本**: `tasks/update_ipam_address.py`

**功能说明：**
1. 从 `gates` 表读取IPv4网关信息
2. 从 `arps` 表读取ARP信息
3. 过滤无效数据（无效MAC、重复网关等）
4. 批量写入IPAM地址表 (`ipam_ipaddr`)

## 注意事项

1. **模块路径**: 配置文件中的 `module` 字段必须是有效的 Python 模块路径
2. **函数名称**: `function` 字段指定的函数必须存在且无参数
3. **日志记录**: 任务应使用 logging 模块记录执行状态
4. **异常处理**: 任务应妥善处理异常，避免影响其他任务
5. **数据库连接**: 任务中的数据库操作应使用项目统一的数据库类

## 故障排查

### 任务未执行

1. 检查配置文件中 `enabled` 是否为 `true`
2. 检查日志确认任务是否成功注册
3. 检查 cron 表达式格式是否正确
4. 检查模块路径和函数名是否正确

### 任务执行失败

1. 查看日志文件 `logs/scheduler.log`
2. 手动运行任务脚本进行调试
3. 检查数据库连接是否正常
4. 检查任务依赖的数据是否存在

## 参考

本任务系统参照 collector 项目实现，详细的 APScheduler 使用说明请参考：
https://apscheduler.readthedocs.io/
