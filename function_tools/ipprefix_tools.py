from utils.ipaddr import decimalism2ip,ip2decimalism,length2netmask,netmask2length

def checkNet(src_net, target_net):
    src_ip, src_mask = src_net.split("/")
    srcint = ip2decimalism(src_ip)
    srcmaskint = ip2decimalism(length2netmask(int(src_mask)))
    src_start = (srcint & srcmaskint)
    src_end = (srcint | (~srcmaskint) & 0xFFFFFFFF)

    dst_ip, dst_mask = target_net.split("/")
    dstint = ip2decimalism(dst_ip)
    dstmaskint = ip2decimalism(length2netmask(int(dst_mask)))
    dst_start = (dstint & dstmaskint)
    dst_end = (dstint | (~dstmaskint) & 0xFFFFFFFF)

    if src_start >= dst_start and src_end <= dst_end:
        return True
    else:
        return False

def mergeNet(net_ist):
    try:
        finall_ips = []
        merge_dict = {}
        ip_stack = []
        for i in net_ist:
            if i not in ip_stack:
                ip_stack.append(i)

        while len(ip_stack) > 0:
            ip_one = ip_stack.pop(0)
            if ip_one.strip() == "":
                continue
            src_ip, src_mask = ip_one.split("/")
            src_ip = decimalism2ip(ip2decimalism(src_ip) & ip2decimalism(length2netmask(int(src_mask))))

            new_mask = length2netmask(int(src_mask) - 1)
            new_maskint = ip2decimalism(new_mask)
            new_ip = decimalism2ip(ip2decimalism(src_ip) & new_maskint)
            new_mask_length = netmask2length(decimalism2ip(new_maskint))

            key = new_ip + "/" + str(new_mask_length)
            if key not in merge_dict.keys():
                merge_dict[key] = {}
                merge_dict[key]["mask_length"] = new_mask_length
                merge_dict[key]["ip"] = src_ip
                merge_dict[key]["mask"] = src_mask
                m_ip = src_ip + "/" + str(src_mask)
                if m_ip not in finall_ips:
                    finall_ips.append(m_ip)
            else:
                # 融合
                if merge_dict[key]["ip"] != src_ip:
                    m_ip = new_ip + "/" + str(new_mask_length)
                    if m_ip not in finall_ips:
                        ip_stack.append(new_ip + "/" + str(new_mask_length))
                        finall_ips.append(new_ip + "/" + str(new_mask_length))

                    del_ip = merge_dict[key]["ip"] + "/" + str(merge_dict[key]["mask"])
                    if del_ip in finall_ips:
                        finall_ips.remove(del_ip)
                    del_ip = src_ip + "/" + str(src_mask)
                    if del_ip in finall_ips:
                        finall_ips.remove(del_ip)

        del_net = []
        for src_net in finall_ips:
            for dst_net in finall_ips:
                if src_net == dst_net:
                    continue
                flag = checkNet(src_net, dst_net)
                if flag is True:
                    del_net.append(src_net)
                    break

        for i in del_net:
            if i in finall_ips:
                finall_ips.remove(i)

        def takeDecm(item):
            return ip2decimalism(item.split("/")[0])

        finall_ips.sort(key=takeDecm)

        return finall_ips
    except Exception as e:
        return []


if __name__ == '__main__':
    # ips = ["10.120.0.0/24", "10.120.0.0/22"]
    ips = ["103.71.120.0/21", "103.71.128.0/22", "103.71.196.0/22", "103.71.200.0/22", "103.72.12.0/22",
           "103.72.16.0/20", "103.72.32.0/20", "103.72.48.0/21", "103.72.128.0/21", "103.74.24.0/21", "103.74.32.0/20",
           "103.74.48.0/22", "45.253.96.0/20", "45.253.112.0/21", "45.253.132.0/22", "45.253.136.0/21",
           "45.253.144.0/20", "45.253.160.0/19", "45.253.192.0/19", "45.253.224.0/20", "45.253.240.0/22",
           "45.254.48.0/21", "45.254.60.0/22", "45.254.64.0/19", "45.254.100.0/22", "45.254.104.0/21",
           "45.254.112.0/20", "45.254.128.0/22", "45.254.136.0/21", "45.254.144.0/21", "45.254.156.0/22",
           "45.254.164.0/22", "45.254.176.0/22", "45.254.236.0/22", "45.254.240.0/22", "45.254.248.0/22",
           "45.255.72.0/22", "42.186.0.0/16", "59.111.0.0/16", "45.127.128.0/22", "103.196.64.0/22", "106.2.32.0/19",
           "106.2.64.0/19", "106.2.96.0/19", "114.113.196.0/22", "114.113.200.0/22", "123.58.160.0/19",
           "223.252.192.0/19", "103.20.68.0/22", "203.217.164.0/22", "203.217.164.0/20"]

    ips = ["203.217.164.0/24","203.217.164.0/22","45.253.136.0/21"]

    ips0 = ["45.254.100.0/22", "45.254.104.0/21", "45.254.112.0/20", "45.254.128.0/22", "45.254.136.0/21",
           "45.254.144.0/21", "45.254.156.0/22", "45.254.164.0/22", "45.254.176.0/22", "45.254.236.0/22",
           "45.254.240.0/22", "45.254.248.0/22"]
    finall_ips = mergeNet(ips)

    print("总数=", len(ips))
    for i in ips:
        print(i)
    print("优化=", len(finall_ips))
    for i in finall_ips:
        print(i)