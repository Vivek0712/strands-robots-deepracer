"""A decider that always knows what the fake camera is showing, so sim runs are deterministic.

The real strands-decider serves `POST /v1/systemone` and `GET /health` (see
`src/strands_decider/server.py` and `schema.py` in strands-labs/strands-decider). The request is
`{"state": <str|dict|list>, "questions": {"<name>": {"type": "noul|choice|score",
"instructions": ..., "criteria": ...}}, "model": "...", "images": ["<base64 or data: URI>"],
"audio": []}`; the response is `{"model": ..., "answers": {"<name>": {"type": "noul", "noul":
p} | {"type": "choice", "choice": name, "probabilities": {...}, "confidence": c} | {"type":
"score", "score": s, "legend": {...}, "probabilities": {...}, "confidence": c}}, "usage":
{"input_tokens", "output_tokens"}, "latency_ms": ms}`. This fake keeps those field names
exactly and answers from the shared frame label instead of a model: a `choice` over the frame
classes returns the label's class (clear 0.93, person_in_frame 0.97, hand over the lens or an
unclear frame -> unclear 0.9, the Sign card -> clear 0.8), a `noul` envelope question parses the
numbers in the command text against the bounds in the envelope text, and a `noul` about a
frame class answers from the label. Physics stops the car; the decider explains. A gate that
fails closed can be proven here: `/control?latency_ms=3000` makes every answer slow and
`/control?fail=1` makes every answer HTTP 500 (`fail=hang` never answers).

Run it: `python -m harness.fake_decider` on `http://127.0.0.1:8111`.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from harness import DECIDER_PORT
from harness.frames import FRAME_CLASSES, LABEL_TO_CLASS, LABELS
from harness.shared import SharedState

logger = logging.getLogger("harness.fake_decider")

MODEL_NAME = "fake-decider"
ENVELOPE_KEYS = ("linear", "angular", "duration")
#: Words in a noul question that mean "is the frame <class>?", answered from the label.
NOUL_CLASS_HINTS: dict[str, tuple[str, ...]] = {
    "person_in_frame": ("person", "people", "human", "someone"),
    "obstacle_near": ("obstacle", "object close", "blocked"),
    "off_surface": ("off the surface", "off surface", "edge", "carpet"),
    "unclear": ("unclear", "dark", "covered", "blind", "obscured"),
    "clear": ("clear", "safe to drive", "path ahead", "free"),
}
_NUMBER = r"[-+]?\d+(?:\.\d+)?"


def render(content: Any) -> str:
    """Text view of a `state` or `instructions` value (str, dict or list)."""
    if isinstance(content, str):
        return content
    return json.dumps(content, sort_keys=True)


def derive_confidence(probabilities: list[float]) -> float:
    n = len(probabilities)
    if n <= 1:
        return 1.0
    p_max = max(probabilities)
    return float(max(0.0, min(1.0, (n * p_max - 1.0) / (n - 1.0))))


def parse_bounds(text: str) -> dict[str, float]:
    """Largest absolute number that follows each envelope key within a short window."""
    bounds: dict[str, float] = {}
    for key in ENVELOPE_KEYS:
        for m in re.finditer(rf"\b{key}\w*\b[^\d\n]{{0,40}}?({_NUMBER})", text, flags=re.IGNORECASE):
            value = abs(float(m.group(1)))
            bounds[key] = max(bounds.get(key, 0.0), value)
    return bounds


def parse_values(text: str) -> dict[str, float]:
    """First number that follows each envelope key (the command's value)."""
    values: dict[str, float] = {}
    for key in ENVELOPE_KEYS:
        m = re.search(rf"\b{key}\w*\b[^\d\n]{{0,12}}?({_NUMBER})", text, flags=re.IGNORECASE)
        if m:
            values[key] = float(m.group(1))
    return values


def split_command_envelope(state: Any, instructions: Any) -> tuple[str, str]:
    """Separate the command text from the envelope text.

    A dict state with `command` and `envelope` keys (any spelling of `envelope`, e.g.
    `briefed_envelope`) is split by key. Otherwise the combined text is split at the first word
    `envelope`: the command comes before it, the bounds after. With neither, both halves are
    the whole text and only keys stated once can be checked.
    """
    if isinstance(state, dict):
        cmd = next((state[k] for k in state if "command" in k.lower()), None)
        env = next((state[k] for k in state if "envelope" in k.lower()), None)
        if cmd is not None and env is not None:
            return render(cmd), render(env)
    state_text = render(state)
    m = re.search(r"envelope", state_text, flags=re.IGNORECASE)
    if m:
        return state_text[: m.start()], state_text[m.end() :]
    text = render(instructions) + "\n" + state_text
    return text, text


def envelope_verdict(command_text: str, envelope_text: str) -> tuple[float, dict[str, Any]]:
    """P(inside envelope) from the numbers alone: 0.95 inside, 0.05 outside, 0.5 unparseable."""
    bounds = parse_bounds(envelope_text)
    values = parse_values(command_text)
    checked = {k: (values[k], bounds[k]) for k in values if k in bounds}
    if not checked:
        return 0.5, {"bounds": bounds, "values": values, "checked": {}}
    violated = {k: v for k, v in checked.items() if abs(v[0]) > v[1] + 1e-9}
    p = 0.05 if violated else 0.95
    return p, {"bounds": bounds, "values": values, "checked": checked, "violated": violated}


class ValidationError(ValueError):
    """A request pydantic would refuse with 422."""


def validate(req: Any) -> dict[str, Any]:
    if not isinstance(req, dict):
        raise ValidationError("body must be a JSON object")
    if "state" not in req or not isinstance(req["state"], str | dict | list):
        raise ValidationError("state must be a string, object or array")
    questions = req.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise ValidationError("questions must be a non-empty object")
    for name, q in questions.items():
        if not isinstance(q, dict):
            raise ValidationError(f"question {name!r} must be an object")
        qtype = q.get("type", "noul")
        if qtype not in ("noul", "choice", "score"):
            raise ValidationError(f"question {name!r}: unknown type {qtype!r}")
        if "instructions" not in q:
            raise ValidationError(f"question {name!r}: instructions is required")
        criteria = q.get("criteria")
        if qtype == "choice":
            if not isinstance(criteria, dict) or len(criteria) < 2:
                raise ValidationError(f"question {name!r}: choice requires at least 2 options")
        elif qtype == "score":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
                raise ValidationError(f"question {name!r}: score requires between 2 and 10 levels")
        elif criteria is not None and (
            not isinstance(criteria, dict) or not set(criteria) <= {"true", "false"}
        ):
            raise ValidationError(
                f"question {name!r}: noul criteria keys must be a subset of {{'true', 'false'}}"
            )
    for field in ("images", "audio"):
        items = req.get(field, [])
        if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
            raise ValidationError(f"{field} must be a list of strings")
    return req


class FakeDecider:
    """The emulated decider server; `latency_ms`, `fail` and `noul_override` are the knobs."""

    def __init__(
        self, host: str = "127.0.0.1", port: int = DECIDER_PORT, *, shared: SharedState | None = None
    ) -> None:
        self.host = host
        self.port = port
        self.shared = shared or SharedState()
        self.latency_ms = 0
        self.fail: str = "0"
        self.noul_override: float | None = None
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> FakeDecider:
        if self._server is not None:
            return self
        self._server = ThreadingHTTPServer((self.host, self.port), _handler(self))
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, name="fake-decider", daemon=True)
        self._thread.start()
        logger.info("fake decider on %s", self.url)
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> FakeDecider:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def reset(self) -> None:
        with self._lock:
            self.latency_ms = 0
            self.fail = "0"
            self.noul_override = None
            self.calls.clear()

    def label(self) -> str:
        label = str(self.shared.get("label", "clear"))
        return label if label in LABELS else "clear"

    def control(self) -> dict[str, Any]:
        with self._lock:
            return {
                "latency_ms": self.latency_ms,
                "fail": self.fail,
                "noul": self.noul_override,
                "label": self.label(),
                "calls": len(self.calls),
            }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "model": MODEL_NAME,
            "checkpoint": "harness/fake_decider.py",
            "base_model": "none",
            "num_slots": 16,
            "max_length": 4096,
            "temperature": 1.0,
            "device": "cpu",
            "prefix_cache": False,
            "vision": True,
            "audio": False,
        }

    # answers ------------------------------------------------------------
    def answer(self, req: dict[str, Any]) -> dict[str, Any]:
        label = self.label()
        state_text = render(req["state"])
        answers: dict[str, Any] = {}
        for name, q in req["questions"].items():
            qtype = q.get("type", "noul")
            if qtype == "choice":
                answers[name] = self._choice(q, label)
            elif qtype == "score":
                answers[name] = self._score(q)
            else:
                answers[name] = self._noul(q, req["state"], label)
        usage = {
            "input_tokens": max(
                1, (len(state_text) + sum(len(render(q)) for q in req["questions"].values())) // 4
            )
        }
        usage["output_tokens"] = 0
        return {"model": req.get("model") or MODEL_NAME, "answers": answers, "usage": usage}

    @staticmethod
    def _choice(q: dict[str, Any], label: str) -> dict[str, Any]:
        options = list(q["criteria"])
        cls, p = LABEL_TO_CLASS[label]
        if cls not in options:
            if set(options) & set(FRAME_CLASSES):
                cls, p = ("unclear", 0.9) if "unclear" in options else (options[0], 0.6)
            else:
                cls, p = options[0], 0.6
        rest = (1.0 - p) / max(1, len(options) - 1)
        probs = {o: round(p if o == cls else rest, 4) for o in options}
        return {
            "type": "choice",
            "choice": cls,
            "probabilities": probs,
            "confidence": round(derive_confidence(list(probs.values())), 4),
        }

    def _noul(self, q: dict[str, Any], state: Any, label: str) -> dict[str, Any]:
        with self._lock:
            override = self.noul_override
        if override is not None:
            return {"type": "noul", "noul": round(float(override), 4)}
        text = render(q["instructions"]) + "\n" + render(state)
        lowered = text.lower()
        envelope_question = any(k in lowered for k in ("envelope", "command", "within"))
        cls, p = LABEL_TO_CLASS[label]
        if not envelope_question:
            for frame_class, hints in NOUL_CLASS_HINTS.items():
                if any(h in lowered for h in hints):
                    return {"type": "noul", "noul": round(p if cls == frame_class else 1.0 - p, 4)}
            return {"type": "noul", "noul": 0.5}
        cmd_text, env_text = split_command_envelope(state, q["instructions"])
        p_env, detail = envelope_verdict(cmd_text, env_text)
        if isinstance(state, dict) and "deterministic_check" in state:
            # The gate sends its own numeric check beside the question; agree with it unless
            # the parsed numbers contradict it (then the numbers win, as a real decider would).
            check_ok = str(state["deterministic_check"]).strip().lower() == "ok"
            p_env = 0.05 if (not check_ok or detail.get("violated")) else 0.95
        return {"type": "noul", "noul": round(p_env, 4)}

    @staticmethod
    def _score(q: dict[str, Any]) -> dict[str, Any]:
        levels = list(q["criteria"])
        n = len(levels)
        mid = (n - 1) // 2
        probs = [0.1 / max(1, n - 1)] * n
        probs[mid] = 0.9
        total = sum(probs)
        probs = [x / total for x in probs]
        score = sum(i * p for i, p in enumerate(probs))
        return {
            "type": "score",
            "score": round(score, 4),
            "legend": {str(i): str(level) for i, level in enumerate(levels)},
            "probabilities": {str(i): round(p, 4) for i, p in enumerate(probs)},
            "confidence": 0.85,
        }


