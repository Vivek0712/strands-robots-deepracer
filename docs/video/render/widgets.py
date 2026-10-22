"""Motion-design widgets for the demo video renderer: spotlight, bar, rail, code panel.

Overlays here follow the ``render(t) -> (RGBA, x, y) | None`` / ``key(t)`` / ``measure()``
contract of ``draw.TextOverlay``; ``CodeSource`` is a ``FrameSource`` like the terminal.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import draw
from .draw import Canvas, clamp01, ease, eased_progress, quantize, rgb, rgba, smoothstep

# --------------------------------------------------------------------------- spotlight


def _lerp_box(a: list[float], b: list[float], u: float) -> list[float]:
    return [a[i] + (b[i] - a[i]) * u for i in range(4)]


class SpotlightOverlay:
    """Dims everything except a feathered rect or circle; the window moves between ``moves``.

    ``{kind: spotlight, shape: rect|circle, box: [x0, y0, x1, y1] (or center: [cx, cy], r),
    feather: 60, dim: 0.7, radius: 16, in, out, ease, moves: [{at, box|center+r, over_ms, ease}]}``.
    Moves default to ``ease_in_out`` (a position change reads better with a soft start).
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.shape = str(spec.get("shape", "rect"))
        self.feather = float(spec.get("feather", 60))
        self.dim = float(spec.get("dim", 0.7))
        self.radius = float(spec.get("radius", 16))
        # v4: a stack of regions, each with its own fade in and out; the viewer sees their union.
        # `lift: [{at, dim, over_ms}]` tweens the outside darkness (0.6 = outside at 40 percent).
        self.regions = [dict(r) for r in spec.get("regions", []) or []]
        self.lifts = sorted((dict(r) for r in spec.get("lift", []) or []), key=lambda r: float(r["at"]))
        if self.regions and "in" not in spec:
            spec = {**spec, "in": min(float(r.get("at", 0.0)) for r in self.regions)}
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.fade = (
            float(spec.get("anim_ms", 400)) / 1000.0 if "anim_ms" in spec else float(spec.get("fade", 0.4))
        )
        self.fade_out = float(spec.get("out_ms", 300)) / 1000.0 if "out" in spec or "out_ms" in spec else 0.0
        self.ease = canvas.curve(spec, legacy=False)
        self.move_ease = spec.get("ease") or canvas.ease or "ease_in_out"
        self.boxes: list[tuple[float, list[float], float, str]] = [
            (self.t_in, self._box(spec) if self._has_box(spec) else [0, 0, 0, 0], 0.0, self.ease)
        ]
        for mv in spec.get("moves", []) or []:
            self.boxes.append(
                (
                    float(mv["at"]),
                    self._box(mv) if ("box" in mv or "center" in mv) else self.boxes[-1][1],
                    float(mv.get("over_ms", 600)) / 1000.0,
                    str(mv.get("ease", self.move_ease)),
                )
            )
        self.boxes.sort(key=lambda b: b[0])

    @staticmethod
    def _has_box(spec: dict[str, Any]) -> bool:
        return "box" in spec or "center" in spec

    @staticmethod
    def _box(spec: dict[str, Any]) -> list[float]:
        if "box" in spec:
            return [float(v) for v in spec["box"]]
        cx, cy = (float(v) for v in spec["center"])
        rx = float(spec.get("rx", spec.get("r", 200)))
        ry = float(spec.get("ry", spec.get("r", 200)))
        return [cx - rx, cy - ry, cx + rx, cy + ry]

    def dim_at(self, t: float) -> float:
        d = self.dim
        for lf in self.lifts:
            at = float(lf["at"])
            if t < at:
                break
            u = eased_progress(t, at, float(lf.get("over_ms", 480)) / 1000.0, str(lf.get("ease", "move")))
            d = d + (float(lf.get("dim", 0.0)) - d) * u
        return d

    def region_levels(self, t: float) -> tuple[float, ...]:
        out = []
        for r in self.regions:
            at = float(r.get("at", self.t_in))
            lv = eased_progress(t, at, float(r.get("fade_ms", 480)) / 1000.0, str(r.get("ease", self.ease)))
            if r.get("out") is not None and t >= float(r["out"]) - float(r.get("out_ms", 480)) / 1000.0:
                lv *= 1.0 - eased_progress(
                    t,
                    float(r["out"]) - float(r.get("out_ms", 480)) / 1000.0,
                    float(r.get("out_ms", 480)) / 1000.0,
                    str(r.get("ease", self.ease)),
                )
            out.append(clamp01(lv))
        return tuple(out)

    def box_at(self, t: float) -> list[float]:
        cur = self.boxes[0][1]
        for i in range(1, len(self.boxes)):
            at, box, over, curve = self.boxes[i]
            if t < at:
                break
            u = eased_progress(t, at, over, curve)
            cur = _lerp_box(cur, box, u)
        return cur

    def alpha(self, t: float) -> float:
        if t < self.t_in or t >= self.t_out:
            return 0.0
        a_in = eased_progress(t, self.t_in, self.fade, self.ease)
        a_out = 1.0 if self.fade_out <= 0 else ease(self.ease, (self.t_out - t) / self.fade_out)
        return min(1.0, a_in, a_out)

    def measure(self) -> dict[str, Any] | None:
        return None

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        if a <= 0:
            return None
        if self.regions:
            levels = self.region_levels(t)
            if max(levels, default=0.0) <= 0:
                return None
            return (quantize(a), quantize(self.dim_at(t)), tuple(quantize(v, 32) for v in levels))
        return (quantize(a), tuple(round(v / 2) for v in self.box_at(t)))

    def _mask(self, c: Canvas, box: list[float], shape: str) -> np.ndarray:
        x0, y0 = c.pt(box[:2])
        x1, y1 = c.pt(box[2:])
        mask = Image.new("L", (c.width, c.height), 0)
        d = ImageDraw.Draw(mask)
        if shape in ("circle", "ellipse"):
            d.ellipse((x0, y0, x1, y1), fill=255)
        else:
            d.rounded_rectangle((x0, y0, x1, y1), radius=c.px(self.radius), fill=255)
        f = c.px(self.feather)
        if f > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(f / 2.5))
        return np.asarray(mask, dtype=np.float32)

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        c = self.canvas
        if self.regions:
            keep = np.zeros((c.height, c.width), dtype=np.float32)
            for r, lv in zip(self.regions, self.region_levels(t), strict=True):
                if lv <= 0:
                    continue
                keep = np.maximum(keep, self._mask(c, self._box(r), str(r.get("shape", self.shape))) * lv)
            # no region active (between stops, after a lift): the mask is gone, not a flat dim
            dim = self.dim_at(t) * max(self.region_levels(t), default=0.0)
            alpha = ((255.0 - keep) * (dim * a)).clip(0, 255).astype(np.uint8)
            layer = Image.new("RGBA", (c.width, c.height), (0, 0, 0, 0))
            layer.putalpha(Image.fromarray(alpha, "L"))
            return layer, 0, 0
        arr = self._mask(c, self.box_at(t), self.shape)
        alpha = ((255.0 - arr) * (self.dim * a)).clip(0, 255).astype(np.uint8)
        layer = Image.new("RGBA", (c.width, c.height), (0, 0, 0, 0))
        layer.putalpha(Image.fromarray(alpha, "L"))
        return layer, 0, 0


