# 变更工单系统重构设计文档

## 一、系统概述

### 1.1 目标
在 central-server 后端和 chen_vue 前端中重新实现变更工单管理系统，支持多轮审批流程、设备命令执行、操作日志记录等功能。

### 1.2 技术栈
- **后端**: Flask (central-server)
- **前端**: Vue.js + Element UI (chen_vue)
- **数据库**: MySQL

---

## 二、数据库设计

### 2.1 工单类型表 (op_types)
```sql
CREATE TABLE op_types (
    pid BIGINT AUTO_INCREMENT COMMENT '类型ID',
    name VARCHAR(100) NOT NULL COMMENT '类型名称',
    op_group1 BIGINT COMMENT '审批组1',
    op_group2 BIGINT COMMENT '审批组2',
    op_group3 BIGINT COMMENT '审批组3',
    PRIMARY KEY (pid)
) COMMENT='工单类型配置表';
```

### 2.2 审批分组表 (op_groups)
```sql
CREATE TABLE op_groups (
    pid BIGINT AUTO_INCREMENT COMMENT '分组ID',
    name VARCHAR(100) NOT NULL COMMENT '分组名称',
    op_list TEXT COMMENT '成员列表(逗号分隔的邮箱前缀)',
    PRIMARY KEY (pid)
) COMMENT='审批分组表';
```

### 2.3 工单列表表 (op_lists)
```sql
CREATE TABLE op_lists (
    op_id BIGINT AUTO_INCREMENT COMMENT '工单ID',
    op_type BIGINT NOT NULL COMMENT '工单类型ID',
    title VARCHAR(200) NOT NULL COMMENT '工单标题',
    descrip TEXT COMMENT '工单描述',
    status VARCHAR(2) NOT NULL DEFAULT '00' COMMENT '工单状态',
    username VARCHAR(40) NOT NULL COMMENT '创建人',
    assigner VARCHAR(40) COMMENT '指定执行人',
    is_auto TINYINT DEFAULT 0 COMMENT '是否自动执行',
    popo VARCHAR(100) COMMENT '通知群组',
    create_time VARCHAR(10) COMMENT '创建时间',
    update_time VARCHAR(10) COMMENT '更新时间',
    begin_time VARCHAR(10) COMMENT '变更开始时间',
    finish_time VARCHAR(10) COMMENT '变更结束时间',
    cur_group VARCHAR(200) COMMENT '当前审批组成员列表',
    cur_user VARCHAR(40) COMMENT '当前处理人',
    step_name VARCHAR(50) COMMENT '当前步骤名称',
    step_id INT COMMENT '当前步骤ID',
    node_info TEXT COMMENT '流程节点信息(JSON)',
    PRIMARY KEY (op_id)
) COMMENT='工单列表表';
```

**状态码说明:**
- `00`: 草稿 - 刚创建，内容未填充
- `01`: 待接手 - 变更人提交工单，等待审批人接手
- `02`: 待审批 - 审批人已接手，待审批
- `10`: 审批通过 - 所有审批流程通过
- `20`: 待变更 - 等待开始变更
- `21`: 变更中 - 正在执行变更
- `90`: 变更完成 - 变更成功完成
- `91`: 变更失败 - 变更执行失败
- `92`: 审批拒绝 - 审批被拒绝
- `93`: 变更取消 - 变更被取消

### 2.4 设备命令表 (op_devs)
```sql
CREATE TABLE op_devs (
    pid BIGINT AUTO_INCREMENT COMMENT '记录ID',
    op_id BIGINT NOT NULL COMMENT '工单ID',
    ip VARCHAR(50) NOT NULL COMMENT '设备IP',
    sysname VARCHAR(100) COMMENT '设备名称',
    model VARCHAR(100) COMMENT '设备型号',
    assert VARCHAR(200) COMMENT '断言内容',
    status VARCHAR(2) COMMENT '执行状态',
    cmd_exec TEXT COMMENT '执行命令',
    cmd_roll TEXT COMMENT '回滚命令',
    result TEXT COMMENT '执行结果',
    tag VARCHAR(50) COMMENT '标签',
    is_auto TINYINT DEFAULT 0 COMMENT '是否自动执行',
    pre_check TEXT COMMENT '预检查结果',
    timestamp VARCHAR(10) COMMENT '时间戳',
    PRIMARY KEY (pid),
    KEY idx_op_id (op_id)
) COMMENT='设备命令执行表';
```

