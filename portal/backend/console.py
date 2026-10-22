"""Console MJPEG proxy for the Pit Wall: the live view is the same for the car and the fake console.

The browser never talks to the car. The portal logs in to the DeepRacer console (CSRF token, then
``POST /login`` with the password from ``DEEPRACER_CONSOLE_PASSWORD``, never logged), opens the MJPEG
route and pipes the bytes through. Against the QA fake console on ``http://127.0.0.1:8090`` there is
no login, so the same code path just streams. ``grab_jpeg`` pulls one frame (SOI FFD8 to EOI FFD9,
the parser from report 07) for audit thumbnails. Physics stops the car; the decider explains.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import AsyncIterator

import httpx

log = logging.getLogger("portal.console")

MJPEG_ROUTE = "/route?topic=/camera_pkg/display_mjpeg&width=480&height=360"
SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
_CSRF = re.compile(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']', re.I)
_CSRF_ALT = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']csrf-token["\']', re.I)


def console_url() -> str:
    return os.environ.get("DEEPRACER_CONSOLE_URL", "http://127.0.0.1:8090").rstrip("/")


class ConsoleStream:
    """One authenticated httpx client per portal process; login is lazy and retried on 401/403."""

    def __init__(self, base_url: str | None = None, password: str | None = None) -> None:
        self.base_url = (base_url or console_url()).rstrip("/")
        self._password = (
            password if password is not None else os.environ.get("DEEPRACER_CONSOLE_PASSWORD", "")
        )
        self._client: httpx.AsyncClient | None = None
        self._logged_in = False
        self.content_type = "multipart/x-mixed-replace; boundary=frame"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                verify=False,
                timeout=httpx.Timeout(5.0, read=15.0),
                follow_redirects=True,
            )
        return self._client

    async def rebind(self, base_url: str | None = None) -> None:
        """Point at a new console (after ``connect.connect`` moved ``DEEPRACER_CONSOLE_URL``)."""
        await self.aclose()
        self.base_url = (base_url or console_url()).rstrip("/")
        self._password = os.environ.get("DEEPRACER_CONSOLE_PASSWORD", self._password)
        self._logged_in = False

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def login(self) -> bool:
        """CSRF login to the console. Returns True when logged in or when no login is needed."""
        if self._logged_in:
            return True
        # Always try the CSRF login, even with an empty password: the QA fake console (like the
        # real one) answers 401 on the MJPEG route until a session cookie exists, and it accepts
        # any password unless FAKE_CONSOLE_PASSWORD is set. An open console (no csrf meta) streams.
        client = self._get_client()
        try:
            page = await client.get("/login")
            match = _CSRF.search(page.text) or _CSRF_ALT.search(page.text)
            if match is None:
                log.warning("console login page had no csrf-token meta; streaming without login")
                self._logged_in = True
                return True
            token = match.group(1)
            resp = await client.post(
                "/login",
                data={"password": self._password},
                headers={"X-CSRFToken": token, "Referer": f"{self.base_url}/login"},
            )
            self._logged_in = resp.status_code < 400
            if not self._logged_in:
                log.warning("console login failed with HTTP %s", resp.status_code)
            return self._logged_in
        except httpx.HTTPError as exc:
            log.warning("console login error: %s", type(exc).__name__)
            return False

    async def stream(self) -> AsyncIterator[bytes]:
        """Yield the raw MJPEG bytes from the console; sets ``self.content_type`` from the upstream."""
        await self.login()
        client = self._get_client()
        for attempt in (1, 2):
            async with client.stream("GET", MJPEG_ROUTE) as resp:
                if resp.status_code in (401, 403):
                    self._logged_in = False  # session expired or never existed: log in once more
                    if attempt == 1 and await self.login():
                        continue
                    raise httpx.HTTPStatusError(
                        "console refused the stream", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                ctype = resp.headers.get("content-type")
                if ctype:
                    self.content_type = ctype
                async for chunk in resp.aiter_bytes():
                    yield chunk
                return

    async def grab_jpeg(self, *, max_bytes: int = 2_000_000) -> bytes | None:
        """Return one complete JPEG from the stream (SOI..EOI), or None if nothing arrived in time."""
        buf = bytearray()
        try:
            async for chunk in self.stream():
                buf.extend(chunk)
                start = buf.find(SOI)
                if start >= 0:
                    end = buf.find(EOI, start + 2)
                    if end >= 0:
                        return bytes(buf[start : end + 2])
                if len(buf) > max_bytes:
                    del buf[: len(buf) - 65536]
        except (httpx.HTTPError, OSError) as exc:
            log.info("no frame from console: %s", type(exc).__name__)
        return None
