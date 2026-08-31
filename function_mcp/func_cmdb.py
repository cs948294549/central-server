import json
from function_collector.func_search import func_fulltext

def search_device_list(search_key):
    """
    通过设备名、SN、IP等信息快速搜索设备
    返回设备列表、ARP列表、LLDP信息、mac地址表、接口地址表等相关信息
    :param search_key: 搜索关键字（可模糊匹配）
    :return:
    """
    try:
        # 直接调用内部方法，不通过 HTTP
        result = func_fulltext(searchKeys=search_key)

        # 返回 JSON 格式的结果
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        else:
            return json.dumps({
                "code": 0,
                "msg": "查询成功",
                "data": result
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "code": -1,
            "msg": "搜索失败: " + str(e),
            "data": []
        }, ensure_ascii=False)
