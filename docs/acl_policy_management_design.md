# ACL 和地址前缀列表管理设计方案

## 文档信息
- 创建时间: 2026-09-10
- 状态: 设计中
- 版本: v0.1

## 一、背景与需求

### 1.1 业务场景
- ACL（访问控制列表）和地址前缀列表属于策略类配置
- 多个设备的配置内容往往一致，需要模板化管理
- 配置来源：从设备备份配置中解析获取
- 厂商差异：H3C、Huawei、Cisco 等厂商语法不同
- 对象组引用：边界设备的 ACL 会引用地址簿和端口组

### 1.2 核心目标
- 策略模板化：相同策略只存储一份，多设备复用
- 厂商适配：支持多厂商配置的标准化和转换
- 版本管理：跟踪策略变更历史
- 差异检测：对比设备实际配置与模板的差异
- 对象组管理：支持地址对象和服务对象的引用关系

### 1.3 ACL 类型说明

**标准 ACL (Basic ACL)**
- 只能基于源 IP 地址过滤
- 不支持目标地址、协议、端口等条件
- 编号范围：2000-2999（行业惯例）
- 示例：
```
H3C:     acl basic 2000
         rule 5 permit source 10.1.0.0 0.0.255.255

Huawei:  acl number 2000
         rule 5 permit source 10.1.0.0 0.0.255.255

Cisco:   access-list 2000 permit 10.1.0.0 0.0.255.255
```

**扩展 ACL (Advanced ACL)**
- 支持源/目标 IP、协议、端口等多维度匹配
- 编号范围：3000-3999（行业惯例）
- 示例：
```
H3C:     acl advanced 3000
         rule 5 permit tcp source 10.1.0.0 0.0.255.255 destination any destination-port eq 80 443

Huawei:  acl number 3000
         rule 5 permit tcp source 10.1.0.0 0.0.255.255 destination any destination-port eq 80 443

Cisco:   ip access-list web-access
         5 permit tcp 10.1.0.0/16 any eq 80 443
```

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────┐
│              前端管理界面                          │
│  (策略模板管理、对象组管理、设备绑定、差异检测)      │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│              API 层                              │
│  (策略 CRUD、解析、渲染、版本管理、依赖检查)        │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│          标准化抽象层                             │
│  (厂商无关的统一模型 - Normalized Model)           │
└─────────────────────────────────────────────────┘
         ↓                              ↓
┌──────────────────┐         ┌──────────────────┐
│  厂商适配器层      │         │   数据持久化层     │
│  (H3C/Huawei/    │         │  (数据库存储)      │
│   Cisco 适配器)   │         │                  │
└──────────────────┘         └──────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│           厂商原生配置                            │
│  (H3C 语法、Huawei 语法、Cisco 语法)               │
└─────────────────────────────────────────────────┘
```

### 2.2 数据流向

**配置解析流程：**
```
设备备份配置 → 厂商适配器解析 → 标准化模型 → 数据库存储
                                    ↓
                            (同时保存原始配置)
```

**配置渲染流程：**
```
数据库读取 → 标准化模型 → 厂商适配器渲染 → 厂商特定配置
                              ↓
                        (可选：展开对象引用)
