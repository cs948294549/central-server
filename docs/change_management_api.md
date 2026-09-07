# 变更工单管理系统 API 接口文档

## 基础信息
- 基础路径: `/op`
- 认证方式: JWT Token (Header: `Authorization: Bearer <token>`)
- 请求头要求:
  - `Authorization`: Bearer token
  - `Sessionid`: 会话ID
  - `Apptime`: 时间戳
  - `Content-Type`: application/json

---

## 一、工单类型管理

### 1.1 获取工单类型列表
**接口**: `POST /op/type/list`

**请求参数**:
```json
{
  "pid": 1,           // 可选，类型ID
  "name": "网络变更"   // 可选，类型名称(模糊查询)
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "timestamp": 1694073600000,
  "data": [
    {
      "pid": 1,
      "name": "网络设备变更",
      "op_group1": 1,
      "op_group2": 2,
      "op_group3": null
    }
  ]
}
```

### 1.2 创建工单类型
**接口**: `POST /op/type/add`

**请求参数**:
```json
{
  "name": "网络设备变更",    // 必填
  "op_group1": 1,            // 可选，审批组1的ID
  "op_group2": 2,            // 可选，审批组2的ID
  "op_group3": null          // 可选，审批组3的ID
}
```

### 1.3 更新工单类型
**接口**: `POST /op/type/update`

**请求参数**:
```json
{
  "pid": 1,                  // 必填
  "name": "网络设备变更",    // 必填
  "op_group1": 1,
  "op_group2": 2,
  "op_group3": null
}
```

### 1.4 删除工单类型
**接口**: `POST /op/type/delete`

**请求参数**:
```json
{
  "pid": 1   // 必填
}
```

---

## 二、审批分组管理

### 2.1 获取审批分组列表
**接口**: `POST /op/group/list`

**请求参数**:
```json
{
  "pid": 1,              // 可选，分组ID
  "name": "网络运维组"   // 可选，分组名称(模糊查询)
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "data": [
    {
      "pid": 1,
      "name": "网络运维组",
      "op_list": "user1,user2,user3"
    }
  ]
}
```

### 2.2 创建审批分组
**接口**: `POST /op/group/add`

**请求参数**:
```json
{
  "name": "网络运维组",                    // 必填
  "op_list": "user1,user2,user3"          // 可选，成员列表(逗号分隔)
}
```

### 2.3 更新审批分组
**接口**: `POST /op/group/update`

**请求参数**:
```json
{
  "pid": 1,                                // 必填
  "name": "网络运维组",                    // 必填
  "op_list": "user1,user2,user3,user4"
}
```

### 2.4 删除审批分组
**接口**: `POST /op/group/delete`

**请求参数**:
```json
{
  "pid": 1   // 必填
}
```

---

## 三、通知群组管理

### 3.1 获取通知群组列表
**接口**: `POST /op/notify/list`

### 3.2 创建通知群组
**接口**: `POST /op/notify/add`

**请求参数**:
```json
{
  "name": "网络运维群",      // 必填
  "descrip": "网络设备变更通知",  // 可选
  "target": "12345678"      // 必填，群组号
}
```

### 3.3 更新通知群组
**接口**: `POST /op/notify/update`

### 3.4 删除通知群组
**接口**: `POST /op/notify/delete`

---

## 四、工单管理

### 4.1 获取工单列表
**接口**: `POST /op/order/list`

**请求参数**:
```json
{
  "op_id": 1,                    // 可选，工单ID
  "title": "核心交换机",          // 可选，标题(模糊查询)
  "status": ["00", "01"],        // 可选，状态列表
  "username": "zhangsan",        // 可选，创建人
  "op_type": 1,                  // 可选，工单类型ID
  "create_time_start": "1694000000",  // 可选，创建时间起始
  "create_time_end": "1694100000",    // 可选，创建时间结束
  "cur_user": "zhangsan",        // 可选，待我处理(查询cur_group包含该用户的工单)
  "limit": 100                   // 可选，返回数量限制
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "data": [
    {
      "op_id": 1,
      "op_type": 1,
      "title": "核心交换机配置变更",
      "descrip": "更新VLAN配置",
      "status": "01",
      "username": "zhangsan",
      "assigner": "lisi",
      "is_auto": 0,
      "popo": "12345678",
      "create_time": "1694073600",
      "update_time": "1694073600",
      "begin_time": "1694080000",
      "finish_time": "1694083600",
      "cur_group": "user1,user2,user3",
      "cur_user": "",
      "step_name": "审批一",
      "step_id": 2,
      "node_info": "[...]"
    }
  ]
}
```

