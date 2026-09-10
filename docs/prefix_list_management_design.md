# 地址前缀列表管理设计方案

## 文档信息
- 创建时间: 2026-09-10
- 状态: 设计中
- 版本: v0.1

## 一、背景与需求

### 1.1 什么是地址前缀列表

地址前缀列表（Prefix List）用于路由过滤和流量控制，主要应用于：
- BGP 路由过滤
- OSPF 路由重分发
- 路由策略匹配条件

**示例配置：**
```
H3C:
ip ip-prefix idc-networks index 10 permit 172.16.0.0 12 greater-equal 16 less-equal 24
ip ip-prefix idc-networks index 20 permit 10.0.0.0 8 greater-equal 16 less-equal 24

Huawei:
ip ip-prefix idc-networks index 10 permit 172.16.0.0 12 greater-equal 16 less-equal 24
ip ip-prefix idc-networks index 20 permit 10.0.0.0 8 greater-equal 16 less-equal 24

Cisco:
ip prefix-list idc-networks seq 10 permit 172.16.0.0/12 ge 16 le 24
ip prefix-list idc-networks seq 20 permit 10.0.0.0/8 ge 16 le 24
```

### 1.2 核心需求

1. **模板化管理**：相同的前缀列表可应用到多个设备
2. **版本管理**：跟踪前缀列表的变更历史，支持回滚
3. **期望状态管理**：明确定义每个设备应该部署哪个版本
4. **实际状态跟踪**：记录设备当前部署的版本
5. **状态对比**：自动对比期望与实际，识别差异
6. **部署管理**：支持批量部署、灰度发布

### 1.3 关键概念

**期望状态（Desired State）**
- 设备**应该**部署什么策略
- 设备**应该**部署哪个版本
- 是否启用该策略

**实际状态（Actual State）**
- 设备**当前**部署了什么版本
- 配置是否与模板一致
- 最后同步时间

**状态对比结果**
- `not_assigned`: 未分配（设备不需要此策略）
- `pending`: 待部署（已分配但未部署）
- `synced`: 已同步（期望=实际，且配置一致）
- `outdated`: 版本过旧（实际版本 < 期望版本）
- `drift`: 配置漂移（版本相同但配置不一致）
- `failed`: 部署失败

## 二、数据模型设计

### 2.1 标准化模型

```json
{
  "name": "idc-networks",
  "description": "IDC 网段前缀列表",
  "vendor_type": "h3c",
  "entries": [
    {
      "seq": 10,
      "action": "permit",
      "prefix": "172.16.0.0/12",
      "ge": 16,
      "le": 24,
      "description": "IDC A 段"
    },
    {
      "seq": 20,
      "action": "permit",
      "prefix": "10.0.0.0/8",
      "ge": 16,
      "le": 24,
      "description": "IDC B 段"
    },
    {
      "seq": 100,
      "action": "deny",
      "prefix": "0.0.0.0/0",
      "le": 32,
      "description": "拒绝其他所有"
    }
  ]
}
```

### 2.2 字段说明

- `seq`: 序列号，决定匹配顺序
- `action`: permit（允许）或 deny（拒绝）
- `prefix`: 网络前缀，CIDR 格式
- `ge`: greater-equal，前缀长度下限（可选）
- `le`: less-equal，前缀长度上限（可选）

**匹配规则：**
- `172.16.0.0/12 ge 16 le 24` 表示：
  - 匹配 172.16.0.0/12 范围内的地址
  - 且前缀长度在 16-24 之间
  - 即匹配 172.16.0.0/16 到 172.31.255.0/24

## 三、数据库设计

### 3.1 核心表结构

#### 3.1.1 前缀列表模板表

```sql
CREATE TABLE prefix_list_templates (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    vendor_type VARCHAR(20),
    
    -- 标准化配置（完整 JSON）
    normalized_config JSON NOT NULL,
    
    -- 厂商特定配置（多厂商支持）
    vendor_configs JSON,
    
    -- 当前版本号
    current_version INT DEFAULT 1,
    
    -- 状态
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    
    -- 元信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    updated_by VARCHAR(50),
    
    UNIQUE KEY uk_name (name),
    INDEX idx_vendor (vendor_type),
    INDEX idx_active (is_active, is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址前缀列表模板';
```

