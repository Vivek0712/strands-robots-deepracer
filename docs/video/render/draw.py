"""Pure-PIL drawing for the demo video renderer.

Every frame of a card, terminal, table or JSON shot, and every text or pointer
overlay on top of a clip or still, is drawn here with Pillow in a 1920x1080
reference coordinate space. A Canvas carries the scale factor so the same shot
list renders at draft size (960x540) or full size without any change to the
numbers a writer typed. Nothing in this module talks to ffmpeg or the network.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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


def is_color(c: Any) -> bool:
    try:
        rgba(c)
        return True
    except (ValueError, TypeError, IndexError):
        return False


# --------------------------------------------------------------------------- fonts


@dataclass
class Fonts:
    """Resolved font files. A spec is ``path`` or ``path:index`` for .ttc collections."""

    sans: str
    sans_bold: str
    mono: str
    sans_medium: str = ""
    sans_medium_italic: str = ""
    mono_bold: str = ""

    @classmethod
    def resolve(cls, sans: str | None = None, sans_bold: str | None = None, mono: str | None = None) -> Fonts:
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
        )

    def get(self, kind: str, size: int) -> ImageFont.FreeTypeFont:
        fallback = {"sans_medium": "sans_bold", "sans_medium_italic": "sans_bold", "mono_bold": "mono"}
        spec = getattr(self, kind, "") or getattr(self, fallback.get(kind, "sans"))
        return _load_font(spec, max(4, int(size)))


@lru_cache(maxsize=256)
def _load_font(spec: str, size: int) -> ImageFont.FreeTypeFont:
    path, _, idx = spec.rpartition(":")
    if not path or not idx.isdigit():
        path, idx = spec, "0"
    font = ImageFont.truetype(path, size, index=int(idx))
    return font


# --------------------------------------------------------------------------- canvas


@dataclass
class Canvas:
    """Output size plus fonts; converts reference (1920x1080) units to pixels."""

    width: int
    height: int
    fonts: Fonts

    @property
    def s(self) -> float:
        return self.width / REF_W

    def px(self, v: float) -> int:
        return round(v * self.s)

    def pt(self, xy: Any) -> tuple[int, int]:
        return (self.px(float(xy[0])), self.px(float(xy[1])))

    def font(self, kind: str, size: float) -> ImageFont.FreeTypeFont:
        return self.fonts.get(kind, self.px(size))

    def scaled(self, factor: float) -> Canvas:
        return Canvas(max(2, round(self.width * factor)), max(2, round(self.height * factor)), self.fonts)

    def blank(self, color: Any = "bg") -> Image.Image:
        return Image.new("RGB", (self.width, self.height), rgb(color))

    def layer(self) -> Image.Image:
        return Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))


# --------------------------------------------------------------------------- easing / anim


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def smoothstep(x: float) -> float:
    x = clamp01(x)
    return x * x * (3 - 2 * x)


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
    bar = plate.get("bar")
    if bar:
        bw = canvas.px(float(bar.get("width", 2)))
        bx = canvas.px(float(bar["x"])) if "x" in bar else box[0]
        d.rectangle((bx, box[1], bx + bw - 1, box[3]), fill=rgba(bar.get("color", "orange"), alpha))


def ref_box(canvas: Canvas, box: Box) -> Box:
    """Canvas pixels back to 1920x1080 reference units."""
    return tuple(round(v / canvas.s) for v in box)  # type: ignore[return-value]


class TextOverlay:
    """One ``text`` entry of a shot. ``render(t)`` gives (RGBA block, x, y) or None."""

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.kind = str(spec.get("kind", "caption"))
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
        self.fade_out = FADE_OUT if "out" in spec else 0.0
        self.anim = str(spec.get("anim", "fade"))
        self.fade = float(spec.get("fade", FADE_IN if float(spec.get("in", 0.0)) > 0 else 0.0))
        self.cps = float(spec.get("cps", 40))
        self.width_ref = spec.get("width")
        self.leading = spec.get("leading")
        self.recolor = sorted((dict(r) for r in spec.get("recolor", [])), key=lambda r: float(r["at"]))
        self.count = spec.get("count")
        self.unit_size = float(spec.get("unit_size", self.size * 0.375))
        self.unit_color = spec.get("unit_color", "ink-dim")
        self.plate = _plate_spec(spec, self.kind)
        self.highlights = [dict(h) for h in spec.get("highlight", [])]
        self.spec = spec

    # ---- state
    def alpha(self, t: float) -> float:
        fade_in = 0.05 if self.anim == "typewriter" else (0.0 if self.anim == "none" else self.fade)
        return envelope(t, self.t_in, self.t_out, fade_in, self.fade_out)

    def visible_chars(self, t: float) -> int:
        if self.anim != "typewriter":
            return len(self.text)
        return min(len(self.text), int((t - self.t_in) * self.cps))

    def color_at(self, t: float) -> Any:
        color = self.color
        for r in self.recolor:
            if t >= float(r["at"]):
                color = r.get("color", color)
        return color

    def count_value(self, t: float) -> str | None:
        if not self.count:
            return None
        c = self.count
        lo, hi = float(c.get("from", 0)), float(c.get("to", 0))
        over = float(c.get("over", 1.0))
        u = smoothstep((t - self.t_in) / over) if over > 0 else 1.0
        v = lo + (hi - lo) * u
        dec = int(c.get("decimals", 0))
        return f"{v:.{dec}f}" if dec else f"{round(v)}"

    def slide(self, t: float) -> float:
        if self.anim in ("slide_up", "slide_left"):
            return 1 - smoothstep((t - self.t_in) / self.fade)
        return 0.0

    def highlight_levels(self, t: float) -> tuple[float, ...]:
        return tuple(smoothstep((t - float(h.get("at", self.t_in))) / 0.25) for h in self.highlights)

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        if a <= 0:
            return None
        hl = tuple(quantize(v, 16) for v in self.highlight_levels(t))
        return (
            quantize(a),
            self.visible_chars(t),
            self.color_at(t),
            self.count_value(t),
            quantize(self.slide(t), 32),
            hl,
        )

    def measure(self) -> dict[str, Any] | None:
        """Final-state text box and plate box in reference units, for the fit check."""
        t = self.t_in + 10.0
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
        if a < 1:
            out_img = out_img.copy()
            out_img.putalpha(out_img.getchannel("A").point(lambda v: int(v * a)))
        return out_img, ox, oy

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
        color = rgba(self.color_at(t))
        block, bw, bh = self._text_block(lines, font, line_h, color, num, self.highlight_levels(t))
        x, y = place_block(c, self.pos, bw, bh)
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
    ) -> tuple[Image.Image, int, int]:
        c = self.canvas
        if self.kind == "counter" and num is not None and lines and num in lines[0]:
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
        bw, bh = tw + 2, th
        block = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(block)
        spans: list[tuple[int, int, int, int, Any, float]] = []
        if self.highlights and self.align == "left":
            for h, lv in zip(self.highlights, hl_levels, strict=True):
                if lv <= 0:
                    continue
                for li, ln in enumerate(lines):
                    for a0, b0, col in find_spans(ln, [h]):
                        spans.append((li, a0, b0, 0, col, lv))
        for li, a0, b0, _, col, lv in spans:
            ln = lines[li]
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
        for li, a0, b0, _, col, lv in spans:
            if lv >= 1:
                ln = lines[li]
                d.text((1 + font.getlength(ln[:a0]), li * line_h), ln[a0:b0], font=font, fill=rgba(col))
        return block, bw, bh

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


class ChipsOverlay:
    """A row of chips (text on small plates), laid out left to right with a gap."""

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
        self.fade_out = FADE_OUT if "out" in spec else 0.0
        self.fade = float(spec.get("fade", FADE_IN if float(spec.get("in", 0.0)) > 0 else 0.0))
        self.anim = str(spec.get("anim", "fade"))

    def alpha(self, t: float) -> float:
        return envelope(t, self.t_in, self.t_out, self.fade, self.fade_out)

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        return None if a <= 0 else (quantize(a), quantize(smoothstep((t - self.t_in) / self.fade), 32))

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

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        c = self.canvas
        font, pad, gap, h, widths, total = self._geometry()
        layer = Image.new("RGBA", (max(1, total), h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        x = 0
        asc = font.getmetrics()[0]
        for s, w in zip(self.items, widths, strict=True):
            rounded(
                d,
                (x, 0, x + w - 1, h - 1),
                c.px(self.radius),
                fill=rgba(self.plate_color, self.plate_alpha * a),
            )
            d.text((x + pad, (h - asc) / 2 - c.px(self.size) * 0.08), s, font=font, fill=rgba(self.color, a))
            x += w + gap
        px, py = c.pt(self.pos)
        if self.anim == "slide_left":
            px -= round((1 - smoothstep((t - self.t_in) / self.fade)) * c.px(24))
        return layer, px, py


class PanelOverlay:
    """A plain plate: ``box`` [x0, y0, x1, y1], colour, alpha, radius, optional left bar."""

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
        self.fade_out = FADE_OUT if "out" in spec else 0.0
        self.fade = float(spec.get("fade", FADE_IN if float(spec.get("in", 0.0)) > 0 else 0.0))
        self.anim = str(spec.get("anim", "fade"))

    def alpha(self, t: float) -> float:
        return envelope(t, self.t_in, self.t_out, self.fade, self.fade_out)

    def measure(self) -> dict[str, Any] | None:
        return None

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        return None if a <= 0 else (quantize(a), quantize(smoothstep((t - self.t_in) / self.fade), 32))

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        c = self.canvas
        x0, y0 = c.pt(self.box[:2])
        x1, y1 = c.pt(self.box[2:])
        layer = Image.new("RGBA", (max(1, x1 - x0 + 1), max(1, y1 - y0 + 1)), (0, 0, 0, 0))
        plate = dict(self.plate)
        if plate.get("bar") and "x" in plate["bar"]:
            plate["bar"] = {**plate["bar"], "x": float(plate["bar"]["x"]) - float(self.box[0])}
        draw_plate(layer, c, (0, 0, x1 - x0, y1 - y0), plate, a)
        if self.anim == "slide_left":
            x0 -= round((1 - smoothstep((t - self.t_in) / self.fade)) * c.px(24))
        return layer, x0, y0


class ImageOverlay:
    """An image (png/jpg/svg) fitted inside ``box`` with an optional soft coloured glow."""

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float, loader: Any = None):
        self.canvas = canvas
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.fade_out = FADE_OUT if "out" in spec else 0.0
        self.fade = float(spec.get("fade", FADE_IN if float(spec.get("in", 0.0)) > 0 else 0.0))
        box = spec["box"]
        x0, y0 = canvas.pt(box[:2])
        x1, y1 = canvas.pt(box[2:])
        src = str(spec["src"])
        im = (loader(src) if loader else Image.open(src)).convert("RGBA")
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
    """Arrows, boxes, circles, highlights, brackets, bars, dotted rules and number badges.

    Drawn with 2x supersampling on a local patch so the edges are clean at any size.
    """

    DRAW_ON = 0.25

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.kind = str(spec.get("kind", "arrow"))
        self.a = canvas.pt(spec.get("from", [0, 0]))
        self.b = canvas.pt(spec.get("to", spec.get("from", [100, 100])))
        self.color = spec.get("color", "orange")
        default_w = {"highlight": 3, "box": 3, "dotted": 2, "bracket": 3}.get(self.kind, 4)
        self.width = max(1, canvas.px(float(spec.get("width", default_w))))
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.fade_out = FADE_OUT if "out" in spec else 0.0
        self.radius = float(spec.get("radius", 8))
        self.fill = spec.get("fill", 0.12 if self.kind == "highlight" else 0.0)
        self.pulse = spec.get("pulse")
        self.stages = [dict(s) for s in spec.get("stages", [])]
        self.grow = float(spec.get("grow", self.DRAW_ON))
        self.threshold_x = spec.get("threshold_x")
        self.color_after = spec.get("color_after")
        self.label = spec.get("label")
        self.r = float(spec.get("r", 18))
        self.ticks = float(spec.get("ticks", 10))
        self.dash = float(spec.get("dash", 6))
        self.spec = spec

    def alpha(self, t: float) -> float:
        if self.pulse:
            count = int(self.pulse.get("count", 2))
            period = float(self.pulse.get("period", 0.3))
            if t < self.t_in or t >= self.t_in + count * period:
                return 0.0
            return abs(math.sin(math.pi * (t - self.t_in) / period))
        return envelope(t, self.t_in, self.t_out, 0.08 if self.t_in > 0 else 0.0, self.fade_out)

    def progress(self, t: float) -> float:
        if self.t_in <= 0 and self.kind != "bar":
            return 1.0  # no `in`: the pointer is there from the first frame, no draw-on
        return smoothstep((t - self.t_in) / (self.grow if self.kind == "bar" else self.DRAW_ON))

    def target(self, t: float) -> tuple[float, float]:
        cur = (float(self.b[0]), float(self.b[1]))
        for st in self.stages:
            at = float(st["at"])
            if t < at:
                break
            nxt = self.canvas.pt(st["to"])
            q = smoothstep((t - at) / self.DRAW_ON)
            cur = (cur[0] + (nxt[0] - cur[0]) * q, cur[1] + (nxt[1] - cur[1]) * q)
        return cur

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        if a <= 0:
            return None
        return (quantize(a), quantize(self.progress(t), 48), tuple(int(v) for v in self.target(t)))

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        p = self.progress(t)
        (x1, y1), (x2, y2) = self.a, self.target(t)
        pad = self.width * 4 + self.canvas.px(self.r if self.kind == "badge" else 0) + 8
        left, top = int(min(x1, x2) - pad), int(min(y1, y2) - pad)
        right, bottom = int(max(x1, x2) + pad), int(max(y1, y2) + pad)
        ss = 2
        img = Image.new("RGBA", ((right - left) * ss, (bottom - top) * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        col = rgba(self.color, a)
        w = max(1, self.width * ss)
        ax, ay = (x1 - left) * ss, (y1 - top) * ss
        bx, by = (x2 - left) * ss, (y2 - top) * ss
        c = self.canvas
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
                f = c.font("sans_bold", float(self.spec.get("size", 22)) * ss)
                lw = f.getlength(str(self.label))
                asc = f.getmetrics()[0]
                d.text((ax - lw / 2, ay - asc * 0.56), str(self.label), font=f, fill=rgba("white", a))
        img = img.resize((right - left, bottom - top), Image.Resampling.LANCZOS)
        return img, left, top


def make_overlay(spec: dict[str, Any], canvas: Canvas, shot_duration: float, loader: Any = None) -> Any:
    kind = str(spec.get("kind", "caption"))
    if kind == "chips":
        return ChipsOverlay(spec, canvas, shot_duration)
    if kind == "panel":
        return PanelOverlay(spec, canvas, shot_duration)
    if kind == "image":
        return ImageOverlay(spec, canvas, shot_duration, loader)
    return TextOverlay(spec, canvas, shot_duration)


class OverlayRenderer:
    """All text overlays and pointers of a shot, composited into one RGBA layer per frame."""

    def __init__(
        self,
        canvas: Canvas,
        texts: list[dict[str, Any]],
        pointers: list[dict[str, Any]],
        shot_duration: float,
        captions: list[tuple[float, float, str]] | None = None,
        loader: Any = None,
    ):
        self.canvas = canvas
        self.items: list[Any] = [Pointer(p, canvas, shot_duration) for p in pointers]
        self.items += [make_overlay(s, canvas, shot_duration, loader) for s in texts]
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
            self.items.append(TextOverlay(spec, canvas, shot_duration))

    def key(self, t: float) -> Any:
        return tuple(it.key(t) for it in self.items)

    def layer(self, t: float) -> Image.Image | None:
        parts = [it.render(t) for it in self.items]
        parts = [p for p in parts if p is not None]
        if not parts:
            return None
        layer = self.canvas.layer()
        for block, x, y in parts:
            layer.alpha_composite(block, (int(x), int(y)))
        return layer


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
    import numpy as np

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


class TerminalSource(FrameSource):
    """Typewriter terminal.

    Lines type at ``cps``; ``schedule`` holds a line back until its time (the cursor waits);
    the first ``pre`` lines are shown dim from frame 0; ``chrome: false`` drops the window
    frame and places the text at ``pos``; ``highlight`` entries ``{match, color}`` colour a
    substring, and with ``at`` they also draw a timed highlight box computed from the font.
    """

    def __init__(self, canvas: Canvas, params: dict[str, Any], duration: float, base_dir: Path | None = None):
        self.canvas = canvas
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
        self.base = make_background(canvas, params.get("bg", "bg"))
        if self.chrome:
            self.box = panel_box(canvas, params)
            self.inner = draw_panel(self.base, canvas, self.box, self.title)
        elif "frame" in params:
            self.inner = panel_box(canvas, params)
        else:
            x, y = canvas.pt(params.get("pos", [SAFE_X, SAFE_Y]))
            w = (
                canvas.px(float(params["width"]))
                if "width" in params
                else canvas.width - canvas.px(SAFE_X) - x
            )
            self.inner = (x, y, min(canvas.width, x + w), canvas.height - canvas.px(SAFE_Y))
        self.font = canvas.font(params.get("font", "mono"), self.size)
        if "leading" in params:
            self.line_h = canvas.px(float(params["leading"]))
        else:
            self.line_h = round(canvas.px(self.size) * 1.5)
        pause = float(params.get("line_pause", 0.12))
        schedule = {int(e["line"]): float(e["at"]) for e in params.get("schedule", [])}
        t = self.delay
        self.starts: list[float] = []
        for i, ln in enumerate(self.lines):
            if i < self.pre:
                self.starts.append(-1.0)
                continue
            if i in schedule:
                t = max(t, schedule[i])
            self.starts.append(t)
            t += len(ln) / self.cps + pause
        self.done_at = t
        self.prompt_color = params.get("prompt_color", "green")

    def hl_levels(self, t: float) -> tuple[float, ...]:
        return tuple(smoothstep((t - float(h["at"])) / 0.25) if "at" in h else 1.0 for h in self.highlights)

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
                out.append((i, min(len(ln), int((t - st) * self.cps))))
            else:
                break
        return out, t >= self.done_at

    def key(self, t: float) -> Any:
        shown, done = self._state(t)
        cursor_on = self.show_cursor and not done and int(t * 2.2) % 2 == 0
        return (tuple(shown), cursor_on, tuple(quantize(v, 16) for v in self.hl_levels(t)))

    def _applies(self, h: dict[str, Any], i: int) -> bool:
        return h.get("line") is None or int(h["line"]) == i

    def frame(self, t: float) -> Image.Image:
        shown, done = self._state(t)
        cursor_on = self.show_cursor and not done and int(t * 2.2) % 2 == 0
        levels = self.hl_levels(t)
        img = self.base.copy().convert("RGBA")
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = self.inner
        max_lines = max(1, (y1 - y0) // self.line_h)
        visible = shown[-max_lines:]
        cw = self.font.getlength("M")
        max_cols = max(8, int((x1 - x0) // cw))
        c = self.canvas
        y = y0
        for k, (i, n) in enumerate(visible):
            full = self.lines[i]
            base_color = self.pre_color if self.starts[i] < 0 else self.color
            active = [
                h for h, lv in zip(self.highlights, levels, strict=True) if lv >= 1 and self._applies(h, i)
            ]
            for h, lv in zip(self.highlights, levels, strict=True):
                if "at" not in h or lv <= 0 or not self._applies(h, i):
                    continue
                for a0, b0, col in find_spans(full[:n], [h]):
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
            for seg_text, color in segments_for(full, active):
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
                d.rectangle(
                    (cx, y + self.line_h * 0.12, cx + cw * 0.9, y + self.line_h * 0.88), fill=rgb(self.color)
                )
            y += self.line_h
        if not shown and cursor_on:
            d.rectangle(
                (x0, y0 + self.line_h * 0.12, x0 + cw * 0.9, y0 + self.line_h * 0.88), fill=rgb(self.color)
            )
        return img.convert("RGB")


class TableSource(FrameSource):
    """Rows revealed one at a time every ``row_every`` seconds, optional highlighted row."""

    def __init__(self, canvas: Canvas, params: dict[str, Any], duration: float):
        self.canvas = canvas
        self.rows = [[str(c) for c in r] for r in params.get("rows", [])]
        self.header = bool(params.get("header", True))
        self.row_every = float(params.get("row_every", 0.6))
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
        age = t - (self.delay + (n - 1) * self.row_every) if n else 0.0
        hl = tuple(quantize((t - float(h.get("at", -1.0))) / 0.25, 8) for h in self.highlight)
        return (n, quantize(age / 0.25, 8), hl)

    def frame(self, t: float) -> Image.Image:
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
    "TableSource",
    "TerminalSource",
    "TextOverlay",
    "draw_panel",
    "is_color",
    "make_background",
    "make_overlay",
    "rgb",
    "rgba",
]