```

## 三、标准化数据模型

### 3.1 ACL 标准模型

```json
{
  "name": "acl-name",
  "acl_type": "basic|advanced",
  "number": 2000,
  "description": "描述信息",
  "rules": [
    {
      "seq": 5,
      "action": "permit|deny",
      
      "source": {
        "type": "direct|object|any",
        "address": "10.1.0.0/16",
        "wildcard": "0.0.255.255",
        "object_name": "office-networks"
      },
      
      "protocol": "tcp|udp|icmp|ip",
      
      "destination": {
        "type": "direct|object|any",
        "address": "192.168.1.0/24",
        "wildcard": "0.0.0.255",
        "object_name": "dmz-servers"
      },
      
      "source_port": {
        "type": "direct|object|any",
        "operator": "eq|range|lt|gt",
        "ports": [1024, 65535],
        "object_name": "high-ports"
      },
      
      "dest_port": {
        "type": "direct|object|any",
        "operator": "eq",
        "ports": [80, 443],
        "object_name": "web-services"
      },
      
      "options": {
        "logging": true,
        "time_range": "work-hours",
        "fragments": false
      }
    }
  ]
}
```

### 3.2 地址对象模型

```json
{
  "name": "office-networks",
  "type": "host|network|range|group",
  "description": "办公网段集合",
  "entries": [
    {
      "type": "network",
      "address": "10.1.0.0/16",
      "wildcard": "0.0.255.255"
    },
    {
      "type": "network",
      "address": "10.2.0.0/16",
      "wildcard": "0.0.255.255"
    },
    {
      "type": "ref",
      "object_name": "branch-offices"
    }
  ]
}
```

### 3.3 服务对象模型

```json
{
  "name": "web-services",
  "type": "single|group",
  "description": "Web 服务端口",
  "entries": [
    {
      "protocol": "tcp",
      "port_operator": "eq",
      "ports": [80, 443]
    },
    {
      "protocol": "tcp",
      "port_operator": "eq",
      "ports": [8080, 8443]
    },
    {
      "type": "ref",
      "object_name": "alternative-web-ports"
    }
  ]
}
```

### 3.4 地址前缀列表模型

```json
{
  "name": "idc-networks",
  "description": "IDC 网段前缀列表",
  "entries": [
    {
      "seq": 10,
      "action": "permit|deny",
      "prefix": "172.16.0.0/12",
      "ge": 16,
      "le": 24
    }
  ]
}
```

## 四、数据库设计

### 4.1 方案选择：混合存储

采用**关系表 + JSON**的混合存储方式：
- 关系字段：存储元信息和关键字段，支持索引和复杂查询
- JSON 字段：存储完整配置和厂商特定配置，灵活扩展

### 4.2 核心表结构

#### 4.2.1 对象组管理表

```sql
-- 地址对象组
CREATE TABLE address_objects (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    type ENUM('host', 'network', 'range', 'group') NOT NULL,
    description TEXT,
    vendor_type VARCHAR(20),
    
    -- 标准化配置（完整 JSON）
    normalized_config JSON,
    
    -- 厂商特定配置
    vendor_configs JSON,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_name (name),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址对象组';

-- 地址对象条目
CREATE TABLE address_object_entries (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    address_object_id BIGINT NOT NULL,
    entry_type ENUM('ip', 'network', 'range', 'ref') NOT NULL,
    
    -- 地址信息
    ip_address VARCHAR(50),
    network_address VARCHAR(50),
    network_mask VARCHAR(50),
    range_start VARCHAR(50),
    range_end VARCHAR(50),
    
    -- 引用其他对象（支持嵌套）
    ref_object_id BIGINT,
    
    sequence INT,
    
    FOREIGN KEY (address_object_id) REFERENCES address_objects(id) ON DELETE CASCADE,
    FOREIGN KEY (ref_object_id) REFERENCES address_objects(id) ON DELETE RESTRICT,
    INDEX idx_sequence (address_object_id, sequence),
    INDEX idx_network (network_address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址对象条目';

-- 服务对象组
CREATE TABLE service_objects (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    type ENUM('single', 'group') NOT NULL,
    description TEXT,
    vendor_type VARCHAR(20),
    
    normalized_config JSON,
    vendor_configs JSON,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_name (name),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='服务对象组';

-- 服务对象条目
CREATE TABLE service_object_entries (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    service_object_id BIGINT NOT NULL,
    entry_type ENUM('port', 'protocol', 'ref') NOT NULL,
    
    -- 服务信息
    protocol VARCHAR(20),
    port_operator VARCHAR(10),
    port_start INT,
    port_end INT,
    
    -- 引用其他服务组
    ref_object_id BIGINT,
    
    sequence INT,
    
    FOREIGN KEY (service_object_id) REFERENCES service_objects(id) ON DELETE CASCADE,
    FOREIGN KEY (ref_object_id) REFERENCES service_objects(id) ON DELETE RESTRICT,
    INDEX idx_sequence (service_object_id, sequence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='服务对象条目';
```

#### 4.2.2 ACL 管理表

```sql
-- ACL 模板主表
CREATE TABLE acl_templates (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    acl_type ENUM('basic', 'advanced') NOT NULL,
    acl_number INT,
    description TEXT,
    vendor_type VARCHAR(20),
    
    -- 标准化配置（完整 JSON，用于渲染和导出）
    normalized_config JSON,
    
    -- 厂商特定配置
    vendor_configs JSON,
    
    -- 版本管理
    version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    
    UNIQUE KEY uk_name (name),
    INDEX idx_type (acl_type),
    INDEX idx_vendor (vendor_type),
    INDEX idx_number (acl_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ACL 模板';

-- ACL 规则表（支持对象引用）
CREATE TABLE acl_rules (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    acl_template_id BIGINT NOT NULL,
    sequence INT NOT NULL,
    action ENUM('permit', 'deny') NOT NULL,
    
    -- 源地址：直接地址 OR 引用对象
    source_type ENUM('direct', 'object', 'any') NOT NULL,
    source_address VARCHAR(50),
    source_address_object_id BIGINT,
    
    -- 目标地址
    dest_type ENUM('direct', 'object', 'any'),
    dest_address VARCHAR(50),
    dest_address_object_id BIGINT,
    
    -- 协议
    protocol VARCHAR(20),
    
    -- 源端口
    source_port_type ENUM('direct', 'object', 'any'),
    source_port JSON,
    source_service_object_id BIGINT,
    
    -- 目标端口
    dest_port_type ENUM('direct', 'object', 'any'),
    dest_port JSON,
    dest_service_object_id BIGINT,
    
    -- 其他选项
    options JSON,
    
    FOREIGN KEY (acl_template_id) REFERENCES acl_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (source_address_object_id) REFERENCES address_objects(id) ON DELETE RESTRICT,
    FOREIGN KEY (dest_address_object_id) REFERENCES address_objects(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_service_object_id) REFERENCES service_objects(id) ON DELETE RESTRICT,
    FOREIGN KEY (dest_service_object_id) REFERENCES service_objects(id) ON DELETE RESTRICT,
    
    UNIQUE KEY uk_template_seq (acl_template_id, sequence),
    INDEX idx_source_addr (source_address),
    INDEX idx_dest_addr (dest_address),
    INDEX idx_source_obj (source_address_object_id),
    INDEX idx_dest_obj (dest_address_object_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ACL 规则';
```

#### 4.2.3 设备绑定与版本管理表

```sql
-- 设备策略绑定表
CREATE TABLE device_acl_bindings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    device_id BIGINT NOT NULL,
    acl_template_id BIGINT NOT NULL,
    
    -- 部署状态
    deployed_version INT,
    status ENUM('pending', 'synced', 'drift', 'failed') DEFAULT 'pending',
    last_sync_at TIMESTAMP,
    
    -- 差异信息
    config_diff JSON,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (acl_template_id) REFERENCES acl_templates(id),
    UNIQUE KEY uk_device_acl (device_id, acl_template_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备 ACL 绑定';

-- ACL 版本历史表
CREATE TABLE acl_version_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    acl_template_id BIGINT NOT NULL,
    version INT NOT NULL,
    
    -- 配置快照
    config_snapshot JSON,
    
    -- 变更信息
    change_type ENUM('create', 'update', 'delete') NOT NULL,
    change_summary TEXT,
    diff JSON,
    
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (acl_template_id) REFERENCES acl_templates(id) ON DELETE CASCADE,
    INDEX idx_template_version (acl_template_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ACL 版本历史';

-- 对象依赖关系表
CREATE TABLE object_dependencies (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    object_type ENUM('address', 'service') NOT NULL,
    object_id BIGINT NOT NULL,
    
    used_by_type ENUM('acl', 'address_object', 'service_object') NOT NULL,
    used_by_id BIGINT NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_object (object_type, object_id),
    INDEX idx_used_by (used_by_type, used_by_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对象依赖关系';
```

#### 4.2.4 地址前缀列表表

```sql
-- 地址前缀列表模板
CREATE TABLE prefix_list_templates (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    vendor_type VARCHAR(20),
    
    normalized_config JSON,
    vendor_configs JSON,
    
    version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    
    UNIQUE KEY uk_name (name),
    INDEX idx_vendor (vendor_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址前缀列表模板';

-- 地址前缀列表条目
CREATE TABLE prefix_list_entries (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    prefix_list_id BIGINT NOT NULL,
    sequence INT NOT NULL,
    action ENUM('permit', 'deny') NOT NULL,
    prefix VARCHAR(50) NOT NULL,
    ge INT,
    le INT,
    
    FOREIGN KEY (prefix_list_id) REFERENCES prefix_list_templates(id) ON DELETE CASCADE,
    UNIQUE KEY uk_list_seq (prefix_list_id, sequence),
    INDEX idx_prefix (prefix)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址前缀列表条目';
```

### 4.3 数据一致性策略

**双写保证：**
- 写入时：同时更新关系表和 JSON 字段
- 读取时：
  - 渲染/导出：直接使用 `normalized_config` JSON
  - 查询/统计：使用关系表字段和索引

**示例代码：**
```python
def create_acl(acl_data):
    with db.transaction():
        # 1. 写入主表（包含完整 JSON）
        acl_id = db.insert('acl_templates', {
            'name': acl_data['name'],
            'acl_type': acl_data['acl_type'],
            'normalized_config': json.dumps(acl_data),
            'vendor_configs': json.dumps(render_vendor_configs(acl_data))
        })
        
        # 2. 写入规则表（便于查询）
        for rule in acl_data['rules']:
            db.insert('acl_rules', {
                'acl_template_id': acl_id,
                'sequence': rule['seq'],
                'action': rule['action'],
                'source_type': rule['source']['type'],
                'source_address': rule['source'].get('address'),
                'source_address_object_id': get_object_id(rule['source'].get('object_name')),
                # ... 其他字段
            })
        
        # 3. 记录版本历史
        db.insert('acl_version_history', {
            'acl_template_id': acl_id,
            'version': 1,
            'config_snapshot': json.dumps(acl_data),
            'change_type': 'create'
        })
    
    return acl_id
```

## 五、厂商适配器设计

### 5.1 适配器架构

```python
class VendorAdapter(ABC):
    """厂商适配器基类"""
    
    @abstractmethod
    def parse_acl(self, raw_config: str) -> dict:
        """解析厂商配置 -> 标准模型"""
        pass
    
    @abstractmethod
    def render_acl(self, normalized: dict, expand_objects: bool = False) -> str:
        """标准模型 -> 厂商配置"""
        pass
    
    @abstractmethod
    def parse_address_object(self, raw_config: str) -> dict:
        """解析地址对象"""
        pass
    
    @abstractmethod
    def parse_service_object(self, raw_config: str) -> dict:
        """解析服务对象"""
        pass
    
    @abstractmethod
    def parse_prefix_list(self, raw_config: str) -> dict:
        """解析地址前缀列表"""
        pass
```

### 5.2 H3C 适配器示例

```python
class H3CAdapter(VendorAdapter):
    def parse_acl(self, raw_config: str) -> dict:
        """
        解析 H3C ACL 配置
        输入示例:
            acl advanced 3000
             rule 5 permit tcp source 10.1.0.0 0.0.255.255 destination any destination-port eq 80 443
        """
        # 实现解析逻辑
        pass
    
    def render_acl(self, normalized: dict, expand_objects: bool = False) -> str:
        """渲染为 H3C 配置"""
        acl_type = normalized['acl_type']
        acl_number = normalized['number']
        
        if acl_type == 'basic':
            lines = [f"acl basic {acl_number}"]
            for rule in normalized['rules']:
                src = self._format_address(rule['source'])
                lines.append(f" rule {rule['seq']} {rule['action']} source {src}")
        
        elif acl_type == 'advanced':
            lines = [f"acl advanced {acl_number}"]
            for rule in normalized['rules']:
                cmd_parts = [f" rule {rule['seq']} {rule['action']}"]
                
                if rule.get('protocol'):
                    cmd_parts.append(rule['protocol'])
                
                # 源地址
                src = self._format_address_with_object(rule['source'], expand_objects)
                cmd_parts.append(f"source {src}")
                
                # 目标地址
                if rule.get('destination'):
                    dst = self._format_address_with_object(rule['destination'], expand_objects)
                    cmd_parts.append(f"destination {dst}")
                
                # 目标端口
                if rule.get('dest_port'):
                    port_str = self._format_port(rule['dest_port'])
                    cmd_parts.append(f"destination-port {port_str}")
                
                lines.append(' '.join(cmd_parts))
        
        return '\n'.join(lines)
    
    def _format_address_with_object(self, addr_config, expand_objects):
        """格式化地址（支持对象引用）"""
        if addr_config['type'] == 'any':
            return 'any'
        elif addr_config['type'] == 'direct':
            ip, cidr = addr_config['address'].split('/')
            wildcard = self._cidr_to_wildcard(int(cidr))
            return f"{ip} {wildcard}"
        elif addr_config['type'] == 'object':
            if expand_objects:
                # 展开对象为具体地址
                return self._expand_address_object(addr_config['object_name'])
            else:
                return f"object-group {addr_config['object_name']}"
    
    def parse_address_object(self, raw_config: str) -> dict:
        """
        解析地址对象组
        输入示例:
            object-group ip address office-networks
             network-object 10.1.0.0 0.0.255.255
             network-object 10.2.0.0 0.0.255.255
        """
        pass
```

### 5.3 厂商特性兼容性

```python
# 特性映射表
FEATURE_SUPPORT = {
    'time_range': {
        'h3c': True,
        'huawei': True,
        'cisco_nx': False
    },
    'object_group': {
        'h3c': True,
        'huawei': 'limited',  # 需要特殊转换
        'cisco_nx': True
    },
    'logging': {
        'h3c': True,
        'huawei': True,
        'cisco_nx': True
    }
}

def validate_features(normalized_config, target_vendor):
    """检查目标厂商是否支持配置中使用的特性"""
    unsupported = []
    
    for rule in normalized_config['rules']:
        if rule.get('options', {}).get('time_range'):
            if not FEATURE_SUPPORT['time_range'].get(target_vendor):
                unsupported.append(f"规则 {rule['seq']}: 时间段功能")
    
    return unsupported
```

## 六、核心功能设计

### 6.1 配置解析与入库

```python
class ConfigParser:
    def __init__(self):
        self.adapters = {
            'h3c': H3CAdapter(),
            'huawei': HuaweiAdapter(),
            'cisco_nx': CiscoNXAdapter()
        }
    
    def parse_device_backup(self, device_id, config_text, vendor):
        """解析设备备份配置"""
        adapter = self.adapters.get(vendor)
        if not adapter:
            raise ValueError(f"不支持的厂商: {vendor}")
        
        # 1. 解析所有对象组
        address_objects = adapter.parse_address_objects(config_text)
        service_objects = adapter.parse_service_objects(config_text)
        
        # 2. 解析 ACL
        acls = adapter.parse_acls(config_text)
        
        # 3. 解析地址前缀列表
        prefix_lists = adapter.parse_prefix_lists(config_text)
        
        # 4. 存储到数据库
        with db.transaction():
            # 先存对象（ACL 可能引用）
            for obj in address_objects:
                self._upsert_address_object(obj)
            for obj in service_objects:
                self._upsert_service_object(obj)
            
            # 再存 ACL
            for acl in acls:
                self._upsert_acl(device_id, acl)
            
            # 最后存前缀列表
            for prefix_list in prefix_lists:
                self._upsert_prefix_list(device_id, prefix_list)
        
        return {
            'address_objects': len(address_objects),
            'service_objects': len(service_objects),
            'acls': len(acls),
            'prefix_lists': len(prefix_lists)
        }
```

### 6.2 配置渲染与导出

```python
class ConfigRenderer:
    def render_acl_for_device(self, acl_id, device_id, options=None):
        """为指定设备渲染 ACL 配置"""
        options = options or {}
        expand_objects = options.get('expand_objects', False)
        
        # 1. 获取设备厂商
        device = db.get_device(device_id)
        vendor = device['vendor_type']
        
        # 2. 获取 ACL 配置
        acl = db.query_one(
            "SELECT normalized_config FROM acl_templates WHERE id = ?",
            [acl_id]
        )
        normalized = json.loads(acl['normalized_config'])
        
        # 3. 选择适配器
        adapter = self.adapters[vendor]
        
        # 4. 如果不展开对象，需要同时输出对象定义
        if not expand_objects and self._has_object_refs(normalized):
            objects = self._collect_dependencies(acl_id)
            
            output = []
            # 先输出对象定义
            for obj in objects['address']:
                output.append(adapter.render_address_object(obj))
            for obj in objects['service']:
                output.append(adapter.render_service_object(obj))
            output.append("")  # 空行分隔
            
            # 再输出 ACL
            output.append(adapter.render_acl(normalized, expand_objects=False))
            
            return '\n'.join(output)
        else:
            return adapter.render_acl(normalized, expand_objects=True)
```

### 6.3 差异检测

```python
class ConfigDiffDetector:
    def detect_drift(self, device_id, acl_template_id):
        """检测设备实际配置与模板的差异"""
        
        # 1. 获取设备当前配置（从最新备份）
        current_config = self._get_device_current_config(device_id)
        
        # 2. 获取模板配置
        template = db.query_one(
            "SELECT normalized_config FROM acl_templates WHERE id = ?",
            [acl_template_id]
        )
        template_config = json.loads(template['normalized_config'])
        
        # 3. 对比差异
        diff = self._compute_diff(current_config, template_config)
        
        # 4. 更新状态
        if diff['has_changes']:
            status = 'drift'
        else:
            status = 'synced'
        
        db.execute(
            """
            UPDATE device_acl_bindings
            SET status = ?, config_diff = ?, last_sync_at = NOW()
            WHERE device_id = ? AND acl_template_id = ?
            """,
            [status, json.dumps(diff), device_id, acl_template_id]
        )
        
        return diff
    
    def _compute_diff(self, current, template):
        """计算配置差异"""
        changes = []
        
        # 对比规则数量
        if len(current['rules']) != len(template['rules']):
            changes.append({
                'type': 'rule_count',
                'current': len(current['rules']),
                'template': len(template['rules'])
            })
        
        # 逐条对比规则
        for i, (cur_rule, tpl_rule) in enumerate(zip(current['rules'], template['rules'])):
            if cur_rule != tpl_rule:
                changes.append({
                    'type': 'rule_diff',
                    'sequence': tpl_rule['seq'],
                    'current': cur_rule,
                    'template': tpl_rule
                })
        
        return {
            'has_changes': len(changes) > 0,
            'changes': changes
        }
```

### 6.4 依赖关系管理

```python
class DependencyManager:
    def check_before_delete(self, object_type, object_id):
        """删除对象前检查依赖"""
        dependencies = db.query(
            """
            SELECT used_by_type, used_by_id
            FROM object_dependencies
            WHERE object_type = ? AND object_id = ?
            """,
            [object_type, object_id]
        )
        
        if dependencies:
            # 有依赖，不能删除
            used_by = []
            for dep in dependencies:
                if dep['used_by_type'] == 'acl':
                    acl = db.get('acl_templates', dep['used_by_id'])
                    used_by.append(f"ACL: {acl['name']}")
                elif dep['used_by_type'] == 'address_object':
                    obj = db.get('address_objects', dep['used_by_id'])
                    used_by.append(f"地址对象: {obj['name']}")
            
            raise DependencyError(f"对象被以下项引用，无法删除: {', '.join(used_by)}")
    
    def get_dependency_tree(self, acl_id):
        """获取 ACL 的完整依赖树（包括嵌套）"""
        # 使用递归查询获取所有依赖
        query = """
        WITH RECURSIVE deps AS (
            -- 直接依赖
            SELECT DISTINCT source_address_object_id AS obj_id, 'address' AS obj_type
            FROM acl_rules WHERE acl_template_id = ? AND source_address_object_id IS NOT NULL
            
            UNION
            
            SELECT DISTINCT dest_address_object_id, 'address'
            FROM acl_rules WHERE acl_template_id = ? AND dest_address_object_id IS NOT NULL
            
            UNION
            
            -- 嵌套依赖
            SELECT e.ref_object_id, 'address'
            FROM deps d
            JOIN address_object_entries e ON d.obj_id = e.address_object_id
            WHERE e.ref_object_id IS NOT NULL
        )
        SELECT DISTINCT * FROM deps
        """
        
        return db.query(query, [acl_id, acl_id])
```

## 七、前端界面设计

### 7.1 策略模板管理页面

```
┌──────────────────────────────────────────────────────┐
│  ACL 模板管理                   [+ 新建]  [导入]  [导出]│
├──────────────────────────────────────────────────────┤
│ 搜索: [____________]  类型: [全部▼]  厂商: [全部▼]   │
├──────────────────────────────────────────────────────┤
│ 名称              类型    编号  规则数  设备数  操作    │
│ office-basic     标准    2000   10     25    [编辑]   │
│ web-access       扩展    3000   15     12    [编辑]   │
│ dmz-protect      扩展    3100    8      5    [编辑]   │
└──────────────────────────────────────────────────────┘
```

### 7.2 ACL 编辑器

```
┌──────────────────────────────────────────────────────┐
│  编辑 ACL: web-access                     [保存] [取消]│
├──────────────────────────────────────────────────────┤
│ 基本信息                                              │
│  名称: [web-access        ]  编号: [3000]            │
│  类型: ● 扩展 ACL  ○ 标准 ACL                        │
│  厂商: [H3C ▼]                                       │
│  描述: [允许办公网访问 Web 服务                    ]  │
├──────────────────────────────────────────────────────┤
│ 规则列表                               [+ 添加规则]   │
│                                                      │
│  规则 5: 允许                            [编辑][删除]│
│    协议: TCP                                         │
│    源地址: 引用对象 "office-networks"                │
│    目标地址: 任意                                     │
│    目标端口: 等于 80, 443                            │
│                                                      │
│  规则 10: 拒绝                           [编辑][删除]│
│    协议: IP                                          │
│    源地址: 任意                                       │
│    目标地址: 任意                                     │
├──────────────────────────────────────────────────────┤
│ 使用此模板的设备 (12)                    [查看详情]   │
│  • bbs1_corp_bj_m01 (已同步)                         │
│  • bbs2_corp_sh_m01 (配置漂移)                       │
│  • ...                                               │
├──────────────────────────────────────────────────────┤
│ 配置预览                                              │
│  [保留引用 ▼]                                        │
│  ┌────────────────────────────────────────────────┐ │
│  │ acl advanced 3000                              │ │
│  │  rule 5 permit tcp source object-group ...    │ │
│  │  rule 10 deny ip source any destination any   │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### 7.3 对象组管理页面

```
┌──────────────────────────────────────────────────────┐
│  地址对象管理                       [+ 新建]  [导入]   │
├──────────────────────────────────────────────────────┤
│ 名称                  类型    条目数  引用次数  操作    │
│ office-networks      组       3       12    [编辑]   │
│ dmz-servers          组       5        8    [编辑]   │
│ vip-192.168.1.1     主机      1        3    [编辑]   │
├──────────────────────────────────────────────────────┤
│  点击查看详情：                                        │
│  ┌────────────────────────────────────────────────┐ │
│  │ office-networks (地址组)                       │ │
│  │                                                │ │
│  │ 包含:                                          │ │
│  │  • 10.1.0.0/16                                │ │
│  │  • 10.2.0.0/16                                │ │
│  │  • 引用: branch-offices                       │ │
│  │                                                │ │
│  │ 被引用于:                                      │ │
│  │  • ACL: web-access (规则 5)                   │ │
│  │  • ACL: app-access (规则 10)                  │ │
│  │  • 地址对象: all-offices                      │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

## 八、实施计划

### 8.1 分阶段实施

**Phase 1: 基础框架（2-3 周）**
- [ ] 数据库表结构设计与创建
- [ ] 基础数据模型和 API
- [ ] 单厂商适配器（H3C 优先）
- [ ] 简单 ACL 解析与存储（不含对象引用）
- [ ] 基础前端界面（列表、查看）

**Phase 2: 核心功能（3-4 周）**
- [ ] 标准 ACL 和扩展 ACL 完整支持
- [ ] 版本管理和历史记录
- [ ] 设备绑定和状态管理
- [ ] 配置渲染和导出
- [ ] 差异检测功能
- [ ] 完善前端编辑器

**Phase 3: 高级特性（2-3 周）**
- [ ] 地址对象和服务对象管理
- [ ] 对象引用支持
- [ ] 依赖关系检查
- [ ] 嵌套对象支持
- [ ] 对象组前端界面

**Phase 4: 多厂商支持（按需）**
- [ ] Huawei 适配器
- [ ] Cisco 适配器
- [ ] 厂商特性兼容性检查
- [ ] 跨厂商配置转换

**Phase 5: 增强功能（按需）**
- [ ] 地址前缀列表支持
- [ ] 批量操作和灰度发布
- [ ] 配置模板智能推荐
- [ ] 配置合规性检查
- [ ] 审计日志

### 8.2 技术栈建议

**后端：**
- Python 3.9+
- FastAPI / Flask
- SQLAlchemy (ORM)
- MySQL 8.0+
- Pydantic (数据验证)

**前端：**
- Vue 3 / React
- Ant Design / Element Plus
- Monaco Editor (配置编辑器)
- ECharts (依赖关系可视化)

### 8.3 关键决策点

1. **对象组优先级**
   - 场景：对象组主要在边界设备使用
   - 建议：Phase 1-2 不支持对象组，Phase 3 再实现
   - 理由：先验证核心流程，避免过早优化

2. **厂商支持顺序**
   - 优先级：根据设备数量和重要性排序
   - 建议：先实现主要厂商（H3C），验证架构合理性后再扩展

3. **配置渲染策略**
   - 展开对象 vs 保留引用：提供选项，由用户选择
   - 默认行为：边界设备保留引用，其他设备展开

## 九、风险与挑战

### 9.1 技术风险

1. **厂商语法差异**
   - 风险：不同厂商的配置语法复杂多变，难以完全覆盖
   - 缓解：采用渐进式支持，优先覆盖常用特性

2. **对象嵌套复杂度**
   - 风险：对象组可能多层嵌套，导致解析和渲染复杂
   - 缓解：限制嵌套层数，提供循环引用检测

3. **配置解析准确性**
   - 风险：备份配置格式可能不规范，解析失败
   - 缓解：增加异常处理和人工审核机制

### 9.2 业务风险

1. **变更风险**
   - 风险：策略模板变更可能影响多个设备
   - 缓解：提供影响范围预览、灰度发布、回滚机制

2. **权限控制**
   - 风险：ACL 属于安全配置，需要严格权限管理
   - 缓解：实施细粒度权限控制和审批流程

### 9.3 性能风险

1. **大规模 ACL 处理**
   - 风险：单个 ACL 可能包含数百条规则
   - 缓解：分页加载、懒加载、配置缓存

2. **依赖关系查询**
   - 风险：递归查询对象依赖可能影响性能
   - 缓解：使用 CTE（公共表达式）、结果缓存

## 十、后续优化方向

1. **AI 辅助**
   - 根据业务需求自动生成 ACL 规则
   - 识别重复或冲突的规则
   - 配置优化建议

2. **可视化增强**
   - ACL 规则流程图
   - 对象依赖关系图谱
   - 策略覆盖范围热力图

3. **合规性检查**
   - 基于安全基线的自动检查
   - 最小权限原则验证
   - 异常访问规则告警

4. **配置仿真**
   - 在线测试 ACL 匹配结果
   - 流量模拟验证

## 附录

### A. 参考资料

- H3C 交换机配置手册
- Huawei 交换机配置手册
- Cisco NX-OS 配置手册

### B. 术语表

- **ACL**: Access Control List，访问控制列表
- **标准 ACL**: 只能基于源 IP 地址过滤的 ACL
- **扩展 ACL**: 支持多维度过滤条件的 ACL
- **地址对象组**: 地址集合的抽象，可被 ACL 引用
- **服务对象组**: 服务/端口集合的抽象，可被 ACL 引用
- **配置漂移**: 设备实际配置与模板不一致的状态

---

*文档维护：请在重大设计变更时更新此文档*
