# 策略管理通用数据库设计

## 文档信息
- 创建时间: 2026-09-10
- 状态: 设计中
- 版本: v0.1

## 一、设计目标

设计一套通用的策略管理数据表结构，支持：
- ✓ 多种策略类型（地址前缀列表、ACL、路由策略、QoS 策略等）
- ✓ 版本管理（每次修改创建新版本）
- ✓ 设备绑定管理（期望状态 + 实际状态）
- ✓ 部署任务管理
- ✓ 易于扩展新的策略类型

## 二、核心表结构

### 2.1 策略模板主表（通用）

```sql
CREATE TABLE policy_templates (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    
    -- 策略标识
    policy_type VARCHAR(50) NOT NULL,          -- 策略类型: prefix_list, acl, route_policy, qos_policy
    name VARCHAR(100) NOT NULL,                -- 策略名称
    description TEXT,
    
    -- 厂商信息
    vendor_type VARCHAR(20),                   -- h3c, huawei, cisco_nx（NULL = 通用）
    
    -- 配置内容（JSON 格式，结构由 policy_type 决定）
    normalized_config JSON NOT NULL,           -- 标准化配置
    vendor_configs JSON,                       -- 厂商特定配置 {"h3c": "...", "huawei": "..."}
    
    -- 版本信息
    current_version INT DEFAULT 1,             -- 当前最新版本号
    
    -- 状态
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    
    -- 元信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    updated_by VARCHAR(50),
    
    UNIQUE KEY uk_type_name (policy_type, name),
    INDEX idx_policy_type (policy_type),
    INDEX idx_vendor (vendor_type),
    INDEX idx_active (is_active, is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略模板主表（通用）';
```

**说明：**
- `policy_type` 区分策略类型，不同类型的 `normalized_config` 结构不同
- 单表存储所有类型策略，便于统一管理
- 通过 `policy_type + name` 保证唯一性

### 2.2 策略版本历史表（通用）

```sql
CREATE TABLE policy_versions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    policy_id BIGINT NOT NULL,
    version INT NOT NULL,
    
    -- 版本快照
    config_snapshot JSON NOT NULL,             -- 该版本的完整配置
    
    -- 变更信息
    change_type ENUM('create', 'update', 'delete') NOT NULL,
    change_summary VARCHAR(500),               -- 变更摘要
    diff JSON,                                 -- 与上一版本的差异
    
    -- 元信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    
    FOREIGN KEY (policy_id) REFERENCES policy_templates(id) ON DELETE CASCADE,
    UNIQUE KEY uk_policy_version (policy_id, version),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略版本历史表（通用）';
```

### 2.3 设备策略绑定表（通用 - 核心表）

```sql
CREATE TABLE device_policy_bindings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    device_id BIGINT NOT NULL,
    policy_id BIGINT NOT NULL,
    
    -- ========== 期望状态（Desired State）==========
    target_version INT,                        -- 目标版本（应该部署的版本，NULL = 不需要部署）
    enabled BOOLEAN DEFAULT TRUE,              -- 是否启用（FALSE = 计划移除）
    
    -- ========== 实际状态（Actual State）==========
    deployed_version INT,                      -- 已部署的版本（NULL = 从未部署）
    last_deploy_at TIMESTAMP,                  -- 上次部署时间
    deploy_status ENUM('success', 'failed', 'in_progress'),
    deploy_error TEXT,                         -- 部署失败原因
    
    -- ========== 状态对比结果 ==========
    sync_status ENUM(
        'not_assigned',   -- 未分配（target_version IS NULL）
        'pending',        -- 待部署（target != deployed 或 deployed IS NULL）
        'synced',         -- 已同步（target == deployed 且配置一致）
        'outdated',       -- 版本过旧（deployed < target）
        'drift',          -- 配置漂移（版本相同但配置不一致）
        'failed'          -- 部署失败
    ) DEFAULT 'pending',
    
    config_diff JSON,                          -- 配置差异详情
    last_check_at TIMESTAMP,                   -- 上次检查时间
    
    -- ========== 元信息 ==========
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    assigned_by VARCHAR(50),                   -- 分配人
    assigned_at TIMESTAMP,                     -- 分配时间
    
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
    FOREIGN KEY (policy_id) REFERENCES policy_templates(id) ON DELETE RESTRICT,
    UNIQUE KEY uk_device_policy (device_id, policy_id),
    INDEX idx_sync_status (sync_status),
    INDEX idx_policy_id (policy_id),
    INDEX idx_target_version (target_version),
    INDEX idx_deployed_version (deployed_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备策略绑定表（通用 - 期望+实际状态）';
```

