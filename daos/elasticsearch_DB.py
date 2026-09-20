from elasticsearch import Elasticsearch

from config.config import Config

g_es = Elasticsearch(
    hosts=Config.es_hosts,
    basic_auth=(Config.es_user, Config.es_password),
    verify_certs=Config.es_verify_certs
)
