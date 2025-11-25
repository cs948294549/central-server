from elasticsearch import Elasticsearch, helpers

hosts = ['http://192.168.56.10:9200']

g_es = Elasticsearch(
    hosts=hosts,
    basic_auth=("elastic", "GVVDt84s"),
    verify_certs=False  # 生产环境建议使用 True 并配置证书
)

# 执行 API 请求
response = g_es.cluster.health()
print(response)

# 查询所有索引
indices_list = g_es.cat.indices(h="index", format='json')
for index in indices_list:
    print(index)