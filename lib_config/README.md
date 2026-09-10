# function_policys - 策略管理模块

## 模块说明

用于解析和管理交换机策略配置（地址前缀列表、ACL、路由策略等）

## 目录结构

```
function_policys/
├── __init__.py                     # 模块入口
├── README.md                       # 说明文档
│
├── parser_base.py                  # 解析器基类
├── parser_h3c.py                   # H3C 配置解析器
├── parser_huawei.py                # Huawei 配置解析器
├── parser_cisco.py                 # Cisco 配置解析器
│
├── service_template.py             # 模板管理服务
├── service_binding.py              # 设备绑定服务
├── service_deploy.py               # 部署管理服务
├── service_match.py                # 配置匹配服务
│
├── fingerprint.py                  # 配置指纹计算
├── config_diff.py                  # 配置差异对比
└── validator.py                    # 配置验证
```

## 核心功能

### 1. 配置解析（parser_*.py）
- 从设备备份配置解析策略
- 支持 H3C、Huawei、Cisco 等厂商
- 转换为标准化 JSON 模型

### 2. 模板管理（service_template.py）
- 策略模板 CRUD
- 版本管理和历史记录
- 配置指纹计算

### 3. 配置匹配（service_match.py）
- 自动识别功能相同的配置
- 相似度计算
- 智能匹配建议

### 4. 设备绑定（service_binding.py）
- 期望状态管理（应该部署什么）
- 实际状态跟踪（当前是什么）
- 配置漂移检测

### 5. 部署管理（service_deploy.py）
- 部署任务创建和执行
- 支持全量/增量/灰度部署
- 部署历史记录

## 设计文档

- [策略管理数据库设计](../docs/policy_management_database_design.md)
- [配置匹配设计](../docs/policy_template_matching_design.md)
- [地址前缀列表管理](../docs/prefix_list_management_design.md)

## 使用示例

### 解析设备配置

```python
from function_policys.parser_h3c import H3CParser
from function_policys.service_template import TemplateService

# 解析配置
parser = H3CParser()
policies = parser.parse_backup(backup_text)

# 匹配或创建模板
service = TemplateService()
for policy in policies:
    result = service.create_or_match(policy)
```

### 创建部署任务

```python
from function_policys.service_deploy import DeployService

service = DeployService()

# 创建任务
task_id = service.create_task(
    policy_id=123,
    device_ids=[1, 2, 3],
    deploy_type='incremental'
)

# 执行部署
result = service.execute_task(task_id)
```

## 开发计划

- [x] Phase 1: 模块结构
- [ ] Phase 2: 前缀列表解析器
- [ ] Phase 3: 模板管理服务
- [ ] Phase 4: 配置匹配服务
- [ ] Phase 5: 设备绑定
- [ ] Phase 6: 部署功能
- [ ] Phase 7: ACL 支持
- [ ] Phase 8: 对象组支持