### 2.5 审批记录表 (op_approve)
```sql
CREATE TABLE op_approve (
    pid BIGINT AUTO_INCREMENT COMMENT '记录ID',
    op_id BIGINT NOT NULL COMMENT '工单ID',
    op_group BIGINT NOT NULL COMMENT '审批分组ID',
    username VARCHAR(40) NOT NULL COMMENT '审批人',
    status VARCHAR(2) COMMENT '审批状态(10:通过, 92:拒绝)',
    timestamp VARCHAR(10) COMMENT '审批时间',
    PRIMARY KEY (pid),
    KEY idx_op_id (op_id)
) COMMENT='审批记录表';
```

### 2.6 操作日志表 (op_logs)
```sql
CREATE TABLE op_logs (
    pid BIGINT AUTO_INCREMENT COMMENT '记录ID',
    op_id BIGINT NOT NULL COMMENT '工单ID',
    tag VARCHAR(2) COMMENT '日志标签',
    msg LONGTEXT NOT NULL COMMENT '日志内容',
    username VARCHAR(40) COMMENT '操作人',
    timestamp VARCHAR(10) COMMENT '操作时间',
    PRIMARY KEY (pid),
    KEY idx_op_id (op_id)
) COMMENT='操作日志表';
```

**日志标签说明:**
- `01`: 创建工单
- `02`: 修改工单
- `03`: 提交审批
- `04`: 接手工单
- `05`: 审批通过
- `06`: 审批拒绝
- `07`: 开始变更
- `08`: 结束变更
- `09`: 取消变更
- `10`: 执行命令
- `11`: 其他操作

### 2.7 通知群组表 (op_notify)
```sql
CREATE TABLE op_notify (
    pid BIGINT AUTO_INCREMENT COMMENT '记录ID',
    name VARCHAR(100) NOT NULL COMMENT '群组名称',
    descrip VARCHAR(200) COMMENT '描述',
    target VARCHAR(100) NOT NULL COMMENT '群组号',
    PRIMARY KEY (pid)
) COMMENT='通知群组表';
```

---

## 三、审批流程设计

### 3.1 node_info 结构
工单提交时根据 op_types 中配置的审批组生成流程节点信息，存储为 JSON 格式：

```json
[
    {
        "id": 1,
        "title": "提交工单",
        "event": "0",
        "description": "工单已提交",
        "data": ""
    },
    {
        "id": 2,
        "title": "审批一",
        "event": "1",
        "description": "待[审批组1名称]接手",
        "data": {
            "pid": 1,
            "name": "审批组1名称",
            "op_list": "user1,user2,user3"
        }
    },
    {
        "id": 3,
        "title": "审批二",
        "event": "1",
        "description": "待[审批组2名称]接手",
        "data": {
            "pid": 2,
            "name": "审批组2名称",
            "op_list": "user4,user5"
        }
    },
    {
        "id": 4,
        "title": "开始变更",
        "event": "",
        "description": "",
        "data": ""
    },
    {
        "id": 5,
        "title": "变更结束",
        "event": "",
        "description": "",
        "data": ""
    }
]
```

### 3.2 状态流转逻辑

```
草稿(00) 
  ↓ [提交工单]
待接手(01) - cur_group 设置为第一个审批组的成员列表
  ↓ [审批人接手]
待审批(02) - cur_user 设置为接手人
  ↓ [审批]
  ├─ 通过 → 检查是否还有下一轮审批
  │          ├─ 有 → 待接手(01) - cur_group 更新为下一个审批组, step_id+1
  │          └─ 无 → 审批通过(10) → 待变更(20)
  └─ 拒绝 → 审批拒绝(92)

待变更(20)
  ↓ [开始变更]
变更中(21)
  ↓ [变更完成]
  ├─ 成功 → 变更完成(90)
  ├─ 失败 → 变更失败(91)
  └─ 取消 → 变更取消(93)
```

