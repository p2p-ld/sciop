import logging
from io import BytesIO
from typing import TYPE_CHECKING, Any, Callable, Coroutine, MutableMapping, Optional

from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.concurrency import iterate_in_threadpool

from sciop.db import get_session
from sciop.exceptions import UploadSizeExceeded
from sciop.logging import init_logger
from sciop.api.deps import get_current_account

if TYPE_CHECKING:
    from fastapi import FastAPI


class ContentSizeLimitMiddleware:
    """
    Content size limiting middleware for ASGI applications

    Cribbed and modified from
    https://github.com/steinnes/content-size-limit-asgi/blob/master/content_size_limit_asgi/middleware.py
    """

    def __init__(
        self,
        app: "FastAPI",
        max_content_size: Optional[int] = None,
    ):
        self.app = app
        self.max_content_size = max_content_size

        self.logger = init_logger("middleware.content-size-limit")

    def receive_wrapper(
        self, receive: Receive
    ) -> Callable[[], Coroutine[Any, Any, MutableMapping[str, Any]]]:
        received = 0

        async def inner() -> MutableMapping[str, Any]:
            nonlocal received
            message = await receive()
            if message["type"] != "http.request" or self.max_content_size is None:
                return message
            body_len = len(message.get("body", b""))
            received += body_len
            if received > self.max_content_size:
                raise UploadSizeExceeded(
                    f"Maximum content size limit ({self.max_content_size}) "
                    f"exceeded ({received} bytes read)"
                )
            return message

        return inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        wrapper = self.receive_wrapper(receive)
        await self.app(scope, wrapper, send)


limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
    default_limits=["100 per minute", "1000 per hour", "10000 per day"],
)


def exempt_scoped(request: Request) -> bool:
    """
    Exempt any account with any scope from rate limits

    FIXME: Needs to also get accounts from header tokens from API requests
    """
    token = request.cookies.get("access_token", None)
    if token is None:
        return False
    session = next(get_session())
    account = get_current_account(session, token)
    if not account:
        return False
    return len(account.scopes) > 0


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, logger: logging.Logger):
        self.logger = logger
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
            msg = None
            if response.status_code < 400:
                level = logging.INFO
            elif response.status_code < 500:
                msg = await self._decode_body(response)
                level = logging.WARNING
            else:
                msg = await self._decode_body(response)
                level = logging.ERROR

            self._log_message(
                response_code=response.status_code, request=request, msg=msg, level=level
            )
            return response
        except HTTPException as e:
            self._log_message(
                response_code=e.status_code, request=request, msg=str(e), level=logging.ERROR
            )
            raise e
        except Exception as e:
            msg = f"Unhandled exception: {str(e)}"
            self._log_message(response_code=500, request=request, msg=msg, level=logging.ERROR)
            raise e

    def _log_message(
        self,
        response_code: int,
        request: Request,
        msg: Optional[str] = None,
        level: int = logging.INFO,
    ) -> None:
        if msg:
            self.logger.log(
                level, "[%s] %s: %s - %s", response_code, request.method, request.url.path, msg
            )
        else:
            self.logger.log(level, "[%s] %s: %s", response_code, request.method, request.url.path)

    async def _decode_body(self, response: Response) -> str:

        if hasattr(response, "body_iterator"):
            chunks = []
            with BytesIO() as raw_buffer:
                async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                    chunks.append(chunk)
                    if not isinstance(chunk, bytes):
                        chunk = chunk.encode(response.charset)
                    raw_buffer.write(chunk)
                body = raw_buffer.getvalue()
            response.body_iterator = iterate_in_threadpool(iter(chunks))
        elif hasattr(response, "body"):
            body = response.body.decode("utf-8")
        else:
            body = b""

        return body.decode("utf-8", errors="ignore")