#### 3.1.2 前缀列表条目表（便于查询）

```sql
CREATE TABLE prefix_list_entries (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    prefix_list_id BIGINT NOT NULL,
    template_version INT NOT NULL,
    
    sequence INT NOT NULL,
    action ENUM('permit', 'deny') NOT NULL,
    prefix VARCHAR(50) NOT NULL,
    prefix_len INT NOT NULL,
    ge INT,
    le INT,
    description VARCHAR(255),
    
    FOREIGN KEY (prefix_list_id) REFERENCES prefix_list_templates(id) ON DELETE CASCADE,
    INDEX idx_template_version (prefix_list_id, template_version),
    INDEX idx_prefix (prefix),
    INDEX idx_sequence (prefix_list_id, template_version, sequence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='前缀列表条目';
```

#### 3.1.3 版本历史表

```sql
CREATE TABLE prefix_list_versions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    prefix_list_id BIGINT NOT NULL,
    version INT NOT NULL,
    
    -- 版本快照（完整配置）
    config_snapshot JSON NOT NULL,
    
    -- 变更信息
    change_type ENUM('create', 'update', 'delete') NOT NULL,
    change_summary VARCHAR(500),
    diff JSON,
    
    -- 元信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    
    FOREIGN KEY (prefix_list_id) REFERENCES prefix_list_templates(id) ON DELETE CASCADE,
    UNIQUE KEY uk_template_version (prefix_list_id, version),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='前缀列表版本历史';
```

#### 3.1.4 设备策略绑定表（核心：期望状态 + 实际状态）

```sql
CREATE TABLE device_prefix_list_bindings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    device_id BIGINT NOT NULL,
    prefix_list_id BIGINT NOT NULL,
    
    -- ========== 期望状态 ==========
    target_version INT,                -- 目标版本（应该部署的版本）
    enabled BOOLEAN DEFAULT TRUE,       -- 是否启用（FALSE = 计划移除）
    
    -- ========== 实际状态 ==========
    deployed_version INT,              -- 已部署的版本（NULL = 从未部署）
    last_deploy_at TIMESTAMP,          -- 上次部署时间
    deploy_status ENUM('success', 'failed', 'in_progress'),
    deploy_error TEXT,                 -- 部署失败原因
    
    -- ========== 状态对比 ==========
    sync_status ENUM(
        'not_assigned',   -- 未分配（target_version IS NULL）
        'pending',        -- 待部署（target != deployed 或 deployed IS NULL）
        'synced',         -- 已同步（target == deployed 且配置一致）
        'outdated',       -- 版本过旧（deployed < target）
        'drift',          -- 配置漂移（版本相同但配置不一致）
        'failed'          -- 部署失败
    ) DEFAULT 'pending',
    
    config_diff JSON,                  -- 配置差异详情
    last_check_at TIMESTAMP,           -- 上次检查时间
    
    -- ========== 元信息 ==========
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    assigned_by VARCHAR(50),           -- 分配人
    assigned_at TIMESTAMP,             -- 分配时间
    
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
    FOREIGN KEY (prefix_list_id) REFERENCES prefix_list_templates(id) ON DELETE RESTRICT,
    UNIQUE KEY uk_device_prefix (device_id, prefix_list_id),
    INDEX idx_sync_status (sync_status),
    INDEX idx_target_version (target_version),
    INDEX idx_deployed_version (deployed_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备前缀列表绑定（期望+实际状态）';
```

#### 3.1.5 部署任务表

