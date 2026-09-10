# 策略模板匹配与合并设计

## 文档信息
- 创建时间: 2026-09-10
- 状态: 设计中
- 版本: v0.1

## 一、问题定义

### 1.1 核心问题

当从多个设备的备份配置中解析出策略时，如何判断它们是否"功能一致"，应该映射到同一个模板？

**示例场景：**

设备 A（H3C）：
```
ip ip-prefix idc-networks index 10 permit 172.16.0.0 12 greater-equal 16 less-equal 24
ip ip-prefix idc-networks index 20 permit 10.0.0.0 8 greater-equal 16 less-equal 24
ip ip-prefix idc-networks index 100 deny 0.0.0.0 0 less-equal 32
```

设备 B（Huawei）：
```
ip ip-prefix idc-networks index 10 permit 172.16.0.0 12 greater-equal 16 less-equal 24
ip ip-prefix idc-networks index 20 permit 10.0.0.0 8 greater-equal 16 less-equal 24
ip ip-prefix idc-networks index 100 deny 0.0.0.0 0 less-equal 32
```

设备 C（Cisco）：
```
ip prefix-list idc-networks seq 10 permit 172.16.0.0/12 ge 16 le 24
ip prefix-list idc-networks seq 20 permit 10.0.0.0/8 ge 16 le 24
ip prefix-list idc-networks seq 100 deny 0.0.0.0/0 le 32
```

**问题：**
- 这三个配置功能完全一致，只是语法不同
- 应该映射到同一个模板 "idc-networks"
- 如何自动识别？

### 1.2 挑战

1. **厂商语法差异**：同样的功能，不同厂商语法不同
2. **名称不统一**：不同设备可能用不同名称
3. **微小差异**：注释、描述、空行等非功能性差异
4. **顺序差异**：条目顺序可能不同（但序列号相同）
5. **部分重叠**：两个配置有 80% 相同，是否应该合并？

## 二、解决方案：配置指纹匹配

### 2.1 核心思路

**配置指纹（Config Fingerprint）**
- 对标准化后的配置计算"指纹"（哈希值）
- 忽略厂商语法差异、名称、注释等非功能性因素
- 只关注功能性内容（条目、动作、参数）
- 相同指纹 = 功能一致 = 映射到同一模板

### 2.2 指纹计算方法

```python
import hashlib
import json

def calculate_policy_fingerprint(normalized_config):
    """
    计算策略配置的指纹
    
    Args:
        normalized_config: 标准化后的配置（dict）
    
    Returns:
        str: 64位哈希值
    """
    # 1. 提取功能性字段（忽略名称、描述等）
    functional_data = {
        'type': normalized_config.get('policy_type'),  # 策略类型必须一致
        'entries': []
    }
    
    # 2. 提取条目的功能性内容
    for entry in normalized_config.get('entries', []):
        functional_entry = {
            'seq': entry['seq'],
            'action': entry['action']
        }
        
        # 根据策略类型提取关键字段
        if normalized_config.get('policy_type') == 'prefix_list':
            functional_entry.update({
                'prefix': entry['prefix'],
                'ge': entry.get('ge'),
                'le': entry.get('le')
            })
        elif normalized_config.get('policy_type') == 'acl':
            functional_entry.update({
                'protocol': entry.get('protocol'),
                'source': _normalize_address(entry.get('source')),
                'destination': _normalize_address(entry.get('destination')),
                'source_port': entry.get('source_port'),
                'dest_port': entry.get('dest_port')
            })
        
        functional_data['entries'].append(functional_entry)
    
    # 3. 排序（确保顺序一致性）
    functional_data['entries'].sort(key=lambda x: x['seq'])
    
    # 4. 序列化为 JSON（确保一致性）
    json_str = json.dumps(functional_data, sort_keys=True, ensure_ascii=False)
    
    # 5. 计算哈希
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

def _normalize_address(addr_config):
    """标准化地址配置（用于指纹计算）"""
    if not addr_config:
        return None
    
    result = {
        'type': addr_config['type']
    }
    
    if addr_config['type'] == 'direct':
        result['address'] = addr_config['address']
    elif addr_config['type'] == 'object':
        # 对象引用：使用对象名的标准化形式
        result['object_name'] = addr_config['object_name'].lower()
    
    return result
```

### 2.3 指纹示例

