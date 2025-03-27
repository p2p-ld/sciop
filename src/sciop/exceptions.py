from datetime import timedelta
from enum import StrEnum
from time import time

from fastapi import HTTPException, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from humanize.time import naturaldelta
from slowapi.errors import RateLimitExceeded


class SciOpException(Exception):
    """Base SciOp Exception"""


class UploadSizeExceeded(ValueError, SciOpException):
    """An uploaded file is too large!"""


class TrackerURLException(SciOpException, ValueError):
    """Exception when something went wrong with the URL given"""


class UDPTrackerException(SciOpException, RuntimeError):
    """Exception when an error has been encountered with the UDPTrackerClient"""


class DNSException(SciOpException, RuntimeError):
    """Error resolving DNS information"""


class TrackerConnectionException(UDPTrackerException):
    """Error connecting to a tracker"""


class ScrapeUnpackException(UDPTrackerException):
    """Scrape results could not be unpacked"""


class ScrapeErrorType(StrEnum):
    dns = "dns"
    """DNS resolution error"""
    connection = "connection"
    """Connection refused"""
    timeout = "timeout"
    """Timeout when communicating"""
    unpack = "unpack"
    """Error unpacking scraped values"""
    default = "default"
    """Unhandled or unknown exception type"""


async def http_handler(request: Request, exc: HTTPException) -> Response:
    """
    Small wrapping of FastAPI's error handling to
    - handle rate limits
    - display errors in htmx
    """

    if request.headers.get("hx-request", False) and exc.status_code != 422:
        return await htmx_error(request, exc)
    else:
        return await http_exception_handler(request, exc)


async def htmx_error(request: Request, exc: HTTPException | RateLimitExceeded) -> Response:
    """
    On HTMX errors that aren't 422s (which are handled clientsite),
    retarget the error to a modal
    """
    from sciop.frontend.templates import templates

    headers = {"HX-Retarget": "#error-modal-container", "HX-Reswap": "innerHTML"}
    if error_headers := getattr(exc, "headers", None):
        headers.update(error_headers)

    if isinstance(exc.detail, str):
        msg = exc.detail
        kwargs = {}
    elif isinstance(exc.detail, dict):
        msg = exc.detail.pop("msg")
        kwargs = exc.detail
    else:
        raise TypeError("Dont know how to handle non-dict, non-str exception details")

    return templates.TemplateResponse(
        request,
        "partials/error-modal.html",
        {"msg": msg, "status_code": exc.status_code, **kwargs},
        headers=headers,
        status_code=exc.status_code,
    )


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    time_remaining = _get_reset_timedelta(request, exc)
    message = f"Rate limit exceeded: {exc.detail}. Try again in {naturaldelta(time_remaining)}"
    if request.headers.get("hx-request", False):
        exc.detail = message
        response = await htmx_error(request, exc)
    else:
        response = JSONResponse(
            {"error": message},
            status_code=429,
        )
    response = request.app.state.limiter._inject_headers(response, request.state.view_rate_limit)
    return response


def _get_reset_timedelta(request: Request, exc: RateLimitExceeded) -> timedelta:
    current_limit = request.state.view_rate_limit
    window_stats = request.app.state.limiter.limiter.get_window_stats(
        current_limit[0], *current_limit[1]
    )
    reset_time = window_stats.reset_time
    return timedelta(seconds=reset_time - time())