```sql
CREATE TABLE prefix_list_deploy_tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_name VARCHAR(100),
    description TEXT,
    
    -- 部署范围
    prefix_list_id BIGINT NOT NULL,
    target_version INT NOT NULL,
    device_ids JSON,                   -- 目标设备 ID 列表
    
    -- 部署策略
    deploy_type ENUM('full', 'incremental', 'canary') DEFAULT 'full',
    canary_ratio DECIMAL(5,2),         -- 灰度比例（0.10 = 10%）
    
    -- 任务状态
    status ENUM('pending', 'running', 'paused', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
    total_devices INT,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    
    -- 时间信息
    scheduled_at TIMESTAMP,            -- 计划执行时间
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- 执行信息
    executed_by VARCHAR(50),
    error_message TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (prefix_list_id) REFERENCES prefix_list_templates(id),
    INDEX idx_status (status),
    INDEX idx_scheduled_at (scheduled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='前缀列表部署任务';
```

#### 3.1.6 部署历史表

```sql
CREATE TABLE prefix_list_deploy_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT,
    device_id BIGINT NOT NULL,
    prefix_list_id BIGINT NOT NULL,
    
    -- 部署信息
    from_version INT,                  -- 原版本
    to_version INT NOT NULL,           -- 目标版本
    
    -- 执行结果
    status ENUM('success', 'failed', 'skipped') NOT NULL,
    error_message TEXT,
    config_before TEXT,                -- 部署前配置
    config_after TEXT,                 -- 部署后配置
    
    -- 时间信息
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_by VARCHAR(50),
    
    FOREIGN KEY (task_id) REFERENCES prefix_list_deploy_tasks(id) ON DELETE SET NULL,
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (prefix_list_id) REFERENCES prefix_list_templates(id),
    INDEX idx_device (device_id),
    INDEX idx_prefix_list (prefix_list_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='前缀列表部署历史';
```

### 3.2 表关系图

```
prefix_list_templates (模板)
    ├─── prefix_list_entries (条目)
    ├─── prefix_list_versions (版本历史)
    ├─── device_prefix_list_bindings (设备绑定)
    │        ├─ target_version (期望状态)
    │        └─ deployed_version (实际状态)
    ├─── prefix_list_deploy_tasks (部署任务)
    └─── prefix_list_deploy_history (部署历史)
```

## 四、核心业务流程

### 4.1 分配策略到设备（设置期望状态）

```python
def assign_prefix_list_to_devices(prefix_list_id, device_ids, target_version=None):
    """
    将前缀列表分配给设备（设置期望状态）
    
    Args:
        prefix_list_id: 前缀列表 ID
        device_ids: 设备 ID 列表
        target_version: 目标版本（None = 使用当前最新版本）
    """
    # 获取目标版本
    if target_version is None:
        prefix_list = db.query_one(
            "SELECT current_version FROM prefix_list_templates WHERE id = ?",
            [prefix_list_id]
        )
        target_version = prefix_list['current_version']
    
    # 为每个设备创建或更新绑定记录
    for device_id in device_ids:
        db.execute(
            """
            INSERT INTO device_prefix_list_bindings 
            (device_id, prefix_list_id, target_version, enabled, sync_status, assigned_by, assigned_at)
            VALUES (?, ?, ?, TRUE, 'pending', ?, NOW())
            ON DUPLICATE KEY UPDATE
                target_version = VALUES(target_version),
                enabled = TRUE,
                sync_status = 'pending',
                assigned_by = VALUES(assigned_by),
                assigned_at = NOW()
            """,
            [device_id, prefix_list_id, target_version, current_user()]
        )
    
    return {
        'prefix_list_id': prefix_list_id,
        'target_version': target_version,
        'device_count': len(device_ids)
    }
```

### 4.2 更新模板版本（触发状态变化）