**核心设计：**
- **期望状态**：`target_version` + `enabled` 定义设备**应该**是什么样
- **实际状态**：`deployed_version` + `deploy_status` 记录设备**当前**是什么样
- **对比结果**：`sync_status` 自动计算期望与实际的差异

### 2.4 部署任务表（通用）

```sql
CREATE TABLE policy_deploy_tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_name VARCHAR(100),
    description TEXT,
    
    -- 部署目标
    policy_id BIGINT NOT NULL,
    target_version INT NOT NULL,
    device_ids JSON,                           -- 目标设备 ID 列表 [1,2,3]
    
    -- 部署策略
    deploy_type ENUM('full', 'incremental', 'canary') DEFAULT 'full',
    canary_ratio DECIMAL(5,2),                 -- 灰度比例（0.10 = 10%）
    
    -- 任务状态
    status ENUM('pending', 'running', 'paused', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
    total_devices INT,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    skipped_count INT DEFAULT 0,
    
    -- 时间信息
    scheduled_at TIMESTAMP,                    -- 计划执行时间
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- 执行信息
    executed_by VARCHAR(50),
    error_message TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (policy_id) REFERENCES policy_templates(id),
    INDEX idx_policy_id (policy_id),
    INDEX idx_status (status),
    INDEX idx_scheduled_at (scheduled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略部署任务表（通用）';
```

### 2.5 部署历史表（通用）

```sql
CREATE TABLE policy_deploy_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT,
    device_id BIGINT NOT NULL,
    policy_id BIGINT NOT NULL,
    
    -- 部署信息
    from_version INT,                          -- 原版本
    to_version INT NOT NULL,                   -- 目标版本
    
    -- 执行结果
    status ENUM('success', 'failed', 'skipped') NOT NULL,
    error_message TEXT,
    config_before TEXT,                        -- 部署前配置
    config_after TEXT,                         -- 部署后配置
    
    -- 时间信息
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_by VARCHAR(50),
    
    FOREIGN KEY (task_id) REFERENCES policy_deploy_tasks(id) ON DELETE SET NULL,
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (policy_id) REFERENCES policy_templates(id),
    INDEX idx_device (device_id),
    INDEX idx_policy (policy_id),
    INDEX idx_task (task_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略部署历史表（通用）';
```

## 三、策略类型扩展表（可选）

### 3.1 前缀列表条目表

```sql
CREATE TABLE policy_prefix_list_entries (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    policy_id BIGINT NOT NULL,
    version INT NOT NULL,                      -- 所属版本
    
    sequence INT NOT NULL,
    action ENUM('permit', 'deny') NOT NULL,
    prefix VARCHAR(50) NOT NULL,
    prefix_len INT NOT NULL,
    ge INT,
    le INT,
    description VARCHAR(255),
    
    FOREIGN KEY (policy_id) REFERENCES policy_templates(id) ON DELETE CASCADE,
    INDEX idx_policy_version (policy_id, version),
    INDEX idx_prefix (prefix),
    INDEX idx_sequence (policy_id, version, sequence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='前缀列表条目表';
```

### 3.2 ACL 规则表