### 4.2 获取工单详情
**接口**: `POST /op/order/detail`

**请求参数**:
```json
{
  "op_id": 1   // 必填
}
```

### 4.3 创建工单
**接口**: `POST /op/order/add`

**请求参数**:
```json
{
  "op_type": 1,                      // 必填，工单类型ID
  "title": "核心交换机配置变更",      // 必填
  "descrip": "更新VLAN配置",          // 可选
  "assigner": "lisi",                // 可选，指定执行人
  "is_auto": 0,                      // 可选，是否自动执行
  "popo": "12345678",                // 可选，通知群组
  "begin_time": "1694080000",        // 可选，变更开始时间
  "finish_time": "1694083600"        // 可选，变更结束时间
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "op_id": 1
  }
}
```

### 4.4 更新工单
**接口**: `POST /op/order/update`

**请求参数**:
```json
{
  "op_id": 1,                        // 必填
  "title": "核心交换机配置变更",      // 可选
  "descrip": "更新VLAN配置",          // 可选
  "assigner": "lisi",                // 可选
  "begin_time": "1694080000",        // 可选
  "finish_time": "1694083600"        // 可选
}
```

### 4.5 删除工单
**接口**: `POST /op/order/delete`

**请求参数**:
```json
{
  "op_id": 1   // 必填
}
```

### 4.6 复制工单
**接口**: `POST /op/order/copy`

**请求参数**:
```json
{
  "op_id": 1   // 必填，原工单ID
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "复制成功",
  "data": {
    "op_id": 2   // 新工单ID
  }
}
```

---

## 五、工单流程操作

### 5.1 提交工单
**接口**: `POST /op/order/submit`

**请求参数**:
```json
{
  "op_id": 1   // 必填
}
```

**功能说明**:
- 将工单从"草稿(00)"状态提交到"待接手(01)"状态
- 根据工单类型配置生成 node_info (审批流程节点信息)
- 设置 cur_group 为第一个审批组的成员列表
- 记录操作日志
- 发送通知(待实现)

### 5.2 接手工单
**接口**: `POST /op/order/takeover`

**请求参数**:
```json
{
  "op_id": 1   // 必填
}
```

**功能说明**:
- 审批组成员接手工单
- 检查当前用户是否在 cur_group 中
- 将工单状态从"待接手(01)"变为"待审批(02)"
- 设置 cur_user 为当前用户

### 5.3 审批工单
**接口**: `POST /op/order/approve`

**请求参数**:
```json
{
  "op_id": 1,       // 必填
  "status": "10"    // 必填，"10"=通过, "92"=拒绝
}
```

**功能说明**:
- 记录审批结果到 op_approve 表
- 如果拒绝(92)，工单状态变为"审批拒绝(92)"
- 如果通过(10):
  - 检查是否还有下一轮审批
  - 有：工单状态变为"待接手(01)"，更新 cur_group 为下一个审批组
  - 无：工单状态变为"待变更(20)"

### 5.4 开始变更
**接口**: `POST /op/order/start`

**请求参数**:
```json
{
  "op_id": 1   // 必填
}
```

**功能说明**:
- 将工单状态从"待变更(20)"变为"变更中(21)"

### 5.5 结束变更
**接口**: `POST /op/order/end`

**请求参数**:
```json
{
  "op_id": 1,       // 必填
  "status": "90"    // 必填，"90"=成功, "91"=失败
}
```

**功能说明**:
- 将工单状态从"变更中(21)"变为最终状态
- "90": 变更完成
- "91": 变更失败

