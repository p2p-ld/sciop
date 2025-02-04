from typing import Optional, Type, TYPE_CHECKING

from sciop.logging import init_logger
from sciop.exceptions import UploadSizeExceeded

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

    def receive_wrapper(self, receive):
        received = 0

        async def inner():
            nonlocal received
            message = await receive()
            if message["type"] != "http.request" or self.max_content_size is None:
                return message
            body_len = len(message.get("body", b""))
            received += body_len
            if received > self.max_content_size:
                raise UploadSizeExceeded(
                    f"Maximum content size limit ({self.max_content_size}) exceeded ({received} bytes read)"
                )
            return message

        return inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        wrapper = self.receive_wrapper(receive)
        await self.app(scope, wrapper, send)