```python
def update_prefix_list(prefix_list_id, new_config, change_summary):
    """
    更新前缀列表（创建新版本）
    """
    with db.transaction():
        # 1. 获取当前版本
        current = db.query_one(
            "SELECT current_version, normalized_config FROM prefix_list_templates WHERE id = ?",
            [prefix_list_id]
        )
        new_version = current['current_version'] + 1
        
        # 2. 计算差异
        diff = compute_diff(
            json.loads(current['normalized_config']),
            new_config
        )
        
        # 3. 更新模板主表
        db.execute(
            """
            UPDATE prefix_list_templates
            SET normalized_config = ?,
                current_version = ?,
                updated_at = NOW(),
                updated_by = ?
            WHERE id = ?
            """,
            [json.dumps(new_config), new_version, current_user(), prefix_list_id]
        )
        
        # 4. 保存版本历史
        db.insert('prefix_list_versions', {
            'prefix_list_id': prefix_list_id,
            'version': new_version,
            'config_snapshot': json.dumps(new_config),
            'change_type': 'update',
            'change_summary': change_summary,
            'diff': json.dumps(diff),
            'created_by': current_user()
        })
        
        # 5. 更新条目表（便于查询）
        _update_entries_table(prefix_list_id, new_version, new_config['entries'])
        
        # 6. 更新所有绑定设备的状态
        # 如果设备的 target_version 指向旧版本，不自动更新
        # 只标记已同步设备为 outdated（如果 target_version = current_version）
        db.execute(
            """
            UPDATE device_prefix_list_bindings
            SET sync_status = CASE
                WHEN target_version = ? THEN 'outdated'  -- 跟踪最新版本的设备
                ELSE sync_status
            END
            WHERE prefix_list_id = ?
            """,
            [current['current_version'], prefix_list_id]
        )
    
    return {
        'prefix_list_id': prefix_list_id,
        'version': new_version,
        'affected_devices': get_affected_device_count(prefix_list_id)
    }
```

### 4.3 升级设备目标版本

```python
def upgrade_device_target_version(prefix_list_id, device_ids=None, target_version=None):
    """
    升级设备的目标版本（修改期望状态）
    
    Args:
        device_ids: 设备 ID 列表（None = 所有已绑定设备）
        target_version: 目标版本（None = 最新版本）
    """
    # 获取最新版本
    if target_version is None:
        prefix_list = db.query_one(
            "SELECT current_version FROM prefix_list_templates WHERE id = ?",
            [prefix_list_id]
        )
        target_version = prefix_list['current_version']
    
    # 构建 WHERE 条件
    where_clause = "prefix_list_id = ?"
    params = [target_version, prefix_list_id]
    
    if device_ids:
        placeholders = ','.join(['?'] * len(device_ids))
        where_clause += f" AND device_id IN ({placeholders})"
        params.extend(device_ids)
    
    # 更新目标版本
    db.execute(
        f"""
        UPDATE device_prefix_list_bindings
        SET target_version = ?,
            sync_status = CASE
                WHEN deployed_version IS NULL THEN 'pending'
                WHEN deployed_version < ? THEN 'outdated'
                WHEN deployed_version = ? THEN 'synced'
                ELSE sync_status
            END,
            updated_at = NOW()
        WHERE {where_clause}
        """,
        params
    )
```

### 4.4 检查配置差异（对比实际状态）

```python
def check_device_config_drift(device_id, prefix_list_id):
    """
    检查设备配置是否与模板一致
    """
    # 1. 获取绑定信息
    binding = db.query_one(
        """
        SELECT deployed_version, target_version
        FROM device_prefix_list_bindings
        WHERE device_id = ? AND prefix_list_id = ?
        """,
        [device_id, prefix_list_id]
    )
    
    if not binding or not binding['deployed_version']:
        return {'status': 'not_deployed'}
    
    # 2. 获取设备当前配置（从最新备份）
    device_config = parse_device_backup(device_id, prefix_list_id)
    
    # 3. 获取模板配置
    template_version = db.query_one(
        """
        SELECT config_snapshot
        FROM prefix_list_versions
        WHERE prefix_list_id = ? AND version = ?
        """,
        [prefix_list_id, binding['deployed_version']]
    )
    template_config = json.loads(template_version['config_snapshot'])
    
    # 4. 对比差异
    diff = compute_config_diff(device_config, template_config)
    
    # 5. 确定状态
    if binding['deployed_version'] < binding['target_version']:
        status = 'outdated'
    elif diff['has_changes']:
        status = 'drift'
    else:
        status = 'synced'
    
    # 6. 更新状态
    db.execute(
        """
        UPDATE device_prefix_list_bindings
        SET sync_status = ?,
            config_diff = ?,
            last_check_at = NOW()
        WHERE device_id = ? AND prefix_list_id = ?
        """,
        [status, json.dumps(diff), device_id, prefix_list_id]
    )
    
    return {
        'status': status,
        'deployed_version': binding['deployed_version'],
        'target_version': binding['target_version'],
        'diff': diff
    }
```