# --------------------------------------------------------------------------- bar


class BarOverlay:
    """A horizontal bar that grows to ``value`` with easing and a count-up label.

    ``{kind: bar, box: [x0, y0, x1, y1], value: 0.91, max: 1.0, color: green, track: panel_border,
    radius: 4, label: "{v:.2f}", label_pos: end|follow|none, label_size: 28, label_color: ink,
    marker: 0.65, marker_color: ink-dim, over_ms: 800, in, ease, glow}``.
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.box = [float(v) for v in spec["box"]]
        self.value = float(spec.get("value", 1.0))
        self.max = float(spec.get("max", 1.0)) or 1.0
        self.color = spec.get("color", "green")
        self.track = spec.get("track", "panel_border")
        self.track_alpha = float(spec.get("track_alpha", 1.0))
        self.radius = float(spec.get("radius", 4))
        self.label = spec.get("label", "{v:.2f}")
        self.label_pos = str(spec.get("label_pos", "end"))
        self.label_size = float(spec.get("label_size", 28))
        self.label_color = spec.get("label_color", "ink")
        self.label_font = spec.get("font", "mono")
        self.marker = spec.get("marker")
        self.marker_color = spec.get("marker_color", "ink-dim")
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.over = float(spec.get("over_ms", 800)) / 1000.0
        self.fade_out = 0.3 if "out" in spec else 0.0
        self.ease = canvas.curve(spec, legacy=False)
        self.glow = draw.glow_spec(spec, canvas)
        self.gap = float(spec.get("label_gap", 14))

    def p(self, t: float) -> float:
        return eased_progress(t, self.t_in, self.over, self.ease)

    def alpha(self, t: float) -> float:
        if t < self.t_in or t >= self.t_out:
            return 0.0
        a = min(1.0, eased_progress(t, self.t_in, 0.25, self.ease))
        if self.fade_out > 0:
            a = min(a, smoothstep((self.t_out - t) / self.fade_out))
        return a

    def _label_text(self, p: float) -> str:
        v = self.value * min(1.0, p)
        try:
            return str(self.label).format(v=v, n=v, pct=v / self.max * 100)
        except (KeyError, IndexError, ValueError):
            return str(self.label)

    def _geom(self) -> tuple[int, int, int, int, Any, int]:
        c = self.canvas
        x0, y0 = c.pt(self.box[:2])
        x1, y1 = c.pt(self.box[2:])
        font = c.font(self.label_font, self.label_size)
        lw = math.ceil(font.getlength(self._label_text(1.0)))
        return x0, y0, x1, y1, font, lw

    def measure(self) -> dict[str, Any] | None:
        x0, y0, x1, y1, _font, lw = self._geom()
        right = x1 + (self.canvas.px(self.gap) + lw if self.label_pos != "none" else 0)
        return {"text": draw.ref_box(self.canvas, (x0, y0, right, y1))}

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        if a <= 0:
            return None
        extra = (
            (round(draw.glow_strength(self.glow, t) * 64),) if self.glow and self.glow.get("pulse") else ()
        )
        return (quantize(a), round(self.p(t) * 1024), *extra)

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        c = self.canvas
        x0, y0, x1, y1, font, lw = self._geom()
        p = self.p(t)
        pad = c.px(8)
        w = (x1 - x0) + pad * 2 + (c.px(self.gap) + lw + pad if self.label_pos != "none" else 0)
        h = (y1 - y0) + pad * 2 + c.px(self.label_size)
        layer = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        bx0, by0, bx1, by1 = (
            pad,
            pad + c.px(self.label_size) // 2,
            pad + (x1 - x0),
            pad + c.px(self.label_size) // 2 + (y1 - y0),
        )
        r = c.px(self.radius)
        d.rounded_rectangle((bx0, by0, bx1, by1), radius=r, fill=rgba(self.track, self.track_alpha * a))
        fill_w = (bx1 - bx0) * min(1.0, max(0.0, p * self.value / self.max))
        if fill_w >= 1:
            d.rounded_rectangle((bx0, by0, bx0 + fill_w, by1), radius=r, fill=rgba(self.color, a))
        if self.marker is not None:
            mx = bx0 + (bx1 - bx0) * float(self.marker) / self.max
            d.line(
                (mx, by0 - c.px(6), mx, by1 + c.px(6)), fill=rgba(self.marker_color, a), width=max(1, c.px(2))
            )
        if self.label_pos != "none":
            text = self._label_text(p)
            asc = font.getmetrics()[0]
            ty = (by0 + by1) / 2 - asc * 0.62
            if self.label_pos == "follow":
                tx = bx0 + fill_w + c.px(self.gap)
            else:
                tx = bx1 + c.px(self.gap)
            d.text((tx, ty), text, font=font, fill=rgba(self.label_color, a))
        return layer, x0 - pad, y0 - pad - c.px(self.label_size) // 2

    def glow_part(self, t: float, rendered: tuple[Image.Image, int, int] | None) -> Any:
        if not self.glow or rendered is None:
            return None
        img, x, y = rendered
        g = self.glow
        m = g["margin"]
        big = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
        big.alpha_composite(img, (m, m))
        return draw.glow_layer(big, g["color"], g["radius"], draw.glow_strength(g, t)), x - m, y - m


# --------------------------------------------------------------------------- rail


class RailOverlay:
    """Chapter progress rail: ``n`` segments, the ``active`` one fills with easing and glows.

    ``{kind: rail, n: 7, active: 3, pos: bottom|top, labels: [...], color: orange,
    dim_color: panel_border, width: 1200, gap: 10, thickness: 4, fill_ms: 600, in, ease,
    label_size: 20, margin: 36}``. ``active`` is 1-based; segments before it are lit at 55 percent.
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.n = max(1, int(spec.get("n", 7)))
        self.active = int(spec.get("active", 1))
        self.pos = str(spec.get("pos", "bottom"))
        self.labels = [str(v) for v in spec.get("labels", [])]
        self.color = spec.get("color", "orange")
        self.dim_color = spec.get("dim_color", "panel_border")
        self.width = float(spec.get("width", 1200))
        self.gap = float(spec.get("gap", 10))
        self.thickness = float(spec.get("thickness", 4))
        self.margin = float(spec.get("margin", 36))
        self.label_size = float(spec.get("label_size", 20))
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.fill = float(spec.get("fill_ms", 600)) / 1000.0
        self.ease = canvas.curve(spec, legacy=False)
        self.glow_on = bool(spec.get("glow", True))
        self.fade_out = 0.3 if "out" in spec else 0.0

    def alpha(self, t: float) -> float:
        if t < self.t_in or t >= self.t_out:
            return 0.0
        a = min(1.0, eased_progress(t, self.t_in, 0.3, self.ease))
        if self.fade_out > 0:
            a = min(a, smoothstep((self.t_out - t) / self.fade_out))
        return a

    def p(self, t: float) -> float:
        return min(1.0, eased_progress(t, self.t_in, self.fill, self.ease))

    def measure(self) -> dict[str, Any] | None:
        return None

    def key(self, t: float) -> Any:
        a = self.alpha(t)
        return None if a <= 0 else (quantize(a), round(self.p(t) * 512))

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        a = self.alpha(t)
        if a <= 0:
            return None
        c = self.canvas
        W = c.px(self.width)
        gap, th = c.px(self.gap), max(1, c.px(self.thickness))
        seg_w = (W - gap * (self.n - 1)) / self.n
        label_h = c.px(self.label_size) + c.px(8) if self.labels else 0
        glow_m = c.px(12)
        H = th + label_h + 2 * glow_m
        layer = Image.new("RGBA", (W + 2 * glow_m, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        bar_y = glow_m + (label_h if self.pos == "bottom" else 0)
        p = self.p(t)
        font = c.font("sans", self.label_size)
        for i in range(self.n):
            x0 = glow_m + i * (seg_w + gap)
            x1 = x0 + seg_w
            idx = i + 1
            if idx < self.active:
                col = rgba(self.color, 0.55 * a)
            elif idx == self.active:
                col = rgba(self.dim_color, a)
            else:
                col = rgba(self.dim_color, a)
            d.rounded_rectangle((x0, bar_y, x1, bar_y + th), radius=th // 2, fill=col)
            if idx == self.active and p > 0:
                d.rounded_rectangle(
                    (x0, bar_y, x0 + seg_w * p, bar_y + th), radius=th // 2, fill=rgba(self.color, a)
                )
            if i < len(self.labels):
                lab = self.labels[i]
                lw = font.getlength(lab)
                lx = x0 + seg_w / 2 - lw / 2
                ly = glow_m if self.pos == "bottom" else bar_y + th + c.px(8)
                lcol = rgba("ink", a) if idx == self.active else rgba("ink-dim", 0.8 * a)
                d.text((lx, ly), lab, font=font, fill=lcol)
        if self.glow_on and p > 0:
            i = self.active - 1
            x0 = glow_m + i * (seg_w + gap)
            g = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            ImageDraw.Draw(g).rounded_rectangle(
                (x0, bar_y, x0 + seg_w * p, bar_y + th), radius=th // 2, fill=rgba(self.color, 0.9 * a)
            )
            g = g.filter(ImageFilter.GaussianBlur(c.px(8)))
            layer = Image.alpha_composite(g, layer)
        x = (c.width - W) // 2 - glow_m
        y = c.height - c.px(self.margin) - H + glow_m if self.pos == "bottom" else c.px(self.margin) - glow_m
        return layer, x, y


# --------------------------------------------------------------------------- bloom (the LED)


class BloomOverlay:
    """An additive coloured disc that pulses: the LED bloom of DESIGN section 5.

    ``{kind: bloom, center: [x, y], r: 24, color: red, alpha_peak: 0.6, alpha_floor: 0.15,
    pulses: 2, period_ms: 330, in, out}``. Each pulse eases from the peak to the floor over
    one period; after the last pulse the bloom holds at the floor until ``out``.
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.center = canvas.pt(spec["center"])
        self.r = canvas.px(float(spec.get("r", 24)))
        self.color = spec.get("color", "red")
        self.peak = float(spec.get("alpha_peak", 0.6))
        self.floor = float(spec.get("alpha_floor", 0.15))
        self.pulses = int(spec.get("pulses", 2))
        self.period = float(spec.get("period_ms", 330)) / 1000.0
        self.t_in = float(spec.get("in", 0.0))
        self.t_out = float(spec.get("out", shot_duration))
        self.fade_out = float(spec.get("out_ms", 240)) / 1000.0 if "out" in spec else 0.0
        self.ease = canvas.curve(spec, legacy=False)

    def level(self, t: float) -> float:
        if t < self.t_in or t >= self.t_out:
            return 0.0
        u = t - self.t_in
        if self.period > 0 and u < self.pulses * self.period:
            phase = (u % self.period) / self.period
            k = self.floor + (self.peak - self.floor) * (1.0 - ease(self.ease, phase))
        else:
            k = self.floor
        if self.fade_out > 0:
            k *= smoothstep((self.t_out - t) / self.fade_out)
        return k

    def measure(self) -> dict[str, Any] | None:
        return None

    def key(self, t: float) -> Any:
        k = self.level(t)
        return None if k <= 0 else quantize(k, 128)

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        if self.level(t) <= 0:
            return None
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), self.center[0], self.center[1]

    def glow_part(self, t: float, rendered: Any) -> Any:
        k = self.level(t)
        if k <= 0:
            return None
        m = self.r * 3
        layer = Image.new("RGBA", (2 * m, 2 * m), (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse(
            (m - self.r, m - self.r, m + self.r, m + self.r), fill=rgba(self.color, k)
        )
        layer = layer.filter(ImageFilter.GaussianBlur(self.r / 1.5))
        return layer, self.center[0] - m, self.center[1] - m


# --------------------------------------------------------------------------- progress rail (global time)


class ProgressRailOverlay:
    """The 3 px chapter rail of DESIGN section 10, driven by the film's global time.

    ``{kind: progress_rail, segments: [[x0, x1], ...], chapters: [[t0, t1], ...] (global seconds),
    y: [0, 3], track_color: ink-mute, track_alpha: 0.35, fill_color: ink-dim, head_color: orange,
    head_px: 16, draw_on: {at: 1.06, ms: 720, ease: draw}}``. The renderer injects
    ``_global_start`` (the shot's start on the timeline) so the fill is right across every cut.
    """

    def __init__(self, spec: dict[str, Any], canvas: Canvas, shot_duration: float):
        self.canvas = canvas
        self.segments = [(float(a), float(b)) for a, b in spec["segments"]]
        self.chapters = [(float(a), float(b)) for a, b in spec["chapters"]]
        self.y = [float(v) for v in spec.get("y", [0, 3])]
        self.track_color = spec.get("track_color", "ink-mute")
        self.track_alpha = float(spec.get("track_alpha", 0.35))
        self.fill_color = spec.get("fill_color", "ink-dim")
        self.head_color = spec.get("head_color", "orange")
        self.head_px = float(spec.get("head_px", 16))
        d = spec.get("draw_on") or {}
        self.draw_at = float(d.get("at", 0.0))
        self.draw_ms = float(d.get("ms", 720)) / 1000.0
        self.draw_ease = str(d.get("ease", "draw"))
        self.g0 = float(spec.get("_global_start", 0.0))
        self.t_out = float(spec.get("out", shot_duration))

    def fill_x(self, T: float) -> float:
        """Fill position in reference px at global time ``T``."""
        x = 0.0
        for (x0, x1), (t0, t1) in zip(self.segments, self.chapters, strict=True):
            if T >= t1:
                x = x1
            elif T >= t0:
                return x0 + (x1 - x0) * (T - t0) / max(1e-6, t1 - t0)
            else:
                return x
        return x

    def track_w(self, T: float) -> float:
        return draw.REF_W * eased_progress(T, self.draw_at, self.draw_ms, self.draw_ease)

    def measure(self) -> dict[str, Any] | None:
        return None

    def key(self, t: float) -> Any:
        if t >= self.t_out:
            return None
        T = self.g0 + t
        tw = self.track_w(T)
        if tw <= 0:
            return None
        return (round(tw), round(self.fill_x(T)))

    def render(self, t: float) -> tuple[Image.Image, int, int] | None:
        if t >= self.t_out:
            return None
        c = self.canvas
        T = self.g0 + t
        tw = self.track_w(T)
        if tw <= 0:
            return None
        fx_ = min(self.fill_x(T), tw)
        y0, y1 = c.px(self.y[0]), max(c.px(self.y[0]) + 1, c.px(self.y[1]))
        layer = Image.new("RGBA", (c.width, y1 - y0), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for x0, x1 in self.segments:
            a, b = c.px(x0), c.px(min(x1, tw))
            if b <= a:
                continue
            d.rectangle((a, 0, b - 1, y1 - y0 - 1), fill=rgba(self.track_color, self.track_alpha))
            fb = c.px(min(x1, fx_))
            if fb > a:
                d.rectangle((a, 0, fb - 1, y1 - y0 - 1), fill=rgba(self.fill_color))
                if x0 <= fx_ < x1:
                    ha = max(a, fb - c.px(self.head_px))
                    d.rectangle((ha, 0, fb - 1, y1 - y0 - 1), fill=rgba(self.head_color))
        return layer, 0, y0


def make_widget(kind: str, spec: dict[str, Any], canvas: Canvas, shot_duration: float) -> Any:
    if kind == "spotlight":
        return SpotlightOverlay(spec, canvas, shot_duration)
    if kind == "bar":
        return BarOverlay(spec, canvas, shot_duration)
    if kind == "rail":
        return RailOverlay(spec, canvas, shot_duration)
    if kind == "bloom":
        return BloomOverlay(spec, canvas, shot_duration)
    if kind == "progress_rail":
        return ProgressRailOverlay(spec, canvas, shot_duration)
    raise ValueError(f"unknown widget {kind!r}")


# --------------------------------------------------------------------------- code panel

PY_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in",
    "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "match", "case",
}  # fmt: skip
PY_BUILTINS = {
    "print", "len", "range", "int", "float", "str", "list", "dict", "set", "tuple", "isinstance", "super",
    "self", "cls", "open", "min", "max", "abs", "round", "enumerate", "zip", "any", "all", "bool", "type",
}  # fmt: skip
_PY_TOKEN = re.compile(
    r"(#.*$)"  # 1 comment
    r"|(\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\"(?:[^\"\\\\]|\\\\.)*\"|'(?:[^'\\\\]|\\\\.)*')"  # 2 string
    r"|(@\w[\w.]*)"  # 3 decorator
    r"|\b(\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|0x[0-9a-fA-F]+)\b"  # 4 number
    r"|\b(def|class)\s+(\w+)"  # 5 keyword + 6 name
    r"|\b([A-Za-z_]\w*)\b",  # 7 identifier
    re.MULTILINE,
)
CODE_COLORS = {
    "comment": "muted",
    "string": "green",
    "decorator": "amber",
    "number": "orange",
    "keyword": "violet",
    "name": "cyan",
    "builtin": "cyan",
    "plain": "ink",
}


def python_tokens(line: str) -> list[tuple[str, str]]:
    """Split one line of Python into (text, role) pieces for colouring."""
    out: list[tuple[str, str]] = []
    pos = 0
    for m in _PY_TOKEN.finditer(line):
        if m.start() > pos:
            out.append((line[pos : m.start()], "plain"))
        if m.group(1):
            out.append((m.group(1), "comment"))
        elif m.group(2):
            out.append((m.group(2), "string"))
        elif m.group(3):
            out.append((m.group(3), "decorator"))
        elif m.group(4):
            out.append((m.group(4), "number"))
        elif m.group(5):
            out.append((m.group(5), "keyword"))
            out.append((line[m.end(5) : m.start(6)], "plain"))
            out.append((m.group(6), "name"))
        else:
            ident = m.group(7)
            role = "keyword" if ident in PY_KEYWORDS else ("builtin" if ident in PY_BUILTINS else "plain")
            out.append((ident, role))
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], "plain"))
    return out


class CodeSource(draw.FrameSource):
    """Code editor panel: title bar, line numbers, Python colours, a thin accent gutter and
    highlighted line ranges that fade in.

    ``{kind: code, src|lines|text, title: gate.py, size: 26, start_line: 1, numbers: true,
    lang: python, start: 0.3, stagger: 30, anim: rise, ease, accent: orange,
    highlight: [{lines: [12, 15], at: 1.5, color: orange}], frame, bg}``.
    """

    def __init__(self, canvas: Canvas, params: dict[str, Any], duration: float, base_dir: Path | None = None):
        self.canvas = canvas
        self.lines = draw.read_lines(params, base_dir)
        self.size = float(params.get("size", 26))
        self.title = params.get("title", "main.py")
        self.start_line = int(params.get("start_line", 1))
        self.numbers = bool(params.get("numbers", True))
        self.lang = str(params.get("lang", "python"))
        self.delay = float(params.get("start", 0.3))
        self.stagger = float(params.get("stagger", 30)) / 1000.0
        self.anim = str(params.get("anim", "rise"))
        self.line_ms = float(params.get("line_ms", 360)) / 1000.0
        self.ease = canvas.curve(params, legacy=False)
        self.accent = params.get("accent", "orange")
        self.highlights = [dict(h) for h in params.get("highlight", []) or []]
        for h in self.highlights:
            h.setdefault("color", self.accent)
            h.setdefault("at", self.delay + 0.6)
        self.box = draw.panel_box(canvas, params)
        self.base = draw.make_background(canvas, params.get("bg", "bg"))
        self.inner = draw.draw_panel(self.base, canvas, self.box, self.title)
        self.font = canvas.font(params.get("font", "mono"), self.size)
        self.line_h = (
            canvas.px(float(params["leading"])) if "leading" in params else round(canvas.px(self.size) * 1.55)
        )
        digits = len(str(self.start_line + len(self.lines)))
        self.cw = self.font.getlength("0")
        self.gutter = int(self.cw * (digits + 1) + canvas.px(20)) if self.numbers else canvas.px(12)
        d = ImageDraw.Draw(self.base)
        x0, y0, _x1, y1 = self.inner
        gx = x0 + self.gutter - canvas.px(10)
        d.rectangle(
            (gx, y0 - canvas.px(8), gx + max(1, canvas.px(2)), y1 + canvas.px(8)), fill=rgb("panel_border")
        )
        self.gx = gx

    def _line_p(self, t: float, i: int) -> float:
        return eased_progress(t, self.delay + i * self.stagger, self.line_ms, self.ease)

    def _hl_levels(self, t: float) -> tuple[float, ...]:
        return tuple(ease(self.ease, (t - float(h["at"])) / 0.4) for h in self.highlights)

    def key(self, t: float) -> Any:
        ps = tuple(round(self._line_p(t, i) * 256) for i in range(len(self.lines)))
        return (ps, tuple(round(v * 64) for v in self._hl_levels(t)))

    def _tokens(self, line: str) -> list[tuple[str, str]]:
        if self.lang == "python":
            return python_tokens(line)
        if self.lang == "json":
            return [
                (
                    tok,
                    {"key": "name", "str": "string", "num": "number", "punct": "plain", "plain": "plain"}[r],
                )
                for tok, r in draw.json_tokens(line)
            ]
        return [(line, "plain")]

    def frame(self, t: float) -> Image.Image:
        c = self.canvas
        img = self.base.copy().convert("RGBA")
        x0, y0, x1, y1 = self.inner
        max_lines = max(1, (y1 - y0) // self.line_h)
        levels = self._hl_levels(t)
        # highlighted ranges: a soft band plus an accent bar in the gutter
        for h, lv in zip(self.highlights, levels, strict=True):
            if lv <= 0:
                continue
            a, b = (int(v) for v in h["lines"])
            ia, ib = a - self.start_line, b - self.start_line
            if ib < 0 or ia >= max_lines:
                continue
            ya = y0 + max(0, ia) * self.line_h - c.px(4)
            yb = y0 + (min(max_lines - 1, ib) + 1) * self.line_h - c.px(2)
            band = Image.new("RGBA", img.size, (0, 0, 0, 0))
            bd = ImageDraw.Draw(band)
            bd.rounded_rectangle(
                (x0 + self.gutter - c.px(4), ya, x1, yb), radius=c.px(6), fill=rgba(h["color"], 0.10 * lv)
            )
            bd.rectangle((self.gx - c.px(1), ya, self.gx + max(1, c.px(3)), yb), fill=rgba(h["color"], lv))
            img.alpha_composite(band)
        text_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(text_layer)
        for i, line in enumerate(self.lines[:max_lines]):
            p = self._line_p(t, i)
            if p <= 0:
                continue
            y = y0 + i * self.line_h
            dy = round((1 - min(1.0, p)) * c.px(draw.RISE_PX) * 0.5) if self.anim == "rise" else 0
            a = min(1.0, p) if self.anim != "none" else 1.0
            if self.numbers:
                num = str(self.start_line + i)
                nw = self.font.getlength(num)
                d.text((self.gx - c.px(18) - nw, y + dy), num, font=self.font, fill=rgba("muted", 0.8 * a))
            x = x0 + self.gutter
            in_hl = any(
                lv >= 1 and int(h["lines"][0]) <= self.start_line + i <= int(h["lines"][1])
                for h, lv in zip(self.highlights, levels, strict=True)
            )
            for tok, role in self._tokens(line):
                col = CODE_COLORS[role]
                if in_hl and role == "plain":
                    col = "ink"
                d.text((x, y + dy), tok, font=self.font, fill=rgba(col, a))
                x += self.font.getlength(tok)
        img.alpha_composite(text_layer)
        return img.convert("RGB")


__all__ = [
    "BarOverlay",
    "BloomOverlay",
    "CodeSource",
    "ProgressRailOverlay",
    "RailOverlay",
    "SpotlightOverlay",
    "make_widget",
    "python_tokens",
]