**配置1（H3C）：**
```json
{
  "name": "idc-networks",
  "policy_type": "prefix_list",
  "entries": [
    {"seq": 10, "action": "permit", "prefix": "172.16.0.0/12", "ge": 16, "le": 24},
    {"seq": 20, "action": "permit", "prefix": "10.0.0.0/8", "ge": 16, "le": 24}
  ]
}
```
**指纹：** `a3f5b8c9d2e1f4a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0`

**配置2（Cisco，名称不同但内容相同）：**
```json
{
  "name": "IDC_NETWORKS",
  "policy_type": "prefix_list",
  "entries": [
    {"seq": 10, "action": "permit", "prefix": "172.16.0.0/12", "ge": 16, "le": 24},
    {"seq": 20, "action": "permit", "prefix": "10.0.0.0/8", "ge": 16, "le": 24}
  ]
}
```
**指纹：** `a3f5b8c9d2e1f4a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0`（相同！）

## 三、数据库设计支持

### 3.1 增加指纹字段

```sql
ALTER TABLE policy_templates
ADD COLUMN config_fingerprint CHAR(64) NOT NULL,
ADD INDEX idx_fingerprint (config_fingerprint);

ALTER TABLE policy_versions
ADD COLUMN config_fingerprint CHAR(64) NOT NULL;
```

### 3.2 配置来源追踪表

```sql
CREATE TABLE policy_config_sources (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    policy_id BIGINT NOT NULL,
    
    -- 来源设备
    device_id BIGINT NOT NULL,
    device_config_name VARCHAR(100),           -- 设备上的配置名称
    
    -- 解析信息
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_config TEXT,                           -- 原始配置（厂商特定）
    
    -- 匹配信息
    match_type ENUM('exact', 'similar', 'manual') NOT NULL,
    similarity_score DECIMAL(5,2),             -- 相似度（0-100）
    
    FOREIGN KEY (policy_id) REFERENCES policy_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES devices(id),
    INDEX idx_device (device_id),
    INDEX idx_policy (policy_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略配置来源追踪';
```

### 3.3 配置匹配候选表（临时表）

```sql
CREATE TABLE policy_match_candidates (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    
    -- 解析出的配置
    device_id BIGINT NOT NULL,
    device_config_name VARCHAR(100),
    policy_type VARCHAR(50) NOT NULL,
    normalized_config JSON NOT NULL,
    config_fingerprint CHAR(64) NOT NULL,
    
    -- 匹配结果
    matched_policy_id BIGINT,                  -- 匹配到的模板 ID
    match_confidence DECIMAL(5,2),             -- 匹配置信度
    match_status ENUM('pending', 'matched', 'conflict', 'new') DEFAULT 'pending',
    
    -- 用户决策
    user_decision ENUM('accept', 'reject', 'create_new', 'merge'),
    decided_at TIMESTAMP,
    decided_by VARCHAR(50),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (matched_policy_id) REFERENCES policy_templates(id),
    INDEX idx_fingerprint (config_fingerprint),
    INDEX idx_status (match_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略匹配候选（解析后待确认）';
```

## 四、匹配流程设计

### 4.1 自动匹配流程