### 4.5 创建部署任务

```python
def create_deploy_task(prefix_list_id, device_ids=None, deploy_type='full'):
    """
    创建部署任务
    
    Args:
        device_ids: 指定设备列表（None = 所有待部署设备）
        deploy_type: full（全量）| incremental（增量）| canary（灰度）
    """
    with db.transaction():
        # 1. 确定目标设备
        if device_ids is None:
            # 查询所有需要部署的设备
            devices = db.query(
                """
                SELECT device_id, target_version
                FROM device_prefix_list_bindings
                WHERE prefix_list_id = ?
                  AND enabled = TRUE
                  AND sync_status IN ('pending', 'outdated', 'drift')
                """,
                [prefix_list_id]
            )
            device_ids = [d['device_id'] for d in devices]
        
        if not device_ids:
            raise ValueError("没有需要部署的设备")
        
        # 2. 获取目标版本（取最大值）
        target_version = db.query_one(
            """
            SELECT MAX(target_version) as max_version
            FROM device_prefix_list_bindings
            WHERE prefix_list_id = ? AND device_id IN ({})
            """.format(','.join(['?'] * len(device_ids))),
            [prefix_list_id] + device_ids
        )['max_version']
        
        # 3. 创建任务
        task_id = db.insert('prefix_list_deploy_tasks', {
            'task_name': f"部署前缀列表 v{target_version}",
            'prefix_list_id': prefix_list_id,
            'target_version': target_version,
            'device_ids': json.dumps(device_ids),
            'deploy_type': deploy_type,
            'total_devices': len(device_ids),
            'status': 'pending',
            'executed_by': current_user()
        })
        
        return {
            'task_id': task_id,
            'device_count': len(device_ids),
            'target_version': target_version
        }
```

### 4.6 执行部署

```python
def execute_deploy_task(task_id):
    """
    执行部署任务
    """
    # 1. 获取任务信息
    task = db.get('prefix_list_deploy_tasks', task_id)
    device_ids = json.loads(task['device_ids'])
    
    # 2. 更新任务状态
    db.execute(
        "UPDATE prefix_list_deploy_tasks SET status = 'running', started_at = NOW() WHERE id = ?",
        [task_id]
    )
    
    success_count = 0
    failed_count = 0
    
    # 3. 逐个设备部署
    for device_id in device_ids:
        try:
            # 获取设备绑定信息
            binding = db.query_one(
                """
                SELECT target_version, deployed_version
                FROM device_prefix_list_bindings
                WHERE device_id = ? AND prefix_list_id = ?
                """,
                [device_id, task['prefix_list_id']]
            )
            
            # 获取目标版本配置
            version_config = db.query_one(
                """
                SELECT config_snapshot
                FROM prefix_list_versions
                WHERE prefix_list_id = ? AND version = ?
                """,
                [task['prefix_list_id'], binding['target_version']]
            )
            
            # 渲染配置
            device = db.get('devices', device_id)
            rendered_config = render_prefix_list(
                json.loads(version_config['config_snapshot']),
                device['vendor_type']
            )
            
            # 部署到设备（实际执行）
            deploy_result = deploy_config_to_device(device_id, rendered_config)
            
            if deploy_result['success']:
                # 更新绑定状态
                db.execute(
                    """
                    UPDATE device_prefix_list_bindings
                    SET deployed_version = ?,
                        last_deploy_at = NOW(),
                        deploy_status = 'success',
                        sync_status = 'synced',
                        deploy_error = NULL
                    WHERE device_id = ? AND prefix_list_id = ?
                    """,
                    [binding['target_version'], device_id, task['prefix_list_id']]
                )
                
                success_count += 1
                status = 'success'
                error_msg = None
            else:
                status = 'failed'
                error_msg = deploy_result['error']
                failed_count += 1
                
                # 标记失败
                db.execute(
                    """
                    UPDATE device_prefix_list_bindings
                    SET deploy_status = 'failed',
                        sync_status = 'failed',
                        deploy_error = ?
                    WHERE device_id = ? AND prefix_list_id = ?
                    """,
                    [error_msg, device_id, task['prefix_list_id']]
                )
            
            # 记录部署历史
            db.insert('prefix_list_deploy_history', {
                'task_id': task_id,
                'device_id': device_id,
                'prefix_list_id': task['prefix_list_id'],
                'from_version': binding['deployed_version'],
                'to_version': binding['target_version'],
                'status': status,
                'error_message': error_msg,
                'completed_at': 'NOW()',
                'executed_by': current_user()
            })
            
        except Exception as e:
            failed_count += 1
            logger.error(f"部署失败 device_id={device_id}: {e}")
    
    # 4. 更新任务状态
    final_status = 'completed' if failed_count == 0 else 'failed'
    db.execute(
        """
        UPDATE prefix_list_deploy_tasks
        SET status = ?,
            success_count = ?,
            failed_count = ?,
            completed_at = NOW()
        WHERE id = ?
        """,
        [final_status, success_count, failed_count, task_id]
    )
    
    return {
        'task_id': task_id,
        'success': success_count,
        'failed': failed_count
    }
```

