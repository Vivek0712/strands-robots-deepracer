"""Motion curves, post effects and custom transitions for the demo video renderer.

Pure numpy/Pillow helpers with no knowledge of shots or fonts: named easing curves
(CSS cubic-bezier solved per frame), the per-frame post pass (vignette, seeded
luminance grain), letterbox geometry, and the frame composers behind the
``push_left``/``push_right``/``whip`` transitions that ffmpeg's ``xfade`` cannot do
with an eased curve.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

import numpy as np
from PIL import Image

# --------------------------------------------------------------------------- easing

# CSS cubic-bezier control points (x1, y1, x2, y2); P0 = (0, 0), P3 = (1, 1).
BEZIERS: dict[str, tuple[float, float, float, float]] = {
    "ease_out": (0.16, 1.0, 0.3, 1.0),
    "ease_in_out": (0.65, 0.0, 0.35, 1.0),
    "ease_in": (0.32, 0.0, 0.67, 0.0),
    # the named curves of DESIGN.md section 7 (v4)
    "enter": (0.16, 1.0, 0.30, 1.0),
    "exit": (0.70, 0.0, 0.84, 0.0),
    "move": (0.65, 0.0, 0.35, 1.0),
    "camera": (0.76, 0.0, 0.24, 1.0),
    "draw": (0.22, 1.0, 0.36, 1.0),
    "count": (0.16, 1.0, 0.30, 1.0),
    "drift": (0.37, 0.0, 0.63, 1.0),
}
EASES = {"linear", "smooth", "spring", *BEZIERS}
DEFAULT_EASE = "ease_out"
LEGACY_EASE = "smooth"  # the smoothstep curve every pre-v3 element used
SPRING_C1 = 1.2  # back-out overshoot constant: peaks at about 1.05


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def smoothstep(x: float) -> float:
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def _bezier_y(x1: float, y1: float, x2: float, y2: float, x: float) -> float:
    """y of the cubic bezier at the parameter where its x equals ``x`` (Newton, then bisection)."""
    cx, cy = 3 * x1, 3 * y1
    bx, by = 3 * (x2 - x1) - cx, 3 * (y2 - y1) - cy
    ax, ay = 1 - cx - bx, 1 - cy - by

    def sx(t: float) -> float:
        return ((ax * t + bx) * t + cx) * t

    t = x
    for _ in range(8):
        err = sx(t) - x
        if abs(err) < 1e-7:
            break
        d = (3 * ax * t + 2 * bx) * t + cx
        if abs(d) < 1e-6:
            break
        t -= err / d
    if not (0.0 <= t <= 1.0) or abs(sx(t) - x) > 1e-6:
        lo, hi = 0.0, 1.0
        for _ in range(40):
            t = (lo + hi) / 2
            if sx(t) < x:
                lo = t
            else:
                hi = t
    return ((ay * t + by) * t + cy) * t


@lru_cache(maxsize=65536)
def _ease_cached(name: str, q: int) -> float:
    u = q / 4096.0
    if name == "spring":
        v = u - 1.0
        return 1.0 + (SPRING_C1 + 1.0) * v * v * v + SPRING_C1 * v * v
    x1, y1, x2, y2 = BEZIERS[name]
    return _bezier_y(x1, y1, x2, y2, u)


def ease(name: str | None, u: float) -> float:
    """Eased 0..1 for a linear 0..1 input (clamped). ``spring`` may exceed 1 by about 5 percent."""
    u = clamp01(u)
    if name in (None, "linear"):
        return u
    if name == "smooth":
        return u * u * (3 - 2 * u)
    if name not in EASES:
        raise ValueError(f"unknown ease {name!r}; expected one of {sorted(EASES)}")
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    return _ease_cached(name, round(u * 4096))


def is_ease(name: Any) -> bool:
    return isinstance(name, str) and name in EASES


def resolve_ease(explicit: Any, default: str | None, legacy: bool) -> str:
    """Curve for one element: its own ``ease``, else the shot list's, else ``smooth`` for
    pre-v3 element kinds (so an unchanged shot list renders as before) or ``ease_out``."""
    if explicit:
        if not is_ease(explicit):
            raise ValueError(f"unknown ease {explicit!r}; expected one of {sorted(EASES)}")
        return str(explicit)
    if default:
        return default
    return LEGACY_EASE if legacy else DEFAULT_EASE


def breathe(t: float, period: float, low: float = 0.4) -> float:
    """LED-style pulse: an eased sine between ``low`` and 1 with the given period in seconds."""
    if period <= 0:
        return 1.0
    raw = 0.5 - 0.5 * math.cos(2 * math.pi * t / period)
    return low + (1.0 - low) * smoothstep(raw)


# --------------------------------------------------------------------------- post pass


class Post:
    """Vignette and seeded luminance grain applied to every composed frame before encode.

    The vignette is a fixed multiplier map; grain is a bank of pre-drawn noise tiles
    (``seed``) rolled by a deterministic offset per frame, so a render is reproducible
    and unchanged shots stay cache-stable.
    """

    def __init__(
        self,
        width: int,
        height: int,
        vignette: float = 0.0,
        grain: float = 0.0,
        seed: int = 7,
        grain_size: float = 2.0,
        inner: float = 0.38,
    ):
        self.width, self.height = width, height
        self.vignette = float(vignette)
        self.grain = float(grain)
        self.seed = int(seed)
        self.grain_size = max(1.0, float(grain_size))
        self.inner = min(0.99, max(0.0, float(inner)))
        self.vig: np.ndarray | None = None
        if self.vignette > 0:
            ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
            nx = (xs - (width - 1) / 2) / (width / 2)
            ny = (ys - (height - 1) / 2) / (height / 2)
            r = np.sqrt(nx * nx + ny * ny) / math.sqrt(2.0)
            # zero inside r = inner of the half-diagonal, the full amount at the corners
            k = np.clip((r - self.inner) / (1.0 - self.inner), 0.0, 1.0)
            k = k * k * (3 - 2 * k)
            self.vig = (1.0 - self.vignette * k).astype(np.float32)[..., None]
            # a fixed sub-LSB dither so the falloff does not band on flat dark backgrounds
            rng = np.random.default_rng(self.seed + 1)
            self.dither = rng.uniform(-0.5, 0.5, size=(height, width, 1)).astype(np.float32)
        self.bank: list[np.ndarray] = []
        if self.grain > 0:
            # grain is drawn at 1/grain_size resolution and upsampled bilinearly: softer clumps
            # like film grain, and far fewer bits for the encoder than per-pixel noise
            rng = np.random.default_rng(self.seed)
            std = self.grain * 255.0
            gw, gh = max(2, round(width / self.grain_size)), max(2, round(height / self.grain_size))
            for _ in range(8):
                noise = rng.normal(0.0, std, size=(gh, gw)).astype(np.float32)
                if (gw, gh) != (width, height):
                    small = Image.fromarray(noise, "F")
                    noise = np.array(
                        small.resize((width, height), Image.Resampling.BILINEAR), dtype=np.float32
                    )
                    noise *= self.grain_size**0.5  # bilinear averaging lowers the variance; put it back
                self.bank.append(np.clip(noise, -4 * std, 4 * std).astype(np.int16))

    @property
    def active(self) -> bool:
        return self.vig is not None or bool(self.bank)

    @property
    def per_frame(self) -> bool:
        return bool(self.bank)

    def static(self, img: Image.Image) -> Image.Image:
        """The frame-independent part (vignette)."""
        if self.vig is None:
            return img
        arr = np.asarray(img, dtype=np.float32)
        out = np.rint(arr * self.vig + self.dither).clip(0, 255).astype(np.uint8)
        return Image.fromarray(out, "RGB")

    def grain_bytes(self, arr: np.ndarray, index: int) -> bytes:
        """The frame ``arr`` (uint8 HxWx3) with the grain tile for frame ``index`` added, as bytes."""
        if not self.bank:
            return arr.tobytes()
        tile = self.bank[index % len(self.bank)]
        # a different roll each frame breaks the tile periodicity without a fresh RNG draw
        h = (index * 7919 + self.seed) % self.height
        w = (index * 104729 + self.seed * 3) % self.width
        noise = np.roll(np.roll(tile, h, axis=0), w, axis=1)[..., None]
        out = arr.astype(np.int16) + noise
        return np.clip(out, 0, 255).astype(np.uint8).tobytes()


def letterbox_bars(width: int, height: int, letterbox: float) -> int:
    """Bar height in px for ``letterbox`` given as an aspect ratio (2.39) or a bar height in px."""
    if not letterbox or letterbox <= 0:
        return 0
    if letterbox > 20:  # px
        return int(letterbox)
    target_h = width / float(letterbox)
    if target_h >= height:
        return 0
    bar = round((height - target_h) / 2)
    return bar - bar % 2


# --------------------------------------------------------------------------- transitions

CUSTOM_TRANSITIONS = {"push_left", "push_right", "whip"}


def push(a: np.ndarray, b: np.ndarray, p: float, direction: str = "left") -> np.ndarray:
    """Both frames move: ``a`` leaves and ``b`` enters from the opposite edge; ``p`` is eased 0..1."""
    w = a.shape[1]
    shift = round(clamp01(p) * w)
    out = np.empty_like(a)
    if shift <= 0:
        out[:] = a
        return out
    if shift >= w:
        out[:] = b
        return out
    if direction == "left":
        out[:, : w - shift] = a[:, shift:]
        out[:, w - shift :] = b[:, :shift]
    else:
        out[:, shift:] = a[:, : w - shift]
        out[:, :shift] = b[:, w - shift :]
    return out


def dissolve(a: np.ndarray, b: np.ndarray, p: float) -> np.ndarray:
    """A plain cross-dissolve between two frames at mix ``p`` (0 = a, 1 = b)."""
    u = clamp01(p)
    out = a.astype(np.float32) * (1.0 - u) + b.astype(np.float32) * u
    return out.clip(0, 255).astype(np.uint8)


def whip(a: np.ndarray, b: np.ndarray, p0: float, p1: float, direction: str = "left") -> np.ndarray:
    """A push averaged over the progress interval [p0, p1] of this frame: directional motion blur.

    Both frames move at the same speed, so the time average equals a horizontal box blur of
    the joined strip ``a | b`` with a kernel as wide as this frame's travel, cropped at the
    frame's mid position. Done with a cumulative sum, so the streak is smooth at any speed.
    """
    h, w = a.shape[:2]
    pm = clamp01((p0 + p1) / 2)
    k = round(abs(p1 - p0) * w)
    if k <= 1:
        return push(a, b, pm, direction)
    strip = np.concatenate([a, b] if direction == "left" else [b, a], axis=1).astype(np.float32)
    x0 = pm * w if direction == "left" else (1.0 - pm) * w
    lo = round(x0 - k / 2)
    half = k // 2 + 1
    padded = np.pad(strip, ((0, 0), (half, half), (0, 0)), mode="edge")
    csum = np.cumsum(padded, axis=1)
    csum = np.concatenate([np.zeros((h, 1, 3), dtype=np.float32), csum], axis=1)
    # output column c averages strip[c + lo : c + lo + k], shifted by the left padding
    start = np.arange(w) + lo + half
    start = np.clip(start, 0, padded.shape[1] - k)
    out = (csum[:, start + k] - csum[:, start]) / k
    return out.clip(0, 255).astype(np.uint8)


__all__ = [
    "BEZIERS",
    "CUSTOM_TRANSITIONS",
    "DEFAULT_EASE",
    "EASES",
    "LEGACY_EASE",
    "Post",
    "breathe",
    "clamp01",
    "dissolve",
    "ease",
    "is_ease",
    "letterbox_bars",
    "push",
    "resolve_ease",
    "smoothstep",
    "whip",
]
