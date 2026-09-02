from function_mcp.func_switch import run_cmd, get_vendor
from function_mcp.func_message import sendMessage
from function_mcp.func_cmdb import search_device_list, location_device, query_cloud_bill


# --------------------------
# MCP 工具定义 (纯手写，不依赖 SDK)
# --------------------------
MCP_TOOLS_prompt = [
    {
        "name": "run_cmd",
        "description": "登录交换机设备执行命令，获取执行结果",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip": {"type": "string", "description": "交换机IP"},
                "cmds": {"type": "array", "description": "需要执行的命令列表"},
                "vendor": {"type": "string", "description": "设备厂商，没有获取到具体的信息就不填，可选[h3c/huawei/cisco_nx (nx系列)/cisco_xr(非nx系列)]"},
            },
            "required": ["ip", "cmds"]
        }
    },
    {
        "name": "location_device",
        "description": "用于定位设备并获取详细网络信息。输入设备名/SN/IP等关键字，返回该设备的多维度数据（设备信息、ARP表、LLDP邻居、MAC地址表、接口IP表等）。注意：返回数据有数量限制，适合查询单个或少量设备的详细信息，不适合批量获取完整列表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search_key": {"type": "string", "description": "关键字对于设备可模糊匹配，如 dc19 csw"},
            },
            "required": ["search_key"]
        }
    },
    {
        "name": "search_device_list",
        "description": "用于搜索并返回完整的设备列表。仅通过设备名（sysname）和设备自身描述信息（sysdesc，包含型号、版本等）进行筛选。返回完整的匹配设备列表，但仅包含设备基本信息（IP、设备名、型号、版本等），不包含ARP/LLDP/MAC表等详细数据。适合需要获取完整设备清单的场景。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sysname": {"type": "string", "description": "关键字对于设备可模糊匹配，如 dc19 csw"},
                "sysdesc_reg": {"type": "string", "description": "设备描述中可带设备型号，如 N9K-C9336C-FX2"},
            },
            "required": ["sysname"]
        }
    },
    {
        "name": "send_message",
        "description": "发送消息通知（支持点对点和群组消息）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "msg": {"type": "string", "description": "消息内容"},
                "msg_type": {"type": "string", "description": "消息类型：p2p（点对点）或 group（群组）"},
                "receiver": {"type": "string", "description": "接收者ID（p2p为用户ID，group为群组ID）"},
            },
            "required": ["msg", "msg_type", "receiver"]
        }
    },
    {
        "name": "get_vendor",
        "description": "获取设备厂商信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip": {"type": "string", "description": "设备IP"},
            },
            "required": ["ip"]
        }
    },
    {
        "name": "query_cloud_bill",
        "description": "查询云平台账单信息，支持腾讯云和火山云。可按标签筛选，返回费用汇总、产品分类、支付方式等信息。默认不返回明细账单以节省内容。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cloud_provider": {"type": "string", "description": "云平台标识：tencent（腾讯云）或 volcano（火山云）"},
                "month": {"type": "string", "description": "账单月份，格式：yyyy-MM，如 2026-08"},
                "tag_key": {"type": "string", "description": "标签键（可选），用于筛选特定标签的资源，如：24H 网络带宽"},
                "tag_value": {"type": "string", "description": "标签值（可选），配合tag_key使用，如：24H 网络带宽"},
                "include_details": {"type": "boolean", "description": "是否包含明细账单（默认false），设为true时返回每条资源的详细信息"}
            },
            "required": ["cloud_provider", "month"]
        }
    }
]


MCP_TOOLS = {
    "run_cmd": run_cmd,
    "location_device": location_device,
    "send_message": sendMessage,
    "get_vendor": get_vendor,
    "search_device_list": search_device_list,
    "query_cloud_bill": query_cloud_bill
}
