import difflib
import re
# 样式
'''
增加
删除
修改的
'''


def getMaxDict(label_dict):
    max_labels = {}
    while len(label_dict.keys()) > 0:
        max_cost = 0
        max_label = ""
        for i in label_dict.keys():
            if int(label_dict[i]) > max_cost:
                max_cost = int(label_dict[i])
                max_label = i

        if max_label != "" and max_cost > 0:
            max_labels[max_label] = max_cost
            max_l, max_r = max_label.split("_")
            del_labels = []
            for i in label_dict.keys():
                pairs = i.split("_")
                if len(pairs) == 2:
                    if pairs[0] == max_l:
                        del_labels.append(i)
                    if pairs[1] == max_r:
                        del_labels.append(i)
                    if pairs[0] > max_l and pairs[1] > max_r:
                        pass
                    elif pairs[0] < max_l and pairs[1] < max_r:
                        pass
                    else:
                        del_labels.append(i)

            for i in del_labels:
                if i in label_dict.keys():
                    del label_dict[i]
        else:
            del_labels = []
            for i in label_dict.keys():
                if label_dict[i] == 0:
                    del_labels.append(i)
            for i in del_labels:
                if i in label_dict.keys():
                    del label_dict[i]
    return max_labels

# 块儿不同，对比行
def compareLines(src_lines, dst_lines):
    ss = difflib.ndiff(src_lines, dst_lines)
    sequences = []
    start_flag = False
    seq_cache = {"type": "conflict", "dels": [], "adds": []}
    for i in ss:
        if i[0] == " ":
            if start_flag is True:
                sequences.append(seq_cache)
                seq_cache = {"type": "conflict", "dels": [], "adds": []}
                start_flag = False
            sequences.append({"type": "normal", "value": i[2:]})
        elif i[0] in ["+", "-"]:
            if start_flag is False:
                start_flag = True
            if i[0] == "+":
                seq_cache["adds"].append(i[2:])
            if i[0] == "-":
                seq_cache["dels"].append(i[2:])
        else:
            # print("不识别", i)
            pass
    sequences.append(seq_cache)

    src_lines = []
    dst_lines = []

    for item_seq in sequences:
        if item_seq["type"] == "normal":
            if "\n" in item_seq["value"]:
                for txt in item_seq["value"].split("\n"):
                    src_lines.append({"type": "same", "value": txt})
                    dst_lines.append({"type": "same", "value": txt})
            else:
                src_lines.append({"type": "same", "value": item_seq["value"]})
                dst_lines.append({"type": "same", "value": item_seq["value"]})
        else:
            dd_src = []
            dd_dst = []

            cost_dict = {}
            for item_del_idx in range(0, len(item_seq["dels"])):
                for item_add_idx in range(0, len(item_seq["adds"])):
                    _, _, cost = compareStrCol(item_seq["dels"][item_del_idx], item_seq["adds"][item_add_idx])
                    cost_dict[str(item_del_idx) + "_" + str(item_add_idx)] = cost
            # print("1-------", cost_dict)
            max_dict = getMaxDict(cost_dict)
            # print("2-------", max_dict)
            for item_del_idx in range(0, len(item_seq["dels"])):
                is_confilict = False
                label_del = str(item_del_idx) + "_"
                label_key = ""
                for key in max_dict.keys():
                    if key.startswith(label_del):
                        label_key = int(key.split("_")[1])
                        # print(label_del, label_key)
                        is_confilict = True

                if is_confilict is True:
                    if "\n" in item_seq["dels"][item_del_idx]:
                        src_, dst_ = compareLines(src_lines=item_seq["dels"][item_del_idx].split("\n"),
                                                  dst_lines=item_seq["adds"][label_key].split("\n"))
                        src_lines += src_
                        dd_src += src_
                    else:
                        src_, dst_, cost = compareStrCol(item_seq["dels"][item_del_idx], item_seq["adds"][label_key])
                        # print(item_del_idx, label_key)
                        # print(src_, "|", dst_, cost)
                        src_lines.append({"type": "chg", "value": src_})
                        dd_src.append({"type": "chg", "value": src_})
                else:
                    if "\n" in item_seq["dels"][item_del_idx]:
                        for txt in item_seq["dels"][item_del_idx].split("\n"):
                            src_lines.append({"type": "del", "value": "\0-" + txt + "\1"})
                            dd_src.append({"type": "del", "value": "\0-" + txt + "\1"})
                    else:
                        src_lines.append({"type": "del", "value": "\0-" + item_seq["dels"][item_del_idx] + "\1"})
                        dd_src.append({"type": "del", "value": "\0-" + item_seq["dels"][item_del_idx] + "\1"})

            for item_add_idx in range(0, len(item_seq["adds"])):
                is_confilict = False
                label_add = "_" + str(item_add_idx)
                label_key = ""
                for key in max_dict.keys():
                    if key.endswith(label_add):
                        label_key = int(key.split("_")[0])
                        # print(label_add, label_key)
                        is_confilict = True

                if is_confilict is True:
                    if "\n" in item_seq["adds"][item_add_idx]:
                        src_, dst_ = compareLines(src_lines=item_seq["dels"][label_key].split("\n"),
                                                  dst_lines=item_seq["adds"][item_add_idx].split("\n"))
                        dst_lines += dst_
                        dd_dst += dst_
                    else:
                        src_, dst_, cost = compareStrCol(item_seq["dels"][label_key], item_seq["adds"][item_add_idx])
                        # print(label_key, item_add_idx)
                        # print(src_, "|", dst_, cost)
                        dst_lines.append({"type": "chg", "value": dst_})
                        dd_dst.append({"type": "chg", "value": dst_})
                else:
                    if "\n" in item_seq["adds"][item_add_idx]:
                        for txt in item_seq["adds"][item_add_idx].split("\n"):
                            dst_lines.append({"type": "add", "value": "\0+" + txt + "\1"})
                            dd_dst.append({"type": "add", "value": "\0+" + txt + "\1"})
                    else:
                        dst_lines.append({"type": "add", "value": "\0+" + item_seq["adds"][item_add_idx] + "\1"})
                        dd_dst.append({"type": "add", "value": "\0+" + item_seq["adds"][item_add_idx] + "\1"})

            # print("==============")
            # for i in dd_src:
            #     print(i)
            # for i in dd_dst:
            #     print(i)
            # print("===============")
    return src_lines, dst_lines