### 3.3 关键字段说明
- **step_id**: 当前流程步骤，对应 node_info 中的 id
- **step_name**: 当前步骤名称，对应 node_info 中的 title
- **cur_group**: 当前审批组的成员列表(逗号分隔)
- **cur_user**: 当前处理人(接手人或审批人)

---

## 四、后端 API 设计

### 4.1 文件结构
```
central-server/
├── api/
│   └── api_change_mgmt.py          # 变更工单 API Blueprint
├── daos/
│   └── dao_change_mgmt.py          # 数据访问层
└── docs/
    └── change_management_design.md  # 本设计文档
```

### 4.2 API 端点列表

#### 4.2.1 工单类型管理
- `GET /api/change/types` - 获取工单类型列表
- `POST /api/change/type` - 创建工单类型
- `PUT /api/change/type/<type_id>` - 更新工单类型
- `DELETE /api/change/type/<type_id>` - 删除工单类型

#### 4.2.2 审批分组管理
- `GET /api/change/groups` - 获取审批分组列表
- `POST /api/change/group` - 创建审批分组
- `PUT /api/change/group/<group_id>` - 更新审批分组
- `DELETE /api/change/group/<group_id>` - 删除审批分组

#### 4.2.3 通知群组管理
- `GET /api/change/notify-groups` - 获取通知群组列表
- `POST /api/change/notify-group` - 创建通知群组
- `PUT /api/change/notify-group/<notify_id>` - 更新通知群组
- `DELETE /api/change/notify-group/<notify_id>` - 删除通知群组

#### 4.2.4 工单管理
- `GET /api/change/orders` - 获取工单列表(支持筛选)
- `GET /api/change/order/<op_id>` - 获取工单详情
- `POST /api/change/order` - 创建工单
- `PUT /api/change/order/<op_id>` - 更新工单
- `DELETE /api/change/order/<op_id>` - 删除工单
- `POST /api/change/order/<op_id>/copy` - 复制工单

#### 4.2.5 工单流程操作
- `POST /api/change/order/<op_id>/submit` - 提交工单
- `POST /api/change/order/<op_id>/takeover` - 接手工单
- `POST /api/change/order/<op_id>/approve` - 审批工单
- `POST /api/change/order/<op_id>/start` - 开始变更
- `POST /api/change/order/<op_id>/end` - 结束变更
- `POST /api/change/order/<op_id>/cancel` - 取消变更

#### 4.2.6 设备命令管理
- `GET /api/change/order/<op_id>/devices` - 获取工单设备列表
- `POST /api/change/order/<op_id>/device` - 添加设备
- `PUT /api/change/device/<dev_id>` - 更新设备命令
- `DELETE /api/change/device/<dev_id>` - 删除设备
- `POST /api/change/order/<op_id>/execute` - 执行设备命令
- `POST /api/change/order/<op_id>/precheck` - 预检查

#### 4.2.7 日志查询
- `GET /api/change/order/<op_id>/logs` - 获取工单日志
- `GET /api/change/order/<op_id>/approvals` - 获取审批记录

---

## 五、前端页面设计

### 5.1 文件结构
```
chen_vue/src/view/pages/
└── change-management/           # 变更工单模块
    ├── index.vue                # 工单列表主页
    ├── detail.vue               # 工单详情页
    ├── components/
    │   ├── OrderForm.vue        # 工单表单组件
    │   ├── DeviceList.vue       # 设备列表组件
    │   ├── ApprovalFlow.vue     # 审批流程组件
    │   └── LogTimeline.vue      # 日志时间线组件
    └── config/
        ├── index.vue            # 配置管理入口
        ├── TypeConfig.vue       # 工单类型配置
        ├── GroupConfig.vue      # 审批分组配置
        └── NotifyConfig.vue     # 通知群组配置
```

