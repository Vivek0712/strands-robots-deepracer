"""HTTP client for the strands-decider System One API, the rover's explanation layer.

The decider is a small calibrated classifier that answers typed questions in about 150 ms:
"is this command inside the briefed envelope?", "are the arguments grounded in what the user
said?" (two yes/no answers with a probability) and "what did the user ask for?" (a five-way
choice), all three in one text request (``ask_many``); then "what is in front of the camera?"
(one of five classes with a probability, asked in the same request as a yes/no "is a person
visible", see ``ask_frame``). Every answer comes back with its latency so the screen can show
the number. When the decider is slow, down or returns nonsense (a missing key, a probability
that is a bool, a string, NaN or outside [0, 1], a class outside the criteria), the client
raises ``DeciderUnavailable`` and the gate fails closed: no motion.
Physics stops the car; the decider explains.

Wire format (copied from ``src/strands_decider/schema.py`` and ``server.py`` in
strands-labs/strands-decider; the fake decider in ``harness/fake_decider.py`` implements the same shape)::

    POST {DECIDER_URL}/v1/systemone
    {
      "state": <str | dict | list>,                      # rendered deterministically server-side
      "model": "strands-decider-latest",
      "questions": {
        "<name>": {"type": "noul",   "instructions": <str>, "criteria": {"true": ..., "false": ...}?},
        "<name>": {"type": "choice", "instructions": <str>, "criteria": {"<class>": <desc | null>, ...}}
      },
      "images": ["<base64 JPEG or data: URI>", ...],      # part of the state; needs `serve --vision`
      "audio":  ["<base64 WAV/FLAC/OGG/MP3>", ...]        # Gemma 4 E2B/E4B with `--audio` only
    }
    -> 200
    {
      "model": "<checkpoint name>",
      "answers": {
        "<name>": {"type": "noul",   "noul": <P(true)>},
        "<name>": {"type": "choice", "choice": "<class>", "probabilities": {"<class>": p, ...},
                   "confidence": <normalised max-probability>}
      },
      "usage": {"input_tokens": int, "output_tokens": int},
      "latency_ms": <server-side ms, float>
    }
    -> 422 on caller errors (too many options, malformed permutation), detail in body.
    GET  {DECIDER_URL}/health -> {"status": "ok", "model", "checkpoint", "base_model", "num_slots",
                                  "max_length", "temperature", "device", "prefix_cache", "vision", "audio"}

Fields the contract (docs/dev/CONTRACTS.md §7) does not mention but the server has: ``model``
(request and response), ``usage``, ``confidence`` on choice answers, the server-side
``latency_ms`` (we report the client-measured round trip instead, which is what the stop
budget cares about), ``audio``, and the third question kind ``score`` (ordered rubric,
``{"type": "score", "score": float, "legend": {...}, "probabilities": {...}, "confidence"}``),
which this project does not use.
"""

from __future__ import annotations

import base64
import contextlib
import logging
import math
import os
import tempfile
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_DECIDER_URL = "http://127.0.0.1:8111"
DEFAULT_TIMEOUT_S = 1.5
DEFAULT_MODEL = "strands-decider-latest"
SYSTEMONE_PATH = "/v1/systemone"
HEALTH_PATH = "/health"

#: After a timed-out ask the server may still be busy with it; asks in this window fail fast.
COOLDOWN_AFTER_TIMEOUT_S = 8.0
_request_lock = threading.Lock()


#: A request the server may still be chewing on after its client died (a portal restart kills the
#: process mid-ask): the next ask must wait this long after that request started.
logger = logging.getLogger(__name__)

ORPHAN_SETTLE_S = 6.0


