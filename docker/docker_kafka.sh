docker run -d \
  --name kafka-kraft \
  --network kafka-kraft-network \
  -p 9092:9094 \
  -v /root/apps/kafka_app/config/server.properties:/opt/kafka/config/kraft/server.properties \
  -v kafka-kraft-data:/tmp/kraft-combined-logs \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1 \
  -e KAFKA_CLUSTER_ID=ZVdyytDRT9-qRZRX4fC2RQ \
  apache/kafka:3.8.0 \
  /opt/kafka/bin/kafka-server-start.sh /opt/kafka/config/kraft/server.properties