### 5.2 页面功能

#### 5.2.1 工单列表页 (index.vue)
- 工单列表展示(表格)
- 筛选条件:
  - 工单ID
  - 工单标题
  - 工单状态(多选)
  - 创建时间范围
  - 创建人
  - 工单类型
  - 设备IP/名称
  - 命令内容
  - "待我处理" 复选框(筛选 cur_group 包含当前用户的工单)
  - 自动化标记
- 操作按钮:
  - 创建工单
  - 查看详情
  - 编辑(仅草稿状态)
  - 删除(仅草稿状态)
  - 复制工单
  - 提交审批
  - 接手/审批(待我处理的工单)

#### 5.2.2 工单详情页 (detail.vue)
- 工单基本信息展示
- 审批流程可视化(步骤条组件)
- 设备列表和命令展示
- 操作日志时间线
- 审批记录展示
- 操作按钮(根据状态和权限动态显示):
  - 编辑
  - 提交审批
  - 接手
  - 审批通过/拒绝
  - 开始变更
  - 结束变更
  - 取消变更
  - 执行命令
  - 预检查

#### 5.2.3 配置管理页 (config/index.vue)
使用 Tab 组件切换三个配置子页面:
- Tab 1: 工单类型配置
- Tab 2: 审批分组配置
- Tab 3: 通知群组配置

---

## 六、核心逻辑实现

### 6.1 提交工单逻辑
```python
def submit_order(op_id, username):
    # 1. 获取工单信息
    order = get_order(op_id)
    
    # 2. 获取工单类型配置
    type_cfg = get_type(order['op_type'])
    
    # 3. 构建 node_info
    node_list = [{"id": 1, "title": "提交工单", "event": "0", "description": "工单已提交", "data": ""}]
    
    # 4. 处理审批组1
    if type_cfg['op_group1']:
        group1 = get_group(type_cfg['op_group1'])
        node_list.append({
            "id": 2, "title": "审批一", "event": "1",
            "description": f"待[{group1['name']}]接手",
            "data": group1
        })
        cur_group = group1['op_list']
        
        # 5. 处理审批组2
        if type_cfg['op_group2']:
            group2 = get_group(type_cfg['op_group2'])
            node_list.append({
                "id": 3, "title": "审批二", "event": "1",
                "description": f"待[{group2['name']}]接手",
                "data": group2
            })
            
            # 6. 处理审批组3
            if type_cfg['op_group3']:
                group3 = get_group(type_cfg['op_group3'])
                node_list.append({
                    "id": 4, "title": "审批三", "event": "1",
                    "description": f"待[{group3['name']}]接手",
                    "data": group3
                })
    
    # 7. 添加变更节点
    node_list.append({"id": len(node_list)+1, "title": "开始变更", "event": "", "description": "", "data": ""})
    node_list.append({"id": len(node_list)+1, "title": "变更结束", "event": "", "description": "", "data": ""})
    
    # 8. 更新工单状态
    update_order(op_id, {
        'status': '01',
        'node_info': json.dumps(node_list),
        'cur_group': cur_group,
        'step_id': 2,
        'step_name': '审批一'
    })
    
    # 9. 记录日志
    add_log(op_id, '03', f'{username} 提交工单', username)
    
    # 10. 发送通知
    send_notification(order['popo'], f'工单 {op_id} 已提交，待 {node_list[1]["data"]["name"]} 接手')
```

