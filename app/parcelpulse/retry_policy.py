from collections.abc import Mapping
from typing import Any

from .messaging import DEAD_EXCHANGE, MAIN_EXCHANGE

MAX_RETRIES = 3


def failure_destination(
    headers: Mapping[str, Any],
    attempts: int,
) -> tuple[str, str, dict[str, Any], bool]:
    """Determine whether a failed message should be retried or dead-lettered."""
    updated_headers = dict(headers)

    if attempts < MAX_RETRIES:
        updated_headers["x-retry-count"] = attempts + 1
        return MAIN_EXCHANGE, "retry", updated_headers, False

    updated_headers["x-retry-count"] = attempts
    return DEAD_EXCHANGE, "dead", updated_headers, True
