from puresnmp import get, bulkwalk

def snmpget(ip, community, oid, coding="utf-8"):
    try:
        res = get(ip, community, oid)
        if type(res) == bytes or type(res) == int or type(res) == str:
            if type(res) == bytes:
                if coding == "utf-8":
                    ret = res.decode("utf-8", "ignore")
                else:
                    ret = res.hex()
            else:
                ret = res
        else:
            ret = repr(str(res))
        return ret
    except Exception as e:
        print("snmpget exception=", ip, oid, e)
        return None

def snmpwalk(ip, community, oids, bulk_size=10, coding="utf-8"):
    try:
        res = bulkwalk(ip, community, oids=[oids], bulk_size=bulk_size)
        values = {}
        for i in res:
            if type(i[1]) == bytes or type(i[1]) == int or type(i[1]) == str:
                if type(i[1]) == bytes:
                    if coding == "utf-8":
                        values[str(i[0])] = i[1].decode("utf-8", "ignore")
                    else:
                        values[str(i[0])] = i[1].hex()
                else:
                    values[str(i[0])] = i[1]
            else:
                values[str(i[0])] = str(repr(str(i[1])))

        return values
    except Exception as e:
        print("snmpwalk exception=", ip, oids, e)
        return None

if __name__ == '__main__':
    aa = snmpget("10.92.42.64", "Mrtg.Dikong", "1.3.6.1.2.1.1.1.0", "utf-8")
    print(aa)

    # aa = snmpwalk("192.168.110.153", "public", "1.3.6.1.2.1.4.22.1.2", bulk_size=10, coding="utf-8")
    # print(aa)