# 行不同，对比明细，返回原始字符串
def compareStrCol(src_txt, dst_txt):
    ss = difflib.ndiff(str(src_txt), str(dst_txt))

    ret_src = ""
    ret_dst = ""

    src_f = False
    dst_f = False
    lines = []
    current_line = 0
    for i in ss:
        # print(i, current_line)
        if i[0] == "-":
            if current_line > 0:
                lines.append(current_line)
                current_line = 0
            if src_f is False:
                ret_src += "\0-" + i[2]
                src_f = True
            else:
                ret_src += i[2]
        if i[0] == "+":
            if current_line > 0:
                lines.append(current_line)
                current_line = 0
            if dst_f is False:
                ret_dst += "\0+" + i[2]
                dst_f = True
            else:
                ret_dst += i[2]
        if i[0] == " ":
            if src_f is True:
                ret_src += "\1" + i[2]
                src_f = False
            else:
                ret_src += i[2]

            if dst_f is True:
                ret_dst += "\1" + i[2]
                dst_f = False
            else:
                ret_dst += i[2]

            if dst_f is False and src_f is False:
                current_line += 1
    if src_f is True:
        ret_src += "\1"

    if dst_f is True:
        ret_dst += "\1"

    src_ret = ret_src
    dst_ret = ret_dst
    # .replace('\0+', '[+').replace('\0-', '[-').replace('\1', ']')

    if len(lines) > 0:
        cost = max(lines)
    else:
        cost = 0
    # print(src_ret)
    # print("=============", cost)
    # print(dst_ret)
    return src_ret, dst_ret, cost


def genHtmlTamplate(src_list, dst_list, numlines=-1):
    tmp_prefix = '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
          "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html>

