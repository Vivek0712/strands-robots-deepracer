"""Pure-PIL drawing for the demo video renderer.

Every frame of a card, terminal, table or JSON shot, and every text or pointer
overlay on top of a clip or still, is drawn here with Pillow in a 1920x1080
reference coordinate space. A Canvas carries the scale factor so the same shot
list renders at draft size (960x540) or full size without any change to the
numbers a writer typed. Nothing in this module talks to ffmpeg or the network.
"""

from __future__ import annotations

import bisect
import itertools
import json
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, features

from .fx import breathe, clamp01, ease, resolve_ease, smoothstep

REF_W, REF_H = 1920, 1080
SAFE_X, SAFE_Y = 96, 72

PALETTE: dict[str, str] = {
    "bg": "#0b0b10",
    "ink": "#f2f2f7",
    "ink-dim": "#a0a0ad",
    "text": "#f2f2f7",
    "muted": "#a0a0ad",
    "orange": "#ff6b3d",
    "cyan": "#3ddcff",
    "violet": "#7c5cff",
    "green": "#3fb950",
    "amber": "#ffb347",
    "red": "#ff4d4f",
    "panel": "#15161c",
    "panel_border": "#262833",
    "surface": "#13131a",
    "surface2": "#1a1a23",
    "ink-mute": "#6b6b78",
    "black": "#000000",
    "white": "#ffffff",
}

DEFAULT_FONTS = {
    "sans": [
        "/System/Library/Fonts/HelveticaNeue.ttc:0",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "sans_bold": [
        "/System/Library/Fonts/HelveticaNeue.ttc:1",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "sans_medium": [
        "/System/Library/Fonts/HelveticaNeue.ttc:10",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "sans_medium_italic": [
        "/System/Library/Fonts/HelveticaNeue.ttc:11",
        "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    ],
    "mono": [
        "/System/Library/Fonts/Menlo.ttc:0",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
    "mono_bold": [
        "/System/Library/Fonts/Menlo.ttc:1",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ],
}

FADE_IN = 0.4
FADE_OUT = 0.3
SLIDE_PX = 36
RISE_PX = 24
WIPE_SOFT_PX = 8
BLUR_IN_PX = 8
SCALE_IN_FROM = 0.96
POP_FROM = 0.8
LEGACY_ANIMS = {"fade", "slide_up", "slide_left", "typewriter", "none"}
ENTER_ANIMS = {"rise", "scale_in", "wipe", "blur_in", "pop", "rise_left", "rise_right"}
ANIMS = LEGACY_ANIMS | ENTER_ANIMS
VERDICT_COLORS = {"proceed": "green", "guide": "amber", "confirm": "cyan", "deny": "red"}


# --------------------------------------------------------------------------- colours


def rgba(c: Any, alpha: float = 1.0) -> tuple[int, int, int, int]:
    """Palette name, #rrggbb, #rrggbbaa or (r,g,b[,a]) tuple to an RGBA tuple."""
    a = round(255 * max(0.0, min(1.0, alpha)))
    if isinstance(c, (list, tuple)):
        r, g, b = int(c[0]), int(c[1]), int(c[2])
        if len(c) > 3:
            a = round(int(c[3]) * alpha)
        return (r, g, b, a)
    s = PALETTE.get(str(c), str(c))
    s = s.lstrip("#")
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)
    if len(s) == 8:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), round(int(s[6:8], 16) * alpha))
    raise ValueError(f"bad colour {c!r}")


def rgb(c: Any) -> tuple[int, int, int]:
    return rgba(c)[:3]


def blend_rgba(a: Any, b: Any, u: float) -> tuple[int, int, int, int]:
    """Linear mix of two colours (names, hex or tuples) at ``u`` (0 = a, 1 = b)."""
    ca, cb = rgba(a), rgba(b)
    u = clamp01(u)
    return tuple(round(ca[i] + (cb[i] - ca[i]) * u) for i in range(4))  # type: ignore[return-value]


def tween_color(base: Any, steps: list[dict[str, Any]], t: float, default_over: float = 0.0) -> Any:
    """``base`` recoloured by ``[{at, color, over_ms, ease}]``: a hard switch when ``over_ms`` is 0
    (the pre-v4 behaviour), else an eased blend."""
    color: Any = base
    cur: Any = base
    for r in steps:
        at = float(r["at"])
        if t < at:
            break
        nxt = r.get("color", cur)
        over = float(r.get("over_ms", default_over * 1000)) / 1000.0
        if over > 0:
            color = blend_rgba(cur, nxt, ease(str(r.get("ease", "move")), (t - at) / over))
        else:
            color = nxt
        cur = nxt
    return color


def is_color(c: Any) -> bool:
    try:
        rgba(c)
        return True
    except (ValueError, TypeError, IndexError):
        return False


# --------------------------------------------------------------------------- fonts


def text_engine(requested: str = "auto") -> str:
    """``raqm`` (kerning, ligatures, complex scripts) when Pillow was built with libraqm, else ``basic``."""
    have = bool(features.check("raqm"))
    if requested == "raqm" and not have:
        raise RuntimeError("text_engine raqm requested but this Pillow has no libraqm")
    if requested == "basic":
        return "basic"
    return "raqm" if have else "basic"


@dataclass
class Fonts:
    """Resolved font files. A spec is ``path`` or ``path:index`` for .ttc collections."""

    sans: str
    sans_bold: str
    mono: str
    sans_medium: str = ""
    sans_medium_italic: str = ""
    mono_bold: str = ""
    engine: str = "basic"

    @classmethod
    def resolve(
        cls,
        sans: str | None = None,
        sans_bold: str | None = None,
        mono: str | None = None,
        engine: str = "auto",
    ) -> Fonts:
        def pick(kind: str, override: str | None) -> str:
            cands = [override or os.environ.get(f"VIDEO_FONT_{kind.upper()}"), *DEFAULT_FONTS[kind]]
            for spec in cands:
                if spec and Path(spec.rsplit(":", 1)[0]).exists():
                    return spec
            raise FileNotFoundError(f"no {kind} font found; pass --font-{kind.replace('_', '-')}")

        return cls(
            pick("sans", sans),
            pick("sans_bold", sans_bold),
            pick("mono", mono),
            pick("sans_medium", None),
            pick("sans_medium_italic", None),
            pick("mono_bold", None),
            text_engine(engine),
        )

    def get(self, kind: str, size: int) -> ImageFont.FreeTypeFont:
        fallback = {"sans_medium": "sans_bold", "sans_medium_italic": "sans_bold", "mono_bold": "mono"}
        spec = getattr(self, kind, "") or getattr(self, fallback.get(kind, "sans"))
        return _load_font(spec, max(4, int(size)), self.engine)


@lru_cache(maxsize=256)
def _load_font(spec: str, size: int, engine: str = "basic") -> ImageFont.FreeTypeFont:
    path, _, idx = spec.rpartition(":")
    if not path or not idx.isdigit():
        path, idx = spec, "0"
    layout = ImageFont.Layout.RAQM if engine == "raqm" else ImageFont.Layout.BASIC
    font = ImageFont.truetype(path, size, index=int(idx), layout_engine=layout)
    return font


# --------------------------------------------------------------------------- canvas


@dataclass
class Canvas:
    """Output size plus fonts; converts reference (1920x1080) units to pixels."""

    width: int
    height: int
    fonts: Fonts
    ease: str | None = None  # the shot list's default curve; None keeps pre-v3 elements on smoothstep

    @property
    def s(self) -> float:
        return self.width / REF_W

    def curve(self, spec: dict[str, Any], legacy: bool) -> str:
        """The easing curve for an element: ``spec['ease']``, else the shot list default, else
        ``smooth`` for pre-v3 element kinds and ``ease_out`` for the new ones."""
        return resolve_ease(spec.get("ease"), self.ease, legacy)

    def px(self, v: float) -> int:
        return round(v * self.s)

    def pt(self, xy: Any) -> tuple[int, int]:
        return (self.px(float(xy[0])), self.px(float(xy[1])))

    def font(self, kind: str, size: float) -> ImageFont.FreeTypeFont:
        return self.fonts.get(kind, self.px(size))

    def scaled(self, factor: float) -> Canvas:
        return Canvas(
            max(2, round(self.width * factor)), max(2, round(self.height * factor)), self.fonts, self.ease
        )

    def blank(self, color: Any = "bg") -> Image.Image:
        return Image.new("RGB", (self.width, self.height), rgb(color))

    def layer(self) -> Image.Image:
        return Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))


# --------------------------------------------------------------------------- easing / anim


def envelope(
    t: float, t_in: float, t_out: float, fade_in: float = FADE_IN, fade_out: float = FADE_OUT
) -> float:
    """0..1 visibility of an element shown from t_in to t_out with soft edges."""
    if t < t_in or t >= t_out:
        return 0.0
    a = smoothstep((t - t_in) / fade_in) if fade_in > 0 else 1.0
    b = smoothstep((t_out - t) / fade_out) if fade_out > 0 else 1.0
    return min(a, b)


def quantize(x: float, steps: int = 64) -> int:
    return round(clamp01(x) * steps)


def eased_progress(t: float, start: float, over: float, curve: str) -> float:
    """Eased 0..1 of a move that starts at ``start`` and lasts ``over`` seconds (1 when over <= 0)."""
    if over <= 0:
        return 1.0 if t >= start else 0.0
    return ease(curve, (t - start) / over)


def _scale_alpha(img: Image.Image, a: float) -> Image.Image:
    if a >= 1:
        return img
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v, a=a: int(v * a)))
    return out