```python
def process_device_backup(device_id, backup_config):
    """
    处理设备备份配置
    
    流程：
    1. 解析配置 -> 标准化模型
    2. 计算指纹
    3. 查找匹配的模板
    4. 创建候选记录（待用户确认）
    """
    # 1. 解析配置
    adapter = get_vendor_adapter(device['vendor_type'])
    parsed_policies = adapter.parse_all_policies(backup_config)
    
    for policy_config in parsed_policies:
        # 2. 标准化并计算指纹
        normalized = normalize_config(policy_config)
        fingerprint = calculate_policy_fingerprint(normalized)
        
        # 3. 查找匹配
        match_result = find_matching_template(fingerprint, normalized)
        
        # 4. 创建候选记录
        candidate_id = db.insert('policy_match_candidates', {
            'device_id': device_id,
            'device_config_name': policy_config['name'],
            'policy_type': normalized['policy_type'],
            'normalized_config': json.dumps(normalized),
            'config_fingerprint': fingerprint,
            'matched_policy_id': match_result['policy_id'],
            'match_confidence': match_result['confidence'],
            'match_status': match_result['status']
        })
    
    return {
        'total': len(parsed_policies),
        'exact_match': count_by_status('matched'),
        'conflict': count_by_status('conflict'),
        'new': count_by_status('new')
    }

def find_matching_template(fingerprint, normalized_config):
    """
    查找匹配的模板
    
    Returns:
        {
            'policy_id': int or None,
            'confidence': float (0-100),
            'status': 'matched' | 'conflict' | 'new'
        }
    """
    # 1. 精确匹配：指纹完全相同
    exact_match = db.query_one(
        """
        SELECT id, name FROM policy_templates
        WHERE config_fingerprint = ?
          AND policy_type = ?
          AND is_deleted = FALSE
        LIMIT 1
        """,
        [fingerprint, normalized_config['policy_type']]
    )
    
    if exact_match:
        return {
            'policy_id': exact_match['id'],
            'confidence': 100.0,
            'status': 'matched'
        }
    
    # 2. 相似匹配：计算相似度
    similar_policies = db.query(
        """
        SELECT id, name, normalized_config
        FROM policy_templates
        WHERE policy_type = ?
          AND is_deleted = FALSE
        """,
        [normalized_config['policy_type']]
    )
    
    best_match = None
    max_similarity = 0.0
    
    for policy in similar_policies:
        similarity = calculate_similarity(
            normalized_config,
            json.loads(policy['normalized_config'])
        )
        
        if similarity > max_similarity:
            max_similarity = similarity
            best_match = policy
    
    # 3. 判断是否足够相似
    if max_similarity >= 80.0:  # 阈值：80% 相似度
        return {
            'policy_id': best_match['id'],
            'confidence': max_similarity,
            'status': 'conflict'  # 需要用户确认
        }
    else:
        return {
            'policy_id': None,
            'confidence': 0.0,
            'status': 'new'  # 新配置，建议创建新模板
        }

def calculate_similarity(config1, config2):
    """
    计算两个配置的相似度
    
    Returns:
        float: 0-100 的相似度分数
    """
    entries1 = config1.get('entries', [])
    entries2 = config2.get('entries', [])
    
    if len(entries1) == 0 and len(entries2) == 0:
        return 100.0
    
    if len(entries1) == 0 or len(entries2) == 0:
        return 0.0
    
    # 按序列号对齐
    entries1_dict = {e['seq']: e for e in entries1}
    entries2_dict = {e['seq']: e for e in entries2}
    
    all_seqs = set(entries1_dict.keys()) | set(entries2_dict.keys())
    
    matched = 0
    for seq in all_seqs:
        e1 = entries1_dict.get(seq)
        e2 = entries2_dict.get(seq)
        
        if e1 and e2 and entries_equal(e1, e2):
            matched += 1
    
    return (matched / len(all_seqs)) * 100.0

def entries_equal(entry1, entry2):
    """判断两个条目是否功能相同"""
    # 移除非功能性字段
    e1 = {k: v for k, v in entry1.items() if k not in ['description', 'comment']}
    e2 = {k: v for k, v in entry2.items() if k not in ['description', 'comment']}
    
    return e1 == e2
```

### 4.2 用户确认流程

