"""Laptop side of the PWM sampler: ship ``remote_sampler.py`` to the car over SSH and read it back.

``PwmSampler`` starts ``python3 -u -c <remote_sampler>`` on the car through ``car/connect/car.sh
ssh`` (credentials stay in ``~/.config/deepracer/env``), reads ``S <t> <duty0> <duty1>`` lines
at 100 Hz into memory, and lets a test stamp laptop events onto the car's clock with ``mark()``:
the line goes down the SSH channel and comes back as ``M <t_car> <label>``. The RTT of a few
``ping`` marks gives the one-way delay (half the minimum round trip), which is the error bar on
every latency measured this way. Physics stops the car; this is the ruler we hold against it.
"""

from __future__ import annotations

import base64
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CAR_SH = HERE.parents[1] / "car" / "connect" / "car.sh"
REMOTE = HERE / "remote_sampler.py"
PWM0 = "/sys/class/pwm/pwmchip0/pwm0/duty_cycle"  # throttle
PWM1 = "/sys/class/pwm/pwmchip0/pwm1/duty_cycle"  # steering


@dataclass
class Sample:
    t_car: float
    values: list[int]
    t_laptop_recv: float


@dataclass
class Mark:
    label: str
    t_laptop_sent: float
    t_car: float | None = None
    t_laptop_recv: float | None = None

    @property
    def rtt_ms(self) -> float | None:
        if self.t_laptop_recv is None:
            return None
        return (self.t_laptop_recv - self.t_laptop_sent) * 1000.0


@dataclass
class PwmSampler:
    """One sampler run on the car. ``start()``, ``mark()``, ``stop()``; then read ``samples``."""

    files: tuple[str, ...] = (PWM0, PWM1)
    rate_hz: float = 100.0
    duration_s: float = 40.0
    samples: list[Sample] = field(default_factory=list)
    marks: dict[str, Mark] = field(default_factory=dict)
    raw: list[str] = field(default_factory=list)
    one_way_ms: float | None = None
    _proc: Any = None
    _thread: Any = None
    _ready: threading.Event = field(default_factory=threading.Event)
    _ended: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _mark_seq: int = 0

    def start(self, timeout: float = 20.0) -> PwmSampler:
        code = base64.b64encode(REMOTE.read_bytes()).decode()
        remote = (
            f'python3 -u -c "$(echo {code} | base64 -d)" --rate {self.rate_hz:g} '
            f"--duration {self.duration_s:g} {' '.join(self.files)}"
        )
        self._proc = subprocess.Popen(
            ["bash", str(CAR_SH), "ssh", remote],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._reader, name="pwm-sampler-reader", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            self.stop()
            raise RuntimeError("PWM sampler did not report READY (ssh or python3 on the car failed)")
        return self

    def _reader(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            now = time.monotonic()
            line = line.rstrip("\r\n")
            if not line:
                continue
            with self._lock:
                self.raw.append(line)
                parts = line.split()
                if parts[0] == "S" and len(parts) >= 3:
                    try:
                        self.samples.append(Sample(float(parts[1]), [int(v) for v in parts[2:]], now))
                    except ValueError:
                        pass
                elif parts[0] == "M" and len(parts) >= 3:
                    mark = self.marks.get(parts[2])
                    if mark is not None:
                        mark.t_car = float(parts[1])
                        mark.t_laptop_recv = now
                elif parts[0] == "READY":
                    self._ready.set()
                elif parts[0] == "END":
                    self._ended.set()
        self._ended.set()

    def mark(self, label: str) -> Mark:
        """Stamp ``label`` onto the car clock now. Returns the Mark (filled in asynchronously)."""
        assert self._proc is not None and self._proc.stdin is not None
        with self._lock:
            self._mark_seq += 1
            label = f"{label}#{self._mark_seq}" if label in self.marks else label
            mark = Mark(label, time.monotonic())
            self.marks[label] = mark
        self._proc.stdin.write(label + "\n")
        self._proc.stdin.flush()
        return mark

    def wait_mark(self, mark: Mark, timeout: float = 2.0) -> Mark:
        deadline = time.monotonic() + timeout
        while mark.t_car is None and time.monotonic() < deadline:
            time.sleep(0.002)
        return mark

    def measure_one_way(self, pings: int = 5) -> float:
        """Half the minimum RTT of ``pings`` marks, in ms; stored on ``one_way_ms``."""
        rtts: list[float] = []
        for i in range(pings):
            m = self.wait_mark(self.mark(f"ping{i}"))
            if m.rtt_ms is not None:
                rtts.append(m.rtt_ms)
            time.sleep(0.05)
        if not rtts:
            raise RuntimeError("no ping mark came back from the sampler")
        self.one_way_ms = min(rtts) / 2.0
        return self.one_way_ms

    def stop(self) -> list[Sample]:
        if self._proc is None:
            return self.samples
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.write("Q\n")
                self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        self._ended.wait(5.0)
        try:
            self._proc.wait(5.0)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None
        return self.samples

    # -- analysis ----------------------------------------------------------------------------

    def value_at(self, t_car: float, channel: int = 0) -> int | None:
        """The last sampled value at or before ``t_car``."""
        last = None
        for s in self.samples:
            if s.t_car > t_car:
                break
            last = s.values[channel] if channel < len(s.values) else None
        return last

    def first_after(self, t_car: float, channel: int, predicate: Any) -> Sample | None:
        for s in self.samples:
            if s.t_car >= t_car and channel < len(s.values) and predicate(s.values[channel]):
                return s
        return None

    def values_between(self, t0: float, t1: float, channel: int = 0) -> list[int]:
        return [s.values[channel] for s in self.samples if t0 <= s.t_car <= t1 and channel < len(s.values)]

    def latency_ms(self, mark: Mark, channel: int, predicate: Any) -> dict[str, Any]:
        """From ``mark`` to the first sample (same channel) satisfying ``predicate``, in ms.

        ``raw_ms`` is car-clock difference; ``corrected_ms`` adds the one-way delay (the mark
        reached the car that much after the laptop event). ``None`` when never satisfied.
        """
        self.wait_mark(mark)
        if mark.t_car is None:
            return {"raw_ms": None, "corrected_ms": None, "one_way_ms": self.one_way_ms}
        hit = self.first_after(mark.t_car, channel, predicate)
        if hit is None:
            return {"raw_ms": None, "corrected_ms": None, "one_way_ms": self.one_way_ms}
        raw = (hit.t_car - mark.t_car) * 1000.0
        corrected = raw + (self.one_way_ms or 0.0)
        return {
            "raw_ms": round(raw, 1),
            "corrected_ms": round(corrected, 1),
            "one_way_ms": None if self.one_way_ms is None else round(self.one_way_ms, 1),
        }

    def dump(self) -> dict[str, Any]:
        return {
            "files": list(self.files),
            "rate_hz": self.rate_hz,
            "one_way_ms": self.one_way_ms,
            "marks": {
                k: {"t_car": m.t_car, "rtt_ms": None if m.rtt_ms is None else round(m.rtt_ms, 1)}
                for k, m in self.marks.items()
            },
            "samples": [[round(s.t_car, 4), *s.values] for s in self.samples],
        }


__all__ = ["PWM0", "PWM1", "Mark", "PwmSampler", "Sample"]