```sql
CREATE TABLE policy_acl_rules (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    policy_id BIGINT NOT NULL,
    version INT NOT NULL,
    
    sequence INT NOT NULL,
    action ENUM('permit', 'deny') NOT NULL,
    
    -- 源地址
    source_type ENUM('direct', 'object', 'any') NOT NULL,
    source_address VARCHAR(50),
    source_address_object_id BIGINT,
    
    -- 目标地址
    dest_type ENUM('direct', 'object', 'any'),
    dest_address VARCHAR(50),
    dest_address_object_id BIGINT,
    
    -- 协议和端口
    protocol VARCHAR(20),
    source_port JSON,
    dest_port JSON,
    
    -- 其他选项
    options JSON,
    
    FOREIGN KEY (policy_id) REFERENCES policy_templates(id) ON DELETE CASCADE,
    INDEX idx_policy_version (policy_id, version),
    INDEX idx_source_addr (source_address),
    INDEX idx_dest_addr (dest_address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ACL 规则表';
```

**说明：**
- 这些扩展表是**可选的**，用于提供更好的查询能力
- 主配置仍存储在 `policy_templates.normalized_config` 中
- 扩展表通过 `version` 字段支持版本查询

### 3.3 对象组表（ACL 依赖）

```sql
-- 地址对象组
CREATE TABLE policy_address_objects (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    type ENUM('host', 'network', 'range', 'group') NOT NULL,
    description TEXT,
    vendor_type VARCHAR(20),
    
    normalized_config JSON,
    vendor_configs JSON,
    
    current_version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_name (name),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址对象组';

-- 服务对象组
CREATE TABLE policy_service_objects (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    type ENUM('single', 'group') NOT NULL,
    description TEXT,
    vendor_type VARCHAR(20),
    
    normalized_config JSON,
    vendor_configs JSON,
    
    current_version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_name (name),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='服务对象组';

-- 对象依赖关系表
CREATE TABLE policy_object_dependencies (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    object_type ENUM('address', 'service') NOT NULL,
    object_id BIGINT NOT NULL,
    
    used_by_type ENUM('policy', 'address_object', 'service_object') NOT NULL,
    used_by_id BIGINT NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_object (object_type, object_id),
    INDEX idx_used_by (used_by_type, used_by_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对象依赖关系';
```

## 四、数据示例

### 4.1 前缀列表示例

**policy_templates 表：**
```sql
INSERT INTO policy_templates (policy_type, name, normalized_config, current_version) VALUES
('prefix_list', 'idc-networks', '{
  "name": "idc-networks",
  "entries": [
    {"seq": 10, "action": "permit", "prefix": "172.16.0.0/12", "ge": 16, "le": 24},
    {"seq": 20, "action": "permit", "prefix": "10.0.0.0/8", "ge": 16, "le": 24}
  ]
}', 1);
```

**device_policy_bindings 表：**
```sql
-- 设备 1 应该部署 v2，但实际只部署了 v1（版本过旧）
INSERT INTO device_policy_bindings VALUES
(1, 1, 1, 2, TRUE, 1, '2026-09-01 10:00:00', 'success', NULL, 'outdated', NULL, '2026-09-10 08:00:00', ...);

-- 设备 2 应该部署 v2，且已部署 v2（已同步）
INSERT INTO device_policy_bindings VALUES
(2, 2, 1, 2, TRUE, 2, '2026-09-10 09:00:00', 'success', NULL, 'synced', NULL, '2026-09-10 09:01:00', ...);

-- 设备 3 应该部署 v2，但还没部署（待部署）
INSERT INTO device_policy_bindings VALUES
(3, 3, 1, 2, TRUE, NULL, NULL, NULL, NULL, 'pending', NULL, NULL, ...);
```

### 4.2 ACL 示例

**policy_templates 表：**
```sql
INSERT INTO policy_templates (policy_type, name, normalized_config, current_version) VALUES
('acl', 'web-access', '{
  "name": "web-access",
  "acl_type": "advanced",
  "number": 3000,
  "rules": [
    {
      "seq": 5,
      "action": "permit",
      "protocol": "tcp",
      "source": {"type": "object", "object_name": "office-networks"},
      "destination": {"type": "any"},
      "dest_port": {"type": "direct", "operator": "eq", "ports": [80, 443]}
    }
  ]
}', 1);
```

## 五、关键查询示例

