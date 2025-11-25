from kafka import KafkaConsumer, KafkaProducer
import time
import hashlib
import requests
import json
import base64


kafka_online = ["localhost:9092"]

kafka_server = kafka_online


class Producer(object):
    def __init__(self, topic):
        self.producer = KafkaProducer(bootstrap_servers=kafka_server)
        self.topic = topic

    def submit(self, data, key=None, partition=0):
        self.producer.send(self.topic, key=key.encode("utf-8"), value=json.dumps(data).encode("utf-8"),
                           partition=partition)

    def close(self):
        self.producer.close()


class Consumer(object):
    def __init__(self, topic, group_id=None):
        self.topic = topic
        self.consumer = KafkaConsumer(self.topic, bootstrap_servers=kafka_server, enable_auto_commit=True,
                                      group_id=group_id,
                                      auto_offset_reset='latest')

if __name__ == '__main__':
    dd = Consumer("collect_data", group_id="test_group")
    for msg in dd.consumer:
        print("worker %s " % 1 + "%s:%d:%d: key=%s value=%s" % (
            msg.topic, msg.partition, msg.offset, msg.key, msg.value))
