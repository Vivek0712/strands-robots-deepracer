"""One small JSON file that the three fakes share, so they agree on what the car is seeing.

The fake car owns the car's state (frame label, battery level, calibration profile). The fake
console and the fake decider need the same facts to serve a consistent picture, and they may
run in another process (`make fake-console` next to `make fake-car`). Rather than have them
poll each other over HTTP, every writer updates `runs/sim/shared.json` atomically and every
reader re-reads it when its mtime changes. The file lives under `runs/` (gitignored); override
the path with `DEEPRACER_SIM_SHARED`.

Keys: `label` (frame label, see `harness.frames.LABELS`), `battery` (int, -1..10),
`calibration` (`"uninitialised"` or `"calibrated"`).
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {"label": "clear", "battery": 10, "calibration": "calibrated"}


def default_path() -> Path:
    env = os.environ.get("DEEPRACER_SIM_SHARED")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "runs" / "sim" / "shared.json"


class SharedState:
    """Atomic, mtime-cached JSON key/value store shared by the fakes."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_path()
        self._lock = threading.RLock()
        self._cache: dict[str, Any] = dict(DEFAULTS)
        self._mtime: float | None = None

    def _load(self) -> None:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            self._cache = dict(DEFAULTS)
            self._mtime = None
            return
        if self._mtime is not None and stat.st_mtime_ns == self._mtime:
            return
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            self._cache = {**DEFAULTS, **data}
            self._mtime = stat.st_mtime_ns

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            self._load()
            return self._cache.get(key, DEFAULTS.get(key, default))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._load()
            return dict(self._cache)

    def set(self, **values: Any) -> dict[str, Any]:
        with self._lock:
            self._load()
            self._cache.update(values)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._cache, sort_keys=True))
            os.replace(tmp, self.path)
            self._mtime = self.path.stat().st_mtime_ns
            return dict(self._cache)

    def reset(self) -> dict[str, Any]:
        return self.set(**DEFAULTS)


__all__ = ["DEFAULTS", "SharedState", "default_path"]
