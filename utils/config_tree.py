"""
配置节点树工具

将配置文本根据缩进关系转换为树形结构，便于处理层级配置
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def build_config_tree(config_text: str) -> Optional[List[Dict[str, Any]]]:
    """
    根据配置缩进生成节点树

    将配置文本按照缩进关系解析为树形结构，便于处理层级配置（如 VPN、接口、路由策略等）

    Args:
        config_text: 配置文本

    Returns:
        List[Dict]: 节点树列表，每个节点包含:
            - content: 当前行内容
            - indent: 缩进级别（空格数）
            - child: 子节点列表

        失败返回 None

    示例:
        输入:
            ip vpn-instance VPN1
             route-distinguisher 100:1
             address-family ipv4
              vpn-target 100:1

        输出:
            [
                {
                    "content": "ip vpn-instance VPN1",
                    "indent": 0,
                    "child": [
                        {
                            "content": " route-distinguisher 100:1",
                            "indent": 1,
                            "child": []
                        },
                        {
                            "content": " address-family ipv4",
                            "indent": 1,
                            "child": [
                                {
                                    "content": "  vpn-target 100:1",
                                    "indent": 2,
                                    "child": []
                                }
                            ]
                        }
                    ]
                }
            ]
    """

    def count_spaces(line: str) -> int:
        """计算行首空格数"""
        for i, char in enumerate(line):
            if char != ' ':
                return i
        return len(line)

    # 分行并添加结束标记
    lines = config_text.split("\n")
    lines.append("end")

    root_stack = []

    for line in lines:
        # 跳过空行
        if line.strip() == "":
            continue

        indent = count_spaces(line)
        current_node = {
            "content": line,
            "indent": indent,
            "child": []
        }

        if len(root_stack) == 0:
            # 栈为空，直接入栈
            root_stack.append(current_node)
        else:
            stack_node = root_stack.pop()

            # 当前节点缩进 >= 栈顶节点缩进（同级或子节点）
            if current_node["indent"] >= stack_node["indent"]:
                root_stack.append(stack_node)
                root_stack.append(current_node)
            else:
                # 当前节点缩进 < 栈顶节点缩进（需要合并）
                flag = False
                cache_child = [stack_node]  # 缓存兄弟节点
                cache_indent = stack_node["indent"]

                while len(root_stack) > 0 and current_node["indent"] <= cache_indent:
                    cache_node = root_stack.pop()

                    if cache_indent == cache_node["indent"]:
                        # 缩进相同，是兄弟节点
                        cache_child.insert(0, cache_node)
                    elif cache_indent > cache_node["indent"]:
                        # cache_node 缩进更小，是父节点
                        cache_node["child"] += cache_child
                        cache_child = [cache_node]
                    else:
                        # 异常情况：栈内节点缩进更大（不应该出现）
                        logger.error(f"配置树构建失败: 缩进异常 at '{cache_node['content']}'")
                        return None

                    cache_indent = cache_node["indent"]

                    # 处理特殊情况（华为 banner 等场景：缩进顺序可能为 0 3 2 1 0）
                    if current_node["indent"] >= cache_indent:
                        flag = True
                        root_stack.append(cache_node)
                        root_stack.append(current_node)
                        break

                if not flag:
                    logger.error(f"配置树构建失败: 无法归并节点 '{current_node['content']}'")
                    return None

    # 过滤掉单独的 # 或 ! 行（注释分隔符）
    final_stack = []
    for node in root_stack:
        stripped_content = node["content"].strip()

        if stripped_content in ("#", "!"):
            # 如果注释行有子节点，提取子节点
            if len(node["child"]) > 0:
                final_stack.extend(node["child"])
            # 否则跳过该行
        else:
            final_stack.append(node)

    logger.debug(f"配置树构建完成: 根节点数={len(final_stack)}")
    return final_stack


def find_nodes_by_pattern(tree: List[Dict[str, Any]],
                          pattern: str,
                          use_regex: bool = False) -> List[Dict[str, Any]]:
    """
    在配置树中查找匹配的节点

    Args:
        tree: 配置树
        pattern: 匹配模式（字符串或正则表达式）
        use_regex: 是否使用正则表达式匹配

    Returns:
        List[Dict]: 匹配的节点列表
    """
    import re

    matched_nodes = []

    def search_tree(nodes: List[Dict[str, Any]]):
        for node in nodes:
            content = node["content"].strip()

            if use_regex:
                if re.search(pattern, content):
                    matched_nodes.append(node)
            else:
                if pattern in content:
                    matched_nodes.append(node)

            # 递归搜索子节点
            if node["child"]:
                search_tree(node["child"])

    search_tree(tree)
    return matched_nodes


def print_tree(tree: List[Dict[str, Any]], max_depth: int = -1):
    """
    打印配置树（用于调试）

    Args:
        tree: 配置树
        max_depth: 最大深度（-1 表示不限制）
    """
    def print_node(node: Dict[str, Any], depth: int = 0):
        if max_depth >= 0 and depth > max_depth:
            return

        indent_str = "  " * depth
        content = node["content"].strip()
        print(f"{indent_str}[{depth}] {content}")

        for child in node["child"]:
            print_node(child, depth + 1)

    for node in tree:
        print_node(node)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s - %(message)s'
    )

    # 测试配置（H3C VPN 示例）
    test_config = """
#
sysname Test-Router
#
ip vpn-instance VPN1
 route-distinguisher 100:1
 #
 address-family ipv4
  vpn-target 100:1 import-extcommunity
  vpn-target 100:1 export-extcommunity
 #
 address-family ipv6
  vpn-target 100:1 import-extcommunity
#
ip vpn-instance VPN2
 route-distinguisher 200:2
 address-family ipv4
  vpn-target 200:2 import-extcommunity
  vpn-target 200:2 export-extcommunity
#
interface Vlan-interface100
 ip binding vpn-instance VPN1
 ip address 10.1.1.1 255.255.255.0
#
interface Vlan-interface200
 ip binding vpn-instance VPN2
 ip address 10.2.2.1 255.255.255.0
#
    """

    print("=" * 60)
    print("配置树构建测试")
    print("=" * 60)

    # 构建配置树
    tree = build_config_tree(test_config)

    if tree:
        print(f"\n成功构建配置树，根节点数: {len(tree)}\n")

        print("完整配置树:")
        print("-" * 60)
        print_tree(tree)

        # 测试节点查找
        print("\n" + "=" * 60)
        print("查找测试: 查找所有 VPN 实例")
        print("=" * 60)

        vpn_nodes = find_nodes_by_pattern(tree, r"^ip vpn-instance", use_regex=True)
        print(f"\n找到 {len(vpn_nodes)} 个 VPN 实例:\n")

        for vpn_node in vpn_nodes:
            print(f"VPN: {vpn_node['content'].strip()}")
            print(f"  子节点数: {len(vpn_node['child'])}")
            for child in vpn_node["child"]:
                print(f"    - {child['content'].strip()}")
            print()

        # 测试接口查找
        print("=" * 60)
        print("查找测试: 查找所有接口")
        print("=" * 60)

        intf_nodes = find_nodes_by_pattern(tree, "interface", use_regex=False)
        print(f"\n找到 {len(intf_nodes)} 个接口:\n")

        for intf_node in intf_nodes:
            print(f"接口: {intf_node['content'].strip()}")
            for child in intf_node["child"]:
                print(f"    {child['content'].strip()}")
            print()

    else:
        print("配置树构建失败")
