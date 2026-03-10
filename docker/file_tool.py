#! coding:utf-8
import socket
import argparse
from threading import Thread

def recv_data(sock,length):
    recv_bytes = b''
    remaining = length
    while remaining > 0:
        _ = sock.recv(remaining)
        if _:
            recv_bytes += _
        else:
            break
        remaining = length - len(recv_bytes)
    return recv_bytes

def readsock(sock, addr):
    print("收到连接:", addr)
    try:
        file_name_cache = b''
        file_name = ""
        sock.settimeout(5)
        while True:
            _ = sock.recv(1024)
            if _:
                file_name_cache += _
                if file_name_cache[0:4] == b'\x00\x01\x01\x00' and file_name_cache[-4:] == b'\x00\x01\x01\x00' and len(file_name_cache)>8:
                    file_name = file_name_cache[4:-4].decode("utf-8", "ignore")
                    print("开始接收文件==", file_name)
                    sock.sendall(b'okok')
                    break
            else:
                break

        with open("file_{}".format(file_name), "wb") as f:
            while True:
                _ = sock.recv(1024)
                if _:
                    f.write(_)
                else:
                    break
    except Exception as e:
        print(e)
        sock.close()

def server(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", int(port)))
    sock.listen(5)
    while True:
        clientsocket, addr = sock.accept()
        Thread(target=readsock, args=(clientsocket, addr)).start()

def client(target_ip, target_port, filename):
    try:
        with open(filename, "rb") as f:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.connect((target_ip, int(target_port)))

            sock.sendall(b'\x00\x01\x01\x00')
            sock.sendall(filename.encode("utf-8", "ignore"))
            sock.sendall(b'\x00\x01\x01\x00')

            data = recv_data(sock, 4)
            if data == b'okok':
                print("开始传输")
                dd = f.read(1024)
                while dd:
                    sock.sendall(dd)
                    dd = f.read(1024)

                return "success"
            else:
                sock.close()
                return "failed"
    except Exception as e:
        print(e)
        return "failed"


def shell():
    description = '''
    # 开启服务监听收文件
    python3 file_tool.py -m s -p 20000

    # 开启客户端发文件
    python3 file_tool.py -m c -t ip:port

    '''
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-m', '--mode', help='s/c', required=True)
    parser.add_argument('-p', '--port', help='port', default=8000)
    parser.add_argument('-t', '--target', help='target ip and port')
    parser.add_argument('-f', '--file', help='file name')
    args = parser.parse_args()

    if args.mode == "c":
        if args.target:
            ipdata = args.target.split(":")
            if len(ipdata) == 2:
                ip, port = ipdata
            else:
                ip = ipdata[0]
                port = 8000

            if args.file:
                ff = client(target_ip=ip, target_port=int(port), filename=args.file)
                if ff == "success":
                    print("传输完成!")
                else:
                    print("传输失败!")
            else:
                print("未指定文件")

        else:
            print("未指定目标, -t ip:port")
    else:
        print("bind port", args.port)
        server(port=int(args.port))

if __name__ == '__main__':
    shell()