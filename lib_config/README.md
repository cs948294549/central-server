# lib_config - 配置编解码库

## 模块说明

用于解析和生成交换机策略配置（地址前缀列表、ACL、路由策略等），提供配置文本与数据模型之间的双向转换。

## 目录结构

```
lib_config/
├── __init__.py                     # 模块入口
├── README.md                       # 说明文档
├── models.py                       # 标准化数据模型
│
├── parsers/                        # 解析器（配置文本 -> 模型）
│   ├── __init__.py
│   ├── parser_base.py              # 解析器基类
│   └── parser_cisco.py             # Cisco 配置解析器
│
└── encoders/                       # 编码器（模型 -> 配置文本）
    ├── __init__.py
    ├── encode_base.py              # 编码器基类
    └── encode_cisco.py             # Cisco 配置编码器
```

## 核心功能

### 1. 配置解析 (parsers/)
- 从设备备份配置解析策略
- 支持 H3C、Huawei、Cisco 等厂商
- 转换为标准化数据模型

**解析流程：**
配置文本 → 配置树（节点） → 正则匹配 → 标准化模型对象

### 2. 配置编码 (encoders/)
- 从标准化模型生成厂商配置
- 支持多厂商格式输出
- 保证往返转换一致性

**编码流程：**
标准化模型对象 → 厂商特定格式 → 配置文本

### 3. 数据模型 (models.py)
- 标准化配置表示
- 支持序列化（to_dict）和反序列化（from_dict）
- 厂商无关的抽象层

## 使用示例

### 解析配置

```python
from lib_config import get_parser

# 解析 Cisco 配置
parser = get_parser('cisco_nx', config_text)
result = parser.parse(sections=['prefix_lists'])

# 访问解析结果
for prefix_list in result.prefix_lists:
    print(f"前缀列表: {prefix_list.name}")
    for entry in prefix_list.entries:
        print(f"  seq {entry.seq}: {entry.action} {entry.prefix}")

# 转换为字典
data_dict = result.to_dict()
```

### 生成配置

```python
from lib_config import get_encoder

# 准备数据（字典格式）
data = {
    'prefix_lists': [
        {
            'name': 'idc-networks',
            'entries': [
                {
                    'seq': 10,
                    'action': 'permit',
                    'prefix': '172.16.0.0/12',
                    'ge': 16,
                    'le': 24
                }
            ]
        }
    ]
}

# 生成 Cisco 配置
encoder = get_encoder('cisco_nx')
config_text = encoder.encode(data, sections=['prefix_lists'])
print(config_text)
```

### 完整往返转换

```python
from lib_config import get_parser, get_encoder

# 1. 解析配置文本
parser = get_parser('cisco_nx', original_config)
result = parser.parse(sections=['prefix_lists'])

# 2. 转换为字典
data_dict = result.to_dict()

# 3. 编码回配置文本
encoder = get_encoder('cisco_nx')
regenerated_config = encoder.encode(data_dict, sections=['prefix_lists'])
```

## 设计模式

### 解析器设计
- **基类框架**：`BaseParser` 提供通用流程
- **动态方法查找**：通过 `parse_{section}` 命名约定自动调用
- **配置树解析**：基于缩进构建节点树，便于处理层级配置
- **按需解析**：支持 `sections` 参数选择性解析

### 编码器设计
- **基类框架**：`BaseEncoder` 提供通用流程
- **动态方法查找**：通过 `encode_{section}` 命名约定自动调用
- **模型驱动**：从标准化模型生成配置文本
- **按需编码**：支持 `sections` 参数选择性生成

### 注册机制
- 使用装饰器 `@register_parser` 和 `@register_encoder` 自动注册
- 工厂方法 `get_parser()` 和 `get_encoder()` 获取实例
- 支持同一厂商多种格式（如 cisco_nx 和 cisco_ios）

## 扩展指南

### 添加新厂商解析器

```python
from lib_config.parsers.parser_base import BaseParser, register_parser
from lib_config.models import PrefixListConfig

@register_parser('h3c')
class H3CParser(BaseParser):
    def _init_available_sections(self):
        self.available_sections = {'prefix_lists'}
    
    def parse_prefix_lists(self) -> List[PrefixListConfig]:
        # 实现 H3C 格式解析
        pass
```

### 添加新厂商编码器

```python
from lib_config.encoders.encode_base import BaseEncoder, register_encoder
from lib_config.models import PrefixListConfig

@register_encoder('h3c')
class H3CEncoder(BaseEncoder):
    def _init_available_sections(self):
        self.available_sections = {'prefix_lists'}
    
    def encode_prefix_lists(self, prefix_lists: List[PrefixListConfig]) -> str:
        # 实现 H3C 格式生成
        pass
```

## 当前支持

### 厂商
- [x] Cisco NX-OS
- [x] Cisco IOS
- [ ] H3C
- [ ] Huawei

### 策略类型
- [x] 地址前缀列表（Prefix List）
- [ ] 访问控制列表（ACL）
- [ ] 路由策略（Route Policy）
- [ ] 对象组（Object Group）

## 设计文档

- [策略管理数据库设计](../docs/policy_management_database_design.md)
- [配置匹配设计](../docs/policy_template_matching_design.md)
- [地址前缀列表管理](../docs/prefix_list_management_design.md)

## 开发计划

- [x] Phase 1: 模块结构和基类框架
- [x] Phase 2: Cisco 前缀列表解析器
- [x] Phase 3: Cisco 前缀列表编码器
- [x] Phase 4: 往返转换测试
- [ ] Phase 5: H3C 解析器/编码器
- [ ] Phase 6: Huawei 解析器/编码器
- [ ] Phase 7: ACL 支持
- [ ] Phase 8: 对象组支持
