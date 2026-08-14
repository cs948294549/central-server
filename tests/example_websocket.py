import json
import requests

def test_websocket_simple():
    url = "http://netops.vdian.net/sock/send_msg"
    headers = {"Content-Type": "application/json"}
    data = {
        "msg": "Hello World!",
        "target": "submitData"
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))

    print(response.text)

if __name__ == '__main__':
    test_websocket_simple()