<head>
    <meta http-equiv="Content-Type"
          content="text/html; charset=utf-8" />
    <title></title>
    <style type="text/css">
        table.diff {font-family:Courier; border:medium; width: 1000px;white-space: pre-line;}
        .diff_header {background-color:#e0e0e0}
        td.diff_header {text-align:right; width: 50px;}
td {word-break:break-all; text-align: left}
        .diff_next {background-color:#c0c0c0}
        .diff_add {background-color:#aaffaa}
        .diff_chg {background-color:#ffff77}
        .diff_sub {background-color:#ffaaaa}
    </style>
</head>

<body>

    <table class="diff" id="difflib_chg_to0__top"
           cellspacing="0" cellpadding="0" rules="groups" >
        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
    '''
    tmp_ending = '''
    </table>
    <table class="diff" summary="Legends">
        <tr> <th colspan="2"> Legends </th> </tr>
        <tr> <td> <table border="" summary="Colors">
                      <tr><th> Colors </th> </tr>
                      <tr><td class="diff_add">&nbsp;Added&nbsp;</td></tr>
                      <tr><td class="diff_chg">Changed</td> </tr>
                      <tr><td class="diff_sub">Deleted</td> </tr>
                  </table></td>
             <td> <table border="" summary="Links">
                      <tr><th colspan="2"> Links </th> </tr>
                      <tr><td>(f)irst change</td> </tr>
                      <tr><td>(n)ext change</td> </tr>
                      <tr><td>(t)op</td> </tr>
                  </table></td> </tr>
    </table>
</body>

</html>
'''

    index_url = 0
    l_key = 0
    r_key = 0
    temp_lists = []
    while l_key < len(src_list) or r_key < len(dst_list):
        if l_key < len(src_list):
            if src_list[l_key]["type"] == "del":
                temp_lists.append(
                    {"type": "del", "l_index": l_key + 1, "l_value": src_list[l_key]["value"], "r_index": -1,
                     "r_value": "",
                     "next_id": index_url + 1})
                l_key += 1
                index_url += 1
                continue
        if r_key < len(dst_list):
            if dst_list[r_key]["type"] == "add":
                temp_lists.append(
                    {"type": "add", "l_index": -1, "l_value": "", "r_index": r_key + 1,
                     "r_value": dst_list[r_key]["value"],
                     "next_id": index_url + 1})
                r_key += 1
                index_url += 1
                continue
        if l_key < len(src_list) and r_key < len(dst_list):
            if src_list[l_key]["type"] == "chg" and dst_list[r_key]["type"] == "chg":
                temp_lists.append(
                    {"type": "chg", "l_index": l_key + 1, "l_value": src_list[l_key]["value"], "r_index": r_key + 1,
                     "r_value": dst_list[r_key]["value"],
                     "next_id": index_url + 1})
                index_url += 1
            else:
                temp_lists.append(
                    {"type": "same", "l_index": l_key + 1, "l_value": src_list[l_key]["value"], "r_index": r_key + 1,
                     "r_value": dst_list[r_key]["value"],
                     "next_id": -1})
            l_key += 1
            r_key += 1

    def split_feature(tmp_list, split_num):
        if split_num > 0:
            tag_list = []
            for row_id in range(0, len(tmp_list)):
                if tmp_list[row_id]["type"] != "same":
                    if row_id - split_num >= 0:
                        start = row_id - split_num
                    else:
                        start = 0

                    if row_id + split_num <= len(tmp_list) - 1:
                        end = row_id + split_num
                    else:
                        end = len(tmp_list) - 1
                    tag_list = list(set(tag_list).union(set([i for i in range(start, end + 1)])))

            flag = False
            responds = []
            respond_cache = []
            for i in range(0, len(tmp_list)):
                if i in tag_list:
                    if flag is False:
                        flag = True
                    respond_cache.append(tmp_list[i])
                else:
                    if flag is True:
                        responds.append(respond_cache)
                        respond_cache = []
                        flag = False
                    else:
                        pass

            if flag is True:
                responds.append(respond_cache)

            return responds
        else:
            return [tmp_list]

    html_list = split_feature(temp_lists, split_num=numlines)

    table_html = ""
    for table_id in range(0, len(html_list)):
        table_html += '<tbody>'
        for row_id in range(0, len(html_list[table_id])):
            row_html = '<tr>'
            # 添加head
            if table_id == 0 and row_id == 0:
                row_html += '<td class="diff_next"><a href="#difflib_chg_1">f</a></td>'
            elif table_id == (len(html_list) - 1) and row_id == (len(html_list[table_id]) - 1):
                row_html += '<td class="diff_next"><a href="#difflib_chg_to0__top">t</a></td>'
            else:
                if html_list[table_id][row_id]["next_id"] > -1:
                    nn = html_list[table_id][row_id]["next_id"]
                    row_html += '<td class="diff_next" id="difflib_chg_{nid}"><a href="#difflib_chg_{nid_n}">n</a></td>'.format(
                        nid=nn, nid_n=nn + 1)
                else:
                    row_html += '<td class="diff_next"></td>'

            # 添加序号及内容
            if html_list[table_id][row_id]["type"] == "same":
                row_html += '<td class="diff_header">{l_index}</td><td>{l_value}</td>'.format(
                    l_index=html_list[table_id][row_id]["l_index"],
                    l_value=html_list[table_id][row_id]["l_value"])
                row_html += '<td class="diff_header">{r_index}</td><td>{r_value}</td>'.format(
                    r_index=html_list[table_id][row_id]["r_index"],
                    r_value=html_list[table_id][row_id]["r_value"])
            elif html_list[table_id][row_id]["type"] == "add":
                row_html += '<td class="diff_header"></td><td></td>'
                row_html += '<td class="diff_header">{r_index}</td><td>{r_value}</td>'.format(
                    r_index=html_list[table_id][row_id]["r_index"],
                    r_value=html_list[table_id][row_id]["r_value"].replace('\0+', '<span class="diff_add">'))
            elif html_list[table_id][row_id]["type"] == "del":
                row_html += '<td class="diff_header">{l_index}</td><td>{l_value}</td>'.format(
                    l_index=html_list[table_id][row_id]["l_index"],
                    l_value=html_list[table_id][row_id]["l_value"].replace('\0-', '<span class="diff_sub">'))
                row_html += '<td class="diff_header"></td><td></td>'
            elif html_list[table_id][row_id]["type"] == "chg":
                row_html += '<td class="diff_header">{l_index}</td><td>{l_value}</td>'.format(
                    l_index=html_list[table_id][row_id]["l_index"],
                    l_value=html_list[table_id][row_id]["l_value"].replace('\0-', '<span class="diff_sub">'))
                row_html += '<td class="diff_header">{r_index}</td><td>{r_value}</td>'.format(
                    r_index=html_list[table_id][row_id]["r_index"],
                    r_value=html_list[table_id][row_id]["r_value"].replace('\0+', '<span class="diff_add">'))
            else:
                print("异常序列", html_list[table_id][row_id])
            row_html += '</tr>'

            table_html += row_html

        table_html += '</tbody>'

    table_html = table_html.replace('\0+', '<span class="diff_add">'). \
        replace('\0-', '<span class="diff_sub">'). \
        replace('\0^', '<span class="diff_chg">'). \
        replace('\1', '</span>'). \
        replace('\t', '&nbsp;')
    return tmp_prefix + table_html + tmp_ending



def check_diff(text_src, text_target, flag):
    src_lines = re.split(r"\n(?=\S)", text_src)
    src_lines_split = text_src.split("\n")
    dst_lines = re.split(r"\n(?=\S)", text_target)
    dst_lines_split = text_target.split("\n")
    if len(src_lines_split) - len(src_lines) > 10:
        ret_src, ret_dst = compareLines(src_lines=src_lines, dst_lines=dst_lines)
        if flag is True:
            ret = genHtmlTamplate(src_list=ret_src, dst_list=ret_dst, numlines=-1)
            return ret
        else:
            ret = genHtmlTamplate(src_list=ret_src, dst_list=ret_dst, numlines=5)
            return ret
    else:
        hd = difflib.HtmlDiff()
        if flag is True:
            diff = hd.make_file(src_lines_split, dst_lines_split)
        else:
            diff = hd.make_file(src_lines_split, dst_lines_split, context=True, numlines=5)
        diff = diff.replace("table.diff {font-family:Courier; border:medium;}",
                            "table.diff {font-family:Courier; border:medium; width: 1000px;}") \
            .replace("td.diff_header {text-align:right}",
                     "td.diff_header {text-align:right; width: 50px;}\ntd {word-break:break-all; text-align: left}") \
            .replace(" nowrap=\"nowrap\"", "")

        return diff

if __name__ == '__main__':
    str1 = '''#
vlan 1
#
vlan 101 to 112
#
vlan 201
#
vlan 207
#
vlan 1101
vlan 1201
#
vlan 1207
1
2
3
4
6
'''
    str2 = '''#
vlan 1
#
vlan 101 to 102
vlan 101 to 112
#
vlan 201
#
vlan 207
#
vlan 1101 to 1102
vlan 2222
#
vlan 1207
5
6'''
    # compareStrCol(str1, str2)
    # src_tt = ""
    # dst_tt = ""
    # with open("../tmp/3.txt", "r") as f:
    #     src_tt = f.read()
    # with open("../tmp/4.txt", "r") as f:
    #     dst_tt = f.read()
    # src_tt_a = re.split(r"\n(?=\S)", src_tt)
    # dst_tt_a = re.split(r"\n(?=\S)", dst_tt)

    # from Module.ConfigLog import check_diff
    # ret = check_diff(text_src=str1, text_target=str2, flag=True)
    # print(ret)

    ret_src, ret_dst = compareLines(str1.split("\n"), str2.split("\n"))
    # ret_src, ret_dst = compareLines(src_tt_a, dst_tt_a)
    print("-----------------")
    ret = genHtmlTamplate(src_list=ret_src, dst_list=ret_dst, numlines=5)
    print(ret)