@contextlib.contextmanager
def _process_lock(base_url: str) -> Iterator[None]:
    """One request at a time across processes too: a portal restart, a beat and a test script all
    share the same decider, and two requests in flight abort the MPS server (seen three times on
    2026-10-17). A file lock keyed by the server's port; no-op where ``fcntl`` is absent.

    Beside the lock lives a busy marker (``started`` wall time and pid). When a holder dies
    mid-request the lock is released at once but the server is still encoding; the next holder
    reads the marker and waits out ``ORPHAN_SETTLE_S`` from that start before sending.
    """
    try:
        import fcntl
    except ImportError:  # pragma: no cover - windows
        yield
        return
    port = urlparse(base_url).port or 80
    base = Path(tempfile.gettempdir())
    lock_path = base / f"deepracer-decider-{port}.lock"
    busy_path = base / f"deepracer-decider-{port}.busy"
    with open(lock_path, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            try:
                started, pid = busy_path.read_text(encoding="utf-8").split()
                started_f, pid_i = float(started), int(pid)
            except (OSError, ValueError):
                started_f, pid_i = 0.0, 0
            if started_f > 0 and pid_i != os.getpid():
                remaining = ORPHAN_SETTLE_S - (time.time() - started_f)
                if remaining > 0:
                    logger.info(
                        "decider: a request from pid %d may still run; waiting %.1fs", pid_i, remaining
                    )
                    time.sleep(remaining)
            busy_path.write_text(f"{time.time()} {os.getpid()}", encoding="utf-8")
            try:
                yield
            finally:
                with contextlib.suppress(OSError):
                    busy_path.write_text("0 0", encoding="utf-8")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


_cooldown_until: dict[str, float] = {}  # base_url -> monotonic deadline

#: A 1x1 grey JPEG (vision models warm on the image path too; a text-only warm-up would not).
WARM_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////////2wBDAf//////////////////////////"
    "////////////////////////////////////////////////////////////////////////////////wAARCAAB"
    "AAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAA"
    "AAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AVwD/2Q=="
)


class DeciderUnavailable(RuntimeError):
    """The decider did not give a usable answer in time: timeout, HTTP error or malformed body.

    The gate treats this as "vision unavailable" and denies motion (fail closed).
    """


def _b64(image: bytes | str) -> str:
    if isinstance(image, bytes):
        return base64.b64encode(image).decode("ascii")
    return image