## 五、关键查询示例

### 5.1 查询待部署设备

```sql
-- 查询指定前缀列表的所有待部署设备
SELECT 
    d.id,
    d.hostname,
    d.ip_address,
    b.target_version,
    b.deployed_version,
    b.sync_status,
    b.last_check_at
FROM device_prefix_list_bindings b
JOIN devices d ON b.device_id = d.id
WHERE b.prefix_list_id = ?
  AND b.enabled = TRUE
  AND b.sync_status IN ('pending', 'outdated', 'drift')
ORDER BY d.hostname;
```

### 5.2 查询设备的所有策略状态

```sql
-- 查询单个设备绑定的所有前缀列表及状态
SELECT 
    p.name,
    b.target_version,
    b.deployed_version,
    b.sync_status,
    b.last_deploy_at,
    b.last_check_at,
    CASE 
        WHEN b.deployed_version IS NULL THEN '未部署'
        WHEN b.deployed_version < b.target_version THEN '版本过旧'
        WHEN b.sync_status = 'drift' THEN '配置漂移'
        WHEN b.sync_status = 'synced' THEN '已同步'
        ELSE b.sync_status
    END as status_desc
FROM device_prefix_list_bindings b
JOIN prefix_list_templates p ON b.prefix_list_id = p.id
WHERE b.device_id = ?
  AND b.enabled = TRUE
ORDER BY b.sync_status DESC, p.name;
```

### 5.3 查询模板的部署覆盖情况

```sql
-- 查询前缀列表在各设备上的部署情况
SELECT 
    b.sync_status,
    COUNT(*) as device_count,
    GROUP_CONCAT(d.hostname SEPARATOR ', ') as devices
FROM device_prefix_list_bindings b
JOIN devices d ON b.device_id = d.id
WHERE b.prefix_list_id = ?
  AND b.enabled = TRUE
GROUP BY b.sync_status
ORDER BY 
    FIELD(b.sync_status, 'synced', 'pending', 'outdated', 'drift', 'failed');
```

### 5.4 查询版本差异影响

```sql
-- 查询升级到新版本会影响多少设备
SELECT 
    COUNT(*) as affected_devices,
    SUM(CASE WHEN b.sync_status = 'synced' THEN 1 ELSE 0 END) as currently_synced,
    SUM(CASE WHEN b.sync_status != 'synced' THEN 1 ELSE 0 END) as need_deploy
FROM device_prefix_list_bindings b
WHERE b.prefix_list_id = ?
  AND b.enabled = TRUE
  AND b.target_version < ?;  -- 小于新版本号
```