### 5.1 查询所有待部署的策略

```sql
SELECT 
    pt.policy_type,
    pt.name,
    COUNT(*) as pending_devices,
    GROUP_CONCAT(d.hostname) as device_list
FROM device_policy_bindings dpb
JOIN policy_templates pt ON dpb.policy_id = pt.id
JOIN devices d ON dpb.device_id = d.id
WHERE dpb.enabled = TRUE
  AND dpb.sync_status IN ('pending', 'outdated', 'drift')
GROUP BY pt.policy_type, pt.name
ORDER BY pending_devices DESC;
```

### 5.2 查询设备的所有策略状态

```sql
SELECT 
    pt.policy_type,
    pt.name,
    dpb.target_version,
    dpb.deployed_version,
    dpb.sync_status,
    dpb.last_deploy_at,
    CASE dpb.sync_status
        WHEN 'synced' THEN '✓ 已同步'
        WHEN 'pending' THEN '⏳ 待部署'
        WHEN 'outdated' THEN '⚠ 版本过旧'
        WHEN 'drift' THEN '⚠ 配置漂移'
        WHEN 'failed' THEN '✗ 失败'
    END as status_desc
FROM device_policy_bindings dpb
JOIN policy_templates pt ON dpb.policy_id = pt.id
WHERE dpb.device_id = ?
  AND dpb.enabled = TRUE
ORDER BY dpb.sync_status DESC, pt.policy_type, pt.name;
```

### 5.3 查询策略的设备覆盖情况

```sql
SELECT 
    dpb.sync_status,
    COUNT(*) as device_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM device_policy_bindings dpb
WHERE dpb.policy_id = ?
  AND dpb.enabled = TRUE
GROUP BY dpb.sync_status
ORDER BY FIELD(dpb.sync_status, 'synced', 'pending', 'outdated', 'drift', 'failed');
```

### 5.4 查询特定策略类型的统计

```sql
-- 统计所有前缀列表的部署情况
SELECT 
    pt.name,
    pt.current_version,
    COUNT(dpb.id) as total_devices,
    SUM(CASE WHEN dpb.sync_status = 'synced' THEN 1 ELSE 0 END) as synced,
    SUM(CASE WHEN dpb.sync_status IN ('pending', 'outdated') THEN 1 ELSE 0 END) as need_deploy,
    SUM(CASE WHEN dpb.sync_status = 'drift' THEN 1 ELSE 0 END) as drift,
    SUM(CASE WHEN dpb.sync_status = 'failed' THEN 1 ELSE 0 END) as failed
FROM policy_templates pt
LEFT JOIN device_policy_bindings dpb ON pt.id = dpb.policy_id AND dpb.enabled = TRUE
WHERE pt.policy_type = 'prefix_list'
  AND pt.is_active = TRUE
  AND pt.is_deleted = FALSE
GROUP BY pt.id
ORDER BY pt.name;
```

### 5.5 查询版本升级影响范围

```sql
-- 如果将策略升级到新版本，会影响哪些设备
SELECT 
    d.hostname,
    d.ip_address,
    dpb.deployed_version as current_version,
    ? as new_version,
    dpb.sync_status
FROM device_policy_bindings dpb
JOIN devices d ON dpb.device_id = d.id
WHERE dpb.policy_id = ?
  AND dpb.enabled = TRUE
  AND (dpb.target_version < ? OR dpb.deployed_version < ?)
ORDER BY d.hostname;
```

## 六、状态转换逻辑

### 6.1 状态自动更新触发点

**1. 分配策略时：**
```sql
-- target_version 设置，deployed_version = NULL
sync_status = 'pending'
```

**2. 更新模板版本时：**
```sql
-- 如果设备的 target_version = 旧版本（跟踪最新）
UPDATE device_policy_bindings
SET sync_status = 'outdated'
WHERE policy_id = ? AND target_version = ?
```

**3. 部署成功后：**
```sql
UPDATE device_policy_bindings
SET deployed_version = target_version,
    sync_status = 'synced',
    deploy_status = 'success',
    last_deploy_at = NOW()
WHERE device_id = ? AND policy_id = ?
```

