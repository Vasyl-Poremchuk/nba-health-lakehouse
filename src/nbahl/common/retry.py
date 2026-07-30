import logging
from collections.abc import Callable
from typing import Any, TypeVar

from structlog.typing import FilteringBoundLogger
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

F = TypeVar("F", bound=Callable[..., Any])


def nba_api_retry(logger: FilteringBoundLogger) -> Callable[[F], F]:
    """Build the shared retry policy for NBA Stats API calls.

    Retries up to 3 times with exponential backoff (3-10 s), logging each
    retry attempt through ``logger`` at WARNING level, and re-raises the
    original exception after the final attempt.

    Args:
        logger: structlog logger used for the before-sleep retry warning.

    Returns:
        A configured ``tenacity.retry`` decorator.
    """
    return retry(
        stop=stop_after_attempt(max_attempt_number=3),
        before_sleep=before_sleep_log(
            logger=logger, log_level=logging.WARNING
        ),
        wait=wait_exponential(multiplier=1, min=3, max=10),
        reraise=True,
    )
