import threading
from concurrent.futures.thread import ThreadPoolExecutor
import functools

# 错误
class T_thread(threading.Thread):
    def __init__(self,func,args):
        # threading.Thread.__init__(self)
        super(T_thread, self).__init__()
        self.func = func
        self.args = args
        self.result = self.func(*self.args)

    def get_result(self):
        try:
            return self.result
        except Exception:
            return None

# 正确
class MyThread(threading.Thread):
    def __init__(self, func, args=(), kwargs=()):
        super(MyThread, self).__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.result = self.func(*self.args, *self.kwargs)

    def get_result(self):
        try:
            return self.result  # 如果子线程不使用join方法，此处可能会报没有self.result的错误
        except Exception:
            return None


def execAllFunctions(tasks, max_workers=8, callback=None):
    result = {}
    def cb(future, name):
        stdout = future.result()
        result[name] = stdout

    with ThreadPoolExecutor(max_workers=max_workers) as p:
        # 提交任务
        for task in tasks:
            future = p.submit(task["func"], *task["args"], **task["kwargs"])
            future.add_done_callback(functools.partial(cb, name=task["name"]))

    # 回调函数
    if callback:
        callback(result)

    return result