import asyncio
import contextlib
import time
from threading import Thread

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from uvicorn import Config, Server


class UvicornTestServer(Server):
    """Uvicorn test server
    https://stackoverflow.com/a/64454876/13113166
    """

    def __init__(self, config: Config):
        """Create a Uvicorn test server

        Args:
            app (FastAPI, optional): the FastAPI app. Defaults to main.app.
            host (str, optional): the host ip. Defaults to '127.0.0.1'.
            port (int, optional): the port. Defaults to PORT.
        """
        self._startup_done = asyncio.Event()
        super().__init__(config=config)

    async def startup(self, sockets: list | None = None) -> None:
        """Override uvicorn startup"""
        await super().startup(sockets=sockets)
        self.config.setup_event_loop()
        self._startup_done.set()

    async def up(self) -> None:
        """Start up server asynchronously"""
        loop = asyncio.get_event_loop()
        self._serve_task = loop.create_task(self.serve())
        await self._startup_done.wait()

    async def down(self) -> None:
        """Shut down server asynchronously"""
        self.should_exit = True
        await self._serve_task


class UvicornSyncServer(Server):
    """
    For running with synchronous code (e.g. with requests rather than httpx)

    Borrowed from https://github.com/encode/uvicorn/discussions/1455
    """

    @contextlib.contextmanager
    def run_in_thread(self) -> None:
        thread = Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                time.sleep(1e-3)
            yield
        finally:
            self.should_exit = True
            thread.join()


class RequestHoarderMiddleware(BaseHTTPMiddleware):
    """
    Just keep holding on to the requests what could go wrong

    Look i don't know of any better way to access the attrs than this
    ```
    uvicorn_server.config.app.middleware_stack.app
    ```
    if you have no other middleware.
    """

    def __init__(self, app: Starlette):
        super().__init__(app)
        self.requests = []
        self.responses = []

    async def dispatch(self, request: Request, call_next) -> Response:
        self.requests.append(request)
        response = await call_next(request)
        self.responses.append(response)
        return response
