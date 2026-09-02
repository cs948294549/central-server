import json
from function_collector.func_search import func_fulltext, get_deviceslist

def location_device(search_key):
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

def search_device_list(sysname, sysdesc_reg=None):
    try:
        # 直接调用内部方法，不通过 HTTP
        if sysdesc_reg:
            result = get_deviceslist({"sysname": sysname, "sysdesc_reg": sysdesc_reg})
        else:
            result = get_deviceslist({"sysname": sysname})

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


def query_cloud_bill(cloud_provider, month, tag_key="24H 网络带宽", tag_value="24H 网络带宽", include_details=False):
    """
    查询云平台账单
    :param cloud_provider: 云平台标识 (tencent/volcano)
    :param month: 账单月份 yyyy-MM
    :param tag_key: 标签键（可选，用于筛选）
    :param tag_value: 标签值（可选，用于筛选）
    :param include_details: 是否包含明细账单（默认False，节省返回内容）
    :return: 格式化的文本报告
    """
    try:
        if cloud_provider.lower() == "tencent":
            from function_clouds.tencent_bill import analyze_tencent_bill, format_tencent_report
            result = analyze_tencent_bill(
                month=month,
                tag_key=tag_key if tag_key else "",
                tag_value=tag_value if tag_value else "",
                include_details=include_details
            )
            return format_tencent_report(result)
        elif cloud_provider.lower() == "volcano":
            from function_clouds.volcano_bill import analyze_volcano_bill, format_volcano_report
            result = analyze_volcano_bill(
                month=month,
                tag_key=tag_key or "",
                tag_value=tag_value or "",
                include_details=include_details
            )
            return format_volcano_report(result)
        else:
            return f"❌ 不支持的云平台: {cloud_provider}\n当前支持: tencent（腾讯云）, volcano（火山云）"
    except Exception as e:
        return f"❌ 查询云账单失败: {str(e)}"


if __name__ == '__main__':
    print(query_cloud_bill("tencent", "2026-09"))