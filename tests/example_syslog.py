import json
import time

import requests
from hashlib import md5

def sign_key(secret, timestamp):
    expected_signature = md5((str(secret) + str(timestamp)).encode("utf-8")).hexdigest()
    return expected_signature

def test_syslog_simple():
    url = "http://netops.vdian.net/api/data/submit_syslog"
    t = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "key": "chensong",
        "secret":sign_key("90f82219ae7f3452ec84762395b7b51c", t),
        "Apptime": t
    }
    data = {
        "message": "Hello World!1",
        "ip": "1.1.1.1"
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))

    print(response.text)

if __name__ == '__main__':
    test_syslog_simple()