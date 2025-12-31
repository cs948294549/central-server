from services.syslog.filter_blacklist import get_blacklisted_entries
from services.syslog.log_merge import get_mergelisted_entries

def check_blacklist(message):
    '''
    :param message: {"message":"", "ip":""}
    :return:
    '''
    blacklisted_entries = get_blacklisted_entries()
    for entry in blacklisted_entries:
        if entry.matches(str(message["message"])):
            return {"status": "matched", "entry": entry.to_dict()}
    return {"status": "unmatched", "entry": {}}

def check_mergelist(message):
    '''
    :param message: {"message":"", "ip":""}
    :return:
    '''
    mergelisted_entries = get_mergelisted_entries()
    for entry in mergelisted_entries:
        if entry.matches(str(message["message"])):
            return {"status": "matched", "entry": entry.to_dict()}
    return {"status": "unmatched", "entry": {}}


if __name__ == '__main__':
    ret = check_mergelist({"message": "%Jan  1 08:46:32:471 2011 vrrp-test-2 %%IFNET/3/PHY_UPDOWN: Vlan-interface162 link status is up.","ip":"1.1.1.1"})
    print(ret)