def animate_block(
    block: Image.Image, anim: str, p: float, canvas: Canvas, pad: int = 0, scale_from: float | None = None
) -> Image.Image:
    """Apply an entrance (or, time-reversed, an exit) to an RGBA block at eased progress ``p``.

    ``p`` runs 0 (hidden) to 1 (at rest; ``spring`` may overshoot). Offsets for ``rise`` and
    ``slide_*`` are the caller's job (they move the block's position); this handles alpha,
    scale, the left-to-right wipe mask and the blur. ``pad`` is the transparent margin the
    caller already added so a blur or an overshooting scale has room.
    """
    if p >= 1 and anim not in ("scale_in", "pop"):
        return block
    if anim in ("scale_in", "pop"):
        lo = SCALE_IN_FROM if anim == "scale_in" else POP_FROM
        if scale_from is not None:
            lo = float(scale_from)
        s = lo + (1 - lo) * p
        if abs(s - 1) < 1e-3 and p >= 1:
            return block
        w, h = block.size
        nw, nh = max(1, round(w * s)), max(1, round(h * s))
        small = block.resize((nw, nh), Image.Resampling.LANCZOS)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.alpha_composite(small, ((w - nw) // 2, (h - nh) // 2))
        a = min(1.0, p * (2.0 if anim == "pop" else 1.0))
        return _scale_alpha(out, a)
    if anim == "wipe":
        w, h = block.size
        soft = max(1, canvas.px(WIPE_SOFT_PX))
        edge = p * (w + soft)
        col = np.arange(w, dtype=np.float32)
        ramp = np.clip((edge - col) / soft, 0.0, 1.0)
        alpha = np.asarray(block.getchannel("A"), dtype=np.float32) * ramp[None, :]
        out = block.copy()
        out.putalpha(Image.fromarray(alpha.clip(0, 255).astype(np.uint8), "L"))
        return out
    if anim == "blur_in":
        r = canvas.px(BLUR_IN_PX) * (1 - p)
        out = block.filter(ImageFilter.GaussianBlur(r)) if r >= 0.3 else block
        return _scale_alpha(out, p)
    # fade, rise, slide_*, none, typewriter: alpha only
    return _scale_alpha(block, p)


def glow_layer(block: Image.Image, color: Any, radius: int, strength: float) -> Image.Image:
    """A blurred, coloured copy of the block's alpha for additive bloom (same size as the block)."""
    r, g, b, _ = rgba(color)
    a = block.getchannel("A")
    if radius > 0:
        a = a.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        a = a.point(lambda v, k=strength: min(255, int(v * k)))
    out = Image.new("RGBA", block.size, (r, g, b, 0))
    out.putalpha(a)
    return out


def glow_spec(spec: dict[str, Any], canvas: Canvas) -> dict[str, Any] | None:
    """Normalised ``glow: {color, radius, strength, pulse: {period, low}}`` or None."""
    g = spec.get("glow")
    if not g or not isinstance(g, dict):
        return None
    return {
        "color": g.get("color", spec.get("color", "cyan")),
        "radius": canvas.px(float(g.get("radius", 18))),
        "margin": canvas.px(float(g.get("radius", 18))) * 2,
        "strength": float(g.get("strength", 0.8)),
        "pulse": g.get("pulse"),
        "settle": g.get("settle"),
        "t0": float(spec.get("in", 0.0) or 0.0),
    }


def glow_strength(g: dict[str, Any], t: float) -> float:
    k = float(g["strength"])
    settle = g.get("settle")
    if settle:
        s = settle if isinstance(settle, dict) else {}
        over = float(s.get("over_ms", 480)) / 1000.0
        u = ease(str(s.get("ease", "enter")), (t - float(g.get("t0", 0.0))) / over) if over > 0 else 1.0
        k = k + (float(s.get("to", k)) - k) * u
    pulse = g.get("pulse")
    if pulse:
        p = pulse if isinstance(pulse, dict) else {}
        k *= breathe(t, float(p.get("period", 2.0)), float(p.get("low", 0.4)))
    return k


# --------------------------------------------------------------------------- text helpers


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap on spaces; a paragraph that already fits is kept verbatim (indentation included)."""
    out: list[str] = []
    for para in text.split("\n"):
        if font.getlength(para) <= max_width:
            out.append(para)
            continue
        words = para.split(" ")
        line = ""
        for w in words:
            cand = w if not line else f"{line} {w}"
            if font.getlength(cand) <= max_width or not line:
                line = cand
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


def text_block_size(lines: list[str], font: ImageFont.FreeTypeFont, line_h: int) -> tuple[int, int]:
    """Width of the widest line; height = (n - 1) leadings plus the face's ascent + descent."""
    w = max((math.ceil(font.getlength(ln)) for ln in lines), default=0)
    asc, desc = font.getmetrics()
    return w, line_h * (max(1, len(lines)) - 1) + asc + desc


def draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    xy: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    line_h: int,
    align: str = "left",
    width: int | None = None,
) -> None:
    x0, y = xy
    for ln in lines:
        x = x0
        if align != "left" and width:
            lw = font.getlength(ln)
            x = x0 + (width - lw) / 2 if align == "center" else x0 + width - lw
        draw.text((x, y), ln, font=font, fill=fill)
        y += line_h


def rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: Any = None,
    outline: Any = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def place_block(canvas: Canvas, pos: Any, bw: int, bh: int) -> tuple[int, int]:
    """Anchor a block of bw x bh pixels at a 9-grid code or an explicit [x, y] top-left."""
    if isinstance(pos, (list, tuple)):
        return canvas.pt(pos)
    pos = str(pos or "mc")
    mx, my = canvas.px(SAFE_X), canvas.px(SAFE_Y)
    row, col = pos[0], pos[1]
    x = {"l": mx, "c": (canvas.width - bw) // 2, "r": canvas.width - mx - bw}[col]
    y = {"t": my, "m": (canvas.height - bh) // 2, "b": canvas.height - my - bh}[row]
    return x, y


def find_spans(line: str, highlights: list[dict[str, Any]]) -> list[tuple[int, int, Any]]:
    """Non-overlapping (start, end, color) spans for highlight matches in a line."""
    spans: list[tuple[int, int, Any]] = []
    taken = [False] * len(line)
    for h in highlights:
        m = str(h.get("match", ""))
        if not m:
            continue
        start = 0
        while True:
            i = line.find(m, start)
            if i < 0:
                break
            if not any(taken[i : i + len(m)]):
                spans.append((i, i + len(m), h.get("color", "orange")))
                for k in range(i, i + len(m)):
                    taken[k] = True
            start = i + len(m)
    spans.sort()
    return spans


def segments_for(line: str, highlights: list[dict[str, Any]]) -> list[tuple[str, Any]]:
    segs: list[tuple[str, Any]] = []
    cur = 0
    for a, b, color in find_spans(line, highlights):
        if a > cur:
            segs.append((line[cur:a], None))
        segs.append((line[a:b], color))
        cur = b
    if cur < len(line):
        segs.append((line[cur:], None))
    return segs or [("", None)]


def typed_prefix(lines: list[str], nchars: float, nl_cost: float) -> tuple[list[str], bool]:
    """Lines visible after ``nchars`` characters typed; newlines cost nl_cost chars. Returns (lines, done)."""
    out: list[str] = []
    budget = nchars
    for ln in lines:
        if budget <= 0:
            break
        if budget >= len(ln):
            out.append(ln)
            budget -= len(ln) + nl_cost
        else:
            out.append(ln[: int(budget)])
            budget = -1
            break
    done = budget >= 0 and len(out) == len(lines)
    return out, done


# --------------------------------------------------------------------------- text overlays

OVERLAY_STYLE: dict[str, dict[str, Any]] = {
    "title": {"font": "sans_bold", "size": 64, "color": "ink", "pos": [96, 72], "align": "left"},
    "subtitle": {"font": "sans", "size": 44, "color": "ink-dim", "pos": "bc", "align": "center"},
    "lower_third": {"font": "sans_medium", "size": 32, "color": "ink", "pos": [112, 964], "align": "left"},
    "caption": {"font": "sans_medium", "size": 40, "color": "ink", "pos": "bc", "align": "center"},
    "code": {"font": "mono", "size": 28, "color": "ink", "pos": "mc", "align": "left"},
    "counter": {"font": "sans_bold", "size": 96, "color": "ink", "pos": "tl", "align": "left"},
    "bullet": {"font": "sans", "size": 40, "color": "ink", "pos": "ml", "align": "left"},
    "label": {"font": "sans", "size": 30, "color": "ink", "pos": "tl", "align": "left"},
    "mono": {"font": "mono", "size": 28, "color": "ink", "pos": "tl", "align": "left"},
    "chip": {"font": "mono_bold", "size": 30, "color": "bg", "pos": "tl", "align": "left"},
    "ticker": {"font": "sans_bold", "size": 96, "color": "ink", "pos": "tl", "align": "left"},
}

Box = tuple[int, int, int, int]


def _plate_spec(spec: dict[str, Any], kind: str) -> dict[str, Any] | None:
    plate = spec.get("plate")
    if plate is None and kind in ("chip", "lower_third"):
        plate = {}
    if plate is None or plate is False:
        return None
    plate = dict(plate) if isinstance(plate, dict) else {}
    if kind == "chip":
        plate.setdefault("color", spec.get("bg", "cyan"))
        plate.setdefault("alpha", 1.0)
        plate.setdefault("pad", 10)
        plate.setdefault("radius", 6)
    plate.setdefault("color", "bg")
    plate.setdefault("alpha", 0.6)
    plate.setdefault("pad", 16)
    plate.setdefault("radius", 6)
    return plate


def anchor_offset(anchor: str, bw: int, bh: int) -> tuple[int, int]:
    """Offset to turn an anchor point into a top-left for a bw x bh block."""
    anchor = anchor or "tl"
    row, col = anchor[0], anchor[1]
    dx = {"l": 0, "c": -bw // 2, "r": -bw}[col]
    dy = {"t": 0, "m": -bh // 2, "b": -bh}[row]
    return dx, dy


def draw_plate(layer: Image.Image, canvas: Canvas, box: Box, plate: dict[str, Any], alpha: float) -> None:
    d = ImageDraw.Draw(layer)
    rounded(
        d,
        box,
        canvas.px(float(plate.get("radius", 6))),
        fill=rgba(plate["color"], float(plate["alpha"]) * alpha),
    )
    border = plate.get("border")
    if border:
        b = border if isinstance(border, dict) else {}
        rounded(
            d,
            box,
            canvas.px(float(plate.get("radius", 6))),
            outline=rgba(b.get("color", "ink"), float(b.get("alpha", 0.12)) * alpha),
            width=max(1, canvas.px(float(b.get("width", 1)))),
        )
    bar = plate.get("bar")
    if bar:
        bw = canvas.px(float(bar.get("width", 2)))
        bx = canvas.px(float(bar["x"])) if "x" in bar else box[0]
        d.rectangle((bx, box[1], bx + bw - 1, box[3]), fill=rgba(bar.get("color", "orange"), alpha))


def ref_box(canvas: Canvas, box: Box) -> Box:
    """Canvas pixels back to 1920x1080 reference units."""
    return tuple(round(v / canvas.s) for v in box)  # type: ignore[return-value]


class TextOverlay:
    """One ``text`` entry of a shot. ``render(t)`` gives (RGBA block, x, y) or None.

    Pre-v3 behaviour (``anim`` fade/slide_up/slide_left/typewriter/none, smoothstep curve,
    0.4 s fade when ``in`` > 0) is unchanged unless the element or the shot list sets
    ``ease``. The v3 entrances ``rise``, ``scale_in``, ``wipe``, ``blur_in`` and ``pop`` take
    ``anim_ms``, mirror on exit through ``out_anim``/``out_ms`` (time-reversed), stagger
    multi-line blocks with ``stagger`` (ms per line) and carry an additive ``glow``.
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.kind = str(spec.get("kind", "caption"))
        if self.kind == "chip" and spec.get("verdict"):
            verdict = str(spec["verdict"]).lower()
            spec = {**spec, "bg": VERDICT_COLORS.get(verdict, spec.get("bg", "cyan"))}
        style = OVERLAY_STYLE.get(self.kind, OVERLAY_STYLE["caption"])
        self.text = str(spec.get("text", ""))
        self.size = float(spec.get("size", style["size"]))
        self.color = spec.get("color", style["color"])
        self.pos = spec.get("pos", style["pos"])
        self.anchor = str(spec.get("anchor", "tl"))
        self.align = spec.get("align", style["align"])
        self.font_kind = spec.get("font", style["font"])
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.anim = str(spec.get("anim", "fade"))
        legacy = self.anim in LEGACY_ANIMS and self.kind != "ticker"
        if self.anim == "pop" and not spec.get("ease"):
            self.ease = "spring"
        else:
            self.ease = canvas.curve(spec, legacy)
        if "anim_ms" in spec:
            self.fade = float(spec["anim_ms"]) / 1000.0
        else:
            later = self.t_in > 0 or self.anim in ENTER_ANIMS
            self.fade = float(spec.get("fade", FADE_IN if later else 0.0))
        self.out_anim = str(spec.get("out_anim", self.anim if self.anim in ENTER_ANIMS else "fade"))
        if "out_ms" in spec:
            self.fade_out = float(spec["out_ms"]) / 1000.0
        else:
            self.fade_out = FADE_OUT if "out" in spec else 0.0
        self.stagger = float(spec.get("stagger", 0.0)) / 1000.0
        self.glow = glow_spec(spec, canvas)
        self.cps = float(spec.get("cps", 40))
        self.width_ref = spec.get("width")
        self.leading = spec.get("leading")
        self.recolor = sorted((dict(r) for r in spec.get("recolor", [])), key=lambda r: float(r["at"]))
        self.count = spec.get("count")
        if self.kind == "ticker":
            self.count = {
                "from": spec.get("from", 0),
                "to": spec.get("to", 0),
                "over": float(spec.get("over_ms", 900)) / 1000.0,
                "decimals": spec.get("decimals", 0),
                "thousands": spec.get("thousands", False),
            }
            if "text" not in spec:
                self.text = "{n}" + (f" {spec['unit']}" if spec.get("unit") else "")
        self.count_ease = canvas.curve(spec, legacy=self.kind != "ticker")
        self.unit_size = float(spec.get("unit_size", self.size * 0.375))
        self.unit_color = spec.get("unit_color", "ink-dim")
        self.plate = _plate_spec(spec, self.kind)
        self.highlights = [dict(h) for h in spec.get("highlight", [])]
        self.spec = spec
        self.v3 = self.anim in ENTER_ANIMS or self.out_anim in ENTER_ANIMS or self.stagger > 0
        self._lines_n = 1
        self._line_h = 1
        # v4: tracking (fraction of the em), caps, the kicker's middle dot, eased recolours,
        # alpha settles, position tweens and a custom scale_in start
        self.track = float(spec.get("track", 0.0) or 0.0)
        if spec.get("caps"):
            self.text = self.text.upper()
        if spec.get("middot"):
            self.text = self.text.replace(" . ", " \u00b7 ")
        self.scale_from = spec.get("scale_from")
        self.settles = sorted((dict(r) for r in spec.get("settle", []) or []), key=lambda r: float(r["at"]))
        self.moves = sorted((dict(m) for m in spec.get("move", []) or []), key=lambda m: float(m["at"]))
        self.base_alpha = float(spec.get("alpha", 1.0))

    # ---- state
    def p_in(self, t: float, offset: float = 0.0) -> float:
        """Eased entrance progress, 0 hidden .. 1 at rest (spring overshoots)."""
        if self.anim == "typewriter":
            return smoothstep((t - self.t_in) / 0.05)
        if self.anim == "none":
            return 1.0 if t >= self.t_in else 0.0
        return eased_progress(t, self.t_in + offset, self.fade, self.ease)

    def p_out(self, t: float) -> float:
        """Eased exit progress, 1 at rest .. 0 gone."""
        if self.fade_out <= 0:
            return 1.0
        return ease(self.ease, (self.t_out - t) / self.fade_out)

    def alpha(self, t: float) -> float:
        if t < self.t_in or t >= self.t_out:
            return 0.0
        a_in = 1.0 if self.anim == "wipe" else min(1.0, self.p_in(t))
        a_out = 1.0 if self.out_anim == "wipe" else min(1.0, self.p_out(t))
        return min(a_in, a_out)

    def visible_chars(self, t: float) -> int:
        if self.anim != "typewriter":
            return 1 << 20  # the whole substituted text (a `{n}` counter may be longer than its template)
        return min(len(self.text), int((t - self.t_in) * self.cps))

    def color_at(self, t: float) -> Any:
        return tween_color(self.color, self.recolor, t)

    def settle_k(self, t: float) -> float:
        """Alpha multiplier from ``settle: [{at, alpha, over_ms, ease}]`` (labels dimming to 70 percent)."""
        k = self.base_alpha
        for r in self.settles:
            at = float(r["at"])
            if t < at:
                break
            u = eased_progress(t, at, float(r.get("over_ms", 240)) / 1000.0, str(r.get("ease", "move")))
            k = k + (float(r.get("alpha", 0.7)) - k) * u
        return k

    def pos_at(self, t: float) -> Any:
        """The position after ``move: [{at, pos, over_ms, ease}]`` tweens (the scale travelling)."""
        if not self.moves or not isinstance(self.pos, (list, tuple)):
            return self.pos
        cur = [float(self.pos[0]), float(self.pos[1])]
        for m in self.moves:
            at = float(m["at"])
            if t < at:
                break
            nxt = [float(v) for v in m["pos"]]
            u = eased_progress(t, at, float(m.get("over_ms", 720)) / 1000.0, str(m.get("ease", "move")))
            cur = [cur[i] + (nxt[i] - cur[i]) * u for i in range(2)]
        return cur

    def track_px(self) -> float:
        return self.track * self.canvas.px(self.size) if self.track else 0.0

    def text_len(self, font: ImageFont.FreeTypeFont, s: str) -> float:
        return font.getlength(s) + self.track_px() * max(0, len(s) - 1)

    def highlight_settles(self, t: float) -> tuple[float, ...]:
        out = []
        for h in self.highlights:
            k = 1.0
            if h.get("settle_at") is not None and t >= float(h["settle_at"]):
                u = eased_progress(t, float(h["settle_at"]), 0.24, "move")
                k = 1.0 - (1.0 - float(h.get("settle_to", 0.5))) * u
            out.append(k)
        return tuple(out)

    def count_value(self, t: float) -> str | None:
        if not self.count:
            return None
        c = self.count
        lo, hi = float(c.get("from", 0)), float(c.get("to", 0))
        over = float(c.get("over", 1.0))
        u = ease(self.count_ease, (t - self.t_in) / over) if over > 0 else 1.0
        v = lo + (hi - lo) * u
        dec = int(c.get("decimals", 0))
        if c.get("thousands"):
            return f"{v:,.{dec}f}" if dec else f"{round(v):,}"
        return f"{v:.{dec}f}" if dec else f"{round(v)}"

    def slide(self, t: float) -> float:
        if self.anim in ("slide_up", "slide_left"):
            return 1 - self.p_in(t)
        return 0.0

    def highlight_levels(self, t: float) -> tuple[float, ...]:
        out = []
        for h in self.highlights:
            at = float(h.get("at", self.t_in))
            if h.get("style") == "underline":
                over = float(h.get("draw_ms", 240)) / 1000.0
                out.append(ease(str(h.get("ease", "draw")), (t - at) / over) if over > 0 else 1.0)
            else:
                out.append(smoothstep((t - at) / 0.25))
        return tuple(out)

    def _line_progress(self, t: float) -> tuple[float, ...]:
        n = self._lines_n if self.stagger > 0 else 1
        return tuple(self.p_in(t, i * self.stagger) for i in range(n))

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        if a <= 0:
            return None
        hl = tuple(quantize(v, 16) for v in self.highlight_levels(t))
        base = (
            quantize(a),
            min(self.visible_chars(t), len(self.text)),
            self.color_at(t),
            self.count_value(t),
            quantize(self.slide(t), 32),
            hl,
        )
        extra: tuple[Any, ...] = ()
        if self.highlights and any(h.get("settle_at") is not None for h in self.highlights):
            extra += (tuple(quantize(v, 16) for v in self.highlight_settles(t)),)
        if self.settles:
            extra += (quantize(self.settle_k(t)),)
        if self.moves:
            extra += (tuple(round(float(v) * 2) for v in self.pos_at(t)),)
        if self.count and self.spec.get("count_alpha") is not None:
            extra += (self.counting(t),)
        if self.v3:
            extra += (
                round(self.p_in(t) * 256),
                round(self.p_out(t) * 256),
                tuple(round(p * 256) for p in self._line_progress(t)),
            )
        if self.glow and self.glow.get("pulse"):
            extra += (round(glow_strength(self.glow, t) * 64),)
        return base + extra if extra else base

    def counting(self, t: float) -> bool:
        """True while a counter is still running (its digits then render at ``count_alpha``)."""
        if not self.count:
            return False
        over = float(self.count.get("over", 1.0))
        return over > 0 and t < self.t_in + over

    def measure(self) -> dict[str, Any] | None:
        """Final-state text box and plate box in reference units, for the fit check."""
        t = self.t_in + 10.0
        for m in self.moves:
            t = max(t, float(m["at"]) + float(m.get("over_ms", 720)) / 1000.0 + 1.0)
        self.t_out = max(self.t_out, t + 10.0)
        _block, x, y, bw, bh, pbox = self._layout(t)
        out: dict[str, Any] = {"text": ref_box(self.canvas, (x, y, x + bw, y + bh))}
        if pbox is not None:
            out["plate"] = ref_box(self.canvas, pbox)
        return out

    # ---- drawing
    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        block, x, y, bw, bh, pbox = self._layout(t)
        out_img, ox, oy = block, x, y
        if pbox is not None:
            out_img, ox, oy = self._compose_plate(block, x, y, bw, bh, pbox)
        k = self.settle_k(t)
        if self.counting(t) and self.spec.get("count_alpha") is not None:
            k *= float(self.spec["count_alpha"])
        if self.v3:
            img, ax, ay = self._animate(out_img, ox, oy, x - ox, y - oy, t)
            return (_scale_alpha(img, k) if k < 1 else img), ax, ay
        a *= k
        if a < 1:
            out_img = out_img.copy()
            out_img.putalpha(out_img.getchannel("A").point(lambda v: int(v * a)))
        return out_img, ox, oy

    def _offsets(self, anim: str, p: float) -> tuple[int, int]:
        c = self.canvas
        if anim == "rise":
            return 0, round((1 - p) * c.px(float(self.spec.get("travel", RISE_PX))))
        if anim == "rise_left":
            return -round((1 - p) * c.px(float(self.spec.get("travel", RISE_PX)))), 0
        if anim == "rise_right":
            return round((1 - p) * c.px(float(self.spec.get("travel", RISE_PX)))), 0
        if anim == "slide_up":
            return 0, round((1 - p) * c.px(SLIDE_PX))
        if anim == "slide_left":
            return -round((1 - p) * c.px(24)), 0
        return 0, 0

    def _animate(
        self, img: Image.Image, ox: int, oy: int, tx: int, ty: int, t: float
    ) -> tuple[Image.Image, int, int]:
        """v3 entrance/exit: per-line stagger, scale/wipe/blur, offsets; (tx, ty) is the text
        block's origin inside ``img`` (non-zero when a plate was composed around it)."""
        c = self.canvas
        pin, pout = self.p_in(t), self.p_out(t)
        pad = c.px(BLUR_IN_PX) * 2 if "blur_in" in (self.anim, self.out_anim) else 0
        if pad:
            big = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
            big.alpha_composite(img, (pad, pad))
            img, ox, oy, tx, ty = big, ox - pad, oy - pad, tx + pad, ty + pad
        dx, dy = 0, 0
        if pout < 1:
            img = animate_block(img, self.out_anim, pout, c, pad)
            ex, ey = self._offsets(self.out_anim, pout)
            dx, dy = dx + ex, dy + ey
        n = self._lines_n
        if self.stagger > 0 and n > 1 and pin < 1:
            line_h = self._line_h
            extra = c.px(RISE_PX) + c.px(SLIDE_PX)
            out = Image.new("RGBA", (img.width + extra, img.height + extra), (0, 0, 0, 0))
            cuts = [0] + [ty + i * line_h for i in range(1, n)] + [img.height]
            for i in range(n):
                y0, y1 = cuts[i], cuts[i + 1]
                if y1 <= y0:
                    continue
                p_i = self.p_in(t, i * self.stagger)
                if p_i <= 0:
                    continue
                band = img.crop((0, y0, img.width, y1))
                band = animate_block(band, self.anim, p_i, c, pad)
                bx, by = self._offsets(self.anim, p_i)
                out.alpha_composite(band, (max(0, bx + extra // 2), max(0, y0 + by)))
            return out, ox + dx - extra // 2, oy + dy
        img = animate_block(img, self.anim, pin, c, pad, self.scale_from)
        ex, ey = self._offsets(self.anim, pin)
        return img, ox + dx + ex, oy + dy + ey

    def glow_part(self, t: float, rendered: tuple[Image.Image, int, int] | None) -> Any:
        """The additive bloom layer for this frame, or None."""
        if not self.glow or rendered is None:
            return None
        img, x, y = rendered
        g = self.glow
        m = g["margin"]
        big = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
        big.alpha_composite(img, (m, m))
        return glow_layer(big, g["color"], g["radius"], glow_strength(g, t)), x - m, y - m

    def _layout(self, t: float) -> tuple[Image.Image, int, int, int, int, Box | None]:
        c = self.canvas
        font = c.font(self.font_kind, self.size)
        line_h = c.px(float(self.leading)) if self.leading else round(c.px(self.size) * 1.3)
        max_w = c.px(float(self.width_ref)) if self.width_ref else c.width - 2 * c.px(SAFE_X)
        text = self.text
        num = self.count_value(t)
        if num is not None:
            text = text.replace("{n}", num)
        shown = text[: self.visible_chars(t)]
        if self.anim == "typewriter" and len(shown) < len(text) and int(t * 2.5) % 2 == 0:
            shown += "_"
        if self.spec.get("nowrap", num is not None):
            lines = shown.split("\n") if shown else [" "]
        else:
            lines = wrap_text(shown or " ", font, max_w)
        self._lines_n, self._line_h = len(lines), line_h
        color = rgba(self.color_at(t))
        block, bw, bh = self._text_block(
            lines, font, line_h, color, num, self.highlight_levels(t), self.highlight_settles(t)
        )
        x, y = place_block(c, self.pos_at(t), bw, bh)
        if isinstance(self.pos, (list, tuple)):
            dx, dy = anchor_offset(self.anchor, bw, bh)
            x, y = x + dx, y + dy
        s = self.slide(t)
        if self.anim == "slide_up":
            y += round(s * c.px(SLIDE_PX))
        elif self.anim == "slide_left":
            x -= round(s * c.px(24))
        pbox = self._plate_box(x, y, bw, bh) if self.plate is not None else None
        return block, x, y, bw, bh, pbox

    def _text_block(
        self,
        lines: list[str],
        font: ImageFont.FreeTypeFont,
        line_h: int,
        color: Any,
        num: str | None,
        hl_levels: tuple[float, ...] = (),
        hl_settles: tuple[float, ...] = (),
    ) -> tuple[Image.Image, int, int]:
        c = self.canvas
        if self.track:
            return self._tracked_block(lines, font, line_h, color)
        if self.kind in ("counter", "ticker") and num is not None and lines and num in lines[0]:
            head, _, rest = lines[0].partition(num)
            unit_font = c.font(self.spec.get("unit_font", "sans"), self.unit_size)
            unit_color = rgba(self.unit_color)
            nw = math.ceil(font.getlength(head + num))
            uw = math.ceil(unit_font.getlength(rest))
            bw, bh = nw + uw + 2, line_h
            block = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            d = ImageDraw.Draw(block)
            d.text((0, 0), head + num, font=font, fill=color)
            asc_big = font.getmetrics()[0]
            asc_small = unit_font.getmetrics()[0]
            d.text((nw, asc_big - asc_small), rest, font=unit_font, fill=unit_color)
            return block, bw, bh
        tw, th = text_block_size(lines, font, line_h)
        tw = max(tw, 1)
        if self.kind == "bullet":
            dot = c.px(14)
            bw, bh = tw + dot + c.px(24), th
            block = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            d = ImageDraw.Draw(block)
            for i in range(len(lines)):
                cy = i * line_h + line_h // 2
                d.ellipse((0, cy - dot // 2, dot, cy + dot // 2), fill=rgba(self.spec.get("accent", "cyan")))
            draw_lines(d, lines, (dot + c.px(24), 0), font, color, line_h, "left", tw)
            return block, bw, bh
        underlined = any(h.get("style") == "underline" for h in self.highlights)
        bw, bh = tw + 2, th + (c.px(10) if underlined else 0)
        block = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(block)
        spans: list[tuple[int, int, int, int, Any, float]] = []
        if self.highlights and self.align == "left":
            if not hl_settles:
                hl_settles = tuple(1.0 for _ in self.highlights)
            for hi, (h, lv) in enumerate(zip(self.highlights, hl_levels, strict=True)):
                if lv <= 0:
                    continue
                for li, ln in enumerate(lines):
                    for a0, b0, col in find_spans(ln, [h]):
                        spans.append((li, a0, b0, hi, col, lv))
        asc = font.getmetrics()[0]
        for li, a0, b0, hi, col, lv in spans:
            ln = lines[li]
            h = self.highlights[hi]
            if h.get("style") == "underline":
                continue
            x0 = 1 + font.getlength(ln[:a0]) - c.px(4)
            x1 = 1 + font.getlength(ln[:b0]) + c.px(4)
            y0, y1 = li * line_h - c.px(2), li * line_h + line_h - c.px(2)
            d.rounded_rectangle(
                (x0, y0, x1, y1),
                radius=c.px(8),
                fill=rgba(col, 0.12 * lv),
                outline=rgba(col, lv),
                width=max(1, c.px(3)),
            )
        draw_lines(d, lines, (1, 0), font, color, line_h, self.align, tw)
        for li, a0, b0, hi, col, lv in spans:
            ln = lines[li]
            h = self.highlights[hi]
            if h.get("style") == "underline":
                k = hl_settles[hi]
                ux0, ux1 = 1 + font.getlength(ln[:a0]), 1 + font.getlength(ln[:b0])
                uy = li * line_h + asc + c.px(float(h.get("gap", 6)))
                ua = float(h.get("alpha", 1.0)) * k
                d.line(
                    (ux0, uy, ux0 + (ux1 - ux0) * min(1.0, lv), uy),
                    fill=rgba(col, ua),
                    width=max(1, c.px(float(h.get("width", 2)))),
                )
                if h.get("recolor", True):
                    span_col = blend_rgba(color, col, min(1.0, lv) * (0.5 + 0.5 * k))
                    d.text((ux0, li * line_h), ln[a0:b0], font=font, fill=span_col)
            elif lv >= 1:
                d.text((1 + font.getlength(ln[:a0]), li * line_h), ln[a0:b0], font=font, fill=rgba(col))
        return block, bw, bh

    def _tracked_block(
        self, lines: list[str], font: ImageFont.FreeTypeFont, line_h: int, color: Any
    ) -> tuple[Image.Image, int, int]:
        """Letter-spaced text (kicker, pills, chips): drawn one glyph at a time."""
        tp = self.track_px()
        tw = max(1, math.ceil(max(self.text_len(font, ln) for ln in lines)))
        asc, desc = font.getmetrics()
        th = line_h * (max(1, len(lines)) - 1) + asc + desc
        block = Image.new("RGBA", (tw + 2, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(block)
        for li, ln in enumerate(lines):
            lw = self.text_len(font, ln)
            x = 1.0
            if self.align == "center":
                x = 1 + (tw - lw) / 2
            elif self.align == "right":
                x = 1 + tw - lw
            for ch in ln:
                d.text((x, li * line_h), ch, font=font, fill=color)
                x += font.getlength(ch) + tp
        return block, tw + 2, th

    def _plate_box(self, x: int, y: int, bw: int, bh: int) -> Box:
        c = self.canvas
        plate = dict(self.plate or {})
        if self.kind == "lower_third" and "box" not in plate:
            rx, ry = x / c.s, y / c.s
            plate["box"] = [rx - 32, ry - 12, rx + bw / c.s + 16, ry + 44]
        if "box" in plate:
            b = plate["box"]
            return (c.px(b[0]), c.px(b[1]), c.px(b[2]), c.px(b[3]))
        pad = c.px(float(plate["pad"]))
        pady = c.px(float(plate.get("pad_y", plate["pad"])))
        pbox = (x - pad, y - pady, x + bw + pad, y + bh + pady)
        if "y" in plate:
            pbox = (pbox[0], c.px(float(plate["y"][0])), pbox[2], c.px(float(plate["y"][1])))
        return pbox

    def _compose_plate(
        self, block: Image.Image, x: int, y: int, bw: int, bh: int, pbox: Box
    ) -> tuple[Image.Image, int, int]:
        c = self.canvas
        plate = dict(self.plate or {})
        if self.kind == "lower_third" and "bar" not in plate:
            plate["bar"] = {"color": self.spec.get("accent", "orange"), "width": 2, "x": x / c.s - 16}
        ux0, uy0 = min(pbox[0], x), min(pbox[1], y)
        ux1, uy1 = max(pbox[2], x + bw), max(pbox[3], y + bh)
        layer = Image.new("RGBA", (ux1 - ux0 + 1, uy1 - uy0 + 1), (0, 0, 0, 0))
        if plate.get("bar") and "x" in plate["bar"]:
            # the bar's x is a frame coordinate; the layer's origin is the plate's top-left
            plate["bar"] = {**plate["bar"], "x": float(plate["bar"]["x"]) - ux0 / c.s}
        draw_plate(layer, c, (pbox[0] - ux0, pbox[1] - uy0, pbox[2] - ux0, pbox[3] - uy0), plate, 1.0)
        layer.alpha_composite(block, (x - ux0, y - uy0))
        return layer, ux0, uy0


class SpanOverlay:
    """One measured text line whose spans enter on their own anchors (a span reveal).

    ``{kind: label, size, font, color, pos, anchor, spans: [{text, in, anim, ...}, ...], sep: " "}``:
    the full line (spans joined by ``sep``) is measured and placed once; each span is a
    ``TextOverlay`` at its offset inside that line, so the line never re-flows.
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        spans = [dict(s) for s in spec["spans"]]
        kind = str(spec.get("kind", "label"))
        style = OVERLAY_STYLE.get(kind, OVERLAY_STYLE["caption"])
        size = float(spec.get("size", style["size"]))
        font = canvas.font(spec.get("font", style["font"]), size)
        sep = str(spec.get("sep", " "))
        full = sep.join(str(sp["text"]) for sp in spans)
        tp = float(spec.get("track", 0.0) or 0.0) * canvas.px(size)
        total = math.ceil(font.getlength(full) + tp * max(0, len(full) - 1))
        asc, desc = font.getmetrics()
        bh = asc + desc
        pos = spec.get("pos", style["pos"])
        x, y = place_block(canvas, pos, total, bh)
        if isinstance(pos, (list, tuple)):
            dx, dy = anchor_offset(str(spec.get("anchor", "tl")), total, bh)
            x, y = x + dx, y + dy
        base = {k: v for k, v in spec.items() if k not in ("spans", "in", "text", "pos", "anchor", "sep")}
        self.children: list[TextOverlay] = []
        prefix = ""
        for sp in spans:
            off = font.getlength(prefix) + tp * len(prefix)
            child = {
                **base,
                **sp,
                "pos": [(x + off) / canvas.s, y / canvas.s],
                "anchor": "tl",
                "nowrap": True,
            }
            self.children.append(TextOverlay(child, canvas, shot_duration))
            prefix += str(sp["text"]) + sep
        self.box = (x, y, x + total, y + bh)

    def measure(self) -> dict[str, Any] | None:
        return {"text": ref_box(self.canvas, self.box)}

    def key(self, t: float) -> Any:
        keys = tuple(ch.key(t) for ch in self.children)
        return None if all(k is None for k in keys) else keys

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        parts = [r for r in (ch.render(t) for ch in self.children) if r is not None]
        if not parts:
            return None
        x0 = min(p[1] for p in parts)
        y0 = min(p[2] for p in parts)
        x1 = max(p[1] + p[0].width for p in parts)
        y1 = max(p[2] + p[0].height for p in parts)
        layer = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
        for img, px, py in parts:
            layer.alpha_composite(img, (int(px - x0), int(py - y0)))
        return layer, int(x0), int(y0)


class ChipsOverlay:
    """A row of chips (text on small plates), laid out left to right with a gap.

    v3: ``anim: pop|rise|fade`` with ``stagger`` (ms per chip), ``ease``, ``glow``.
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.items = [str(i) for i in spec.get("items", [])]
        self.pos = spec.get("pos", [0, 0])
        self.size = float(spec.get("size", 26))
        self.font_kind = spec.get("font", "mono")
        self.color = spec.get("color", "ink")
        self.plate_color = spec.get("plate_color", "ink-dim")
        self.plate_alpha = float(spec.get("plate_alpha", 0.2))
        self.pad = float(spec.get("pad", 8))
        self.gap = float(spec.get("gap", 12))
        self.radius = float(spec.get("radius", 6))
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.anim = str(spec.get("anim", "fade"))
        self.stagger = float(spec.get("stagger", 0.0)) / 1000.0
        legacy = self.anim in LEGACY_ANIMS
        self.ease = "spring" if self.anim == "pop" and not spec.get("ease") else canvas.curve(spec, legacy)
        if "anim_ms" in spec:
            self.fade = float(spec["anim_ms"]) / 1000.0
        else:
            later = self.t_in > 0 or self.anim in ENTER_ANIMS
            self.fade = float(spec.get("fade", FADE_IN if later else 0.0))
        self.fade_out = (
            float(spec["out_ms"]) / 1000.0 if "out_ms" in spec else (FADE_OUT if "out" in spec else 0.0)
        )
        self.glow = glow_spec(spec, canvas)
        self.v3 = self.anim in ENTER_ANIMS or self.stagger > 0 or not legacy or self.ease != "smooth"

    def alpha(self, t: float) -> float:
        return envelope(t, self.t_in, self.t_out, self.fade, self.fade_out)

    def p_in(self, t: float, i: int = 0) -> float:
        return eased_progress(t, self.t_in + i * self.stagger, self.fade, self.ease)

    def p_out(self, t: float) -> float:
        return 1.0 if self.fade_out <= 0 else ease(self.ease, (self.t_out - t) / self.fade_out)

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        if a <= 0:
            return None
        if not self.v3:
            return (quantize(a), quantize(smoothstep((t - self.t_in) / self.fade), 32))
        extra = (round(glow_strength(self.glow, t) * 64),) if self.glow and self.glow.get("pulse") else ()
        return (
            tuple(round(self.p_in(t, i) * 256) for i in range(len(self.items))),
            round(self.p_out(t) * 256),
            *extra,
        )

    def _geometry(self) -> tuple[ImageFont.FreeTypeFont, int, int, int, list[int], int]:
        c = self.canvas
        font = c.font(self.font_kind, self.size)
        pad, gap = c.px(self.pad), c.px(self.gap)
        h = round(c.px(self.size) * 1.1) + 2 * pad
        widths = [math.ceil(font.getlength(s)) + 2 * pad for s in self.items]
        total = sum(widths) + gap * max(0, len(widths) - 1)
        return font, pad, gap, h, widths, total

    def measure(self) -> dict[str, Any] | None:
        _, _, _, h, _, total = self._geometry()
        px, py = self.canvas.pt(self.pos)
        return {"text": ref_box(self.canvas, (px, py, px + total, py + h))}

    def _chip(self, s: str, w: int, h: int, font: ImageFont.FreeTypeFont, pad: int, a: float) -> Image.Image:
        c = self.canvas
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        rounded(d, (0, 0, w - 1, h - 1), c.px(self.radius), fill=rgba(self.plate_color, self.plate_alpha * a))
        asc = font.getmetrics()[0]
        d.text((pad, (h - asc) / 2 - c.px(self.size) * 0.08), s, font=font, fill=rgba(self.color, a))
        return img

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        if t < self.t_in or t >= self.t_out:
            return None
        c = self.canvas
        font, pad, gap, h, widths, total = self._geometry()
        px, py = c.pt(self.pos)
        if not self.v3:
            a = self.alpha(t)
            if a <= 0:
                return None
            layer = Image.new("RGBA", (max(1, total), h), (0, 0, 0, 0))
            x = 0
            for s, w in zip(self.items, widths, strict=True):
                layer.alpha_composite(self._chip(s, w, h, font, pad, a), (x, 0))
                x += w + gap
            if self.anim == "slide_left":
                px -= round((1 - smoothstep((t - self.t_in) / self.fade)) * c.px(24))
            return layer, px, py
        m = c.px(RISE_PX)
        layer = Image.new("RGBA", (max(1, total) + 2 * m, h + 2 * m), (0, 0, 0, 0))
        pout = min(1.0, self.p_out(t))
        x = m
        for i, (s, w) in enumerate(zip(self.items, widths, strict=True)):
            p = self.p_in(t, i)
            if p > 0:
                chip = animate_block(self._chip(s, w, h, font, pad, 1.0), self.anim, p, c)
                dy = round((1 - p) * c.px(RISE_PX)) if self.anim == "rise" else 0
                dx = -round((1 - p) * c.px(24)) if self.anim == "slide_left" else 0
                layer.alpha_composite(chip, (x + dx, m + dy))
            x += w + gap
        if pout < 1:
            layer = _scale_alpha(layer, pout)
        return layer, px - m, py - m

    def glow_part(self, t: float, rendered: tuple[Image.Image, int, int] | None) -> Any:
        if not self.glow or rendered is None:
            return None
        img, x, y = rendered
        g = self.glow
        mg = g["margin"]
        big = Image.new("RGBA", (img.width + 2 * mg, img.height + 2 * mg), (0, 0, 0, 0))
        big.alpha_composite(img, (mg, mg))
        return glow_layer(big, g["color"], g["radius"], glow_strength(g, t)), x - mg, y - mg


def paint_panel_v2(
    img: Image.Image, canvas: Canvas, box: tuple[int, int, int, int], spec: dict[str, Any], a: float = 1.0
) -> None:
    """DESIGN section 4 panel onto an RGBA image at pixel ``box``: drop shadow, surface fill with a
    radius, optional header strip (three dots, title), hatch fill, 1 px border and inner shadow.

    ``spec``: ``{color: surface, alpha: 1.0, radius: 12, shadow: {blur: 40, alpha: 0.5, dy: 12},
    header: {h: 36, color: surface2, dots: true, title, title_size: 20, title_color: ink-dim,
    title_x}, hatch: {spacing: 24, color: ink, alpha: 0.06, angle: 45}, border: {color: ink,
    alpha: 0.12, width: 1}, inner_shadow: true}``. Every translucent part is drawn on its own
    layer and alpha-composited (ImageDraw itself does not blend).
    """
    c = canvas
    x0, y0, x1, y1 = box
    r = c.px(float(spec.get("radius", 12)))

    def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        return lay, ImageDraw.Draw(lay)

    shadow = spec.get("shadow")
    if shadow:
        sh = shadow if isinstance(shadow, dict) else {}
        blur = c.px(float(sh.get("blur", 40)))
        dy = c.px(float(sh.get("dy", 12)))
        lay, d = layer()
        d.rounded_rectangle(
            (x0, y0 + dy, x1, y1 + dy), radius=r, fill=rgba("black", float(sh.get("alpha", 0.5)) * a)
        )
        if blur > 0:
            lay = lay.filter(ImageFilter.GaussianBlur(blur / 2))
        img.alpha_composite(lay)
    fill = rgba(spec.get("color", "surface"), float(spec.get("alpha", 1.0)) * a)
    lay, d = layer()
    d.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=fill)
    header = spec.get("header")
    hd = (header if isinstance(header, dict) else {}) if header else None
    if hd is not None:
        hh = c.px(float(hd.get("h", 36)))
        hcol = rgba(hd.get("color", "surface2"), a)
        d.rounded_rectangle((x0, y0, x1, y0 + hh + r), radius=r, fill=hcol)
        d.rectangle((x0, y0 + hh, x1, y0 + hh + r), fill=fill)
    img.alpha_composite(lay)
    if hd is not None:
        hh = c.px(float(hd.get("h", 36)))
        lay, d = layer()
        if hd.get("dots", True):
            dot = c.px(float(hd.get("dot", 10)))
            for k in range(3):
                cx = x0 + c.px(20 + 16 * k)
                cy = y0 + hh / 2
                d.ellipse((cx - dot / 2, cy - dot / 2, cx + dot / 2, cy + dot / 2), fill=rgba("ink", 0.2 * a))
        title = hd.get("title")
        if title:
            f = c.font(hd.get("title_font", "mono"), float(hd.get("title_size", 20)))
            tw = f.getlength(str(title))
            asc = f.getmetrics()[0]
            tx = x0 + c.px(float(hd["title_x"])) if hd.get("title_x") is not None else (x0 + x1) / 2 - tw / 2
            d.text(
                (tx, y0 + hh / 2 - asc * 0.58),
                str(title),
                font=f,
                fill=rgba(hd.get("title_color", "ink-dim"), a),
            )
        img.alpha_composite(lay)
    hatch = spec.get("hatch")
    if hatch:
        hs = hatch if isinstance(hatch, dict) else {}
        spacing = max(2, c.px(float(hs.get("spacing", 24))))
        hl, hdraw = layer()
        col = rgba(hs.get("color", "ink"), float(hs.get("alpha", 0.06)) * a)
        w, h = x1 - x0, y1 - y0
        k = -h
        while k < w + h:
            hdraw.line((x0 + k, y1, x0 + k + h, y0), fill=col, width=max(1, c.px(1)))
            k += spacing
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((x0, y0, x1, y1), radius=r, fill=255)
        hl.putalpha(ImageChops.multiply(hl.getchannel("A"), mask))
        img.alpha_composite(hl)
    if spec.get("inner_shadow") or spec.get("border"):
        lay, d = layer()
        if spec.get("inner_shadow"):
            d.line((x0 + r, y0 + 1, x1 - r, y0 + 1), fill=rgba("ink", 0.06 * a), width=1)
            d.line((x0 + r, y1 - 1, x1 - r, y1 - 1), fill=rgba("black", 0.4 * a), width=1)
        border = spec.get("border")
        if border:
            b = border if isinstance(border, dict) else {}
            d.rounded_rectangle(
                (x0, y0, x1, y1),
                radius=r,
                outline=rgba(b.get("color", "ink"), float(b.get("alpha", 0.12)) * a),
                width=max(1, c.px(float(b.get("width", 1)))),
            )
        img.alpha_composite(lay)


PANEL_V2_KEYS = {
    "border",
    "shadow",
    "header",
    "hollow",
    "hatch",
    "move",
    "recolor",
    "anim_ms",
    "ease",
    "inner_shadow",
}


class PanelOverlay:
    """A plain plate: ``box`` [x0, y0, x1, y1], colour, alpha, radius, optional left bar.

    v4 (any of ``border``, ``shadow``, ``header``, ``hollow``, ``hatch``, ``move``, ``recolor``,
    ``anim_ms``, ``ease``, ``inner_shadow``, or ``anim: grow_down|grow_right|rise``): a DESIGN
    section 4 panel with eased entrances, a box tween (``move: [{at, box, over_ms, ease}]``), an
    eased recolour (``recolor: [{at, color, alpha, over_ms, ease}]``) and the ``hollow`` form
    (shadow, corner bites and border only) that frames a clip placed underneath it.
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.box = spec["box"]
        self.plate = {
            "color": spec.get("color", "bg"),
            "alpha": float(spec.get("alpha", 0.6)),
            "radius": float(spec.get("radius", 6)),
            "bar": spec.get("bar"),
        }
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.anim = str(spec.get("anim", "fade"))
        self.v2 = bool(PANEL_V2_KEYS & set(spec)) or self.anim in ("grow_down", "grow_right", "rise")
        if "out_ms" in spec:
            self.fade_out = float(spec["out_ms"]) / 1000.0
        else:
            self.fade_out = FADE_OUT if "out" in spec else 0.0
        if "anim_ms" in spec:
            self.fade = float(spec["anim_ms"]) / 1000.0
        else:
            self.fade = float(spec.get("fade", FADE_IN if float(spec.get("in", 0.0)) > 0 else 0.0))
        self.ease = canvas.curve(spec, legacy=not self.v2)
        self.out_ease = str(spec.get("out_ease", "exit" if self.v2 else self.ease))
        self.spec = spec
        self.moves = sorted((dict(m) for m in spec.get("move", []) or []), key=lambda m: float(m["at"]))
        self.recolors = sorted((dict(r) for r in spec.get("recolor", []) or []), key=lambda r: float(r["at"]))
        self.hollow = bool(spec.get("hollow"))

    def alpha(self, t: float) -> float:
        if not self.v2:
            return envelope(t, self.t_in, self.t_out, self.fade, self.fade_out)
        if t < self.t_in or t >= self.t_out:
            return 0.0
        a_in = (
            eased_progress(t, self.t_in, self.fade, self.ease)
            if self.anim not in ("grow_down", "grow_right")
            else 1.0
        )
        a_out = 1.0 if self.fade_out <= 0 else ease(self.out_ease, (self.t_out - t) / self.fade_out)
        return min(1.0, a_in, a_out)

    def p_in(self, t: float) -> float:
        return eased_progress(t, self.t_in, self.fade, self.ease)

    def box_at(self, t: float) -> list[float]:
        cur = [float(v) for v in self.box]
        for m in self.moves:
            at = float(m["at"])
            if t < at:
                break
            nxt = [float(v) for v in m["box"]]
            u = eased_progress(t, at, float(m.get("over_ms", 720)) / 1000.0, str(m.get("ease", "move")))
            cur = [cur[i] + (nxt[i] - cur[i]) * u for i in range(4)]
        return cur

    def color_at(self, t: float) -> tuple[Any, float]:
        """(colour, alpha) after the eased recolours."""
        col: Any = self.plate["color"]
        alpha = float(self.plate["alpha"])
        cur_col, cur_a = col, alpha
        for r in self.recolors:
            at = float(r["at"])
            if t < at:
                break
            nxt_col = r.get("color", cur_col)
            nxt_a = float(r.get("alpha", cur_a))
            u = eased_progress(t, at, float(r.get("over_ms", 240)) / 1000.0, str(r.get("ease", "move")))
            col = blend_rgba(cur_col, nxt_col, u)
            alpha = cur_a + (nxt_a - cur_a) * u
            cur_col, cur_a = nxt_col, nxt_a
        return col, alpha

    def measure(self) -> dict[str, Any] | None:
        return None

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        if a <= 0:
            return None
        if not self.v2:
            p_in = smoothstep((t - self.t_in) / self.fade) if self.fade > 0 else 1.0
            return (quantize(a), quantize(p_in, 32))
        col, al = self.color_at(t)
        return (
            quantize(a),
            round(self.p_in(t) * 256),
            tuple(round(v * 2) for v in self.box_at(t)),
            rgba(col),
            quantize(al),
        )

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        c = self.canvas
        if not self.v2:
            x0, y0 = c.pt(self.box[:2])
            x1, y1 = c.pt(self.box[2:])
            layer = Image.new("RGBA", (max(1, x1 - x0 + 1), max(1, y1 - y0 + 1)), (0, 0, 0, 0))
            plate = dict(self.plate)
            if plate.get("bar") and "x" in plate["bar"]:
                plate["bar"] = {**plate["bar"], "x": float(plate["bar"]["x"]) - float(self.box[0])}
            draw_plate(layer, c, (0, 0, x1 - x0, y1 - y0), plate, a)
            if self.anim == "slide_left" and self.fade > 0:
                x0 -= round((1 - smoothstep((t - self.t_in) / self.fade)) * c.px(24))
            return layer, x0, y0
        box = self.box_at(t)
        x0, y0 = c.pt(box[:2])
        x1, y1 = c.pt(box[2:])
        p = min(1.0, self.p_in(t))
        if self.anim == "grow_down":
            y1 = y0 + round((y1 - y0) * p)
        elif self.anim == "grow_right":
            x1 = x0 + round((x1 - x0) * p)
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        shadow = self.spec.get("shadow")
        m = 0
        if shadow:
            sh = shadow if isinstance(shadow, dict) else {}
            m = c.px(float(sh.get("blur", 40))) + abs(c.px(float(sh.get("dy", 12)))) + 2
        layer = Image.new("RGBA", (w + 2 * m + 1, h + 2 * m + 1), (0, 0, 0, 0))
        inner = (m, m, m + w, m + h)
        col, al = self.color_at(t)
        r = c.px(float(self.plate["radius"]))
        if self.hollow:
            if shadow:
                sh = shadow if isinstance(shadow, dict) else {}
                blur = c.px(float(sh.get("blur", 40)))
                dy = c.px(float(sh.get("dy", 12)))
                shl = Image.new("RGBA", layer.size, (0, 0, 0, 0))
                ImageDraw.Draw(shl).rounded_rectangle(
                    (m, m + dy, m + w, m + h + dy),
                    radius=r,
                    fill=rgba("black", float(sh.get("alpha", 0.5)) * a),
                )
                if blur > 0:
                    shl = shl.filter(ImageFilter.GaussianBlur(blur / 2))
                keep = Image.new("L", layer.size, 255)
                ImageDraw.Draw(keep).rounded_rectangle(inner, radius=r, fill=0)
                shl.putalpha(ImageChops.multiply(shl.getchannel("A"), keep))
                layer.alpha_composite(shl)
            # corner bites: the picture underneath is rectangular, the panel is rounded
            bite = Image.new("RGBA", layer.size, rgba(self.spec.get("bite", "bg"), a))
            bm = Image.new("L", layer.size, 0)
            bd = ImageDraw.Draw(bm)
            bd.rectangle(inner, fill=255)
            bd.rounded_rectangle(inner, radius=r, fill=0)
            bite.putalpha(bm)
            layer.alpha_composite(bite)
            d = ImageDraw.Draw(layer)
            border = self.spec.get("border") or {}
            d.rounded_rectangle(
                inner,
                radius=r,
                outline=rgba(border.get("color", "ink"), float(border.get("alpha", 0.12)) * a),
                width=max(1, c.px(float(border.get("width", 1)))),
            )
        else:
            spec = {**self.spec, "color": col, "alpha": al}
            paint_panel_v2(layer, c, inner, spec, a)
            bar = self.plate.get("bar")
            if bar:
                d = ImageDraw.Draw(layer)
                bw = c.px(float(bar.get("width", 2)))
                bx = m + (c.px(float(bar["x"])) - x0 if "x" in bar else 0)
                d.rectangle((bx, m, bx + bw - 1, m + h), fill=rgba(bar.get("color", "orange"), a))
        dx, dy_ = 0, 0
        if self.anim == "rise":
            dy_ = round((1 - p) * c.px(float(self.spec.get("travel", 16))))
        elif self.anim == "slide_left":
            dx = -round((1 - p) * c.px(24))
        return layer, x0 - m + dx, y0 - m + dy_


class ImageOverlay:
    """An image (png/jpg/svg) fitted inside ``box`` with an optional soft coloured glow.

    v4: ``crop: [x0, y0, x1, y1]`` (source pixels), ``autocrop: true`` (trim to the content's
    bounding box against the corner colour), ``knockout: {color, tolerance}`` (make the flat
    background transparent), ``anim_ms``/``ease`` for an eased fade.
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float, loader: Any = None):
        self.canvas = canvas
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.fade_out = FADE_OUT if "out" in spec else 0.0
        if "anim_ms" in spec:
            self.fade = float(spec["anim_ms"]) / 1000.0
        else:
            self.fade = float(spec.get("fade", FADE_IN if float(spec.get("in", 0.0)) > 0 else 0.0))
        self.ease = spec.get("ease")
        box = spec["box"]
        x0, y0 = canvas.pt(box[:2])
        x1, y1 = canvas.pt(box[2:])
        src = str(spec["src"])
        im = (loader(src) if loader else Image.open(src)).convert("RGBA")
        if spec.get("crop"):
            im = im.crop(tuple(int(v) for v in spec["crop"]))
        knock = spec.get("knockout")
        if spec.get("autocrop") or knock:
            kc = (knock or {}).get("color") if isinstance(knock, dict) else None
            key = rgb(kc) if kc else im.convert("RGB").getpixel((0, 0))
            tol = float((knock or {}).get("tolerance", 24)) if isinstance(knock, dict) else 24.0
            diff = ImageChops.difference(im.convert("RGB"), Image.new("RGB", im.size, key)).convert("L")
            if spec.get("autocrop"):
                bbox = diff.point(lambda v: 255 if v > tol else 0).getbbox()
                if bbox:
                    im = im.crop(bbox)
                    diff = diff.crop(bbox)
            if knock:
                alpha = diff.point(lambda v: 255 if v >= tol else int(255 * v / max(1.0, tol)))
                im.putalpha(ImageChops.multiply(im.getchannel("A"), alpha))
        bw, bh = max(1, x1 - x0), max(1, y1 - y0)
        r = min(bw / im.width, bh / im.height)
        im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.Resampling.LANCZOS)
        glow = spec.get("glow")
        margin = canvas.px(float(glow.get("radius", 24))) * 2 if glow else 0
        layer = Image.new("RGBA", (bw + 2 * margin, bh + 2 * margin), (0, 0, 0, 0))
        if glow:
            g = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            gd = ImageDraw.Draw(g)
            gd.ellipse(
                (margin // 2, margin // 2, layer.width - margin // 2, layer.height - margin // 2),
                fill=rgba(glow.get("color", "violet"), float(glow.get("alpha", 0.3))),
            )
            g = g.filter(ImageFilter.GaussianBlur(canvas.px(float(glow.get("radius", 24)))))
            layer.alpha_composite(g)
        layer.alpha_composite(im, (margin + (bw - im.width) // 2, margin + (bh - im.height) // 2))
        self.layer = layer
        self.x, self.y = x0 - margin, y0 - margin
        self.box = (x0, y0, x1, y1)

    def alpha(self, t: float) -> float:
        if self.ease:
            if t < self.t_in or t >= self.t_out:
                return 0.0
            a = eased_progress(t, self.t_in, self.fade, str(self.ease))
            return min(a, smoothstep((self.t_out - t) / self.fade_out)) if self.fade_out > 0 else a
        return envelope(t, self.t_in, self.t_out, self.fade, self.fade_out)

    def measure(self) -> dict[str, Any] | None:
        return {"text": ref_box(self.canvas, self.box)}

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        return None if a <= 0 else quantize(a)

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        layer = self.layer
        if a < 1:
            layer = layer.copy()
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
        return layer, self.x, self.y


# --------------------------------------------------------------------------- pointers


class Pointer:
    """Arrows, boxes, circles, highlights, brackets, bars, dotted rules, number badges, and
    the v3 strokes ``line`` and ``leader`` (line plus end dot).

    Drawn with 2x supersampling on a local patch so the edges are clean at any size.
    Arrows, underlines, brackets, lines and leaders draw on along their length; a ``box``
    draws its perimeter on when ``draw_ms`` is set (otherwise it keeps the pre-v3 grow and
    fade). ``draw_ms`` (240 to 480 is the intended range) and ``ease`` shape every draw-on.

    v4: ``path`` (a polyline ``points`` drawing on along its length, ``tail: {px, color}`` for a
    colour change on the last stretch, ``end_dot: {r, color}``), ``node`` (a disc with a
    ``ring`` while it is the current step, recolouring later), leaders that start at the dot
    (``dot_at: start``, the dot fills over ``dot_ms`` first) with an optional ``ping`` ring,
    ``alpha``, ``recolor``, ``settle``, ``out_ms``/``out_ease``, a rounded ``radius`` on a drawn
    box, ``label_color``/``label_font`` on badges, and ``attach: true`` (coordinates follow the
    base picture's camera through the renderer's transform).
    """

    DRAW_ON = 0.25
    V3_KINDS = frozenset({"line", "leader", "path", "node"})

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.kind = str(spec.get("kind", "arrow"))
        self.a = canvas.pt(spec.get("from", [0, 0]))
        self.b = canvas.pt(spec.get("to", spec.get("from", [100, 100])))
        self.points = [canvas.pt(pt) for pt in spec.get("points", []) or []]
        self.color = spec.get("color", "orange")
        default_w = {
            "highlight": 3,
            "box": 3,
            "dotted": 2,
            "bracket": 3,
            "line": 2,
            "leader": 2,
            "path": 2,
        }.get(self.kind, 4)
        self.width = max(1, canvas.px(float(spec.get("width", default_w))))
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        if "out_ms" in spec:
            self.fade_out = float(spec["out_ms"]) / 1000.0
        else:
            self.fade_out = FADE_OUT if "out" in spec else 0.0
        self.out_ease = spec.get("out_ease")
        self.radius = float(spec.get("radius", 8))
        self.round_box = "radius" in spec
        self.fill = spec.get("fill", 0.12 if self.kind == "highlight" else 0.0)
        self.pulse = spec.get("pulse")
        self.stages = [dict(s) for s in spec.get("stages", [])]
        self.grow = float(spec.get("grow", self.DRAW_ON))
        self.threshold_x = spec.get("threshold_x")
        self.color_after = spec.get("color_after")
        self.label = spec.get("label")
        self.label_color = spec.get("label_color", "white")
        self.label_font = spec.get("label_font", "sans_bold")
        self.r = float(spec.get("r", 6 if self.kind == "node" else 18))
        self.ticks = float(spec.get("ticks", 10))
        self.dash = float(spec.get("dash", 6))
        self.dot = float(spec.get("dot", 5))
        self.dot_at = str(spec.get("dot_at", "end"))
        self.dot_ms = float(spec.get("dot_ms", 240)) / 1000.0
        self.ping = spec.get("ping")
        self.ring = spec.get("ring")
        self.tail = spec.get("tail")
        self.end_dot = spec.get("end_dot")
        self.base_alpha = float(spec.get("alpha", 1.0))
        self.recolor = sorted((dict(r) for r in spec.get("recolor", []) or []), key=lambda r: float(r["at"]))
        self.settles = sorted((dict(r) for r in spec.get("settle", []) or []), key=lambda r: float(r["at"]))
        self.attach = bool(spec.get("attach", False))
        self.transform: Any = None
        v3 = self.kind in self.V3_KINDS or "draw_ms" in spec
        self.ease = canvas.curve(spec, legacy=not v3)
        self.draw_on = (
            float(spec["draw_ms"]) / 1000.0 if "draw_ms" in spec else (0.36 if v3 else self.DRAW_ON)
        )
        self.draw_box = self.kind == "box" and "draw_ms" in spec
        self.spec = spec

    # ---- state
    def settle_k(self, t: float) -> float:
        k = 1.0
        for r in self.settles:
            at = float(r["at"])
            if t < at:
                break
            u = eased_progress(t, at, float(r.get("over_ms", 240)) / 1000.0, str(r.get("ease", "move")))
            k = k + (float(r.get("alpha", 0.7)) - k) * u
        return k

    def alpha(self, t: float) -> float:
        if self.pulse:
            count = int(self.pulse.get("count", 2))
            period = float(self.pulse.get("period", 0.3))
            if t < self.t_in or t >= self.t_in + count * period:
                return 0.0
            return abs(math.sin(math.pi * (t - self.t_in) / period))
        if "out_ms" in self.spec or self.out_ease:
            if t < self.t_in or t >= self.t_out:
                return 0.0
            a_in = smoothstep((t - self.t_in) / 0.08) if self.t_in > 0 else 1.0
            a_out = (
                ease(str(self.out_ease or "exit"), (self.t_out - t) / self.fade_out)
                if self.fade_out > 0
                else 1.0
            )
            a = min(a_in, a_out)
        else:
            a = envelope(t, self.t_in, self.t_out, 0.08 if self.t_in > 0 else 0.0, self.fade_out)
        return a * self.base_alpha * self.settle_k(t)

    def color_at(self, t: float) -> Any:
        return tween_color(self.color, self.recolor, t, default_over=0.24)

    def recolor_u(self, t: float) -> float:
        """0 before the first recolour, 1 once it has finished (the node's ring fades with it)."""
        if not self.recolor:
            return 0.0
        r = self.recolor[0]
        return eased_progress(
            t, float(r["at"]), float(r.get("over_ms", 240)) / 1000.0, str(r.get("ease", "move"))
        )

    def line_start(self) -> float:
        return self.t_in + (self.dot_ms if (self.kind == "leader" and self.dot_at == "start") else 0.0)

    def progress(self, t: float) -> float:
        if self.t_in <= 0 and self.kind != "bar" and not self.draw_box and self.kind not in self.V3_KINDS:
            return 1.0  # no `in`: the pointer is there from the first frame, no draw-on
        return ease(self.ease, (t - self.line_start()) / (self.grow if self.kind == "bar" else self.draw_on))

    def target(self, t: float) -> tuple[float, float]:
        cur = (float(self.b[0]), float(self.b[1]))
        for st in self.stages:
            at = float(st["at"])
            if t < at:
                break
            nxt = self.canvas.pt(st["to"])
            q = ease(self.ease, (t - at) / self.draw_on)
            cur = (cur[0] + (nxt[0] - cur[0]) * q, cur[1] + (nxt[1] - cur[1]) * q)
        return cur

    def _tp(self, t: float, pt: tuple[float, float]) -> tuple[float, float]:
        if self.attach and self.transform is not None:
            x, y = self.transform(t, float(pt[0]), float(pt[1]))
            return float(x), float(y)
        return float(pt[0]), float(pt[1])

    def ping_start(self) -> float:
        return self.t_in if self.dot_at == "start" else self.line_start() + self.draw_on

    def ping_u(self, t: float) -> float:
        if not self.ping:
            return 1.0
        return clamp01((t - self.ping_start()) / 0.48)

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        if a <= 0:
            return None
        steps = 256 if (self.draw_box or self.kind in self.V3_KINDS) else 48
        extra: tuple[Any, ...] = ()
        if self.recolor:
            extra += (rgba(self.color_at(t)), quantize(self.recolor_u(t), 32))
        if self.ping:
            extra += (quantize(self.ping_u(t), 32),)
        if self.kind == "leader" and self.dot_at == "start":
            extra += (quantize(ease(self.ease, (t - self.t_in) / self.dot_ms), 32),)
        if self.attach and self.transform is not None:
            extra += (
                tuple(round(v) for v in self._tp(t, self.a)),
                tuple(round(v) for v in self._tp(t, self.b)),
            )
        return (quantize(a), quantize(self.progress(t), steps), tuple(int(v) for v in self.target(t)), *extra)

    # ---- drawing helpers
    def _cap(self, d: ImageDraw.ImageDraw, x: float, y: float, w: int, col: Any) -> None:
        r = w / 2
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)

    @staticmethod
    def _rounded_path(box: tuple[float, float, float, float], r: float) -> list[tuple[float, float]]:
        """Clockwise polyline around a rounded rectangle, starting at the top-left arc's end."""
        x0, y0, x1, y1 = box
        r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
        if r <= 0:
            return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        pts: list[tuple[float, float]] = []

        def arc(cx: float, cy: float, a0: float, a1: float) -> None:
            for k in range(9):
                ang = math.radians(a0 + (a1 - a0) * k / 8)
                pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))

        pts.append((x0 + r, y0))
        pts.append((x1 - r, y0))
        arc(x1 - r, y0 + r, -90, 0)
        pts.append((x1, y1 - r))
        arc(x1 - r, y1 - r, 0, 90)
        pts.append((x0 + r, y1))
        arc(x0 + r, y1 - r, 90, 180)
        pts.append((x0, y0 + r))
        arc(x0 + r, y0 + r, 180, 270)
        return pts

    def _draw_path(
        self,
        d: ImageDraw.ImageDraw,
        pts: list[tuple[float, float]],
        p: float,
        w: int,
        col: Any,
        tail: tuple[float, Any] | None = None,
    ) -> tuple[float, float] | None:
        """Draw the polyline up to fraction ``p`` of its length; ``tail`` = (px, colour) recolours the
        last stretch. Returns the current end point."""
        segs = list(itertools.pairwise(pts))
        total = sum(math.hypot(bx - ax, by - ay) for (ax, ay), (bx, by) in segs)
        left = p * total
        if left <= 0 or total <= 0:
            return None
        tail_from = total - tail[0] if tail else total + 1
        self._cap(d, pts[0][0], pts[0][1], w, col)
        run = 0.0
        end = pts[0]
        for (ax, ay), (bx, by) in segs:
            seg = math.hypot(bx - ax, by - ay)
            if seg <= 0:
                continue
            take = min(seg, left)
            k = take / seg
            tx, ty = ax + (bx - ax) * k, ay + (by - ay) * k
            # split the drawn piece at the tail boundary
            cut = tail_from - run
            if tail and 0 < cut < take:
                kc = cut / seg
                mx, my = ax + (bx - ax) * kc, ay + (by - ay) * kc
                d.line((ax, ay, mx, my), fill=col, width=w)
                d.line((mx, my, tx, ty), fill=tail[1], width=w)
                self._cap(d, mx, my, w, tail[1])
                self._cap(d, tx, ty, w, tail[1])
            else:
                use = tail[1] if (tail and run >= tail_from) else col
                d.line((ax, ay, tx, ty), fill=use, width=w)
                self._cap(d, tx, ty, w, use)
            end = (tx, ty)
            left -= take
            run += take
            if left <= 1e-6:
                break
        return end

    def _perimeter(
        self, d: ImageDraw.ImageDraw, box: tuple[float, float, float, float], p: float, w: int, col: Any
    ) -> None:
        """Draw the box outline clockwise from the top-left corner up to fraction ``p`` of its length."""
        if self.round_box:
            self._draw_path(d, self._rounded_path(box, self.canvas.px(self.radius) * 2), p, w, col)
            return
        x0, y0, x1, y1 = box
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        total = 2 * ((x1 - x0) + (y1 - y0))
        left = p * total
        if left <= 0:
            return
        self._cap(d, x0, y0, w, col)
        for (ax, ay), (bx, by) in itertools.pairwise(pts):
            seg = math.hypot(bx - ax, by - ay)
            if left >= seg:
                d.line((ax, ay, bx, by), fill=col, width=w)
                self._cap(d, bx, by, w, col)
                left -= seg
                if left <= 0:
                    break
            else:
                k = left / seg if seg else 0
                tx, ty = ax + (bx - ax) * k, ay + (by - ay) * k
                d.line((ax, ay, tx, ty), fill=col, width=w)
                self._cap(d, tx, ty, w, col)
                break

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        p = self.progress(t)
        (x1, y1), (x2, y2) = self._tp(t, self.a), self._tp(t, self.target(t))
        pts_px = [self._tp(t, pt) for pt in self.points]
        c = self.canvas
        pad = self.width * 4 + c.px(self.r if self.kind in ("badge", "node") else 0) + 8
        if self.kind == "leader":
            pad += c.px(self.dot) * 2
        if self.ping:
            pad += c.px(16)
        if self.ring:
            pad += c.px(float(self.ring.get("r", 12)))
        if self.end_dot:
            pad += c.px(float(self.end_dot.get("r", 5))) * 2
        allx = [x1, x2, *(q[0] for q in pts_px)]
        ally = [y1, y2, *(q[1] for q in pts_px)]
        left, top = int(min(allx) - pad), int(min(ally) - pad)
        right, bottom = int(max(allx) + pad), int(max(ally) + pad)
        ss = 2
        img = Image.new("RGBA", ((right - left) * ss, (bottom - top) * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        col = rgba(self.color_at(t), a)
        w = max(1, self.width * ss)
        ax, ay = (x1 - left) * ss, (y1 - top) * ss
        bx, by = (x2 - left) * ss, (y2 - top) * ss
        if self.kind in ("arrow", "underline"):
            tx, ty = ax + (bx - ax) * p, ay + (by - ay) * p
            d.line((ax, ay, tx, ty), fill=col, width=w)
            if self.kind == "arrow" and p > 0.05:
                ang = math.atan2(ty - ay, tx - ax)
                head = c.px(12) * ss
                spread = math.radians(26)
                p1 = (tx - head * math.cos(ang - spread), ty - head * math.sin(ang - spread))
                p2 = (tx - head * math.cos(ang + spread), ty - head * math.sin(ang + spread))
                d.polygon([(tx, ty), p1, p2], fill=col)
            else:
                r = w // 2
                d.ellipse((tx - r, ty - r, tx + r, ty + r), fill=col)
                d.ellipse((ax - r, ay - r, ax + r, ay + r), fill=col)
        elif self.kind == "leader" and self.dot_at == "start":
            # the dot fills first, then the line draws from it outward to the label
            dp = ease(self.ease, (t - self.t_in) / self.dot_ms) if self.dot_ms > 0 else 1.0
            r = c.px(self.dot) * ss * dp
            if r > 0:
                d.ellipse((ax - r, ay - r, ax + r, ay + r), fill=col)
            if p > 0:
                tx, ty = ax + (bx - ax) * p, ay + (by - ay) * p
                d.line((ax, ay, tx, ty), fill=col, width=w)
                self._cap(d, ax, ay, w, col)
                self._cap(d, tx, ty, w, col)
            pu = self.ping_u(t)
            if self.ping and pu < 1:
                pr = c.px(5 + 9 * pu) * ss
                d.ellipse(
                    (ax - pr, ay - pr, ax + pr, ay + pr),
                    outline=rgba(self.color_at(t), 0.6 * (1 - pu) * a),
                    width=max(1, c.px(1.5) * ss),
                )
        elif self.kind in ("line", "leader"):
            if p > 0:
                tx, ty = ax + (bx - ax) * p, ay + (by - ay) * p
                d.line((ax, ay, tx, ty), fill=col, width=w)
                self._cap(d, ax, ay, w, col)
                self._cap(d, tx, ty, w, col)
                if self.kind == "leader" and p >= 0.999:
                    r = c.px(self.dot) * ss
                    d.ellipse((bx - r, by - r, bx + r, by + r), fill=col)
                elif self.kind == "leader" and p > 0.85:
                    r = c.px(self.dot) * ss * ((p - 0.85) / 0.15)
                    d.ellipse((bx - r, by - r, bx + r, by + r), fill=col)
            if self.kind == "leader" and self.ping:
                pu = self.ping_u(t)
                if 0 < pu < 1:
                    pr = c.px(5 + 9 * pu) * ss
                    d.ellipse(
                        (bx - pr, by - pr, bx + pr, by + pr),
                        outline=rgba(self.color_at(t), 0.6 * (1 - pu) * a),
                        width=max(1, c.px(1.5) * ss),
                    )
        elif self.kind == "path":
            pts = [((q[0] - left) * ss, (q[1] - top) * ss) for q in pts_px]
            if len(pts) >= 2 and p > 0:
                tail = None
                if self.tail:
                    tail = (c.px(float(self.tail.get("px", 60))) * ss, rgba(self.tail.get("color", "red"), a))
                end = self._draw_path(d, pts, min(1.0, p), w, col, tail)
                if self.end_dot and end is not None and p > 0.85:
                    er = c.px(float(self.end_dot.get("r", 5))) * ss * min(1.0, (p - 0.85) / 0.15)
                    ecol = rgba(
                        self.end_dot.get("color", self.tail.get("color", "red") if self.tail else self.color),
                        a,
                    )
                    ex, ey = pts[-1]
                    d.ellipse((ex - er, ey - er, ex + er, ey + er), fill=ecol)
        elif self.kind == "node":
            r = c.px(self.r) * ss * (0.6 + 0.4 * min(1.0, p))
            d.ellipse((ax - r, ay - r, ax + r, ay + r), fill=col)
            if self.ring:
                ru = 1.0 - self.recolor_u(t)
                if ru > 0 and p > 0:
                    rr = c.px(float(self.ring.get("r", 12))) * ss
                    d.ellipse(
                        (ax - rr, ay - rr, ax + rr, ay + rr),
                        outline=rgba(
                            self.ring.get("color", self.color),
                            float(self.ring.get("alpha", 0.5)) * ru * a * min(1.0, p),
                        ),
                        width=max(1, c.px(float(self.ring.get("width", 1))) * ss),
                    )
        elif self.kind in ("box", "highlight") and self.draw_box:
            box = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
            self._perimeter(d, box, min(1.0, p), w, col)
        elif self.kind in ("box", "highlight"):
            box = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
            grow = 1 - 0.06 * (1 - p)
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            hw, hh = (box[2] - box[0]) / 2 * grow, (box[3] - box[1]) / 2 * grow
            rad = c.px(self.radius) * ss if self.kind == "highlight" else w * 2
            fill = rgba(self.color, a * float(self.fill)) if self.fill else None
            d.rounded_rectangle(
                (cx - hw, cy - hh, cx + hw, cy + hh), radius=rad, fill=fill, outline=col, width=w
            )
        elif self.kind == "circle":
            box = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
            if p < 1:
                d.arc(box, start=-90, end=-90 + 360 * p, fill=col, width=w)
            else:
                d.ellipse(box, outline=col, width=w)
        elif self.kind == "bracket":
            ty = ay + (by - ay) * p
            tick = c.px(self.ticks) * ss
            d.line((ax, ay, ax, ty), fill=col, width=w)
            d.line((ax - tick, ay, ax, ay), fill=col, width=w)
            if p >= 0.98:
                d.line((ax - tick, by, ax, by), fill=col, width=w)
        elif self.kind == "bar":
            right_x = ax + (bx - ax) * p
            color = self.color
            if (
                self.threshold_x is not None
                and self.color_after
                and (left + right_x / ss) >= c.px(float(self.threshold_x))
            ):
                color = self.color_after
            if self.round_box:
                d.rounded_rectangle(
                    (ax, min(ay, by), max(ax + 1, right_x), max(ay, by)),
                    radius=c.px(self.radius) * ss,
                    fill=rgba(color, a),
                )
            else:
                d.rectangle((ax, min(ay, by), right_x, max(ay, by)), fill=rgba(color, a))
        elif self.kind == "dotted":
            length = math.hypot(bx - ax, by - ay)
            if length > 0:
                ux, uy = (bx - ax) / length, (by - ay) / length
                dash = c.px(self.dash) * ss
                pos = 0.0
                while pos < length * p:
                    e = min(pos + dash, length * p)
                    d.line((ax + ux * pos, ay + uy * pos, ax + ux * e, ay + uy * e), fill=col, width=w)
                    pos += dash * 2
        elif self.kind == "badge":
            r = c.px(self.r) * ss * (0.6 + 0.4 * p)
            d.ellipse((ax - r, ay - r, ax + r, ay + r), fill=col)
            if self.label is not None:
                f = c.font(self.label_font, float(self.spec.get("size", 22)) * ss)
                lw = f.getlength(str(self.label))
                asc = f.getmetrics()[0]
                d.text(
                    (ax - lw / 2, ay - asc * 0.56), str(self.label), font=f, fill=rgba(self.label_color, a)
                )
        img = img.resize((right - left, bottom - top), Image.Resampling.LANCZOS)
        return img, left, top


WIDGET_KINDS = {"spotlight", "bar", "rail", "bloom", "progress_rail"}


def make_overlay(spec: dict[str, Any], canvas: Canvas, shot_duration: float, loader: Any = None) -> Any:
    kind = str(spec.get("kind", "caption"))
    if kind == "chips":
        return ChipsOverlay(spec, canvas, shot_duration)
    if kind == "panel":
        return PanelOverlay(spec, canvas, shot_duration)
    if kind == "image":
        return ImageOverlay(spec, canvas, shot_duration, loader)
    if kind in WIDGET_KINDS:
        from . import widgets

        return widgets.make_widget(kind, spec, canvas, shot_duration)
    if spec.get("spans"):
        return SpanOverlay(spec, canvas, shot_duration)
    return TextOverlay(spec, canvas, shot_duration)


class OverlayRenderer:
    """All text overlays and pointers of a shot, composited onto a frame.

    Normal parts alpha-composite in one RGBA layer; ``glow`` parts add (bloom) underneath it.
    """

    def __init__(
        self,
        canvas: Canvas,
        texts: list[dict[str, Any]],
        pointers: list[dict[str, Any]],
        shot_duration: float,
        captions: list[tuple[float, float, str]] | None = None,
        loader: Any = None,
        transform: Any = None,
        global_start: float = 0.0,
    ):
        self.canvas = canvas
        # z order (v4): pointers default to 50, text overlays to 60, captions to 100; a stable
        # sort keeps the pre-v4 order (pointers first, then texts) when no `z` is given
        entries: list[tuple[float, int, Any]] = []
        n = 0
        for p in pointers:
            ptr = Pointer(p, canvas, shot_duration)
            if ptr.attach:
                ptr.transform = transform
            entries.append((float(p.get("z", 50)), n, ptr))
            n += 1
        for sp in texts:
            if sp.get("kind") == "progress_rail":
                sp = {**sp, "_global_start": global_start}
            entries.append((float(sp.get("z", 60)), n, make_overlay(sp, canvas, shot_duration, loader)))
            n += 1
        for start, end, text in captions or []:
            spec = {
                "kind": "caption",
                "text": text,
                "in": start,
                "out": end,
                "pos": "bc",
                "size": 36,
                "plate": True,
            }
            entries.append((100.0, n, TextOverlay(spec, canvas, shot_duration)))
            n += 1
        entries.sort(key=lambda e: (e[0], e[1]))
        self.items: list[Any] = [e[2] for e in entries]
        self.zs: list[float] = [e[0] for e in entries]

    GLOBAL_Z = 97.0  # chrome at or above this z is drawn from the global clock across transitions

    def key(self, t: float) -> Any:
        return tuple(it.key(t) for it in self.items)

    def parts(
        self, t: float, hi_z: bool = True
    ) -> tuple[list[tuple[Image.Image, int, int]], list[tuple[Image.Image, int, int]]]:
        normal: list[tuple[Image.Image, int, int]] = []
        adds: list[tuple[Image.Image, int, int]] = []
        for it, z in zip(self.items, self.zs, strict=True):
            if not hi_z and z >= self.GLOBAL_Z:
                continue
            r = it.render(t)
            if r is None:
                continue
            normal.append(r)
            gp = it.glow_part(t, r) if hasattr(it, "glow_part") else None
            if gp is not None:
                adds.append(gp)
        return normal, adds

    def layer(self, t: float) -> Image.Image | None:
        normal, _ = self.parts(t)
        if not normal:
            return None
        layer = self.canvas.layer()
        for block, x, y in normal:
            layer.alpha_composite(block, (int(x), int(y)))
        return layer

    def composite(self, img: Image.Image, t: float, hi_z: bool = True) -> Image.Image:
        """The frame with this shot's overlays: additive glow first, then the normal layer.
        ``hi_z=False`` leaves out the global chrome (z >= 97), which a transition draws itself."""
        normal, adds = self.parts(t, hi_z)
        if not normal:
            return img
        if adds:
            img = add_parts(img, adds)
        layer = self.canvas.layer()
        for block, x, y in normal:
            layer.alpha_composite(block, (int(x), int(y)))
        out = img.convert("RGBA")
        out.alpha_composite(layer)
        return out.convert("RGB")


def add_parts(img: Image.Image, parts: list[tuple[Image.Image, int, int]]) -> Image.Image:
    """Additive blend of RGBA parts (colour times alpha) onto an RGB frame, clipped to 255."""
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    H, W = arr.shape[:2]
    for block, x, y in parts:
        x, y = int(x), int(y)
        bx0, by0 = max(0, -x), max(0, -y)
        bx1, by1 = min(block.width, W - x), min(block.height, H - y)
        if bx1 <= bx0 or by1 <= by0:
            continue
        b = np.asarray(block, dtype=np.float32)[by0:by1, bx0:bx1]
        rgb_ = b[..., :3] * (b[..., 3:4] / 255.0)
        arr[y + by0 : y + by1, x + bx0 : x + bx1] += rgb_
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")


# --------------------------------------------------------------------------- base sources


class FrameSource:
    """Interface: ``frame(t)`` returns an RGB image of the canvas size; ``key(t)`` is a cache key."""

    def frame(self, t: float) -> Image.Image:
        raise NotImplementedError

    def key(self, t: float) -> Any:
        return None

    def close(self) -> None:
        return None


def make_background(canvas: Canvas, bg: Any) -> Image.Image:
    """Solid colour or a 2..n stop gradient ``[c1, c2]`` / ``{colors:[...], angle: 90}``."""
    if bg is None:
        return canvas.blank("bg")
    if isinstance(bg, dict):
        colors = bg.get("colors", ["bg", "panel"])
        angle = float(bg.get("angle", 90))
    elif isinstance(bg, (list, tuple)):
        colors, angle = list(bg), 90.0
    else:
        return canvas.blank(bg)
    stops = [np.array(rgb(c), dtype=np.float32) for c in colors]
    w, h = canvas.width, canvas.height
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    rad = math.radians(angle)
    proj = (xs / max(1, w - 1)) * math.cos(rad) + (ys / max(1, h - 1)) * math.sin(rad)
    proj = (proj - proj.min()) / max(1e-6, proj.max() - proj.min())
    n = len(stops) - 1
    seg = np.clip(proj * n, 0, n - 1e-6)
    idx = seg.astype(np.int32)
    frac = (seg - idx)[..., None]
    lo = np.stack(stops)[idx]
    hi = np.stack(stops)[np.minimum(idx + 1, n)]
    arr = (lo * (1 - frac) + hi * frac).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


class CardSource(FrameSource):
    def __init__(self, canvas: Canvas, params: dict[str, Any], asset_loader: Any = None):
        self.img = make_background(canvas, params.get("bg", "bg"))
        logo = params.get("logo")
        if logo:
            src = logo.get("src") if isinstance(logo, dict) else logo
            spec = logo if isinstance(logo, dict) else {}
            lw = canvas.px(float(spec.get("width", 320)))
            im = asset_loader(src) if asset_loader else Image.open(src)
            im = im.convert("RGBA")
            ratio = lw / max(1, im.width)
            im = im.resize((lw, max(1, int(im.height * ratio))), Image.Resampling.LANCZOS)
            x, y = place_block(canvas, spec.get("pos", "tc"), im.width, im.height)
            base = self.img.convert("RGBA")
            base.alpha_composite(im, (x, y))
            self.img = base.convert("RGB")

    def frame(self, t: float) -> Image.Image:
        return self.img

    def key(self, t: float) -> Any:
        return "card"


def panel_box(canvas: Canvas, params: dict[str, Any]) -> tuple[int, int, int, int]:
    fr = params.get("frame")
    if fr:
        x, y = canvas.pt(fr[:2])
        return (x, y, x + canvas.px(fr[2]), y + canvas.px(fr[3]))
    mx, my = canvas.px(SAFE_X), canvas.px(SAFE_Y)
    return (mx, my, canvas.width - mx, canvas.height - my)


def draw_panel(
    img: Image.Image, canvas: Canvas, box: tuple[int, int, int, int], title: str | None, bar: bool = True
) -> tuple[int, int, int, int]:
    """Dark rounded panel with an optional macOS-style title bar. Returns the inner content box."""
    d = ImageDraw.Draw(img)
    r = canvas.px(16)
    rounded(d, box, r, fill=rgb("panel"), outline=rgb("panel_border"), width=max(1, canvas.px(2)))
    x0, y0, x1, y1 = box
    if not bar:
        pad = canvas.px(28)
        return (x0 + pad, y0 + pad, x1 - pad, y1 - pad)
    bar_h = canvas.px(48)
    d.rounded_rectangle((x0, y0, x1, y0 + bar_h + r), radius=r, fill=rgb("#1d1f27"))
    d.rectangle((x0, y0 + bar_h - 1, x1, y0 + bar_h + r), fill=rgb("panel"))
    d.line((x0, y0 + bar_h, x1, y0 + bar_h), fill=rgb("panel_border"), width=max(1, canvas.px(2)))
    dot = canvas.px(14)
    for i, c in enumerate(("red", "orange", "green")):
        cx = x0 + canvas.px(24) + i * (dot + canvas.px(12))
        cy = y0 + bar_h // 2
        d.ellipse((cx, cy - dot // 2, cx + dot, cy + dot // 2), fill=rgb(c))
    if title:
        f = canvas.font("sans", 24)
        tw = f.getlength(title)
        d.text(((x0 + x1) / 2 - tw / 2, y0 + bar_h / 2 - canvas.px(14)), title, font=f, fill=rgb("muted"))
    pad = canvas.px(28)
    return (x0 + pad, y0 + bar_h + pad, x1 - pad, y1 - pad)


def wrap_chars(line: str, width: int, indent: str = "  ") -> list[str]:
    """Wrap on spaces at ``width`` characters; continuation lines carry ``indent``."""
    out: list[str] = []
    cur = ""
    prefix = ""
    for word in line.split(" "):
        cand = word if not cur else f"{cur} {word}"
        if len(prefix + cand) <= width or not cur:
            cur = cand
        else:
            out.append(prefix + cur)
            prefix = indent
            cur = word
    out.append(prefix + cur)
    return out


def read_lines(params: dict[str, Any], base_dir: Path | None) -> list[str]:
    if "lines" in params:
        lines = [str(ln) for ln in params["lines"]]
    elif "text" in params and params.get("kind") != "json":
        lines = str(params["text"]).split("\n")
    elif params.get("src"):
        p = Path(str(params["src"]))
        if base_dir and not p.is_absolute():
            p = base_dir / p
        lines = p.read_text(encoding="utf-8").rstrip("\n").split("\n")
    else:
        lines = []
    rng = params.get("line_range")
    if rng:
        lines = lines[int(rng[0]) - 1 : int(rng[1])]
    if params.get("wrap"):
        wrapped: list[str] = []
        for ln in lines:
            wrapped += wrap_chars(ln, int(params["wrap"]), str(params.get("wrap_indent", "  ")))
        lines = wrapped
    return lines


def scanlines(
    img: Image.Image, box: tuple[int, int, int, int], strength: float, every: int = 3
) -> Image.Image:
    """Darken every ``every``-th row inside ``box`` by ``strength`` (CRT look; off by default)."""
    if strength <= 0:
        return img
    arr = np.asarray(img.convert("RGB")).copy()
    x0, y0, x1, y1 = box
    rows = arr[y0:y1:every, x0:x1]
    arr[y0:y1:every, x0:x1] = (rows.astype(np.float32) * (1.0 - strength)).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def soft_band(
    size: tuple[int, int], box: tuple[float, float, float, float], color: Any, alpha: float, blur: float
) -> Image.Image:
    """A feathered highlight band: a filled rectangle blurred into the surrounding area."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=max(1, int(blur)), fill=rgba(color, alpha))
    return layer.filter(ImageFilter.GaussianBlur(blur)) if blur > 0 else layer


class TerminalSource(FrameSource):
    """Typewriter terminal.

    Lines type at ``cps``; ``schedule`` holds a line back until its time (the cursor waits);
    the first ``pre`` lines are shown dim from frame 0; ``chrome: false`` drops the window
    frame and places the text at ``pos``; ``highlight`` entries ``{match, color}`` colour a
    substring, and with ``at`` they also draw a timed highlight box computed from the font
    (``soft: true`` draws a feathered band instead of the box).

    v3: ``jitter`` (0..1, seeded per-character timing), ``seed``, per-line ``pause_ms`` (a
    line may be ``{text, pause_ms}``, or use ``pauses: [{line, ms}]``), ``syntax: json`` for
    key/string/number colours, ``cursor_hz``, ``cursor_style: block|bar``, ``scanlines``.
    """

    def __init__(self, canvas: Canvas, params: dict[str, Any], duration: float, base_dir: Path | None = None):
        self.canvas = canvas
        params = dict(params)
        pauses: dict[int, float] = {}
        if isinstance(params.get("lines"), list):
            plain = []
            for i, ln in enumerate(params["lines"]):
                if isinstance(ln, dict):
                    plain.append(str(ln.get("text", "")))
                    if ln.get("pause_ms") is not None:
                        pauses[i] = float(ln["pause_ms"]) / 1000.0
                else:
                    plain.append(ln)
            params["lines"] = plain
        for e in params.get("pauses", []) or []:
            pauses[int(e["line"])] = float(e.get("ms", 0)) / 1000.0
        self.lines = read_lines(params, base_dir)
        self.cps = float(params.get("cps", 40))
        self.delay = float(params.get("start", 0.3))
        self.highlights = [dict(h) for h in params.get("highlight", [])]
        self.title = params.get("title", "terminal")
        self.size = float(params.get("size", 30))
        self.chrome = bool(params.get("chrome", True))
        self.color = params.get("color", "ink")
        self.pre = int(params.get("pre", 0))
        self.pre_color = params.get("pre_color", "ink-dim")
        self.show_cursor = bool(params.get("cursor", True))
        self.cursor_hz = float(params.get("cursor_hz", 2.2))
        self.cursor_style = str(params.get("cursor_style", "block"))
        self.syntax = params.get("syntax")
        self.scan = float(params.get("scanlines", 0.0) or 0.0)
        self.jitter = float(params.get("jitter", 0.0) or 0.0)
        # v4: a DESIGN section 4 panel under a bare text column, the column's own bottom edge,
        # a 530 ms block cursor that rests after the last line and hides while machine rows print
        self.panel = params.get("panel")
        self.cursor_hold = bool(params.get("cursor_hold", False))
        self.cursor_hide_fast = params.get("cursor_hide_fast")
        self.cursor_blink_ms = params.get("cursor_blink_ms")
        self.cursor_w = params.get("cursor_w")
        self.cursor_h = params.get("cursor_h")
        self.fade_bottom = float(params.get("fade_bottom", 0.0) or 0.0)
        self.base = make_background(canvas, params.get("bg", "bg"))
        if self.panel:
            pb = self.panel.get("box", [SAFE_X, SAFE_Y, REF_W - SAFE_X, REF_H - SAFE_Y])
            px0, py0 = canvas.pt(pb[:2])
            px1, py1 = canvas.pt(pb[2:])
            rgba_base = self.base.convert("RGBA")
            paint_panel_v2(
                rgba_base, canvas, (px0, py0, px1, py1), {"shadow": {}, "border": {}, **self.panel}
            )
            self.base = rgba_base.convert("RGB")
            self.box = (px0, py0, px1, py1)
            x, y = canvas.pt(params.get("pos", [pb[0] + 24, pb[1] + 24]))
            w = canvas.px(float(params["width"])) if "width" in params else px1 - canvas.px(24) - x
            bottom = canvas.px(float(params["bottom"])) if "bottom" in params else py1 - canvas.px(24)
            self.inner = (x, y, min(canvas.width, x + w), bottom)
        elif self.chrome:
            self.box = panel_box(canvas, params)
            self.inner = draw_panel(self.base, canvas, self.box, self.title)
        elif "frame" in params:
            self.box = self.inner = panel_box(canvas, params)
        else:
            x, y = canvas.pt(params.get("pos", [SAFE_X, SAFE_Y]))
            w = (
                canvas.px(float(params["width"]))
                if "width" in params
                else canvas.width - canvas.px(SAFE_X) - x
            )
            bottom = (
                canvas.px(float(params["bottom"]))
                if "bottom" in params
                else canvas.height - canvas.px(SAFE_Y)
            )
            self.inner = (x, y, min(canvas.width, x + w), bottom)
            self.box = self.inner
        self.font = canvas.font(params.get("font", "mono"), self.size)
        if "leading" in params:
            self.line_h = canvas.px(float(params["leading"]))
        else:
            self.line_h = round(canvas.px(self.size) * 1.5)
        pause = float(params.get("line_pause", 0.12))
        schedule: dict[int, float] = {}
        rates: dict[int, float] = {}
        delays: dict[int, float] = {}
        for e in params.get("schedule", []):
            i = int(e["line"])
            if "at" in e:
                schedule[i] = float(e["at"])
            if e.get("cps") is not None:
                rates[i] = float(e["cps"])
            if e.get("delay") is not None:
                delays[i] = float(e["delay"])
        self.v3 = self.jitter > 0 or bool(pauses) or bool(rates) or bool(delays)
        rng = np.random.default_rng(int(params.get("seed", 1)))
        t = self.delay
        self.starts: list[float] = []
        self.char_t: list[list[float]] = []
        self.line_cps: list[float] = []
        for i, ln in enumerate(self.lines):
            cps_i = rates.get(i, self.cps)
            self.line_cps.append(cps_i)
            if i < self.pre:
                self.starts.append(-1.0)
                self.char_t.append([])
                continue
            if i in schedule:
                t = max(t, schedule[i])
            t += delays.get(i, 0.0)
            self.starts.append(t)
            if self.v3:
                steps = (1.0 / cps_i) * (1.0 + self.jitter * rng.uniform(-1.0, 1.0, size=len(ln)))
                times = (t + np.cumsum(np.maximum(steps, 1e-4))).tolist() if len(ln) else []
                self.char_t.append(times)
                t = (times[-1] if times else t) + pause + pauses.get(i, 0.0)
            else:
                self.char_t.append([])
                t += len(ln) / self.cps + pause
        self.done_at = t
        self.prompt_color = params.get("prompt_color", "green")

    def hl_levels(self, t: float) -> tuple[float, ...]:
        out = []
        for h in self.highlights:
            if "at" not in h:
                out.append(1.0)
            elif h.get("style") == "underline":
                over = float(h.get("draw_ms", 240)) / 1000.0
                out.append(ease(str(h.get("ease", "draw")), (t - float(h["at"])) / over) if over > 0 else 1.0)
            else:
                out.append(smoothstep((t - float(h["at"])) / 0.25))
        return tuple(out)

    def hl_settles(self, t: float) -> tuple[float, ...]:
        out = []
        for h in self.highlights:
            k = 1.0
            if h.get("settle_at") is not None and t >= float(h["settle_at"]):
                u = eased_progress(t, float(h["settle_at"]), 0.24, "move")
                k = 1.0 - (1.0 - float(h.get("settle_to", 0.5))) * u
            out.append(k)
        return tuple(out)

    def _typing_fast(self, t: float) -> bool:
        """True while a machine-class line (cps at or above ``cursor_hide_fast``) is printing."""
        if self.cursor_hide_fast is None:
            return False
        thr = float(self.cursor_hide_fast)
        for i, st in enumerate(self.starts):
            if st < 0 or self.line_cps[i] < thr:
                continue
            end = (
                self.char_t[i][-1]
                if (self.v3 and self.char_t[i])
                else st + len(self.lines[i]) / self.line_cps[i]
            )
            if st <= t < end:
                return True
        return False

    def overflowing_lines(self) -> list[tuple[int, int, int]]:
        """(line index, width, column width) in reference units for every line wider than the column."""
        x0, _, x1, _ = self.inner
        limit = x1 - x0
        out = []
        for i, ln in enumerate(self.lines):
            w = math.ceil(self.font.getlength(ln))
            if w > limit:
                out.append((i, round(w / self.canvas.s), round(limit / self.canvas.s)))
        return out

    def _state(self, t: float) -> tuple[list[tuple[int, int]], bool]:
        """Visible (line index, chars) pairs and whether typing has finished."""
        out: list[tuple[int, int]] = []
        for i, ln in enumerate(self.lines):
            st = self.starts[i]
            if st < 0:
                out.append((i, len(ln)))
            elif t >= st:
                if self.v3:
                    out.append((i, bisect.bisect_right(self.char_t[i], t)))
                else:
                    out.append((i, min(len(ln), int((t - st) * self.cps))))
            else:
                break
        return out, t >= self.done_at

    def _cursor_on(self, t: float, done: bool) -> bool:
        if not self.show_cursor or (done and not self.cursor_hold) or self._typing_fast(t):
            return False
        if self.cursor_blink_ms:
            return int(t * 1000.0 / float(self.cursor_blink_ms)) % 2 == 0
        return int(t * self.cursor_hz) % 2 == 0

    def key(self, t: float) -> Any:
        shown, done = self._state(t)
        base = (tuple(shown), self._cursor_on(t, done), tuple(quantize(v, 16) for v in self.hl_levels(t)))
        if any(h.get("settle_at") is not None for h in self.highlights):
            return (*base, tuple(quantize(v, 16) for v in self.hl_settles(t)))
        return base

    def _applies(self, h: dict[str, Any], i: int) -> bool:
        return h.get("line") is None or int(h["line"]) == i

    def _segments(self, full: str, active: list[dict[str, Any]]) -> list[tuple[str, Any]]:
        """(text, colour-or-None) runs: ``syntax: json`` colours first, highlight matches on top."""
        if self.syntax != "json" or '"' not in full:
            return segments_for(full, active)
        colors: list[Any] = [None] * len(full)
        pos = 0
        for tok, role in json_tokens(full):
            col = JSON_COLORS[role] if role not in ("plain", "punct") else None
            for k in range(pos, min(len(full), pos + len(tok))):
                colors[k] = col
            pos += len(tok)
        for a0, b0, col in find_spans(full, active):
            for k in range(a0, b0):
                colors[k] = col
        runs: list[tuple[str, Any]] = []
        for k, ch in enumerate(full):
            if runs and runs[-1][1] == colors[k]:
                runs[-1] = (runs[-1][0] + ch, colors[k])
            else:
                runs.append((ch, colors[k]))
        return runs or [("", None)]

    def frame(self, t: float) -> Image.Image:
        shown, done = self._state(t)
        cursor_on = self._cursor_on(t, done)
        levels = self.hl_levels(t)
        settles = self.hl_settles(t)
        img = self.base.copy().convert("RGBA")
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = self.inner
        max_lines = max(1, (y1 - y0) // self.line_h)
        visible = shown[-max_lines:]
        cw = self.font.getlength("M")
        max_cols = max(8, int((x1 - x0) // cw))
        c = self.canvas
        asc = self.font.getmetrics()[0]
        y = y0
        for k, (i, n) in enumerate(visible):
            full = self.lines[i]
            base_color = self.pre_color if self.starts[i] < 0 else self.color
            active = []
            for h, lv, sk in zip(self.highlights, levels, settles, strict=True):
                if lv <= 0 or not self._applies(h, i):
                    continue
                if h.get("style") == "underline":
                    if h.get("recolor", True):
                        u = min(1.0, lv) * (0.5 + 0.5 * sk)
                        start_col = h.get("from", base_color)
                        active.append({**h, "color": blend_rgba(start_col, h.get("color", "orange"), u)})
                elif lv >= 1:
                    active.append(h)
            for h, lv, sk in zip(self.highlights, levels, settles, strict=True):
                if "at" not in h or lv <= 0 or not self._applies(h, i):
                    continue
                for a0, b0, col in find_spans(full[:n], [h]):
                    if h.get("style") == "underline":
                        if float(h.get("width", 2)) <= 0:
                            continue
                        ux0 = x0 + self.font.getlength(full[:a0])
                        ux1 = x0 + self.font.getlength(full[:b0])
                        uy = y + asc + c.px(float(h.get("gap", 6)))
                        d.line(
                            (ux0, uy, ux0 + (ux1 - ux0) * min(1.0, lv), uy),
                            fill=rgba(col, float(h.get("alpha", 1.0)) * sk),
                            width=max(1, c.px(float(h.get("width", 2)))),
                        )
                        continue
                    if h.get("soft"):
                        band = soft_band(
                            img.size,
                            (x0 + a0 * cw - cw * 1.5, y - c.px(2), x0 + b0 * cw + cw * 1.5, y + self.line_h),
                            col,
                            0.28 * lv,
                            self.line_h * 0.35,
                        )
                        img.alpha_composite(band)
                        d = ImageDraw.Draw(img)
                        continue
                    box = (
                        x0 + a0 * cw - cw * 0.3,
                        y - c.px(4),
                        x0 + b0 * cw + cw * 0.3,
                        y + self.line_h - c.px(2),
                    )
                    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
                    ImageDraw.Draw(layer).rounded_rectangle(
                        box,
                        radius=c.px(8),
                        fill=rgba(col, 0.12 * lv),
                        outline=rgba(col, lv),
                        width=max(1, c.px(3)),
                    )
                    img.alpha_composite(layer)
                    d = ImageDraw.Draw(img)
            x = x0
            remaining = min(n, max_cols)
            for seg_text, color in self._segments(full, active):
                if remaining <= 0:
                    break
                part = seg_text[:remaining]
                remaining -= len(part)
                fill = rgb(color) if color else rgb(base_color)
                if color is None and x == x0 and part.startswith("$ ") and self.chrome:
                    d.text((x, y), "$", font=self.font, fill=rgb(self.prompt_color))
                    d.text((x + cw, y), part[1:], font=self.font, fill=fill)
                else:
                    d.text((x, y), part, font=self.font, fill=fill)
                x += self.font.getlength(part)
            if k == len(visible) - 1 and cursor_on:
                cx = x0 + cw * min(n, max_cols) + (cw * 0.3 if n else 0)
                self._cursor(d, cx, y, cw)
            y += self.line_h
        if not shown and cursor_on:
            self._cursor(d, x0, y0, cw)
        if self.fade_bottom > 0:
            fb = c.px(self.fade_bottom)
            panel_col = rgb((self.panel or {}).get("color", "surface")) if self.panel else rgb("bg")
            grad = Image.new("RGBA", (x1 - x0, fb), (*panel_col, 0))
            gd = ImageDraw.Draw(grad)
            for row in range(fb):
                gd.line((0, row, x1 - x0, row), fill=(*panel_col, int(255 * row / max(1, fb - 1))))
            img.alpha_composite(grad, (x0, y1 - fb))
        out = img.convert("RGB")
        if self.scan > 0:
            out = scanlines(out, self.box, self.scan)
        return out

    def _cursor(self, d: ImageDraw.ImageDraw, cx: float, y: float, cw: float) -> None:
        if self.cursor_w and self.cursor_h:
            w, h = self.canvas.px(float(self.cursor_w)), self.canvas.px(float(self.cursor_h))
            top = y + (self.line_h - h) / 2
            d.rectangle((cx, top, cx + w, top + h), fill=rgb(self.color))
            return
        if self.cursor_style == "bar":
            d.rectangle(
                (cx, y + self.line_h * 0.12, cx + max(2, cw * 0.12), y + self.line_h * 0.88),
                fill=rgb(self.color),
            )
            return
        d.rectangle((cx, y + self.line_h * 0.12, cx + cw * 0.9, y + self.line_h * 0.88), fill=rgb(self.color))


class TableSource(FrameSource):
    """Rows revealed one at a time every ``row_every`` seconds, optional highlighted row."""

    def __init__(self, canvas: Canvas, params: dict[str, Any], duration: float):
        self.canvas = canvas
        self.rows = [[str(c) for c in r] for r in params.get("rows", [])]
        self.header = bool(params.get("header", True))
        self.row_every = float(params.get("row_every", 0.6))
        if params.get("stagger") is not None:
            self.row_every = float(params["stagger"]) / 1000.0
        self.anim = str(params.get("anim", "fade"))
        self.v3 = self.anim in ENTER_ANIMS or "ease" in params or canvas.ease is not None
        self.ease = canvas.curve(params, legacy=self.anim not in ENTER_ANIMS)
        self.row_ms = float(params.get("row_ms", 250 if not self.v3 else 420)) / 1000.0
        self.delay = float(params.get("start", 0.4))
        self.title = params.get("title")
        self.size = float(params.get("size", 34))
        hl = params.get("highlight")
        self.highlight = hl if isinstance(hl, list) else ([hl] if hl else [])
        self.box = panel_box(canvas, params)
        self.base = make_background(canvas, params.get("bg", "bg"))
        self.inner = draw_panel(self.base, canvas, self.box, self.title, bar=bool(self.title))
        self.font = canvas.font("sans", self.size)
        self.bold = canvas.font("sans_bold", self.size)
        self.row_h = round(canvas.px(self.size) * 1.9)
        ncol = max((len(r) for r in self.rows), default=1)
        widths = [0] * ncol
        for r in self.rows:
            for i, cell in enumerate(r):
                widths[i] = max(widths[i], int(self.bold.getlength(cell)) + canvas.px(44))
        avail = self.inner[2] - self.inner[0]
        total = sum(widths) or 1
        if total > avail:
            widths = [int(w * avail / total) for w in widths]
        else:
            extra = (avail - total) // ncol
            widths = [w + extra for w in widths]
        self.widths = widths

    def _visible(self, t: float) -> int:
        if t < self.delay:
            return 0
        n = 1 + int((t - self.delay) / self.row_every)
        return min(len(self.rows), n)

    def key(self, t: float) -> Any:
        n = self._visible(t)
        hl = tuple(quantize((t - float(h.get("at", -1.0))) / 0.25, 8) for h in self.highlight)
        if self.v3:
            ages = tuple(round(self._row_p(t, ri) * 256) for ri in range(n))
            return (n, ages, hl)
        age = t - (self.delay + (n - 1) * self.row_every) if n else 0.0
        return (n, quantize(age / 0.25, 8), hl)

    def _row_p(self, t: float, ri: int) -> float:
        return ease(self.ease, (t - (self.delay + ri * self.row_every)) / self.row_ms)

    def frame(self, t: float) -> Image.Image:
        if self.v3:
            return self._frame_v3(t)
        n = self._visible(t)
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        x0, y0, x1, _ = self.inner
        c = self.canvas
        for ri in range(n):
            row = self.rows[ri]
            y = y0 + ri * self.row_h
            is_header = self.header and ri == 0
            age = t - (self.delay + (ri) * self.row_every)
            a = smoothstep(age / 0.25)
            hl_color = None
            for h in self.highlight:
                if int(h.get("row", -1)) == ri and t >= float(h.get("at", self.delay + ri * self.row_every)):
                    hl_color = h.get("color", "orange")
            if is_header:
                d.rectangle((x0, y, x1, y + self.row_h), fill=rgb("#1d1f27"))
            elif hl_color:
                overlay = Image.new("RGBA", (x1 - x0, self.row_h), rgba(hl_color, 0.22 * a))
                img.paste(overlay, (x0, y), overlay)
                d = ImageDraw.Draw(img)
                d.rectangle((x0, y, x0 + c.px(6), y + self.row_h), fill=rgb(hl_color))
            d.line((x0, y + self.row_h, x1, y + self.row_h), fill=rgb("panel_border"), width=max(1, c.px(2)))
            x = x0
            for ci, cell in enumerate(row):
                font = self.bold if is_header else self.font
                color = rgb("muted") if is_header else (rgb(hl_color) if hl_color else rgb("text"))
                fill = tuple(int(v * a + rgb("panel")[i] * (1 - a)) for i, v in enumerate(color))
                d.text(
                    (x + c.px(22), y + (self.row_h - c.px(self.size)) / 2 - c.px(4)),
                    cell,
                    font=font,
                    fill=fill,
                )
                x += self.widths[ci] if ci < len(self.widths) else 0
        return img

    def _row_strip(self, ri: int, t: float) -> Image.Image:
        """One row drawn at full opacity on a transparent strip (v3 path)."""
        c = self.canvas
        x0, _, x1, _ = self.inner
        w, h = x1 - x0, self.row_h
        strip = Image.new("RGBA", (w, h + 1), (0, 0, 0, 0))
        d = ImageDraw.Draw(strip)
        row = self.rows[ri]
        is_header = self.header and ri == 0
        hl_color = None
        for hl in self.highlight:
            if int(hl.get("row", -1)) == ri and t >= float(hl.get("at", self.delay + ri * self.row_every)):
                hl_color = hl.get("color", "orange")
        if is_header:
            d.rectangle((0, 0, w, h), fill=rgb("#1d1f27"))
        elif hl_color:
            d.rectangle((0, 0, w, h), fill=rgba(hl_color, 0.22))
            d.rectangle((0, 0, c.px(6), h), fill=rgb(hl_color))
        d.line((0, h, w, h), fill=rgb("panel_border"), width=max(1, c.px(2)))
        x = 0
        for ci, cell in enumerate(row):
            font = self.bold if is_header else self.font
            color = rgb("muted") if is_header else (rgb(hl_color) if hl_color else rgb("text"))
            d.text((x + c.px(22), (h - c.px(self.size)) / 2 - c.px(4)), cell, font=font, fill=color)
            x += self.widths[ci] if ci < len(self.widths) else 0
        return strip

    def _frame_v3(self, t: float) -> Image.Image:
        n = self._visible(t)
        img = self.base.copy().convert("RGBA")
        x0, y0, _, _ = self.inner
        c = self.canvas
        for ri in range(n):
            p = self._row_p(t, ri)
            if p <= 0:
                continue
            strip = animate_block(
                self._row_strip(ri, t), self.anim if self.anim in ENTER_ANIMS else "fade", p, c
            )
            dy = round((1 - p) * c.px(RISE_PX) * 0.5) if self.anim == "rise" else 0
            img.alpha_composite(strip, (x0, y0 + ri * self.row_h + dy))
        return img.convert("RGB")


_JSON_TOKEN = re.compile(
    r'("(?:[^"\\]|\\.)*")(\s*:)?|(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)|\b(true|false|null)\b|([{}\[\],])'
)


def json_tokens(line: str) -> list[tuple[str, str]]:
    """Split a pretty-printed JSON line into (text, role) with role in key/str/num/punct/plain."""
    out: list[tuple[str, str]] = []
    pos = 0
    for m in _JSON_TOKEN.finditer(line):
        if m.start() > pos:
            out.append((line[pos : m.start()], "plain"))
        if m.group(1):
            if m.group(2):
                out.append((m.group(1), "key"))
                out.append((m.group(2), "punct"))
            else:
                out.append((m.group(1), "str"))
        elif m.group(3) or m.group(4):
            out.append((m.group(0), "num"))
        else:
            out.append((m.group(0), "punct"))
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], "plain"))
    return out


JSON_COLORS = {"key": "cyan", "str": "green", "num": "orange", "punct": "muted", "plain": "text"}


class JsonSource(FrameSource):
    """Pretty JSON typed out with syntax colours; ``reveal`` highlights substrings afterwards."""

    def __init__(self, canvas: Canvas, params: dict[str, Any], duration: float, base_dir: Path | None = None):
        self.canvas = canvas
        if "data" in params:
            text = json.dumps(params["data"], indent=2)
        elif "src" in params:
            p = Path(params["src"])
            if base_dir and not p.is_absolute():
                p = base_dir / p
            raw = p.read_text(encoding="utf-8")
            try:
                text = json.dumps(json.loads(raw), indent=2)
            except json.JSONDecodeError:
                text = raw.rstrip("\n")
        else:
            raw = str(params.get("text", "{}"))
            try:
                text = json.dumps(json.loads(raw), indent=2)
            except json.JSONDecodeError:
                text = raw
        self.lines = text.split("\n")
        self.cps = float(params.get("cps", 60))
        self.delay = float(params.get("start", 0.3))
        self.size = float(params.get("size", 30))
        self.title = params.get("title", "decision.json")
        total_chars = sum(len(ln) for ln in self.lines)
        self.nl_cost = self.cps * float(params.get("line_pause", 0.05))
        self.type_end = self.delay + (total_chars + self.nl_cost * (len(self.lines) - 1)) / self.cps
        self.reveals: list[dict[str, Any]] = []
        for i, r in enumerate(params.get("reveal", [])):
            r = dict(r)
            r.setdefault("color", "orange")
            r.setdefault("at", self.type_end + 0.4 + 0.6 * i)
            self.reveals.append(r)
        self.box = panel_box(canvas, params)
        self.base = make_background(canvas, params.get("bg", "bg"))
        self.inner = draw_panel(self.base, canvas, self.box, self.title)
        self.font = canvas.font("mono", self.size)
        self.line_h = round(canvas.px(self.size) * 1.5)

    def _state(self, t: float) -> tuple[list[str], tuple[int, ...]]:
        n = max(0.0, (t - self.delay) * self.cps)
        shown, _ = typed_prefix(self.lines, n, self.nl_cost)
        flags = tuple(quantize(smoothstep((t - float(r["at"])) / 0.3), 8) for r in self.reveals)
        return shown, flags

    def key(self, t: float) -> Any:
        shown, flags = self._state(t)
        return (sum(len(s) for s in shown), len(shown), flags)

    def frame(self, t: float) -> Image.Image:
        shown, flags = self._state(t)
        img = self.base.copy()
        x0, y0, _x1, y1 = self.inner
        max_lines = max(1, (y1 - y0) // self.line_h)
        offset = max(0, len(shown) - max_lines)
        visible = shown[offset:]
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        d = ImageDraw.Draw(img)
        cw = self.font.getlength("M")
        for i, ln in enumerate(visible):
            y = y0 + i * self.line_h
            full = self.lines[offset + i]
            active = [(r, flags[k]) for k, r in enumerate(self.reveals) if flags[k] > 0]
            for r, f in active:
                for a, b, color in find_spans(full, [r]):
                    if a >= len(ln):
                        continue
                    alpha = 0.28 * f / 8
                    ld.rounded_rectangle(
                        (
                            x0 + a * cw - cw * 0.3,
                            y - self.line_h * 0.05,
                            x0 + b * cw + cw * 0.3,
                            y + self.line_h * 0.9,
                        ),
                        radius=self.canvas.px(6),
                        fill=rgba(color, alpha),
                        outline=rgba(color, min(1.0, f / 8)),
                        width=max(1, self.canvas.px(2)),
                    )
            x = x0
            consumed = 0
            for tok, role in json_tokens(full):
                if consumed >= len(ln):
                    break
                part = tok[: len(ln) - consumed]
                consumed += len(part)
                color = JSON_COLORS[role]
                for r, f in active:
                    if f >= 8 and r.get("match") and str(r["match"]) in full:
                        a, b, _ = find_spans(full, [r])[0]
                        tok_start = (x and round((x - x0) / cw)) or 0
                        if a <= tok_start < b:
                            color = r.get("color", "orange")
                d.text((x, y), part, font=self.font, fill=rgb(color))
                x += self.font.getlength(part)
        img.paste(layer, (0, 0), layer)
        return img


__all__ = [
    "PALETTE",
    "REF_H",
    "REF_W",
    "SAFE_X",
    "SAFE_Y",
    "Canvas",
    "CardSource",
    "Fonts",
    "FrameSource",
    "JsonSource",
    "OverlayRenderer",
    "Pointer",
    "SpanOverlay",
    "TableSource",
    "TerminalSource",
    "TextOverlay",
    "blend_rgba",
    "draw_panel",
    "is_color",
    "make_background",
    "make_overlay",
    "paint_panel_v2",
    "rgb",
    "rgba",
]