def _handler(decider: FakeDecider) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "uvicorn (fake)"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("decider " + fmt, *args)

        def _json(self, code: int, payload: Any) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            q = {k: v[-1] for k, v in parse_qs(url.query).items()}
            if url.path == "/health":
                self._json(200, decider.health())
            elif url.path == "/control":
                try:
                    with decider._lock:
                        if "latency_ms" in q:
                            decider.latency_ms = max(0, int(q["latency_ms"]))
                        if "fail" in q:
                            decider.fail = (
                                q["fail"]
                                if q["fail"] in {"0", "1", "hang"}
                                else ("1" if q["fail"].lower() in {"true", "yes"} else "0")
                            )
                        if "noul" in q:
                            decider.noul_override = (
                                None if q["noul"] in {"", "none", "null"} else float(q["noul"])
                            )
                    if "label" in q:
                        if q["label"] not in LABELS:
                            raise ValueError(f"unknown label {q['label']!r}")
                        decider.shared.set(label=q["label"])
                    if q.get("reset"):
                        decider.reset()
                except ValueError as exc:
                    self._json(400, {"detail": str(exc)})
                    return
                self._json(200, decider.control())
            else:
                self._json(404, {"detail": "Not Found"})

        def do_POST(self) -> None:
            url = urlsplit(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if url.path == "/control":
                self.path = "/control?" + raw.decode("utf-8", "replace")
                self.do_GET()
                return
            if url.path != "/v1/systemone":
                self._json(404, {"detail": "Not Found"})
                return
            started = time.perf_counter()
            try:
                req = validate(json.loads(raw.decode("utf-8")))
            except (ValueError, UnicodeDecodeError) as exc:
                self._json(422, {"detail": [{"loc": ["body"], "msg": str(exc), "type": "value_error"}]})
                return
            with decider._lock:
                latency = decider.latency_ms
                fail = decider.fail
                decider.calls.append(
                    {
                        "ts": time.time(),
                        "label": decider.label(),
                        "questions": {k: v.get("type", "noul") for k, v in req["questions"].items()},
                        "images": len(req.get("images", [])),
                        "fail": fail,
                        "latency_ms": latency,
                    }
                )
            if fail == "hang":
                time.sleep(30)
                self._json(504, {"detail": "injected hang"})
                return
            if latency:
                time.sleep(latency / 1000.0)
            if fail == "1":
                self._json(500, {"detail": "injected failure"})
                return
            payload = decider.answer(req)
            payload["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            self._json(200, payload)

    return Handler


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=DECIDER_PORT)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(name)s %(message)s")
    with FakeDecider(port=a.port) as decider:
        print(f"fake decider: {decider.url}/v1/systemone  health: {decider.url}/health  (Ctrl-C)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