## 六、前端界面设计

### 6.1 前缀列表管理页面

```
┌────────────────────────────────────────────────────────┐
│  地址前缀列表管理              [+ 新建]  [导入]  [导出] │
├────────────────────────────────────────────────────────┤
│ 名称              当前版本  设备数  同步状态            │
│ idc-networks     v3        25     20✓ 3⚠ 2✗          │
│ partner-routes   v5        12     12✓ 0⚠ 0✗          │
│ bgp-filters      v2         8      6✓ 2⚠ 0✗          │
└────────────────────────────────────────────────────────┘

点击查看详情：
┌────────────────────────────────────────────────────────┐
│ idc-networks (v3)                        [编辑] [部署] │
├────────────────────────────────────────────────────────┤
│ 版本历史:                                              │
│  v3 (当前) - 2026-09-10 添加 IDC C 段                 │
│  v2 - 2026-09-01 修改 ge/le 参数                      │
│  v1 - 2026-08-15 初始版本                             │
├────────────────────────────────────────────────────────┤
│ 条目列表:                                              │
│  10: permit 172.16.0.0/12 ge 16 le 24 (IDC A 段)      │
│  20: permit 10.0.0.0/8 ge 16 le 24 (IDC B 段)         │
│  30: permit 192.168.0.0/16 ge 24 le 28 (IDC C 段) 🆕  │
│  100: deny 0.0.0.0/0 le 32 (拒绝其他)                │
├────────────────────────────────────────────────────────┤
│ 设备部署状态:                          [查看全部]      │
│  ✓ 已同步 (20)   ⚠ 待更新 (3)   ✗ 失败 (2)          │
│                                                        │
│  设备                期望   实际   状态      操作       │
│  bbs1_corp_bj_m01  v3     v3    已同步    [检查]     │
│  bbs2_corp_sh_m01  v3     v2    版本过旧  [部署]     │
│  core_idc_bj_01    v3     v3    配置漂移  [修复]     │
│  edge_partner_01   v3     -     待部署    [部署]     │
└────────────────────────────────────────────────────────┘
```

### 6.2 设备视图

```
┌────────────────────────────────────────────────────────┐
│ 设备: bbs1_corp_bj_m01                                 │
├────────────────────────────────────────────────────────┤
│ 绑定的前缀列表:                                        │
│                                                        │
│ 名称              期望版本  实际版本  状态    操作      │
│ idc-networks     v3       v3       ✓已同步  [检查]   │
│ partner-routes   v5       v4       ⚠过旧    [部署]   │
│ bgp-filters      v2       v2       ⚠漂移    [修复]   │
│                                                        │
│ [批量检查]  [批量部署]  [+ 绑定策略]                   │
└────────────────────────────────────────────────────────┘
```

### 6.3 部署任务页面

```
┌────────────────────────────────────────────────────────┐
│ 部署任务: idc-networks v3                              │
├────────────────────────────────────────────────────────┤
│ 目标设备: 5 台                                         │
│  • bbs2_corp_sh_m01 (v2 → v3)                         │
│  • edge_partner_01 (未部署 → v3)                      │
│  • core_idc_gz_01 (v2 → v3)                           │
│  ...                                                   │
├────────────────────────────────────────────────────────┤
│ 部署策略:                                              │
│  ○ 全量部署（同时部署到所有设备）                      │
│  ● 顺序部署（逐个部署，失败后停止）                    │
│  ○ 灰度部署（先部署 [20]% 设备验证）                  │
├────────────────────────────────────────────────────────┤
│ 计划执行时间: ● 立即执行  ○ 定时执行 [____]           │
│                                                        │
│ [开始部署]  [取消]                                     │
└────────────────────────────────────────────────────────┘

执行中:
┌────────────────────────────────────────────────────────┐
│ 部署进度: 3/5 (60%)  [■■■■■■□□□□] 2 成功, 1 失败      │
├────────────────────────────────────────────────────────┤
│ bbs2_corp_sh_m01     ✓ 部署成功  (2.3s)               │
│ edge_partner_01      ✓ 部署成功  (1.8s)               │
│ core_idc_gz_01       ✗ 部署失败  无法连接设备          │
│ core_idc_sh_01       ⏳ 部署中...                     │
│ edge_idc_bj_02       ⏸ 等待中                         │
│                                                        │
│ [暂停]  [取消]  [跳过失败继续]                         │
└────────────────────────────────────────────────────────┘
```

