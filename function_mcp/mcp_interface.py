from function_mcp.func_switch import run_cmd, get_vendor
from function_mcp.func_message import sendMessage
from function_mcp.func_cmdb import search_device_list


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
        "name": "search_device_list",
        "description": "通过设备名、SN、IP等信息快速搜索设备，返回设备列表、ARP列表、LLDP信息、mac地址表、接口地址表等相关信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search_key": {"type": "string", "description": "关键字对于设备可模糊匹配，如 dc19 csw"},
            },
            "required": ["search_key"]
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
    }
]


MCP_TOOLS = {
    "run_cmd": run_cmd,
    "search_device_list": search_device_list,
    "send_message": sendMessage,
    "get_vendor": get_vendor,
}
