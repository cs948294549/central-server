# 拓扑管理 API 接口文档

## 基础信息

- **Base URL**: `/topology`
- **认证方式**: JWT Token 或 API Key/Secret
- **返回格式**: JSON

## 接口列表

### 1. 获取拓扑列表

**接口地址**: `GET /topology/list`

**请求参数**: 无

**返回示例**:
```json
{
  "code": 200,
  "message": "查询成功",
  "data": [
    {
      "topology_id": 1,
      "topology_name": "IDC-A核心网络",
      "category_types": ["按机房", "IDC-A", "核心层"],
      "description": "IDC-A机房核心网络拓扑",
      "created_by": "admin",
      "created_at": "2026-08-21 10:00:00",
      "updated_by": "admin",
      "updated_at": "2026-08-21 15:30:00",
      "version": 3
    }
  ]
}
```

**说明**: 
- 返回所有拓扑的基本信息（不包含 topology_json 字段）
- 按更新时间倒序排列

---

### 2. 获取拓扑详情

**接口地址**: `GET /topology/detail/<topology_id>`

**请求参数**: 
- `topology_id`: 拓扑ID（路径参数）

**返回示例**:
```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "topology_id": 1,
    "topology_name": "IDC-A核心网络",
    "category_types": ["按机房", "IDC-A", "核心层"],
    "description": "IDC-A机房核心网络拓扑",
    "topology_json": {
      "config": {},
      "nodes": [
        {"id": "192.168.1.1", "label": "Core-SW-01", "type": "switch"}
      ],
      "edges": [
        {"from": "192.168.1.1", "to": "192.168.1.2", "label": "10G"}
      ],
      "groups": []
    },
    "created_by": "admin",
    "created_at": "2026-08-21 10:00:00",
    "updated_by": "admin",
    "updated_at": "2026-08-21 15:30:00",
    "version": 3
  }
}
```

**说明**: 
- 包含完整的拓扑数据（包括 topology_json）
- topology_json 为拓扑图的完整数据结构

---

### 3. 创建拓扑

**接口地址**: `POST /topology/create`

**请求体**:
```json
{
  "topology_name": "IDC-B核心网络",
  "category_types": ["按机房", "IDC-B", "核心层"],
  "description": "IDC-B机房核心网络拓扑",
  "topology_json": "{}"
}
```

**请求参数说明**:
- `topology_name`: (必填) 拓扑名称，必须唯一
- `category_types`: (可选) 分类标签数组，用于生成树结构
- `description`: (可选) 描述信息
- `topology_json`: (可选) 拓扑数据JSON，默认为 "{}"

**返回示例**:
```json
{
  "code": 200,
  "message": "创建成功",
  "data": {
    "topology_id": 2,
    "version": 1
  }
}
```

**错误返回**:
```json
{
  "code": 400,
  "message": "拓扑名称已存在"
}
```

---

### 4. 更新拓扑

**接口地址**: `POST /topology/update`

**请求体**:
```json
{
  "topology_id": 1,
  "topology_name": "IDC-A核心网络(更新)",
  "category_types": ["按机房", "IDC-A", "核心层"],
  "description": "更新后的描述",
  "topology_json": {
    "config": {},
    "nodes": [...],
    "edges": [...],
    "groups": []
  },
  "version": 3
}
```

**请求参数说明**:
- `topology_id`: (必填) 拓扑ID
- `topology_name`: (可选) 拓扑名称
- `category_types`: (可选) 分类标签数组
- `description`: (可选) 描述信息
- `topology_json`: (可选) 拓扑数据JSON
- `version`: (可选) 当前版本号，用于乐观锁检查

**返回示例**:
```json
{
  "code": 200,
  "message": "更新成功"
}
```

**错误返回**:
```json
{
  "code": 400,
  "message": "数据已被他人修改，请刷新后重试"
}
```

**说明**: 
- 使用乐观锁机制，如果 version 不匹配会返回版本冲突错误
- 更新成功后 version 会自动加1
- 只更新提供的字段，未提供的字段保持不变

---

### 5. 删除拓扑

**接口地址**: `DELETE /topology/delete/<topology_id>`

**请求参数**: 
- `topology_id`: 拓扑ID（路径参数）

**返回示例**:
```json
{
  "code": 200,
  "message": "删除成功"
}
```

**错误返回**:
```json
{
  "code": 400,
  "message": "拓扑不存在"
}
```

---

## 数据结构说明

### category_types 字段
- 类型: JSON数组
- 用途: 用于生成拓扑管理的树形结构
- 示例: `["按机房", "IDC-A", "核心层"]` 表示三级分类
- 前端会根据此字段构建树形目录

### topology_json 字段
- 类型: JSON对象（存储为LONGTEXT）
- 结构:
  ```json
  {
    "config": {},          // 全局配置
    "nodes": [],           // 节点数组
    "edges": [],           // 连接数组
    "groups": []           // 分组数组
  }
  ```
- 说明: 
  - 列表接口不返回此字段（数据量大）
  - 详情接口返回完整数据
  - 创建时可以为空，后续通过更新接口填充

### version 字段
- 类型: INT
- 用途: 乐观锁版本控制
- 规则: 
  - 创建时默认为 1
  - 每次更新自动 +1
  - 更新时如果提交的 version 与数据库不一致，返回版本冲突错误

---

## 错误码说明

- `200`: 成功
- `400`: 参数错误或业务逻辑错误
- `401`: 认证失败
- `403`: 权限不足
- `500`: 服务器内部错误

---

## 注意事项

1. 所有接口都需要认证（JWT Token 或 API Key/Secret）
2. 拓扑名称必须唯一
3. 更新拓扑时建议携带 version 字段进行乐观锁检查
4. topology_json 字段在列表接口中不返回，需要通过详情接口获取
5. category_types 为空数组时，拓扑会显示在根目录下