## 七、API 设计

### 7.1 核心 API 端点

```python
# 前缀列表管理
POST   /api/prefix-lists                    # 创建前缀列表
GET    /api/prefix-lists                    # 列表查询
GET    /api/prefix-lists/:id                # 获取详情
PUT    /api/prefix-lists/:id                # 更新（创建新版本）
DELETE /api/prefix-lists/:id                # 删除

# 版本管理
GET    /api/prefix-lists/:id/versions       # 版本历史
GET    /api/prefix-lists/:id/versions/:ver  # 获取指定版本
POST   /api/prefix-lists/:id/rollback       # 回滚到指定版本

# 设备绑定（期望状态管理）
POST   /api/prefix-lists/:id/assign         # 分配给设备
DELETE /api/prefix-lists/:id/unassign       # 取消分配
PUT    /api/prefix-lists/:id/upgrade        # 升级设备目标版本
GET    /api/prefix-lists/:id/bindings       # 查询绑定设备

# 状态检查
POST   /api/devices/:id/check-drift         # 检查配置漂移
GET    /api/devices/:id/prefix-lists        # 查询设备的所有前缀列表

# 部署管理
POST   /api/deploy-tasks                    # 创建部署任务
GET    /api/deploy-tasks                    # 任务列表
GET    /api/deploy-tasks/:id                # 任务详情
POST   /api/deploy-tasks/:id/execute        # 执行任务
POST   /api/deploy-tasks/:id/pause          # 暂停任务
POST   /api/deploy-tasks/:id/cancel         # 取消任务
GET    /api/deploy-tasks/:id/history        # 部署历史
```

### 7.2 请求/响应示例

**分配前缀列表到设备：**
```json
POST /api/prefix-lists/123/assign
{
  "device_ids": [1, 2, 3],
  "target_version": 3  // 可选，默认为最新版本
}

Response:
{
  "success": true,
  "data": {
    "prefix_list_id": 123,
    "target_version": 3,
    "device_count": 3,
    "status": "pending"
  }
}
```

**创建部署任务：**
```json
POST /api/deploy-tasks
{
  "prefix_list_id": 123,
  "device_ids": [1, 2, 3],  // 可选，默认所有待部署设备
  "deploy_type": "incremental",
  "scheduled_at": null  // null = 立即执行
}

Response:
{
  "success": true,
  "data": {
    "task_id": 456,
    "device_count": 3,
    "target_version": 3,
    "status": "pending"
  }
}
```

## 八、总结

### 8.1 核心设计要点

1. **期望状态与实际状态分离**
   - `target_version`: 设备应该部署的版本
   - `deployed_version`: 设备实际部署的版本
   - `sync_status`: 对比结果

2. **版本管理**
   - 每次修改创建新版本
   - 完整的版本历史和快照
   - 支持回滚

3. **灵活的部署控制**
   - 可以选择性升级部分设备
   - 支持灰度发布
   - 部署任务和历史记录

4. **状态自动更新**
   - 模板更新时自动标记相关设备
   - 部署完成后自动更新状态
   - 配置检查后更新 drift 状态

### 8.2 与 ACL 管理的区别

前缀列表比 ACL 简单：
- ✓ 无对象组引用
- ✓ 条目结构固定
- ✓ 更少的厂商差异
- ✓ 适合作为起点验证架构

后续 ACL 管理可以复用这套架构，增加对象组支持即可。

---

*文档维护：设计变更时更新此文档*