### 6.2 审批通过逻辑
```python
def approve_order(op_id, username, approve_status):
    # 1. 获取工单信息
    order = get_order(op_id)
    node_info = json.loads(order['node_info'])
    
    # 2. 记录审批记录
    current_node = node_info[order['step_id'] - 1]
    add_approval_record(op_id, current_node['data']['pid'], username, approve_status)
    
    # 3. 如果拒绝
    if approve_status == '92':
        update_order(op_id, {'status': '92'})
        add_log(op_id, '06', f'{username} 审批拒绝', username)
        send_notification(order['popo'], f'工单 {op_id} 审批被拒绝')
        return
    
    # 4. 如果通过，检查是否还有下一轮审批
    next_step_id = order['step_id'] + 1
    if next_step_id < len(node_info) and node_info[next_step_id - 1]['event'] == '1':
        # 还有下一轮审批
        next_node = node_info[next_step_id - 1]
        update_order(op_id, {
            'status': '01',
            'step_id': next_step_id,
            'step_name': next_node['title'],
            'cur_group': next_node['data']['op_list'],
            'cur_user': ''
        })
        add_log(op_id, '05', f'{username} 审批通过，进入下一轮审批', username)
        send_notification(order['popo'], f'工单 {op_id} {order["step_name"]}通过，待 {next_node["data"]["name"]} 接手')
    else:
        # 所有审批通过
        update_order(op_id, {
            'status': '10',
            'cur_group': '',
            'cur_user': ''
        })
        add_log(op_id, '05', f'{username} 审批通过，所有审批流程完成', username)
        
        # 自动进入待变更状态
        update_order(op_id, {'status': '20'})
        send_notification(order['popo'], f'工单 {op_id} 所有审批通过，进入待变更状态')
```

---

## 七、实施计划

### 7.1 第一阶段: 基础框架搭建
1. 创建数据库表结构
2. 创建后端 API 文件和 DAO 文件
3. 创建前端页面文件结构
4. 实现基础的 CRUD 接口

### 7.2 第二阶段: 配置管理功能
1. 实现工单类型配置页面
2. 实现审批分组配置页面
3. 实现通知群组配置页面

### 7.3 第三阶段: 工单核心功能
1. 实现工单列表页面和筛选功能
2. 实现工单创建和编辑功能
3. 实现设备命令管理
4. 实现工单详情页面

### 7.4 第四阶段: 审批流程
1. 实现提交工单逻辑
2. 实现接手工单逻辑
3. 实现审批逻辑(通过/拒绝)
4. 实现审批流程可视化组件

### 7.5 第五阶段: 变更执行
1. 实现开始变更逻辑
2. 实现命令执行功能
3. 实现预检查功能
4. 实现结束变更逻辑

### 7.6 第六阶段: 日志和通知
1. 实现操作日志记录
2. 实现日志时间线展示
3. 实现通知发送功能
4. 完善各个操作的日志记录

### 7.7 第七阶段: 测试和优化
1. 功能测试
2. 界面优化
3. 性能优化
4. 文档完善

---

## 八、注意事项

1. **权限控制**: 
   - 只有工单创建人可以编辑草稿状态的工单
   - 只有 cur_group 中的成员可以接手工单
   - 只有接手人可以进行审批操作

2. **时间校验**:
   - 变更时间窗口建议在 2AM-6AM
   - 变更时长不建议超过 4 小时

3. **通知机制**:
   - 工单提交时通知审批组
   - 审批通过/拒绝时通知创建人
   - 变更开始/结束时通知相关人员

4. **操作日志**:
   - 所有关键操作都要记录日志
   - 日志内容要清晰明确，包含操作人和时间

5. **数据完整性**:
   - 删除工单类型前检查是否有关联工单
   - 删除审批分组前检查是否被工单类型引用

---

## 九、开发进度

### 已完成
- [x] 设计文档编写
- [x] 数据库表结构设计 (已合并到 `/scripts/db_create.sql`)
- [x] 后端 tables 层实现 (AlterationManageDB.py)
- [x] 后端 API 层实现 (api_change_mgmt.py，URL前缀: `/op`)
- [x] Blueprint 注册到主应用

### 进行中
- [ ] 前端页面开发

### 待完成
- [ ] 数据库表创建
- [ ] 通知功能集成
- [ ] 设备命令执行功能
- [ ] 前端与后端联调
- [ ] 功能测试

---

*文档创建时间: 2026-09-07*
*最后更新时间: 2026-09-07*