**4. 配置检查后：**
```sql
-- 如果检测到配置漂移
UPDATE device_policy_bindings
SET sync_status = 'drift',
    config_diff = ?,
    last_check_at = NOW()
WHERE device_id = ? AND policy_id = ?
```

### 6.2 状态计算逻辑

```python
def calculate_sync_status(binding):
    """计算同步状态"""
    if not binding['enabled'] or binding['target_version'] is None:
        return 'not_assigned'
    
    if binding['deploy_status'] == 'failed':
        return 'failed'
    
    if binding['deployed_version'] is None:
        return 'pending'
    
    if binding['deployed_version'] < binding['target_version']:
        return 'outdated'
    
    # 版本相同，检查配置是否一致
    if binding['config_diff'] and binding['config_diff'].get('has_changes'):
        return 'drift'
    
    return 'synced'
```

## 七、扩展新策略类型步骤

### 7.1 添加路由策略示例

**步骤 1：定义标准化配置结构**
```json
{
  "name": "bgp-import",
  "nodes": [
    {
      "seq": 10,
      "if_match": [
        {"type": "prefix_list", "name": "idc-networks"}
      ],
      "apply": [
        {"type": "set_local_pref", "value": 200}
      ]
    }
  ]
}
```

**步骤 2：插入 policy_templates**
```sql
INSERT INTO policy_templates (policy_type, name, normalized_config, current_version) VALUES
('route_policy', 'bgp-import', '<上述JSON>', 1);
```

**步骤 3：（可选）创建扩展查询表**
```sql
CREATE TABLE policy_route_policy_nodes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    policy_id BIGINT NOT NULL,
    version INT NOT NULL,
    sequence INT NOT NULL,
    if_match JSON,
    apply JSON,
    ...
) ENGINE=InnoDB;
```

**步骤 4：绑定到设备**
```sql
-- 复用 device_policy_bindings 表，无需修改
INSERT INTO device_policy_bindings (device_id, policy_id, target_version, enabled) VALUES
(1, <policy_id>, 1, TRUE);
```

**步骤 5：实现厂商适配器**
```python
class RouteMapAdapter:
    def render(self, normalized_config, vendor):
        # 渲染为厂商特定配置
        pass
```

## 八、设计优势

### 8.1 统一管理
- ✓ 所有策略类型共用一套绑定、版本、部署机制
- ✓ 统一的状态管理（期望 vs 实际）
- ✓ 统一的查询接口

### 8.2 易于扩展
- ✓ 新增策略类型只需：
  1. 定义 `normalized_config` JSON 结构
  2. 实现厂商适配器
  3. （可选）添加扩展查询表
- ✓ 不需要修改核心表结构

### 8.3 灵活性
- ✓ 支持不同设备部署不同版本（灰度发布）
- ✓ 支持策略的启用/禁用
- ✓ 完整的版本历史和回滚能力

### 8.4 可观测性
- ✓ 清晰的状态定义和转换
- ✓ 完整的部署历史记录
- ✓ 配置差异跟踪

## 九、表关系总结

```
核心表（适用所有策略类型）：
    policy_templates (策略模板)
        ├─── policy_versions (版本历史)
        └─── device_policy_bindings (设备绑定 - 期望+实际状态)
                ├─── policy_deploy_tasks (部署任务)
                └─── policy_deploy_history (部署历史)

扩展表（特定策略类型，可选）：
    policy_prefix_list_entries (前缀列表条目)
    policy_acl_rules (ACL 规则)
    policy_address_objects (地址对象)
    policy_service_objects (服务对象)
    policy_object_dependencies (依赖关系)
```

## 十、后续工作

1. **Phase 1**: 实现前缀列表管理（验证通用框架）
2. **Phase 2**: 添加 ACL 管理（验证对象引用支持）
3. **Phase 3**: 添加路由策略、QoS 策略等
4. **Phase 4**: 优化查询性能，添加缓存机制

---

*文档维护：表结构变更时更新此文档*
