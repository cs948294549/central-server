from functools import wraps

def waf(dic):
    if isinstance(dic, dict):
        for i in dic.keys():
            if type(dic[i]) == str:
                dic[i] = dic[i].replace("'", "\\'").replace('"', '\\"')
        return dic
    else:
        return dic

# 检查参数数量
def checkParams(datas, key_array):
    flag = True
    flag_key = ""
    for key in key_array:
        if key in datas.keys():
            pass
        else:
            flag = False
            flag_key = key
            break
    return flag, flag_key

# 装饰器
def decorator_checkparams(key_array=None):
    def params_decorated(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            datas = args
            if len(datas) > 0:
                flag, flag_key = checkParams(datas[0], key_array)
                if flag is True:
                    return func(*args, **kwargs)
                else:
                    return {"status":"failed", "data":None, "message": "请求{}缺失参数=={}".format(str(func.__name__), str(flag_key))}
            else:
                return {"status": "failed", "data": None,"message": "请求{}参数缺失".format(str(func.__name__))}
        return decorated
    return params_decorated