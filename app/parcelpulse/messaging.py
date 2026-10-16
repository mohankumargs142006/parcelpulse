from __future__ import annotations

import os
import pika

MAIN_EXCHANGE = "shipment.exchange"
DEAD_EXCHANGE = "shipment.dlx"
MAIN_QUEUE = "shipment.events"
RETRY_QUEUE = "shipment.events.retry"
DLQ_QUEUE = "shipment.events.dlq"


def parameters() -> pika.URLParameters:
    return pika.URLParameters(os.getenv("RABBITMQ_URL", "amqp://parcelpulse:local_dev_only_change_me@localhost:5672/%2F"))


def declare_topology(channel: pika.channel.Channel) -> None:
    channel.exchange_declare(exchange=MAIN_EXCHANGE, exchange_type="direct", durable=True)
    channel.exchange_declare(exchange=DEAD_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=MAIN_QUEUE, durable=True, arguments={
        "x-dead-letter-exchange": DEAD_EXCHANGE,
        "x-dead-letter-routing-key": "dead",
    })
    channel.queue_bind(queue=MAIN_QUEUE, exchange=MAIN_EXCHANGE, routing_key="events")
    channel.queue_declare(queue=RETRY_QUEUE, durable=True, arguments={
        "x-message-ttl": 5000,
        "x-dead-letter-exchange": MAIN_EXCHANGE,
        "x-dead-letter-routing-key": "events",
    })
    channel.queue_bind(queue=RETRY_QUEUE, exchange=MAIN_EXCHANGE, routing_key="retry")
    channel.queue_declare(queue=DLQ_QUEUE, durable=True)
    channel.queue_bind(queue=DLQ_QUEUE, exchange=DEAD_EXCHANGE, routing_key="dead")


def publish_event(event: dict) -> None:
    connection = pika.BlockingConnection(parameters())
    try:
        channel = connection.channel()
        declare_topology(channel)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange=MAIN_EXCHANGE,
            routing_key="events",
            body=__import__("json").dumps(event, separators=(",", ":")),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
            mandatory=True,
        )
    finally:
        connection.close()
