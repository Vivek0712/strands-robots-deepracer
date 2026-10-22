"""A stdlib client for a running Strands Decider 2B server: one state, many typed questions, one trip.

Strands Decider is a small decision model. You hand it a state (text, a JSON object, up to four
images) and a set of typed questions: a yes/no (``noul``) comes back as a probability, a
``choice`` comes back as one option with a probability per option, a ``score`` comes back as a
level on an ordered rubric. One forward pass answers every question in the request, so asking
three things costs about the same as asking one. This module is the whole network layer a
Strands agent needs to use it: ``urllib`` and ``json``, nothing to install beyond
``strands-agents``, and a client that is synchronous on purpose because the server is best
driven one request at a time (the gates run it in a worker thread with ``asyncio.to_thread``).
When the server is not answering the client raises ``ServerUnavailable``; the gates that use it
treat that as a stop, never as permission. Physics stops the car; the decider explains.

Interface mirrors examples/strands/_client.py in strands-labs/strands-decider (Apache-2.0) so
recipes written against either client are interchangeable, ``last_latency_ms`` included.
Additions here: ``images`` on ``ask`` (the server needs ``serve --vision``), a client-measured
``latency_ms`` for the last call (set on failure too), ``DECIDER_URL`` / ``DECIDER_MODEL``
environment overrides (upstream's ``STRANDS_DECIDER_URL`` is honoured as well), and HTTP errors,
garbled responses and malformed bodies folded into ``ServerUnavailable`` alongside connection
failures.
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any

# --------------------------------------------------------------------------- the name

NAME = "strands-decider"
"""The product name, written once; derived names sit directly below."""

ENV_URL = "DECIDER_URL"
"""Endpoint override. ``STRANDS_DECIDER_URL`` (the upstream example's name) is honoured too."""

ENV_MODEL = "DECIDER_MODEL"
"""Overrides ``MODEL_ID``: the checkpoint name sent as ``model`` on every request."""

DEFAULT_PORT = 8111
DEFAULT_URL = (
    os.environ.get(ENV_URL) or os.environ.get("STRANDS_DECIDER_URL") or f"http://127.0.0.1:{DEFAULT_PORT}"
)

MODEL_ID = os.environ.get(ENV_MODEL, "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610")
"""Sent as ``model`` with every request. The server answers as whatever checkpoint it loaded;
the field documents the wire shape and names the model this library was calibrated against."""

SERVE_HINT = f"{NAME} serve {MODEL_ID} --vision --port {DEFAULT_PORT}"
"""How to start a server, shown when nothing is listening."""

MAX_IMAGES = 4
"""The server accepts at most four images per request."""

#: Everything ``urlopen`` can raise for a dead, slow or garbling server. ``http.client.HTTPException``
#: covers ``BadStatusLine``, ``IncompleteRead`` and ``LineTooLong``; ``ValueError`` covers a body
#: that is not JSON.
_TRANSPORT_ERRORS = (urllib.error.URLError, http.client.HTTPException, TimeoutError, ValueError, OSError)


class ServerUnavailable(RuntimeError):
    """The server did not give a usable answer: connection refused, timeout, HTTP error or bad body.

    Raised with the command that starts a server. A gate that catches this must fail closed.
    """


def _b64(image: bytes | bytearray | str) -> str:
    if isinstance(image, bytes | bytearray):
        return base64.b64encode(bytes(image)).decode("ascii")
    if isinstance(image, str):
        if image.startswith("data:"):
            return image
        base64.b64decode(image, validate=True)  # ValueError (binascii.Error) when it is not base64
        return image
    raise TypeError(f"image must be bytes or a base64 string, got {type(image).__name__}")


_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(url: str) -> threading.Lock:
    """One request at a time per server, process-wide. A Strands agent runs tool calls (and so
    their ``before_tool_call`` gates) concurrently; the 2B checkpoint served on Apple Metal dies
    when two requests reach it at once ("a command encoder is already encoding"), so the client
    serialises them here rather than asking every caller to remember."""
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(url, threading.Lock())


class Decider:
    """One state, many typed questions, one round trip.

    The questions cannot see each other, so their answers stay independent, but the state is
    encoded once and shared across them. Ask everything you need in one ``ask``.

    Args:
        url: Server root. Defaults to ``$DECIDER_URL``, then ``$STRANDS_DECIDER_URL``, then
            ``http://127.0.0.1:8111``.
        timeout: Whole-request budget in seconds. The first request at a new input length on
            Apple silicon can take seconds (shape compile), so the default is generous; a gate
            in a motion loop passes its own budget (the recipes use ``Decider(timeout=1.5)``).
    """

    def __init__(self, url: str = DEFAULT_URL, timeout: float = 120.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.calls = 0
        self.input_tokens = 0
        #: Client-measured round trip of the last ``ask``, in milliseconds (None before the first).
        #: Set on failure too, so a timeout shows its own number, not the previous call's.
        self.latency_ms: float | None = None
        #: The server's own ``latency_ms`` from the last answer, when it reported one.
        self.server_latency_ms: float | None = None

    @property
    def last_latency_ms(self) -> float | None:
        """The server-reported latency of the last answer, under the upstream example's name."""
        return self.server_latency_ms

    # ---- questions -------------------------------------------------------

    @staticmethod
    def noul(instructions: str, criteria: Mapping[str, str] | None = None) -> dict[str, Any]:
        """Yes/no. The answer is P(true).

        ``criteria`` optionally spells out what ``"true"`` and ``"false"`` mean. Write it: the
        two descriptions sharpen the boundary the model is asked to draw.
        """
        question: dict[str, Any] = {"type": "noul", "instructions": instructions}
        if criteria:
            question["criteria"] = dict(criteria)
        return question

    @staticmethod
    def choice(instructions: str, criteria: Mapping[str, str | None]) -> dict[str, Any]:
        """Pick one of N. ``criteria`` maps option name to what that option means.

        Option names are read from the request, not baked into the model, so they can change
        without retraining anything. At least two options.
        """
        if len(criteria) < 2:
            raise ValueError("choice needs at least two options")
        return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}

    @staticmethod
    def score(instructions: str, criteria: Sequence[str]) -> dict[str, Any]:
        """Rate against an ordered rubric, lowest level first (2 to 10 levels)."""
        levels = list(criteria)
        if not 2 <= len(levels) <= 10:
            raise ValueError("score needs between 2 and 10 levels")
        return {"type": "score", "instructions": instructions, "criteria": levels}

    # ---- asking ----------------------------------------------------------

    def _unavailable(self, exc: Exception) -> ServerUnavailable:
        return ServerUnavailable(f"no {NAME} at {self.url} ({exc}). Start one with:\n    {SERVE_HINT}")

    def ask(
        self,
        state: Any,
        questions: Mapping[str, dict[str, Any]],
        images: Sequence[bytes | bytearray | str] | None = None,
    ) -> dict[str, Any]:
        """Evaluate ``state`` against ``questions``; answers come back under the same keys.

        ``state`` may be a string or any JSON value (the server renders objects deterministically).
        ``images`` are JPEG/PNG bytes or base64 strings, at most four, and are part of the state.
        Raises ``ServerUnavailable`` when the server cannot be reached, answers with an HTTP error,
        garbles the response, times out, or returns a body without ``answers``.
        """
        if images and len(images) > MAX_IMAGES:
            raise ValueError(f"at most {MAX_IMAGES} images per request, got {len(images)}")
        request_body: dict[str, Any] = {"state": state, "model": MODEL_ID, "questions": dict(questions)}
        if images:
            request_body["images"] = [_b64(image) for image in images]
        request = urllib.request.Request(
            f"{self.url}/v1/systemone",
            data=json.dumps(request_body).encode(),
            headers={"content-type": "application/json"},
        )
        started = time.perf_counter()
        try:
            with _lock_for(self.url), urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except _TRANSPORT_ERRORS as exc:
            raise self._unavailable(exc) from exc
        finally:
            self.latency_ms = round((time.perf_counter() - started) * 1000, 1)
        if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
            raise self._unavailable(ValueError("response has no answers object"))
        self.calls += 1
        usage = payload.get("usage") or {}
        self.input_tokens += int(usage.get("input_tokens", 0) or 0)
        self.server_latency_ms = payload.get("latency_ms")
        return payload["answers"]

    def health(self) -> dict[str, Any]:
        """``GET /health``: the loaded checkpoint, window and device. Raises if nothing is serving."""
        try:
            with urllib.request.urlopen(f"{self.url}/health", timeout=10) as response:
                body = json.loads(response.read())
        except _TRANSPORT_ERRORS as exc:
            raise self._unavailable(exc) from exc
        if not isinstance(body, dict):
            raise self._unavailable(ValueError("health body is not an object"))
        return body

    def banner(self) -> str:
        h = self.health()
        return (
            f"{NAME}: {h.get('checkpoint', '?')} on {h.get('base_model', '?')} "
            f"[{h.get('device', '?')}, vision {h.get('vision', '?')}] at {self.url}"
        )

    def __str__(self) -> str:
        return f"{self.calls} decisions, {self.input_tokens} input tokens"