```python
def confirm_match_candidate(candidate_id, decision):
    """
    用户确认匹配结果
    
    Args:
        decision: 'accept' | 'reject' | 'create_new' | 'merge'
    """
    candidate = db.get('policy_match_candidates', candidate_id)
    
    if decision == 'accept':
        # 接受匹配，绑定到现有模板
        _bind_to_existing_template(candidate)
    
    elif decision == 'create_new':
        # 创建新模板
        policy_id = _create_new_template(candidate)
        _bind_to_template(candidate, policy_id)
    
    elif decision == 'merge':
        # 合并到现有模板（更新模板内容）
        _merge_to_template(candidate)
    
    elif decision == 'reject':
        # 拒绝，不处理
        pass
    
    # 更新候选记录
    db.execute(
        """
        UPDATE policy_match_candidates
        SET user_decision = ?,
            decided_at = NOW(),
            decided_by = ?
        WHERE id = ?
        """,
        [decision, current_user(), candidate_id]
    )

def _bind_to_existing_template(candidate):
    """绑定到现有模板"""
    # 1. 记录配置来源
    db.insert('policy_config_sources', {
        'policy_id': candidate['matched_policy_id'],
        'device_id': candidate['device_id'],
        'device_config_name': candidate['device_config_name'],
        'raw_config': get_raw_config(candidate),
        'match_type': 'exact' if candidate['match_confidence'] == 100 else 'similar',
        'similarity_score': candidate['match_confidence']
    })
    
    # 2. 创建设备绑定
    db.insert('device_policy_bindings', {
        'device_id': candidate['device_id'],
        'policy_id': candidate['matched_policy_id'],
        'target_version': get_current_version(candidate['matched_policy_id']),
        'deployed_version': get_current_version(candidate['matched_policy_id']),
        'enabled': True,
        'sync_status': 'synced',
        'deploy_status': 'success',
        'last_deploy_at': 'NOW()'
    })

def _create_new_template(candidate):
    """创建新模板"""
    normalized = json.loads(candidate['normalized_config'])
    
    # 生成模板名称
    template_name = _generate_template_name(
        candidate['device_config_name'],
        candidate['policy_type']
    )
    
    # 创建模板
    policy_id = db.insert('policy_templates', {
        'policy_type': candidate['policy_type'],
        'name': template_name,
        'normalized_config': candidate['normalized_config'],
        'config_fingerprint': candidate['config_fingerprint'],
        'current_version': 1,
        'created_by': current_user()
    })
    
    # 创建版本历史
    db.insert('policy_versions', {
        'policy_id': policy_id,
        'version': 1,
        'config_snapshot': candidate['normalized_config'],
        'config_fingerprint': candidate['config_fingerprint'],
        'change_type': 'create',
        'change_summary': f"从设备 {candidate['device_id']} 导入",
        'created_by': current_user()
    })
    
    # 记录来源
    db.insert('policy_config_sources', {
        'policy_id': policy_id,
        'device_id': candidate['device_id'],
        'device_config_name': candidate['device_config_name'],
        'match_type': 'manual'
    })
    
    return policy_id

def _generate_template_name(device_config_name, policy_type):
    """生成模板名称"""
    # 标准化名称
    base_name = device_config_name.lower().replace('_', '-')
    
    # 检查是否重复
    counter = 1
    name = base_name
    
    while db.exists('policy_templates', {'name': name, 'policy_type': policy_type}):
        name = f"{base_name}-{counter}"
        counter += 1
    
    return name
```

## 五、前端交互设计

### 5.1 配置导入页面

```
┌────────────────────────────────────────────────────────┐
│ 导入设备配置                              [关闭]        │
├────────────────────────────────────────────────────────┤
│ 步骤 1: 选择设备                                       │
│  [√] bbs1_corp_bj_m01 (H3C)                           │
│  [√] bbs2_corp_sh_m01 (Huawei)                        │
│  [ ] edge_partner_01 (Cisco)                          │
│                                                        │
│ 步骤 2: 解析配置                        [开始解析]     │
│                                                        │
│  解析进度: 2/2 完成                                    │
│   ✓ bbs1_corp_bj_m01: 发现 3 个前缀列表, 2 个 ACL    │
│   ✓ bbs2_corp_sh_m01: 发现 3 个前缀列表, 2 个 ACL    │
│                                                        │
│ 步骤 3: 匹配结果                      [下一步: 确认]   │
│                                                        │
│  ✓ 精确匹配 (4)   ⚠ 需要确认 (2)   🆕 新配置 (2)    │
└────────────────────────────────────────────────────────┘
```

### 5.2 匹配确认页面

```
┌────────────────────────────────────────────────────────┐
│ 配置匹配确认                                           │
├────────────────────────────────────────────────────────┤
│ 需要确认的配置 (2/2)                                   │
├────────────────────────────────────────────────────────┤
│ 1. 前缀列表: "idc-networks" (bbs1_corp_bj_m01)        │
│                                                        │
│    匹配建议: 合并到现有模板 "idc-networks-v1"         │
│    相似度: 85%                                         │
│                                                        │
│    差异对比:                                           │
│    ┌──────────────────────────────────────────────┐   │
│    │ 现有模板          │ 设备配置                 │   │
│    ├──────────────────────────────────────────────┤   │
│    │ 10: permit ...    │ 10: permit ...          │   │
│    │ 20: permit ...    │ 20: permit ...          │   │
│    │                   │ 30: permit ... 🆕       │   │
│    └──────────────────────────────────────────────┘   │
│                                                        │
│    操作:                                               │
│    ○ 接受匹配（绑定到现有模板，不修改模板）            │
│    ● 合并配置（更新模板，添加新条目 seq 30）          │
│    ○ 创建新模板                                       │
│    ○ 跳过                                             │
│                                                        │
│                             [上一个] [下一个] [确认]   │
└────────────────────────────────────────────────────────┘
```

### 5.3 批量操作页面