def _criteria(classes: Sequence[str] | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(classes, Mapping):
        crit = {str(k): v for k, v in classes.items()}
    else:
        crit = {str(c): None for c in classes}
    if len(crit) < 2:
        raise ValueError("choice requires at least 2 classes")
    return crit


class DeciderClient:
    """Thin, synchronous client for ``POST /v1/systemone``.

    Args:
        base_url: Server root; defaults to ``$DECIDER_URL`` or ``http://127.0.0.1:8111``.
        timeout_s: Whole-request budget. Anything slower is ``DeciderUnavailable``.
        model: The ``model`` field sent with every request.
        transport: Optional ``httpx.BaseTransport`` (tests inject ``httpx.MockTransport``).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        *,
        model: str = DEFAULT_MODEL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("DECIDER_URL") or DEFAULT_DECIDER_URL).rstrip("/")
        self.timeout_s = float(timeout_s)
        self.model = model
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout_s, transport=transport)

    # -- public API ----------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """``GET /health``; raises ``DeciderUnavailable`` when the server is not answering."""
        try:
            response = self._client.get(HEALTH_PATH)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DeciderUnavailable(f"decider health failed: {exc}") from exc
        if not isinstance(body, dict):
            raise DeciderUnavailable("decider health returned a non-object body")
        return body

    def ask_noul(
        self,
        question: str,
        context: str | Mapping[str, Any] | Sequence[Any],
        image_bytes: bytes | None = None,
        *,
        criteria: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Yes/no question about ``context``. Returns ``{"yes", "probability", "latency_ms"}``.

        ``probability`` is P(true) as the server reports it; ``yes`` is ``probability >= 0.5``.
        """
        q: dict[str, Any] = {"type": "noul", "instructions": question}
        if criteria:
            q["criteria"] = dict(criteria)
        answer, latency_ms = self._ask("q", q, context, image_bytes)
        return _parse_noul(answer, latency_ms)

    def ask_choice(
        self,
        question: str,
        classes: Sequence[str] | Mapping[str, Any],
        image_bytes: bytes | None = None,
        *,
        context: str | Mapping[str, Any] | Sequence[Any] = "",
    ) -> dict[str, Any]:
        """Pick one of ``classes`` (names, or name -> description). Returns
        ``{"class", "probability", "latency_ms", "probabilities"}``.

        ``probability`` is the chosen class's own probability (``probabilities[class]``), not the
        server's normalised ``confidence``; the decision table in the gate thresholds on it.
        """
        crit = _criteria(classes)
        q: dict[str, Any] = {"type": "choice", "instructions": question, "criteria": crit}
        answer, latency_ms = self._ask("q", q, context, image_bytes)
        return _parse_choice(answer, crit, latency_ms)

    def ask_frame(
        self,
        person_question: str,
        frame_question: str,
        classes: Sequence[str] | Mapping[str, Any],
        image_bytes: bytes,
        *,
        context: str | Mapping[str, Any] | Sequence[Any] = "",
    ) -> dict[str, Any]:
        """The gate's two frame questions in one request: a yes/no "is a person visible" and
        the five-way choice, both over the same image. Returns ``{"person": <ask_noul shape>,
        "frame": <ask_choice shape>, "latency_ms"}``; both inner ``latency_ms`` are the one
        round trip, since the server answers the two questions from a shared image prefix.

        Measured on the booth model (2026-10-14): about 450 ms for both against 355 ms for the
        choice alone and 670 ms for two separate calls. Any malformed half raises
        ``DeciderUnavailable``: the gate never acts on one answer when it asked for two.
        """
        crit = _criteria(classes)
        questions: dict[str, dict[str, Any]] = {
            "person": {"type": "noul", "instructions": person_question},
            "frame": {"type": "choice", "instructions": frame_question, "criteria": crit},
        }
        answers, latency_ms = self._ask_many(questions, context, image_bytes)
        return {
            "person": _parse_noul(answers["person"], latency_ms),
            "frame": _parse_choice(answers["frame"], crit, latency_ms),
            "latency_ms": latency_ms,
        }

    def ask_many(
        self,
        questions: Mapping[str, dict[str, Any]],
        context: str | Mapping[str, Any] | Sequence[Any],
        image_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        """Several typed questions over one state in one request (one forward pass).

        ``questions`` maps a name to a System One question dict (``{"type": "noul"|"choice",
        "instructions", "criteria"?}``). Returns ``{"answers": {name: <ask_noul or ask_choice
        shape>}, "latency_ms"}``. The gate's text request rides here: the envelope yes/no, the
        grounding yes/no and the intent choice, all over the same conversation and command. Any
        malformed answer raises ``DeciderUnavailable``: the gate never acts on part of a request.
        """
        answers, latency_ms = self._ask_many(questions, context, image_bytes)
        parsed = {name: _parse_answer(q, answers[name], latency_ms) for name, q in questions.items()}
        return {"answers": parsed, "latency_ms": latency_ms}

    def warm(self, timeout_s: float = 120.0, image_bytes: bytes | None = None) -> int:
        """One throwaway question with a long budget, so the first real ask is not the cold one.

        A freshly loaded model on Apple MPS takes seconds for its first forward pass. The gate's
        1.5 s budget would give up on it, and the next request would land while that one is
        still encoding: two concurrent encodes on MPS abort the whole server (Metal
        ``"A command encoder is already encoding to this command buffer"``, seen 2026-10-15).
        Call this once, sequentially, after ``/health`` says the server is up. Returns the
        warm-up latency in ms; failures raise ``DeciderUnavailable``.
        """
        question = {"type": "noul", "instructions": "Is this a warm-up request?"}
        jpeg = image_bytes if image_bytes is not None else WARM_JPEG
        saved = self._client.timeout
        self._client.timeout = httpx.Timeout(float(timeout_s))
        _cooldown_until.pop(self.base_url, None)  # the warm-up is the recovery path; it may wait
        try:
            _, latency_ms = self._ask_many({"warm": question}, "warm-up", jpeg)
        finally:
            self._client.timeout = saved
        return latency_ms

    def close(self) -> None:
        self._client.close()

    # -- internals -----------------------------------------------------------------------

    def _ask(
        self,
        name: str,
        question: dict[str, Any],
        state: str | Mapping[str, Any] | Sequence[Any],
        image_bytes: bytes | None,
    ) -> tuple[dict[str, Any], int]:
        answers, latency_ms = self._ask_many({name: question}, state, image_bytes)
        return answers[name], latency_ms

    def _ask_many(
        self,
        questions: Mapping[str, dict[str, Any]],
        state: str | Mapping[str, Any] | Sequence[Any],
        image_bytes: bytes | None,
    ) -> tuple[dict[str, dict[str, Any]], int]:
        """One POST carrying ``questions``; every named answer must come back or the whole call
        is ``DeciderUnavailable``."""
        payload: dict[str, Any] = {
            "state": state if isinstance(state, str) else _jsonable(state),
            "model": self.model,
            "questions": dict(questions),
        }
        if image_bytes is not None:
            payload["images"] = [_b64(image_bytes)]
        # One request at a time per process, and a cooldown after a timeout: two questions in flight
        # on the MPS server abort it (Metal "command encoder already encoding", 2026-10-15/17).
        now = time.monotonic()
        until = _cooldown_until.get(self.base_url, 0.0)
        if now < until:
            raise DeciderUnavailable(f"decider cooling down for {until - now:.1f}s after a timeout")
        started = time.perf_counter()
        try:
            with _request_lock, _process_lock(self.base_url):
                response = self._client.post(SYSTEMONE_PATH, json=payload)
        except httpx.TimeoutException as exc:
            _cooldown_until[self.base_url] = time.monotonic() + COOLDOWN_AFTER_TIMEOUT_S
            raise DeciderUnavailable(f"decider timeout after {self.timeout_s:.1f}s") from exc
        except httpx.HTTPError as exc:
            raise DeciderUnavailable(f"decider transport error: {exc}") from exc
        latency_ms = round((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            detail = response.text[:200]
            raise DeciderUnavailable(f"decider HTTP {response.status_code}: {detail}")
        try:
            body = response.json()
        except ValueError as exc:
            raise DeciderUnavailable("decider returned non-JSON body") from exc
        answers = body.get("answers") if isinstance(body, dict) else None
        if not isinstance(answers, dict):
            raise DeciderUnavailable(f"decider body missing answers: {str(body)[:200]}")
        for name in questions:
            if not isinstance(answers.get(name), dict):
                raise DeciderUnavailable(f"decider body missing answers[{name!r}]: {str(body)[:200]}")
        return {name: answers[name] for name in questions}, latency_ms


def _probability(value: Any, what: str) -> float:
    """``value`` as a probability or ``DeciderUnavailable``: a real number in [0, 1], never a bool,
    a string or NaN (``json`` accepts the ``NaN`` literal, and NaN passes every ``<`` test)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DeciderUnavailable(f"malformed {what}: {value!r} is not a number")
    p = float(value)
    if math.isnan(p) or not 0.0 <= p <= 1.0:
        raise DeciderUnavailable(f"{what} out of range: {value!r}")
    return p


def _parse_noul(answer: dict[str, Any], latency_ms: int) -> dict[str, Any]:
    if answer.get("type", "noul") != "noul" or "noul" not in answer:
        raise DeciderUnavailable(f"malformed noul answer: {answer!r}")
    p = _probability(answer["noul"], "noul probability")
    return {"yes": p >= 0.5, "probability": p, "latency_ms": latency_ms}


def _parse_choice(answer: dict[str, Any], crit: Mapping[str, Any], latency_ms: int) -> dict[str, Any]:
    probs = answer.get("probabilities")
    chosen = answer.get("choice")
    if (
        answer.get("type", "choice") != "choice"
        or not isinstance(chosen, str)
        or not isinstance(probs, dict)
        or chosen not in crit
        or chosen not in probs
    ):
        raise DeciderUnavailable(f"malformed choice answer: {answer!r}")
    probabilities = {str(k): _probability(v, f"choice probability for {k!r}") for k, v in probs.items()}
    return {
        "class": chosen,
        "probability": probabilities[chosen],
        "latency_ms": latency_ms,
        "probabilities": probabilities,
    }


def _parse_answer(question: dict[str, Any], answer: dict[str, Any], latency_ms: int) -> dict[str, Any]:
    """Parse one answer by its question's type (``noul`` or ``choice``; ``score`` is not used here)."""
    qtype = question.get("type", "noul")
    if qtype == "noul":
        return _parse_noul(answer, latency_ms)
    if qtype == "choice":
        return _parse_choice(answer, _criteria(question["criteria"]), latency_ms)
    raise DeciderUnavailable(f"unsupported question type {qtype!r}")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


__all__ = ["DEFAULT_DECIDER_URL", "DEFAULT_TIMEOUT_S", "DeciderClient", "DeciderUnavailable"]
