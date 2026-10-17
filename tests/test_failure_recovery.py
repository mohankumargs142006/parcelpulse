from unittest.mock import Mock

import pytest

from parcelpulse.messaging import (
    DEAD_EXCHANGE,
    DLQ_QUEUE,
    MAIN_EXCHANGE,
    MAIN_QUEUE,
    RETRY_QUEUE,
    declare_topology,
)
from parcelpulse.retry_policy import failure_destination


@pytest.mark.parametrize(
    ("attempts", "expected_exchange", "expected_route", "expected_count", "is_dlq"),
    [
        (0, MAIN_EXCHANGE, "retry", 1, False),
        (1, MAIN_EXCHANGE, "retry", 2, False),
        (2, MAIN_EXCHANGE, "retry", 3, False),
        (3, DEAD_EXCHANGE, "dead", 3, True),
    ],
)
def test_failure_destination(
    attempts,
    expected_exchange,
    expected_route,
    expected_count,
    is_dlq,
):
    original_headers = {"x-carrier": "demo"}

    exchange, route, headers, dead_letter = failure_destination(
        original_headers, attempts
    )

    assert exchange == expected_exchange
    assert route == expected_route
    assert headers["x-retry-count"] == expected_count
    assert headers["x-carrier"] == "demo"
    assert dead_letter is is_dlq
    assert original_headers == {"x-carrier": "demo"}


def test_rabbitmq_topology_declares_retry_ttl_and_dlq():
    channel = Mock()

    declare_topology(channel)

    channel.queue_declare.assert_any_call(
        queue=RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 5000,
            "x-dead-letter-exchange": MAIN_EXCHANGE,
            "x-dead-letter-routing-key": "events",
        },
    )

    channel.queue_declare.assert_any_call(
        queue=DLQ_QUEUE,
        durable=True,
    )

    channel.queue_bind.assert_any_call(
        queue=MAIN_QUEUE,
        exchange=MAIN_EXCHANGE,
        routing_key="events",
    )

    channel.queue_bind.assert_any_call(
        queue=RETRY_QUEUE,
        exchange=MAIN_EXCHANGE,
        routing_key="retry",
    )

    channel.queue_bind.assert_any_call(
        queue=DLQ_QUEUE,
        exchange=DEAD_EXCHANGE,
        routing_key="dead",
    )