```
┌────────────────────────────────────────────────────────┐
│ 批量导入摘要                                           │
├────────────────────────────────────────────────────────┤
│ 精确匹配 (4) - 将自动绑定                              │
│  • idc-networks (bbs1, bbs2) -> 模板 "idc-networks"   │
│  • partner-routes (edge1, edge2) -> 模板 "partner"    │
│                                                        │
│ 新配置 (2) - 将创建新模板                              │
│  • dmz-access (fw1) -> 新模板 "dmz-access"           │
│  • guest-wifi (sw1) -> 新模板 "guest-wifi"           │
│                                                        │
│ 跳过 (1)                                               │
│  • test-config (dev1)                                 │
│                                                        │
│                                      [取消] [确认导入]  │
└────────────────────────────────────────────────────────┘
```

## 六、高级场景处理

### 6.1 名称不一致但内容相同

**场景：**
- 设备 A: 配置名 "idc-networks"
- 设备 B: 配置名 "IDC_NETWORKS"
- 设备 C: 配置名 "idc_nets"

**解决：**
- 通过指纹匹配，识别为同一配置
- 模板使用标准化名称（如 "idc-networks"）
- 记录每个设备的原始名称在 `policy_config_sources` 表

### 6.2 部分重叠配置

**场景：**
- 模板 A: 10 条规则
- 设备配置: 8 条规则（其中 6 条与模板相同）

**相似度：** 60% (6/10)

**策略：**
- 相似度 >= 80%: 建议合并
- 相似度 50-80%: 提示用户决策
- 相似度 < 50%: 建议创建新模板

### 6.3 配置演化

**场景：**
- 时间 T1: 从设备解析配置 -> 创建模板 v1
- 时间 T2: 设备配置更新 -> 再次解析

**处理：**
```python
def handle_config_evolution(device_id, policy_id, new_config):
    """处理配置演化"""
    binding = get_binding(device_id, policy_id)
    
    if not binding:
        # 新绑定
        return 'create_binding'
    
    # 检查是否有变化
    diff = compare_with_template(new_config, policy_id, binding['deployed_version'])
    
    if not diff['has_changes']:
        # 无变化
        return 'no_change'
    
    # 有变化，更新状态
    db.execute(
        """
        UPDATE device_policy_bindings
        SET sync_status = 'drift',
            config_diff = ?,
            last_check_at = NOW()
        WHERE device_id = ? AND policy_id = ?
        """,
        [json.dumps(diff), device_id, policy_id]
    )
    
    # 建议：是否将设备配置更新到模板
    return {
        'action': 'suggest_update_template',
        'diff': diff
    }
```

### 6.4 冲突解决

**场景：**
- 设备 A 和 B 都有 "idc-networks" 配置
- 但内容不同（相似度 50%）

**处理策略：**
1. 提示用户存在冲突
2. 显示差异对比
3. 选项：
   - 创建两个不同的模板（idc-networks-v1, idc-networks-v2）
   - 选择其中一个作为标准，另一个标记为配置漂移
   - 手动合并差异

## 七、实施建议

### 7.1 阶段实施

**Phase 1: 基础匹配**
- 精确匹配（指纹相同）
- 手动确认机制

**Phase 2: 智能匹配**
- 相似度计算
- 自动建议

**Phase 3: 批量处理**
- 批量导入
- 冲突自动解决策略

### 7.2 匹配阈值配置

```sql
CREATE TABLE system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT,
    description TEXT
) ENGINE=InnoDB;

INSERT INTO system_config VALUES
('policy.match.similarity_threshold', '80', '相似度阈值（百分比）'),
('policy.match.auto_accept_exact', 'true', '自动接受精确匹配'),
('policy.match.conflict_strategy', 'manual', '冲突处理策略: manual|auto_merge');
```

## 八、总结

### 8.1 核心机制

1. **配置指纹**：忽略非功能性差异，计算配置的唯一标识
2. **自动匹配**：通过指纹和相似度算法自动匹配
3. **用户确认**：对于不确定的匹配，由用户决策
4. **来源追踪**：记录配置的来源设备和匹配过程

### 8.2 优势

- ✓ 自动识别不同厂商的相同配置
- ✓ 避免重复创建功能相同的模板
- ✓ 支持配置演化和差异检测
- ✓ 保留完整的追溯信息

### 8.3 注意事项

- 指纹算法需要根据实际情况调优
- 相似度阈值需要根据业务场景调整
- 对于关键配置，建议人工确认
- 定期清理 `policy_match_candidates` 临时表

---

*文档维护：匹配算法优化时更新此文档*
