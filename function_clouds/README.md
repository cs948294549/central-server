# 云账单查询模块 (function_clouds)

统一管理多云平台的账单查询和分析功能。

## 目录结构

```
function_clouds/
├── __init__.py           # 模块入口
├── tencent_bill.py       # 腾讯云账单查询
└── volcano_bill.py       # 火山云账单查询
```

## 使用方法

### 1. 作为模块调用

```python
from function_clouds import analyze_tencent_bill, format_tencent_report

# 查询腾讯云账单（带标签筛选）
result = analyze_tencent_bill(
    month="2026-08",
    tag_key="24H 网络带宽",
    tag_value="24H 网络带宽",
    include_details=False  # 默认不返回明细
)

# 打印格式化报告
print(format_tencent_report(result))

# 或直接使用返回的字典数据
if result['success']:
    print(f"总费用: {result['summary']['total_cost']} 元")
    print(f"共享带宽: {result['summary']['bandwidth_cost']} 元")
```

### 2. 命令行调用（兼容旧方式）

```bash
# 使用默认标签查询
cd projects/central-server
python tasks/tencent_api.py 2026-08

# 不使用标签筛选
python tasks/tencent_api.py 2026-08 --no-tag

# 包含明细账单
python tasks/tencent_api.py 2026-08 --details

# 火山云账单（待实现）
python tasks/ark_api.py 2026-08
```

## 返回数据结构

```python
{
    "success": True,
    "month": "2026-08",
    "filter": {"tag_key": "...", "tag_value": "..."},
    "total_records": 57,
    "summary": {
        "total_cost": 551665.74,
        "bandwidth_cost": 441108.65,  # 腾讯云特有
        "other_cost": 110557.09,      # 腾讯云特有
        "payment": {
            "cash": 539158.82,
            "transfer": 0.00,
            "incentive": 0.00,
            "voucher": 12506.92
        }
    },
    "products": {
        "共享带宽包": {
            "cost": 441108.65,
            "count": 30,
            "cash": 430000.00,
            "voucher": 11108.65
        },
        ...
    },
    "details": [...]  # 仅当 include_details=True 时包含
}
```

## 配置说明

在 `config/config.py` 中配置：

```python
class Config:
    # 腾讯云
    tencent_SECRET_ID = "your_secret_id"
    tencent_SECRET_KEY = "your_secret_key"
    
    # 火山云（待实现）
    volcano_ACCESS_KEY_ID = "your_access_key"
    volcano_SECRET_ACCESS_KEY = "your_secret_key"
```

## 支持的云平台

- [x] 腾讯云 (Tencent Cloud)
- [ ] 火山云 (Volcano Engine) - 待实现 AK/SK 签名认证

## 开发规范

1. 每个云平台一个独立文件 (`xxx_bill.py`)
2. 必须实现两个函数：
   - `analyze_xxx_bill()` - 返回标准化的字典结构
   - `format_xxx_report()` - 格式化为可读文本
3. 返回结构必须包含 `success`, `month`, `summary`, `products` 字段
4. 默认不返回明细数据，通过 `include_details` 参数控制

---
最后更新: 2026-09-02
