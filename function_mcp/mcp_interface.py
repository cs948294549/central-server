from function_mcp.func_switch import run_cmd, get_vendor, create_change_order
from function_mcp.func_message import sendMessage
from function_mcp.func_cmdb import search_device_list, location_device, query_cloud_bill, transIP
from function_mcp.func_flow import query_flow_traffic


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
    # {
    #     "name": "send_message",
    #     "description": "发送消息通知（支持点对点和群组消息）",
    #     "inputSchema": {
    #         "type": "object",
    #         "properties": {
    #             "msg": {"type": "string", "description": "消息内容"},
    #             "msg_type": {"type": "string", "description": "消息类型：p2p（点对点）或 group（群组）"},
    #             "receiver": {"type": "string", "description": "接收者ID（p2p为用户ID，group为群组ID）"},
    #         },
    #         "required": ["msg", "msg_type", "receiver"]
    #     }
    # },
    # {
    #     "name": "get_vendor",
    #     "description": "获取设备厂商信息",
    #     "inputSchema": {
    #         "type": "object",
    #         "properties": {
    #             "ip": {"type": "string", "description": "设备IP"},
    #         },
    #         "required": ["ip"]
    #     }
    # },
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
    },
    {
        "name": "transIP",
        "description": "给文本里每一行的 IP 补上 CMDB 归属描述，格式：IP(描述)。用于把 mtr/traceroute 记录的裸 IP 转换成可读的交换机/服务器路径。每行只处理第一个匹配到的 IP，查不到描述的 IP 原样保留。仅覆盖内网交换机与内网服务器，公网 IP（运营商/CDN 等）和未登记的内网 IP 查不到属正常现象，原样返回即可，不代表查询失败。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_text": {"type": "string", "description": "原始文本，如 mtr/traceroute 的执行结果，可多行"},
                "search_type": {"type": "string", "description": "查询类型：switch（按交换机查，返回 sysname）或 server（按服务器查，返回产品名+使用人+描述），默认 switch"},
            },
            "required": ["ip_text"]
        }
    },
    {
        "name": "query_flow_traffic",
        "description": "查询某个网络出口最近 15 分钟的明细 IP 大流量统计（基于 esflow/ElastiFlow）。按源 IP（出方向）和目的 IP（入方向）分别汇总 Top N 的流量、包数、flow 条数及占比，并自动为每个 IP 补上 CMDB 归属描述。用于排查出口大流量 IP、定位异常占用带宽的服务器。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group": {"type": "string", "description": "出口分组名，默认“博兴出口”，可选：博兴出口/博兴入口 / M5机房出口 / M5机房入口"},
                "top_n": {"type": "integer", "description": "每个方向返回前 N 个 IP，默认 5"}
            },
            "required": []
        }
    },
    {
        "name": "create_change_order",
        "description": "创建设备变更工单。用于批量配置网络设备，生成包含执行命令和回滚命令的变更工单。工单创建后所有人可操作（默认assigner为all）。注意：配置命令必须包含进入配置模式的命令（Cisco设备使用'configure terminal'或'conf t'，H3C/华为设备使用'system-view'），然后是具体配置命令。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "order_content": {
                    "type": "object",
                    "description": "工单内容",
                    "properties": {
                        "title": {"type": "string", "description": "工单标题，简要描述变更内容"},
                        "descrip": {"type": "string", "description": "工单详细描述，说明变更目的、影响范围、注意事项等"}
                    },
                    "required": ["title", "descrip"]
                },
                "devices": {
                    "type": "array",
                    "description": "设备配置列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ip": {"type": "string", "description": "设备IP地址"},
                            "cmd_exec": {"type": "string", "description": "执行命令（多行命令用换行符分隔）。必须以进入配置模式的命令开头：Cisco设备用'configure terminal'或'conf t'，H3C/华为设备用'system-view'"},
                            "cmd_roll": {"type": "string", "description": "回滚命令（多行命令用换行符分隔）。必须以进入配置模式的命令开头，用于在变更失败时恢复配置"},
                            "batch": {"type": "integer", "description": "执行批次，用于分批执行，默认为1"},
                            "tag": {"type": "string", "description": "设备标签，用于标识此设备的变更内容"}
                        },
                        "required": ["ip", "cmd_exec", "cmd_roll"]
                    }
                }
            },
            "required": ["order_content", "devices"]
        }
    }
]


MCP_TOOLS = {
    "run_cmd": run_cmd,
    "location_device": location_device,
    "search_device_list": search_device_list,
    "query_cloud_bill": query_cloud_bill,
    "transIP": transIP,
    "query_flow_traffic": query_flow_traffic,
    "create_change_order": create_change_order
}
