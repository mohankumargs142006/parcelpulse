from __future__ import annotations

import json
import logging
import os
import time

import pika
from prometheus_client import Counter, start_http_server

from .common import archive_event, parse_event
from .db import init_db, store_event
from .messaging import DEAD_EXCHANGE, DLQ_QUEUE, MAIN_EXCHANGE, MAIN_QUEUE, RETRY_QUEUE, declare_topology, parameters

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("parcelpulse.worker")
PROCESSED = Counter("parcelpulse_worker_processed_total", "Unique events successfully processed")
DUPLICATES = Counter("parcelpulse_worker_duplicates_total", "Duplicate events ignored")
FAILURES = Counter("parcelpulse_worker_failures_total", "Processing failures")
DLQ = Counter("parcelpulse_worker_dlq_total", "Events sent to dead-letter queue")
STALE = Counter("parcelpulse_worker_stale_events_total", "Events recorded but not allowed to advance current state")


def main() -> None:
    init_db()
    start_http_server(9101, addr="0.0.0.0")
    while True:
        try:
            connection = pika.BlockingConnection(parameters())
            channel = connection.channel()
            declare_topology(channel)
            channel.basic_qos(prefetch_count=1)
            channel.confirm_delivery()
            def callback(ch, method, properties, body):
                headers = properties.headers or {}
                attempts = int(headers.get("x-retry-count", 0))
                try:
                    event = parse_event(json.loads(body))
                    if os.getenv("SIMULATE_WORKER_FAILURE", "false").lower() == "true":
                        raise RuntimeError("Injected worker failure for recovery demo")
                    archive_event(event)
                    inserted, advanced = store_event(event)
                    if inserted:
                        PROCESSED.inc()
                        if not advanced:
                            STALE.inc()
                        log.info(json.dumps({"event":"processed","event_id":event["event_id"],"shipment_id":event["shipment_id"],"state_advanced":advanced}))
                    else:
                        DUPLICATES.inc()
                        log.info(json.dumps({"event":"duplicate_ignored","event_id":event["event_id"]}))
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    FAILURES.inc()
                    log.exception("Processing failed for delivery: %s", exc)
                    try:
                        if attempts < 3:
                            target_exchange, routing_key = MAIN_EXCHANGE, "retry"
                            new_headers = dict(headers)
                            new_headers["x-retry-count"] = attempts + 1
                        else:
                            target_exchange, routing_key = DEAD_EXCHANGE, "dead"
                            new_headers = {**headers, "x-retry-count": attempts}
                            DLQ.inc()
                        ch.basic_publish(
                            exchange=target_exchange,
                            routing_key=routing_key,
                            body=body,
                            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2, headers=new_headers),
                            mandatory=True,
                        )
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    except Exception:
                        log.exception("Could not publish retry/DLQ copy; requeuing original")
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            channel.basic_consume(queue=MAIN_QUEUE, on_message_callback=callback, auto_ack=False)
            log.info("worker consuming queue=%s retry=%s dlq=%s", MAIN_QUEUE, RETRY_QUEUE, DLQ_QUEUE)
            channel.start_consuming()
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("RabbitMQ connection loop failed; retrying shortly")
            time.sleep(3)

if __name__ == "__main__":
    main()