### 5.6 取消变更
**接口**: `POST /op/order/cancel`

**请求参数**:
```json
{
  "op_id": 1   // 必填
}
```

**功能说明**:
- 将工单状态变为"变更取消(93)"

---

## 六、设备命令管理

### 6.1 获取设备列表
**接口**: `POST /op/device/list`

**请求参数**:
```json
{
  "op_id": 1   // 必填
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "data": [
    {
      "pid": 1,
      "op_id": 1,
      "ip": "10.1.1.1",
      "sysname": "core-sw-01",
      "model": "Cisco N9K",
      "assert": "",
      "status": "",
      "cmd_exec": "vlan 100\n name test",
      "cmd_roll": "no vlan 100",
      "result": "",
      "tag": "",
      "is_auto": 0,
      "pre_check": "",
      "timestamp": "1694073600"
    }
  ]
}
```

### 6.2 添加设备
**接口**: `POST /op/device/add`

**请求参数**:
```json
{
  "op_id": 1,                       // 必填
  "ip": "10.1.1.1",                 // 必填
  "sysname": "core-sw-01",          // 可选
  "model": "Cisco N9K",             // 可选
  "assert": "",                     // 可选，断言内容
  "cmd_exec": "vlan 100\n name test",  // 可选，执行命令
  "cmd_roll": "no vlan 100",        // 可选，回滚命令
  "tag": "",                        // 可选
  "is_auto": 0                      // 可选
}
```

### 6.3 更新设备
**接口**: `POST /op/device/update`

**请求参数**:
```json
{
  "pid": 1,                         // 必填
  "ip": "10.1.1.1",                 // 可选
  "sysname": "core-sw-01",          // 可选
  "cmd_exec": "vlan 100\n name test"  // 可选
}
```

### 6.4 删除设备
**接口**: `POST /op/device/delete`

**请求参数**:
```json
{
  "pid": 1   // 必填
}
```

---

## 七、日志查询

### 7.1 获取工单日志
**接口**: `POST /op/log/list`

**请求参数**:
```json
{
  "op_id": 1   // 必填
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "data": [
    {
      "pid": 1,
      "op_id": 1,
      "tag": "01",
      "msg": "zhangsan 创建工单",
      "username": "zhangsan",
      "timestamp": "1694073600"
    }
  ]
}
```

### 7.2 获取审批记录
**接口**: `POST /op/approval/list`

**请求参数**:
```json
{
  "op_id": 1   // 必填
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "data": [
    {
      "pid": 1,
      "op_id": 1,
      "op_group": 1,
      "username": "lisi",
      "status": "10",
      "timestamp": "1694074000"
    }
  ]
}
```

---

## 八、状态码说明

### 工单状态 (op_lists.status)
| 状态码 | 状态名称 | 说明 |
|-------|---------|------|
| 00 | 草稿 | 刚创建，内容未填充 |
| 01 | 待接手 | 变更人提交工单，等待审批人接手 |
| 02 | 待审批 | 审批人已接手，待审批 |
| 10 | 审批通过 | 所有审批流程通过 |
| 20 | 待变更 | 等待开始变更 |
| 21 | 变更中 | 正在执行变更 |
| 90 | 变更完成 | 变更成功完成 |
| 91 | 变更失败 | 变更执行失败 |
| 92 | 审批拒绝 | 审批被拒绝 |
| 93 | 变更取消 | 变更被取消 |

### 日志标签 (op_logs.tag)
| 标签 | 说明 |
|-----|------|
| 01 | 创建工单 |
| 02 | 修改工单 |
| 03 | 提交审批 |
| 04 | 接手工单 |
| 05 | 审批通过 |
| 06 | 审批拒绝 |
| 07 | 开始变更 |
| 08 | 结束变更 |
| 09 | 取消变更 |
| 10 | 执行命令 |
| 11 | 其他操作 |

---

## 九、错误码说明

| 错误码 | 说明 |
|-------|------|
| 0 | 成功 |
| 1 | 一般错误 |
| 400 | 参数错误 |
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

*文档更新时间: 2026-09-07*
