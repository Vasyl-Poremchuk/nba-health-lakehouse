import logging
from collections.abc import Callable
from typing import Any, TypeVar

import requests
from structlog.typing import FilteringBoundLogger
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

F = TypeVar("F", bound=Callable[..., Any])


def is_http_4xx_or_5xx_error(exception: BaseException) -> bool:
    """Return True if the exception is a retryable HTTP 4xx/5xx error.

    Matches ``requests.HTTPError`` responses with status codes 408, 429,
    500, 502, 503, or 504.

    Args:
        exception: The exception to inspect.

    Returns:
        ``True`` when the exception is a retryable HTTP error, ``False`` otherwise.
    """
    is_true = (
        isinstance(exception, requests.exceptions.HTTPError)
        and isinstance(exception.response, requests.Response)
        and (
            exception.response.status_code in (408, 429)
            or exception.response.status_code in (500, 502, 503, 504)
        )
    )

    return is_true


def nba_api_retry(logger: FilteringBoundLogger) -> Callable[[F], F]:
    """Build the shared retry policy for NBA Stats API calls.

    Retries up to 3 times with exponential backoff (3-10 s), logging each
    retry attempt through ``logger`` at WARNING level, and re-raises the
    original exception after the final attempt. Only retries on HTTP status
    codes 408, 429, 500, 502, 503, or 504 (via ``is_http_4xx_or_5xx_error``)
    and on ``ConnectionError``, ``Timeout``, or ``TooManyRedirects``; all
    other exceptions are re-raised immediately without retrying.

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
        retry=retry_if_exception(is_http_4xx_or_5xx_error)
        | retry_if_exception_type(
            (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.TooManyRedirects,
            )
        ),
        reraise=True,
    )
