"""Shot list to finished MP4 for the demo video renderer.

A shot list (YAML or JSON) is validated into Shot objects, voice-over lengths fix
the "auto" durations, and every shot is rendered to its own cached MP4 segment:
clips and stills are decoded by ffmpeg into raw frames, cards, terminals, tables
and JSON panels are drawn with Pillow, and text or pointer overlays are composited
on top in Python before the frames are piped back into ffmpeg (libx264). The
segments are joined with xfade transitions, the voice, clip audio and music are
mixed in numpy, loudness-normalised in two passes, and muxed into one file with
an .srt sidecar. The same shot list renders a 960x540 draft or the 1080p final.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import audio as audio_mod
from . import draw, fx, widgets

RENDER_VERSION = "4"
XFADE_NAMES = {
    "fade": "fade",
    "dip_to_black": "fadeblack",
    "dissolve": "dissolve",
    "wipeleft": "wipeleft",
    "wiperight": "wiperight",
    "slideleft": "slideleft",
    "slideright": "slideright",
    "fadegrays": "fadegrays",
}
KINDS = {"clip", "still", "card", "terminal", "table", "json", "split", "code"}
COMMON_KEYS = {
    "id", "kind", "duration", "min", "vo", "vo_offset", "text", "pointers", "transition", "notes",
    "black_in", "black_out", "black_ease",
}  # fmt: skip
KIND_KEYS: dict[str, set[str]] = {
    "clip": {
        "src",
        "start",
        "end",
        "speed",
        "fit",
        "zoom",
        "mute",
        "loop",
        "gain",
        "crop",
        "place",
        "fill",
        "fill_blur",
        "fill_brightness",
        "blend",
        "brightness",
        "subject_zoom",
        "drift",
    },
    "still": {
        "src",
        "fit",
        "zoom",
        "at",
        "crop",
        "place",
        "fill",
        "fill_blur",
        "fill_brightness",
        "brightness",
        "dim",
        "regions",
        "layers",
        "base_brightness",
        "camera",
        "subject_zoom",
        "drift",
    },
    "card": {"bg", "logo"},
    "terminal": {
        "src",
        "lines",
        "text",
        "cps",
        "start",
        "highlight",
        "title",
        "size",
        "frame",
        "bg",
        "line_pause",
        "prompt_color",
        "chrome",
        "pos",
        "width",
        "leading",
        "pre",
        "pre_color",
        "schedule",
        "line_range",
        "wrap",
        "wrap_indent",
        "cursor",
        "color",
        "font",
        "jitter",
        "seed",
        "pauses",
        "syntax",
        "cursor_hz",
        "cursor_style",
        "scanlines",
        "panel",
        "bottom",
        "cursor_hold",
        "cursor_hide_fast",
        "cursor_blink_ms",
        "cursor_w",
        "cursor_h",
        "fade_bottom",
    },
    "table": {
        "rows",
        "header",
        "row_every",
        "start",
        "highlight",
        "title",
        "size",
        "frame",
        "bg",
        "anim",
        "stagger",
        "ease",
        "row_ms",
    },
    "json": {"src", "data", "text", "cps", "start", "reveal", "title", "size", "frame", "bg", "line_pause"},
    "split": {"main", "pip", "left", "right", "gap"},
    "code": {
        "src",
        "lines",
        "text",
        "title",
        "size",
        "frame",
        "bg",
        "start_line",
        "numbers",
        "lang",
        "start",
        "stagger",
        "anim",
        "line_ms",
        "ease",
        "accent",
        "highlight",
        "font",
        "leading",
        "line_range",
    },
}
TEXT_KINDS = set(draw.OVERLAY_STYLE) | {"chips", "panel", "image"} | draw.WIDGET_KINDS
POINTER_KINDS = {
    "arrow", "box", "circle", "underline", "highlight", "bracket", "bar", "dotted", "badge", "line", "leader",
    "path", "node",
}  # fmt: skip
PANEL_ANIMS = {"grow_down", "grow_right", "rise", "fade", "slide_left"}
ANIMS = draw.ANIMS
TRANSITIONS = set(XFADE_NAMES) | fx.CUSTOM_TRANSITIONS
VIDEO_EXT = {".mp4", ".webm", ".mov", ".gif", ".mkv", ".m4v"}
POS_CODES = {"tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".svg"}


# --------------------------------------------------------------------------- settings


@dataclass
class Settings:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    draft: bool = False
    build_dir: Path = Path("docs/video/build")
    vo_cache: Path = Path("docs/video/build/vo")
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    fonts: draw.Fonts | None = None
    voice: str = "Matthew"
    engine: str = "generative"
    say_voice: str = "Samantha"
    aws_profile: str | None = "heisenberg"
    aws_region: str = "us-east-1"
    no_vo: bool = False
    music: Path | None = None
    music_level: float = -14.0
    duck_level: float = -22.0
    music_lufs: float | None = None
    duck_lufs: float | None = None
    music_crossfade: float = 2.0
    vo_rate: int | None = None  # SSML prosody rate in percent (neural honours it; generative ignores it)
    vo_breaks: int | None = None  # SSML <break> in ms after each sentence end (generative honours it)
    vo_sentences: bool = False  # one Polly call per sentence, stitched with vo_gap_ms; onsets measured
    vo_gap_ms: int = 600
    min_gap: float = 0.55  # every stitched sentence boundary must carry at least this much silence
    draft_vo: str = "say"  # "say" or "polly": which voice a --draft build uses
    burn_captions: bool = False
    fade_out: float = 0.6
    fade_in: float = 0.0  # global fade from black; the first shot's `transition: fade` still works
    auto_pad: float = 0.4
    ease: str | None = None  # default curve for every element; None keeps pre-v3 elements on smoothstep
    vignette: float = 0.0  # 0..1 edge darkening applied to every composed frame
    vignette_inner: float = 0.38  # radius (of the half-diagonal) inside which the vignette is zero
    rules: dict[str, Any] = field(default_factory=dict)  # v4 `check` rules: caption_zone, one_accent
    grain: float = 0.0  # luminance grain standard deviation as a fraction of full scale (0.04 is film-like)
    grain_seed: int = 7
    grain_size: float = 2.0  # px per grain clump (1 = per-pixel noise, costs many bits to encode)
    grain_cap: float = 16.0  # final-file rate cap in Mbit/s at 1080p while grain is on (0 = none)
    letterbox: float = 0.0  # 0 = no bars; an aspect ratio (2.39) or a bar height in px
    text_engine: str = "auto"  # raqm when Pillow has libraqm, else basic
    verbose: bool = True
    _post: Any = field(default=None, repr=False, compare=False)

    @property
    def canvas(self) -> draw.Canvas:
        return draw.Canvas(self.width, self.height, self.fonts or draw.Fonts.resolve(), self.ease)

    @property
    def segment_cap(self) -> float:
        """Segment rate cap (Mbit/s at 1080p): 3x the final cap while grain is on, else none."""
        return 3.0 * self.grain_cap if self.grain > 0 and self.grain_cap > 0 else 0.0

    @property
    def post(self) -> fx.Post:
        """The post pass for this output size (built once; the grain bank is a few MB)."""
        want = (
            self.width, self.height, self.vignette, self.grain, self.grain_seed, self.grain_size,
            self.vignette_inner,
        )  # fmt: skip
        if self._post is None or self._post[0] != want:
            self._post = (want, fx.Post(*want))
        return self._post[1]

    def log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)


def find_ffmpeg(name: str = "ffmpeg") -> str:
    for cand in (shutil.which(name), f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"):
        if cand and Path(cand).exists():
            return cand
    raise FileNotFoundError(f"{name} not found; install ffmpeg or pass --ffmpeg")


# --------------------------------------------------------------------------- shot list


@dataclass
class Shot:
    id: str
    kind: str
    duration: float | str
    vo: str | None
    vo_offset: float
    text: list[dict[str, Any]]
    pointers: list[dict[str, Any]]
    transition: dict[str, Any]
    params: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict)
    min_duration: float = 0.0
    black_in: float = 0.0
    black_out: float = 0.0


@dataclass
class ShotList:
    path: Path
    meta: dict[str, Any]
    shots: list[Shot]
    errors: list[str]
    warnings: list[str]

    @property
    def base_dir(self) -> Path:
        return Path(self.meta.get("base_dir", ".")).resolve()


def load_shot_list(path: Path) -> ShotList:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise SystemExit(
                "PyYAML is not installed; use a JSON shot list or `uv pip install pyyaml`"
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if isinstance(data, list):
        meta, raw_shots = {}, data
    elif isinstance(data, dict):
        meta = {k: v for k, v in data.items() if k != "shots"}
        raw_shots = data.get("shots", [])
    else:
        raise SystemExit("shot list must be a list of shots or a mapping with a `shots` key")
    errors: list[str] = []
    warnings: list[str] = []
    shots: list[Shot] = []
    defaults = dict(meta.get("defaults", {}))
    seen: set[str] = set()
    base_dir = Path(meta.get("base_dir", ".")).resolve()
    for i, raw in enumerate(raw_shots):
        shot = normalize_shot(raw, i, defaults, base_dir, errors, warnings)
        if shot.id in seen:
            errors.append(f"[{shot.id}] duplicate id")
        seen.add(shot.id)
        shots.append(shot)
    if not shots:
        errors.append("shot list has no shots")
    return ShotList(path, meta, shots, errors, warnings)


def _resolve(src: str, base_dir: Path) -> Path:
    p = Path(src).expanduser()
    return p if p.is_absolute() else (base_dir / p)


def normalize_shot(
    raw: Any, index: int, defaults: dict[str, Any], base_dir: Path, errors: list[str], warnings: list[str]
) -> Shot:
    if not isinstance(raw, dict):
        errors.append(f"[#{index}] shot must be a mapping")
        raw = {"id": f"shot{index:02d}", "kind": "card"}
    sid = str(raw.get("id") or f"shot{index:02d}")
    tag = f"[{sid}]"
    kind = str(raw.get("kind", "card"))
    if kind not in KINDS:
        errors.append(f"{tag} unknown kind {kind!r}; expected one of {sorted(KINDS)}")
    merged = {**defaults, **raw}
    duration: float | str = merged.get("duration", "auto")
    if duration != "auto":
        try:
            duration = float(duration)
            if duration <= 0:
                errors.append(f"{tag} duration must be > 0")
        except (TypeError, ValueError):
            errors.append(f"{tag} duration must be a number of seconds or 'auto'")
            duration = 3.0
    vo = merged.get("vo")
    vo = str(vo).strip() if vo else None
    if duration == "auto" and not vo:
        errors.append(f"{tag} duration 'auto' needs a `vo` line")
    vo_offset = float(merged.get("vo_offset", 0.0) or 0.0)
    transition = merged.get("transition", {"kind": "cut"})
    if isinstance(transition, str):
        transition = {"kind": transition}
    tkind = str(transition.get("kind", "cut"))
    transition = {
        "kind": tkind,
        "duration": float(transition.get("duration", 0.25 if tkind == "whip" else 0.5)),
        "ease": transition.get("ease"),
        "direction": str(transition.get("direction", "left")),
        # v4: run inside the incoming shot's first frames over a frozen plate of the outgoing
        # shot's last frame, so the timeline does not shorten
        "inside": bool(transition.get("inside", False)),
    }
    if transition["inside"] and tkind not in ("push_left", "push_right", "dissolve", "fade"):
        errors.append(f"{tag} inside transitions must be push_left, push_right, dissolve or fade")
    if tkind != "cut" and tkind not in TRANSITIONS:
        errors.append(f"{tag} unknown transition {tkind!r}")
    if transition["ease"] is not None and not fx.is_ease(transition["ease"]):
        errors.append(f"{tag} transition ease must be one of {sorted(fx.EASES)}")
    texts = list(raw.get("text", []) or [])
    pointers = list(raw.get("pointers", []) or [])
    for ti, t in enumerate(texts):
        _check_overlay(t, f"{tag} text[{ti}]", errors, warnings)
    for pi, p in enumerate(pointers):
        _check_pointer(p, f"{tag} pointers[{pi}]", errors, warnings)
    params = {k: v for k, v in raw.items() if k not in COMMON_KEYS}
    params["kind"] = kind
    allowed = KIND_KEYS.get(kind, set())
    for k in params:
        if k != "kind" and k not in allowed:
            warnings.append(f"{tag} key {k!r} is not used by kind {kind!r}")
    _check_params(kind, params, tag, base_dir, errors, warnings)
    shot = Shot(sid, kind, duration, vo, vo_offset, texts, pointers, transition, params, raw)
    shot.min_duration = float(merged.get("min", 0.0) or 0.0)
    shot.black_in = float(merged.get("black_in", 0.0) or 0.0)
    shot.black_out = float(merged.get("black_out", 0.0) or 0.0)
    return shot


def _check_overlay(t: Any, tag: str, errors: list[str], warnings: list[str]) -> None:
    if not isinstance(t, dict):
        errors.append(f"{tag} must be a mapping")
        return
    if t.get("kind", "caption") not in TEXT_KINDS:
        errors.append(f"{tag} unknown text kind {t.get('kind')!r}")
    kind = t.get("kind", "caption")
    needs = {
        "chips": "items", "panel": "box", "image": "src", "bar": "box", "rail": "n", "ticker": "to",
        "bloom": "center", "progress_rail": "segments",
    }.get(kind, "text")  # fmt: skip
    if kind == "spotlight":
        if "box" not in t and "center" not in t and not t.get("regions"):
            errors.append(f"{tag} spotlight needs `box`, `center` or `regions`")
    elif needs == "text" and t.get("spans"):
        pass
    elif needs not in t:
        errors.append(f"{tag} needs `{needs}`")
    pos = t.get("pos")
    if kind == "rail":
        if pos is not None and pos not in ("top", "bottom"):
            errors.append(f"{tag} rail pos must be top or bottom")
    else:
        ok_pos = (isinstance(pos, str) and pos in POS_CODES) or (
            isinstance(pos, (list, tuple)) and len(pos) == 2
        )
        if pos is not None and not ok_pos:
            errors.append(f"{tag} pos must be one of {sorted(POS_CODES)} or [x, y]")
    allowed_anims = ANIMS | PANEL_ANIMS if kind == "panel" else ANIMS
    if t.get("anim", "fade") not in allowed_anims:
        errors.append(f"{tag} anim must be one of {sorted(allowed_anims)}")
    if t.get("out_anim") is not None and t["out_anim"] not in ANIMS:
        errors.append(f"{tag} out_anim must be one of {sorted(ANIMS)}")
    if t.get("ease") is not None and not fx.is_ease(t["ease"]):
        errors.append(f"{tag} ease must be one of {sorted(fx.EASES)}")
    glow = t.get("glow")
    if glow is not None and kind not in ("rail",):
        if not isinstance(glow, dict):
            errors.append(f"{tag} glow must be a mapping {{color, radius, strength}}")
        elif "color" in glow and not draw.is_color(glow["color"]):
            errors.append(f"{tag} bad glow colour {glow['color']!r}")
    if "color" in t and not draw.is_color(t["color"]):
        errors.append(f"{tag} bad colour {t['color']!r}")
    if "in" in t and "out" in t and not (isinstance(t["in"], str) or isinstance(t["out"], str)):
        if float(t["out"]) <= float(t["in"]):
            errors.append(f"{tag} out must be after in")


def _check_pointer(p: Any, tag: str, errors: list[str], warnings: list[str]) -> None:
    if not isinstance(p, dict):
        errors.append(f"{tag} must be a mapping")
        return
    if p.get("kind", "arrow") not in POINTER_KINDS:
        errors.append(f"{tag} unknown pointer kind {p.get('kind')!r}")
    if p.get("kind") == "path":
        pts = p.get("points")
        if not isinstance(pts, list) or len(pts) < 2:
            errors.append(f"{tag} path needs `points` (two or more [x, y])")
        return
    for key in ("from", "to"):
        v = p.get(key)
        if key == "to" and p.get("kind") in ("badge", "node") and v is None:
            continue
        if not (isinstance(v, (list, tuple)) and len(v) == 2):
            errors.append(f"{tag} `{key}` must be [x, y]")
        elif not (0 <= float(v[0]) <= draw.REF_W and 0 <= float(v[1]) <= draw.REF_H):
            warnings.append(f"{tag} `{key}` {v} is outside the 1920x1080 frame")
    if "color" in p and not draw.is_color(p["color"]):
        errors.append(f"{tag} bad colour {p['color']!r}")
    if p.get("ease") is not None and not fx.is_ease(p["ease"]):
        errors.append(f"{tag} ease must be one of {sorted(fx.EASES)}")


def _check_params(
    kind: str, params: dict[str, Any], tag: str, base_dir: Path, errors: list[str], warnings: list[str]
) -> None:
    if kind in ("clip", "still"):
        src = params.get("src")
        if not src:
            errors.append(f"{tag} {kind} needs `src`")
        elif not _resolve(str(src), base_dir).exists():
            errors.append(f"{tag} asset not found: {src}")
        if params.get("fit", "contain") not in ("contain", "cover"):
            errors.append(f"{tag} fit must be contain or cover")
        z = params.get("zoom")
        if z is not None:
            if not isinstance(z, dict) or not all(
                isinstance(z.get(k), (list, tuple)) and len(z[k]) == 3 for k in ("from", "to")
            ):
                errors.append(f"{tag} zoom must be {{from: [cx, cy, scale], to: [cx, cy, scale]}}")
            elif min(float(z["from"][2]), float(z["to"][2])) < 1.0:
                errors.append(f"{tag} zoom scale must be >= 1.0")
            elif isinstance(z.get("ease"), str) and not fx.is_ease(z["ease"]):
                errors.append(f"{tag} zoom ease must be true/false or one of {sorted(fx.EASES)}")
        cam = params.get("camera")
        if cam is not None:
            keys = cam.get("keys", []) if isinstance(cam, dict) else cam
            if not isinstance(keys, list) or not keys:
                errors.append(f"{tag} camera must be a list of keyframes or {{keys: [...], settle, ease}}")
            else:
                for ki, k in enumerate(keys):
                    if not isinstance(k, dict) or "at" not in k:
                        errors.append(f"{tag} camera[{ki}] needs `at`")
                        continue
                    if not k.get("hold") and not (
                        isinstance(k.get("view"), (list, tuple)) and len(k["view"]) == 3
                    ):
                        errors.append(f"{tag} camera[{ki}] needs `view: [cx, cy, scale]` or `hold: true`")
                    if isinstance(k.get("ease"), str) and not fx.is_ease(k["ease"]):
                        errors.append(f"{tag} camera[{ki}] ease must be seconds or one of {sorted(fx.EASES)}")
                if isinstance(keys[0], dict) and keys[0].get("hold"):
                    errors.append(f"{tag} the first camera keyframe cannot be a hold")
        if kind == "clip" and float(params.get("speed", 1.0) or 1.0) <= 0:
            errors.append(f"{tag} speed must be > 0")
    elif kind == "card":
        bg = params.get("bg")
        if bg is not None and not isinstance(bg, (list, dict)) and not draw.is_color(bg):
            errors.append(f"{tag} bad bg colour {bg!r}")
        logo = params.get("logo")
        if logo:
            lsrc = logo.get("src") if isinstance(logo, dict) else logo
            if not lsrc or not _resolve(str(lsrc), base_dir).exists():
                errors.append(f"{tag} logo not found: {lsrc}")
    elif kind == "terminal":
        if not any(k in params for k in ("src", "lines", "text")):
            errors.append(f"{tag} terminal needs `src`, `lines` or `text`")
        elif "src" in params and not _resolve(str(params["src"]), base_dir).exists():
            errors.append(f"{tag} terminal src not found: {params['src']}")
        for h in params.get("highlight", []) or []:
            if not isinstance(h, dict) or "match" not in h:
                errors.append(f"{tag} highlight entries need `match`")
    elif kind == "table":
        rows = params.get("rows")
        if not isinstance(rows, list) or not rows or not all(isinstance(r, list) for r in rows):
            errors.append(f"{tag} table needs `rows` as a list of lists")
    elif kind == "code":
        if not any(k in params for k in ("src", "lines", "text")):
            errors.append(f"{tag} code needs `src`, `lines` or `text`")
        elif "src" in params and not _resolve(str(params["src"]), base_dir).exists():
            errors.append(f"{tag} code src not found: {params['src']}")
        for h in params.get("highlight", []) or []:
            if not isinstance(h, dict) or not (
                isinstance(h.get("lines"), (list, tuple)) and len(h["lines"]) == 2
            ):
                errors.append(f"{tag} code highlight entries need `lines: [first, last]`")
    elif kind == "json":
        if not any(k in params for k in ("src", "data", "text")):
            errors.append(f"{tag} json needs `src`, `data` or `text`")
        elif "src" in params and not _resolve(str(params["src"]), base_dir).exists():
            errors.append(f"{tag} json src not found: {params['src']}")
    elif kind == "split":
        if "main" in params:
            if not isinstance(params.get("pip"), dict) or "shot" not in params["pip"]:
                errors.append(f"{tag} split with `main` needs `pip: {{shot: ..., pos: ..., scale: ...}}`")
            children = [("main", params["main"]), ("pip.shot", (params.get("pip") or {}).get("shot"))]
        elif "left" in params and "right" in params:
            children = [("left", params["left"]), ("right", params["right"])]
        else:
            errors.append(f"{tag} split needs `main` + `pip` or `left` + `right`")
            children = []
        for name, child in children:
            if not isinstance(child, dict):
                errors.append(f"{tag} split child {name} must be a shot mapping")
                continue
            if child.get("kind") == "split":
                errors.append(f"{tag} split children cannot be splits")
            child_errors: list[str] = []
            normalize_shot(
                {"id": f"{tag}.{name}", "duration": 1, **child}, 0, {}, base_dir, child_errors, warnings
            )
            errors.extend(child_errors)


# --------------------------------------------------------------------------- asset loading


def load_image(path: Path, build_dir: Path) -> Image.Image:
    """Open a raster image; render .svg through qlmanage (macOS) or rsvg-convert when present."""
    if path.suffix.lower() == ".svg":
        out_dir = build_dir / "stills"
        out_dir.mkdir(parents=True, exist_ok=True)
        png = out_dir / (path.stem + ".png")
        if not png.exists() or png.stat().st_mtime < path.stat().st_mtime:
            if shutil.which("rsvg-convert"):
                subprocess.run(["rsvg-convert", "-w", "1920", "-o", str(png), str(path)], check=True)
            elif shutil.which("qlmanage"):
                subprocess.run(
                    ["qlmanage", "-t", "-s", "1920", "-o", str(out_dir), str(path)],
                    check=True,
                    capture_output=True,
                )
                (out_dir / (path.name + ".png")).replace(png)
            else:
                raise FileNotFoundError("no SVG renderer (rsvg-convert or qlmanage) available")
        path = png
    return Image.open(path).convert("RGB")


def fit_image(img: Image.Image, w: int, h: int, fit: str, bg: Any = "bg") -> Image.Image:
    """Letterbox (contain) or crop (cover) an image into exactly w x h without stretching."""
    sw, sh = img.size
    if fit == "cover":
        r = max(w / sw, h / sh)
    else:
        r = min(w / sw, h / sh)
    nw, nh = max(1, round(sw * r)), max(1, round(sh * r))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (w, h), draw.rgb(bg))
    canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2))
    return canvas


class KenBurns:
    """Eased move from (cx, cy, scale) to (cx, cy, scale) over the shot.

    ``ease`` is ``true`` (smoothstep, the pre-v3 default), ``false`` (linear) or a curve name;
    without an ``ease`` key the shot list's default curve applies when one is set.
    """

    def __init__(self, spec: dict[str, Any] | None, duration: float, default_curve: str | None = None):
        self.spec = spec
        self.duration = max(1e-6, duration)
        if spec:
            self.a = [float(v) for v in spec["from"]]
            self.b = [float(v) for v in spec["to"]]
            e = spec.get("ease", True)
            if isinstance(e, str):
                self.curve = e
            elif "ease" not in spec and default_curve:
                self.curve = default_curve
            else:
                self.curve = "smooth" if e else "linear"
            self.k = max(1.0, self.a[2], self.b[2])
        else:
            self.k = 1.0

    @property
    def active(self) -> bool:
        return self.spec is not None

    def params(self, t: float) -> tuple[float, float, float]:
        u = fx.ease(self.curve, draw.clamp01(t / self.duration))
        return tuple(self.a[i] + (self.b[i] - self.a[i]) * u for i in range(3))  # type: ignore[return-value]

    def params_depth(self, t: float, depth: float) -> tuple[float, float, float]:
        """The view a layer at ``depth`` sees: its motion relative to the start is scaled by 1 + depth."""
        cx, cy, s = self.params(t)
        k = 1.0 + depth
        return (
            self.a[0] + (cx - self.a[0]) * k,
            self.a[1] + (cy - self.a[1]) * k,
            max(1e-3, self.a[2] + (s - self.a[2]) * k),
        )

    def apply(self, big: Image.Image, t: float, w: int, h: int) -> Image.Image:
        cx, cy, s = self.params(t)
        bw, bh = big.size
        cw, ch = bw / s, bh / s
        x0 = min(max(0.0, cx * bw - cw / 2), bw - cw)
        y0 = min(max(0.0, cy * bh - ch / 2), bh - ch)
        box = (round(x0), round(y0), round(x0 + cw), round(y0 + ch))
        return big.resize((w, h), Image.Resampling.BILINEAR, box=box)

    def apply_layer(
        self, padded: Image.Image, margin: int, t: float, depth: float, w: int, h: int
    ) -> Image.Image:
        """Crop a parallax layer (an RGBA image padded by ``margin`` px) with the depth-adjusted view."""
        cx, cy, s = self.params_depth(t, depth)
        bw, bh = padded.width - 2 * margin, padded.height - 2 * margin
        cw, ch = bw / s, bh / s
        x0 = cx * bw - cw / 2 + margin
        y0 = cy * bh - ch / 2 + margin
        x0 = min(max(0.0, x0), padded.width - cw)
        y0 = min(max(0.0, y0), padded.height - ch)
        box = (round(x0), round(y0), round(x0 + cw), round(y0 + ch))
        return padded.resize((w, h), Image.Resampling.BILINEAR, box=box)


def grab_frame(ffmpeg: str, src: Path, at: float) -> Image.Image:
    """One frame of a video at ``at`` seconds, as an RGB image."""
    import io

    proc = subprocess.run(
        [ffmpeg, "-v", "error", "-nostdin", "-ss", f"{at:.3f}", "-i", str(src), "-frames:v", "1",
         "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True,
    )  # fmt: skip
    return Image.open(io.BytesIO(proc.stdout)).convert("RGB")


def fit_rgba(img: Image.Image, w: int, h: int, fit: str) -> Image.Image:
    """``fit_image`` for RGBA layers: contain or cover into w x h on a transparent canvas."""
    sw, sh = img.size
    r = max(w / sw, h / sh) if fit == "cover" else min(w / sw, h / sh)
    nw, nh = max(1, round(sw * r)), max(1, round(sh * r))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((w - nw) // 2, (h - nh) // 2))
    return canvas


def blur_fill(img: Image.Image, w: int, h: int, radius: int, brightness: float) -> Image.Image:
    """The image scaled to cover w x h, blurred and darkened: the fill behind a narrow clip."""
    cover = fit_image(img, w, h, "cover")
    cover = cover.filter(ImageFilter.GaussianBlur(max(1, radius)))
    return ImageEnhance.Brightness(cover).enhance(brightness)


class SubjectMotion:
    """Motion of a placed picture after the crop (DESIGN section 6): a push-in about a centre
    and a two-layer drift (the subject one way, the blur fill the other).

    ``subject_zoom: {from: 1.0, to: 1.03, start: 0.0, end: <shot end>, center: [x, y], ease: drift,
    clip: true}`` and ``drift: {subject: [dx, dy], fill: [dx, dy], start, end, ease: drift}``.
    ``map_point`` carries attached overlays (leaders, dots) with the picture.
    """

    def __init__(
        self,
        zoom: dict[str, Any] | None,
        drift: dict[str, Any] | None,
        duration: float,
        geom: tuple[int, int, int, int],
        canvas: draw.Canvas,
    ):
        self.zoom = dict(zoom) if zoom else None
        self.drift = dict(drift) if drift else None
        self.duration = duration
        self.geom = geom
        self.canvas = canvas
        px0, py0, pw, ph = geom
        if self.zoom and self.zoom.get("center"):
            self.center = canvas.pt(self.zoom["center"])
        else:
            self.center = (px0 + pw / 2, py0 + ph / 2)
        self.clip = bool(self.zoom.get("clip", True)) if self.zoom else True

    @property
    def active(self) -> bool:
        return bool(self.zoom or self.drift)

    def _u(self, spec: dict[str, Any], t: float) -> float:
        start = float(spec.get("start", 0.0))
        end = float(spec.get("end", self.duration))
        return fx.ease(str(spec.get("ease", "drift")), (t - start) / max(1e-6, end - start))

    def scale(self, t: float) -> float:
        if not self.zoom:
            return 1.0
        a, b = float(self.zoom.get("from", 1.0)), float(self.zoom.get("to", 1.0))
        return a + (b - a) * self._u(self.zoom, t)

    def _off(self, key: str, t: float) -> tuple[float, float]:
        if not self.drift or not self.drift.get(key):
            return 0.0, 0.0
        dx, dy = (float(v) for v in self.drift[key])
        u = self._u(self.drift, t)
        return self.canvas.s * dx * u, self.canvas.s * dy * u

    def subject_offset(self, t: float) -> tuple[float, float]:
        return self._off("subject", t)

    def fill_offset(self, t: float) -> tuple[float, float]:
        return self._off("fill", t)

    def fill_margin(self) -> int:
        if not self.drift or not self.drift.get("fill"):
            return 0
        return math.ceil(max(abs(float(v)) for v in self.drift["fill"]) * self.canvas.s) + 1

    def map_point(self, t: float, x: float, y: float) -> tuple[float, float]:
        s = self.scale(t)
        ox, oy = self.subject_offset(t)
        cx, cy = self.center
        return cx + (x - cx) * s + ox, cy + (y - cy) * s + oy

    def key(self, t: float) -> Any:
        return (round(self.scale(t) * 4096), tuple(round(v * 2) for v in self.subject_offset(t)),
                tuple(round(v * 2) for v in self.fill_offset(t)))  # fmt: skip

    def place_subject(self, base: Image.Image, fg: Image.Image, t: float) -> Image.Image:
        """``fg`` (the picture at its placed size) scaled about the centre and drifted, pasted on
        ``base`` (clipped to the place box when ``clip``)."""
        px0, py0, pw, ph = self.geom
        s = self.scale(t)
        ox, oy = self.subject_offset(t)
        cx, cy = self.center
        if abs(s - 1.0) > 1e-4:
            fg = fg.resize((max(1, round(pw * s)), max(1, round(ph * s))), Image.Resampling.LANCZOS)
        nx0 = cx - (cx - px0) * s + ox
        ny0 = cy - (cy - py0) * s + oy
        out = base.copy()
        if self.clip:
            cx0, cy0 = round(px0 - nx0), round(py0 - ny0)
            region = fg.crop((cx0, cy0, cx0 + pw, cy0 + ph))
            out.paste(region, (px0, py0))
        else:
            out.paste(fg, (round(nx0), round(ny0)))
        return out


class StillSource(draw.FrameSource):
    """A still (image or one video frame) with crop, placement, blur fill, brightness, dim,
    lit regions and timed overlay layers."""

    def __init__(
        self,
        canvas: draw.Canvas,
        params: dict[str, Any],
        duration: float,
        base_dir: Path,
        build_dir: Path,
        ffmpeg: str = "ffmpeg",
    ):
        self.canvas = canvas
        self.duration = duration
        W, H = canvas.width, canvas.height
        src = _resolve(str(params["src"]), base_dir)
        if src.suffix.lower() in VIDEO_EXT:
            img = grab_frame(ffmpeg, src, float(params.get("at", 0.0)))
        else:
            img = load_image(src, build_dir)
        crop = params.get("crop")
        if crop:
            img = img.crop(tuple(int(v) for v in crop))
        self.crop = crop
        place = params.get("place")
        self.camera = self._camera_keys(params.get("camera"), canvas)
        if self.camera:
            # keyframed views [cx, cy, scale] held between eased moves; the working image is
            # the source fitted at the largest scale so the tightest view is cropped 1:1
            kmax = max(float(k["view"][2]) for k in self.camera)
            self.big = fit_image(img, round(W * kmax), round(H * kmax), str(params.get("fit", "contain")))
            if params.get("brightness") is not None:
                self.big = ImageEnhance.Brightness(self.big).enhance(float(params["brightness"]))
            self.kb = KenBurns(None, duration)
            self.geom = None
            self.regions = []
            self.layers = []
            self.dim = None
            return
        self.kb = KenBurns(params.get("zoom") if not place else None, duration, canvas.ease)
        self.geom: tuple[int, int, int, int] | None = None
        self.motion: SubjectMotion | None = None
        self.fill_img: Image.Image | None = None
        self.fg: Image.Image | None = None
        if place:
            px0, py0 = canvas.pt(place[:2])
            px1, py1 = canvas.pt(place[2:])
            pw, ph = max(1, px1 - px0), max(1, py1 - py0)
            self.geom = (px0, py0, pw, ph)
            fg = img.resize((pw, ph), Image.Resampling.LANCZOS)
            motion = SubjectMotion(
                params.get("subject_zoom"), params.get("drift"), duration, self.geom, canvas
            )
            m = motion.fill_margin()
            if params.get("fill") == "blur":
                base = blur_fill(
                    img,
                    W + 2 * m,
                    H + 2 * m,
                    canvas.px(float(params.get("fill_blur", 24))),
                    float(params.get("fill_brightness", 0.35)),
                )
            else:
                base = Image.new("RGB", (W + 2 * m, H + 2 * m), draw.rgb("bg"))
            if motion.active:
                k = params.get("brightness")
                if k is not None:
                    base = ImageEnhance.Brightness(base).enhance(float(k))
                    fg = ImageEnhance.Brightness(fg).enhance(float(k))
                self.motion, self.fill_img, self.fg, self.fill_m = motion, base, fg, m
            base.paste(fg, (px0 + m, py0 + m))
            if m:
                base = base.crop((m, m, m + W, m + H))
        else:
            bw, bh = round(W * self.kb.k), round(H * self.kb.k)
            base = fit_image(img, bw, bh, str(params.get("fit", "contain")))
        if params.get("brightness") is not None:
            base = ImageEnhance.Brightness(base).enhance(float(params["brightness"]))
        self.big = base
        # lit regions over a dimmed base (shot 4 style)
        self.regions = [dict(r) for r in params.get("regions", [])]
        self.base_b = float(params.get("base_brightness", 0.25))
        if self.regions:
            ats = sorted({float(r["at"]) for r in self.regions})
            for r in self.regions:
                later = [a for a in ats if a > float(r["at"])]
                r.setdefault("settle_at", later[0] if later else None)
                r.setdefault("settle_to", 0.7)
                x0, y0 = canvas.pt(r["box"][:2])
                x1, y1 = canvas.pt(r["box"][2:])
                mask = np.zeros((H, W), dtype=bool)
                mask[y0:y1, x0:x1] = True
                r["mask"] = mask
            self.arr = np.asarray(self.big, dtype=np.float32)
        # timed layers sharing the crop and placement (shot 3 style); under a Ken Burns `zoom`
        # each layer is cropped with its own depth-adjusted view (parallax)
        self.layers: list[dict[str, Any]] = []
        self.parallax = self.kb.active
        for spec in params.get("layers", []):
            lp = _resolve(str(spec["src"]), base_dir)
            lim = Image.open(lp).convert("RGBA")
            if crop:
                lim = lim.crop(tuple(int(v) for v in crop))
            if self.parallax:
                bw, bh = self.big.size
                fitted = fit_rgba(lim, bw, bh, str(params.get("fit", "contain")))
                margin = max(8, round(max(bw, bh) * 0.12))
                full = Image.new("RGBA", (bw + 2 * margin, bh + 2 * margin), (0, 0, 0, 0))
                full.alpha_composite(fitted, (margin, margin))
            else:
                margin = 0
                full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                if self.geom:
                    px0, py0, pw, ph = self.geom
                    full.alpha_composite(lim.resize((pw, ph), Image.Resampling.LANCZOS), (px0, py0))
                else:
                    full.alpha_composite(fit_image(lim.convert("RGB"), W, H, "contain").convert("RGBA"))
            self.layers.append(
                {
                    "img": full,
                    "margin": margin,
                    "depth": float(spec.get("depth", 0.0)),
                    "at": float(spec.get("at", 0.0)),
                    "fade": float(spec.get("fade", 0.4)),
                    "settle_at": spec.get("settle_at"),
                    "settle_to": float(spec.get("settle_to", 0.7)),
                }
            )
        self.dim = params.get("dim")

    @staticmethod
    def _camera_keys(spec: Any, canvas: draw.Canvas) -> list[dict[str, Any]]:
        """Normalise ``camera`` (a list, or ``{keys, settle, ease}``) into sorted keyframes with
        ``view``, ``over`` (seconds), ``curve``, ``hold`` and ``settle``."""
        if not spec:
            return []
        if isinstance(spec, dict):
            keys = [dict(k) for k in spec.get("keys", [])]
            settle = float(spec.get("settle", 0.0) or 0.0)
            cam_ease = spec.get("ease")
        else:
            keys = [dict(k) for k in spec]
            settle, cam_ease = 0.0, None
        keys.sort(key=lambda k: float(k["at"]))
        out: list[dict[str, Any]] = []
        for k in keys:
            e = k.get("ease", 0.6)
            if isinstance(e, str):
                over, curve = float(k.get("over", 0.6)), e
            else:
                over, curve = float(e), (cam_ease or canvas.ease or "smooth")
            if k.get("hold"):
                view = list(out[-1]["view"]) if out else [0.5, 0.5, 1.0]
                over = 0.0
            else:
                view = [float(v) for v in k["view"]]
            out.append(
                {
                    "at": float(k["at"]),
                    "view": view,
                    "over": over,
                    "curve": curve,
                    "hold": bool(k.get("hold")),
                    "settle": float(k.get("settle", settle) or 0.0),
                }
            )
        return out

    def _region_levels(self, t: float) -> tuple[float, ...]:
        out = []
        for r in self.regions:
            lit = draw.smoothstep((t - float(r["at"])) / 0.4)
            settle = draw.smoothstep((t - float(r["settle_at"])) / 0.4) if r["settle_at"] is not None else 0.0
            level = 1.0 - (1.0 - float(r["settle_to"])) * settle
            out.append(self.base_b + (level - self.base_b) * lit)
        return tuple(out)

    def _layer_opacities(self, t: float) -> tuple[float, ...]:
        out = []
        for ly in self.layers:
            o = draw.smoothstep((t - ly["at"]) / ly["fade"])
            if ly["settle_at"] is not None:
                o *= 1.0 - (1.0 - ly["settle_to"]) * draw.smoothstep((t - float(ly["settle_at"])) / 0.4)
            out.append(o)
        return tuple(out)

    def _dim(self, t: float) -> float:
        if not self.dim:
            return 1.0
        at, to, over = (
            float(self.dim.get("at", 0.0)),
            float(self.dim.get("to", 0.4)),
            float(self.dim.get("over", 0.3)),
        )
        return 1.0 - (1.0 - to) * fx.ease(str(self.dim.get("ease", "smooth")), (t - at) / over)

    def view(self, t: float) -> tuple[float, float, float]:
        kfs = self.camera
        i = 0
        for j, k in enumerate(kfs):
            if t >= k["at"]:
                i = j
        key = kfs[i]
        cur = list(key["view"])
        over = key["over"]
        if i > 0 and over > 0 and t < key["at"] + over:
            prev = kfs[i - 1]["view"]
            u = fx.ease(key["curve"], (t - key["at"]) / over)
            cur = [prev[n] + (cur[n] - prev[n]) * u for n in range(3)]
            return cur[0], cur[1], cur[2]
        if key["settle"]:
            # a slow push over the hold: from the end of the last real move to the next real key
            j = i
            while j > 0 and kfs[j]["hold"]:
                j -= 1
            hold_start = kfs[j]["at"] + (kfs[j]["over"] if j > 0 else 0.0)
            nxt = next((k["at"] for k in kfs[i + 1 :] if not k["hold"]), self.duration)
            u = fx.ease("ease_in_out", (t - hold_start) / max(1e-6, nxt - hold_start))
            cur[2] = cur[2] * (1.0 + key["settle"] * u)
        return cur[0], cur[1], cur[2]

    def map_point(self, t: float, x: float, y: float) -> tuple[float, float]:
        """Frame coordinates at the shot's start to frame coordinates at ``t`` (attached overlays)."""
        if self.motion is not None:
            return self.motion.map_point(t, x, y)
        return x, y

    def key(self, t: float) -> Any:
        if self.camera:
            return ("cam", *tuple(round(v, 4) for v in self.view(t)))
        if self.motion is not None:
            return (
                "motion",
                self.motion.key(t),
                tuple(draw.quantize(v, 32) for v in self._layer_opacities(t)),
                draw.quantize(self._dim(t), 64),
            )
        if self.kb.active:
            return (
                "kb",
                draw.quantize(t / self.kb.duration, 4096),
                tuple(draw.quantize(v, 32) for v in self._layer_opacities(t)),
            )
        return (
            tuple(draw.quantize(v, 32) for v in self._region_levels(t)),
            tuple(draw.quantize(v, 32) for v in self._layer_opacities(t)),
            draw.quantize(self._dim(t), 64),
        )

    def frame(self, t: float) -> Image.Image:
        if self.camera:
            cx, cy, sc = self.view(t)
            bw, bh = self.big.size
            cw, ch = bw / sc, bh / sc
            x0 = min(max(0.0, cx * bw - cw / 2), bw - cw)
            y0 = min(max(0.0, cy * bh - ch / 2), bh - ch)
            box = (round(x0), round(y0), round(x0 + cw), round(y0 + ch))
            return self.big.resize((self.canvas.width, self.canvas.height), Image.Resampling.LANCZOS, box=box)
        if self.kb.active:
            W, H = self.canvas.width, self.canvas.height
            base = self.kb.apply(self.big, t, W, H)
            if not self.layers:
                return base
            out = base.convert("RGBA")
            for ly, o in zip(self.layers, self._layer_opacities(t), strict=True):
                if o <= 0:
                    continue
                layer = self.kb.apply_layer(ly["img"], ly["margin"], t, ly["depth"], W, H)
                if o < 1:
                    layer.putalpha(layer.getchannel("A").point(lambda v, o=o: int(v * o)))
                out.alpha_composite(layer)
            return out.convert("RGB")
        img = self.big
        if self.motion is not None and self.fill_img is not None and self.fg is not None:
            W, H = self.canvas.width, self.canvas.height
            m = self.fill_m
            fx_, fy_ = self.motion.fill_offset(t)
            base = self.fill_img.crop(
                (m - round(fx_), m - round(fy_), m - round(fx_) + W, m - round(fy_) + H)
            )
            img = self.motion.place_subject(base, self.fg, t)
        if self.regions:
            levels = self._region_levels(t)
            amap = np.full(self.arr.shape[:2], self.base_b, dtype=np.float32)
            for r, lv in zip(self.regions, levels, strict=True):
                amap[r["mask"]] = np.maximum(amap[r["mask"]], lv)
            img = Image.fromarray((self.arr * amap[..., None]).clip(0, 255).astype(np.uint8), "RGB")
        if self.layers:
            out = img.convert("RGBA")
            for ly, o in zip(self.layers, self._layer_opacities(t), strict=True):
                if o <= 0:
                    continue
                layer = ly["img"]
                if o < 1:
                    layer = layer.copy()
                    layer.putalpha(layer.getchannel("A").point(lambda v, o=o: int(v * o)))
                out.alpha_composite(layer)
            img = out.convert("RGB")
        k = self._dim(t)
        if k < 1.0:
            img = ImageEnhance.Brightness(img).enhance(k)
        return img


class ClipSource(draw.FrameSource):
    """Sequential frames from ffmpeg: fitted to the canvas, or cropped and placed in a
    rectangle over a darkened blur fill, with optional frame blending for low-fps sources."""

    def __init__(
        self,
        canvas: draw.Canvas,
        params: dict[str, Any],
        duration: float,
        fps: int,
        base_dir: Path,
        ffmpeg: str,
    ):
        self.canvas = canvas
        self.fps = fps
        W, H = canvas.width, canvas.height
        place = params.get("place")
        self.kb = KenBurns(params.get("zoom") if not place else None, duration, canvas.ease)
        src = _resolve(str(params["src"]), base_dir)
        speed = float(params.get("speed", 1.0) or 1.0)
        start = params.get("start")
        end = params.get("end")
        bg = draw.PALETTE["bg"].replace("#", "0x")
        pre = [f"setpts=PTS/{speed:.4f}"]
        crop = params.get("crop")
        if crop:
            cx0, cy0, cx1, cy1 = (int(v) for v in crop)
            pre.append(f"crop={cx1 - cx0}:{cy1 - cy0}:{cx0}:{cy0}")
        pre.append(f"minterpolate=fps={fps}:mi_mode=blend" if params.get("blend") else f"fps={fps}")
        k = params.get("brightness")
        tail = f",colorchannelmixer=rr={float(k)}:gg={float(k)}:bb={float(k)}" if k is not None else ""
        cmd = [ffmpeg, "-v", "error", "-nostdin"]
        if params.get("loop"):
            cmd += ["-stream_loop", "-1"]
        if start:
            cmd += ["-ss", f"{float(start):.3f}"]
        cmd += ["-i", str(src), "-an"]
        if end:
            cmd += ["-t", f"{(float(end) - float(start or 0)) / speed:.3f}"]
        else:
            cmd += ["-t", f"{duration * 1.02 + 0.5:.3f}"]
        if place:
            px0, py0 = canvas.pt(place[:2])
            px1, py1 = canvas.pt(place[2:])
            pw, ph = max(2, px1 - px0), max(2, py1 - py0)
            self.w, self.h = W, H
            if params.get("fill") == "blur":
                sigma = max(1.0, canvas.px(float(params.get("fill_blur", 24))) / 2)
                fb = float(params.get("fill_brightness", 0.35))
                graph = (
                    f"[0:v]{','.join(pre)},split[a][b];"
                    f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma={sigma:.1f},"
                    f"colorchannelmixer=rr={fb}:gg={fb}:bb={fb}[bg];"
                    f"[b]scale={pw}:{ph}:flags=lanczos[fg];[bg][fg]overlay={px0}:{py0}{tail},format=rgb24[out]"
                )
            else:
                graph = f"[0:v]{','.join(pre)},scale={pw}:{ph}:flags=lanczos"
                graph += f",pad={W}:{H}:{px0}:{py0}:color={bg}{tail},format=rgb24[out]"
            cmd += ["-filter_complex", graph, "-map", "[out]"]
        else:
            self.w = round(W * self.kb.k)
            self.h = round(H * self.kb.k)
            self.w += self.w % 2
            self.h += self.h % 2
            fit = str(params.get("fit", "contain"))
            if fit == "cover":
                vf = f"scale={self.w}:{self.h}:force_original_aspect_ratio=increase:flags=bicubic"
                vf += f",crop={self.w}:{self.h}"
            else:
                vf = (
                    f"scale={self.w}:{self.h}:force_original_aspect_ratio=decrease:flags=bicubic,"
                    f"pad={self.w}:{self.h}:(ow-iw)/2:(oh-ih)/2:color={bg}"
                )
            cmd += ["-vf", f"{','.join(pre)},{vf}{tail},format=rgb24"]
        cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.nbytes = self.w * self.h * 3
        self.last: Image.Image | None = None
        self.next_index = 0
        self.eof = False
        self.motion: SubjectMotion | None = None
        if place and (params.get("subject_zoom") or params.get("drift")):
            px0, py0 = canvas.pt(place[:2])
            px1, py1 = canvas.pt(place[2:])
            geom = (px0, py0, max(2, px1 - px0), max(2, py1 - py0))
            self.motion = SubjectMotion(
                params.get("subject_zoom"), params.get("drift"), duration, geom, canvas
            )

    def map_point(self, t: float, x: float, y: float) -> tuple[float, float]:
        if self.motion is not None:
            return self.motion.map_point(t, x, y)
        return x, y

    def _read_frame(self) -> Image.Image | None:
        assert self.proc.stdout is not None
        buf = bytearray()
        while len(buf) < self.nbytes:
            chunk = self.proc.stdout.read(self.nbytes - len(buf))
            if not chunk:
                self.eof = True
                return None
            buf += chunk
        return Image.frombuffer("RGB", (self.w, self.h), bytes(buf), "raw", "RGB", 0, 1)

    def frame(self, t: float) -> Image.Image:
        want = round(t * self.fps)
        while self.next_index <= want and not self.eof:
            img = self._read_frame()
            if img is None:
                break
            self.last = img
            self.next_index += 1
        if self.last is None:
            self.last = Image.new("RGB", (self.w, self.h), draw.rgb("bg"))
        if self.kb.active:
            return self.kb.apply(self.last, t, self.canvas.width, self.canvas.height)
        if self.motion is not None and self.motion.active:
            px0, py0, pw, ph = self.motion.geom
            fg = self.last.crop((px0, py0, px0 + pw, py0 + ph))
            return self.motion.place_subject(self.last, fg, t)
        return self.last

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        if self.proc.stdout:
            self.proc.stdout.close()
        self.proc.wait()


# --------------------------------------------------------------------------- shot renderers


class ShotRenderer(draw.FrameSource):
    """Base frames for a shot plus its text, pointers and burned captions."""

    def __init__(
        self,
        shot: Shot,
        duration: float,
        canvas: draw.Canvas,
        settings: Settings,
        base_dir: Path,
        captions: list[tuple[float, float, str]] | None = None,
        global_start: float = 0.0,
        chrome_skip_before: float = 0.0,
        chrome_skip_last: bool = False,
    ):
        self.shot = shot
        self.duration = duration
        self.canvas = canvas
        self.global_start = global_start
        # frames that become transition plates carry no global chrome (z >= 97): the first
        # `chrome_skip_before` seconds of a shot entered by an inside transition, and the last
        # frame of a shot that the next one pushes out; the transition draws that chrome itself
        self.chrome_skip_before = chrome_skip_before
        self.chrome_skip_last = chrome_skip_last
        self.fps = settings.fps
        p = shot.params
        kind = shot.kind
        if kind == "card":
            self.base: draw.FrameSource = draw.CardSource(
                canvas, p, lambda s: load_image(_resolve(s, base_dir), settings.build_dir)
            )
        elif kind == "still":
            self.base = StillSource(canvas, p, duration, base_dir, settings.build_dir, settings.ffmpeg)
        elif kind == "clip":
            self.base = ClipSource(canvas, p, duration, settings.fps, base_dir, settings.ffmpeg)
        elif kind == "terminal":
            self.base = draw.TerminalSource(canvas, p, duration, base_dir)
        elif kind == "table":
            self.base = draw.TableSource(canvas, p, duration)
        elif kind == "json":
            self.base = draw.JsonSource(canvas, p, duration, base_dir)
        elif kind == "code":
            self.base = widgets.CodeSource(canvas, p, duration, base_dir)
        elif kind == "split":
            self.base = SplitSource(shot, duration, canvas, settings, base_dir)
        else:
            raise ValueError(f"unknown kind {kind}")
        loader = lambda s: load_image(_resolve(s, base_dir), settings.build_dir)  # noqa: E731
        transform = getattr(self.base, "map_point", None)
        self.overlay = draw.OverlayRenderer(
            canvas, shot.text, shot.pointers, duration, captions, loader, transform, global_start
        )
        self.black_ease = shot.raw.get("black_ease")

    def black(self, t: float) -> float:
        """Brightness multiplier for the dip-to-black edges (black_in / black_out)."""
        k = 1.0
        if self.shot.black_in > 0 and t < self.shot.black_in:
            hold = min(0.1, self.shot.black_in / 3)
            k = 0.0 if t < hold else draw.smoothstep((t - hold) / max(1e-6, self.shot.black_in - hold))
        if self.shot.black_out > 0 and t > self.duration - self.shot.black_out:
            u = (self.duration - t) / self.shot.black_out
            if self.black_ease:
                k = min(k, 1.0 - fx.ease(str(self.black_ease), 1.0 - u))
            else:
                k = min(k, draw.smoothstep(u))
        return k

    def hi_z(self, t: float) -> bool:
        if t < self.chrome_skip_before - 1e-6:
            return False
        return not (self.chrome_skip_last and t >= self.duration - 1.5 / self.fps)

    def key(self, t: float) -> Any:
        bk = self.base.key(t)
        if bk is None:
            return None
        return (bk, self.overlay.key(t), draw.quantize(self.black(t), 64), self.hi_z(t))

    def frame(self, t: float) -> Image.Image:
        img = self.overlay.composite(self.base.frame(t), t, self.hi_z(t))
        k = self.black(t)
        if k < 1.0:
            img = ImageEnhance.Brightness(img).enhance(k)
        return img

    def close(self) -> None:
        self.base.close()


def child_shot(spec: dict[str, Any], parent: Shot, name: str) -> Shot:
    errors: list[str] = []
    warnings: list[str] = []
    child = normalize_shot(
        {"id": f"{parent.id}.{name}", "duration": 1, **spec}, 0, {}, Path("."), errors, warnings
    )
    if errors:
        raise ValueError("; ".join(errors))
    return child


class SplitSource(draw.FrameSource):
    """Picture-in-picture (`main` + `pip`) or side by side (`left` + `right`)."""

    def __init__(self, shot: Shot, duration: float, canvas: draw.Canvas, settings: Settings, base_dir: Path):
        self.canvas = canvas
        p = shot.params
        self.mode = "pip" if "main" in p else "side"
        if self.mode == "pip":
            pip = p["pip"]
            self.scale = float(pip.get("scale", 0.3))
            self.pos = pip.get("pos", "br")
            self.border = pip.get("border", "panel_border")
            self.main = ShotRenderer(
                child_shot(p["main"], shot, "main"), duration, canvas, settings, base_dir
            )
            self.pip = ShotRenderer(
                child_shot(pip["shot"], shot, "pip"), duration, canvas.scaled(self.scale), settings, base_dir
            )
            self.children = [self.main, self.pip]
        else:
            gap = canvas.px(float(p.get("gap", 24)))
            half = (canvas.width - 2 * canvas.px(draw.SAFE_X) - gap) / canvas.width
            self.left = ShotRenderer(
                child_shot(p["left"], shot, "left"), duration, canvas.scaled(half), settings, base_dir
            )
            self.right = ShotRenderer(
                child_shot(p["right"], shot, "right"), duration, canvas.scaled(half), settings, base_dir
            )
            self.children = [self.left, self.right]
            self.gap = gap
        self.bg = canvas.blank("bg")

    def key(self, t: float) -> Any:
        keys = [c.key(t) for c in self.children]
        return None if any(k is None for k in keys) else tuple(keys)

    def frame(self, t: float) -> Image.Image:
        c = self.canvas
        if self.mode == "pip":
            img = self.main.frame(t).copy()
            small = self.pip.frame(t)
            m = c.px(2)
            x, y = draw.place_block(c, self.pos, small.width + 2 * m, small.height + 2 * m)
            d = ImageDraw.Draw(img)
            d.rectangle(
                (x, y, x + small.width + 2 * m - 1, y + small.height + 2 * m - 1), fill=draw.rgb(self.border)
            )
            img.paste(small, (x + m, y + m))
            return img
        img = self.bg.copy()
        lf, rf = self.left.frame(t), self.right.frame(t)
        y = (c.height - lf.height) // 2
        x0 = (c.width - (lf.width + rf.width + self.gap)) // 2
        img.paste(lf, (x0, y))
        img.paste(rf, (x0 + lf.width + self.gap, y))
        return img

    def close(self) -> None:
        for ch in self.children:
            ch.close()


# --------------------------------------------------------------------------- timeline


@dataclass
class Placed:
    shot: Shot
    start: float
    duration: float
    vo: audio_mod.VoResult | None
    trans_kind: str
    trans_dur: float

    @property
    def vo_start(self) -> float:
        return self.start + self.shot.vo_offset

    @property
    def end(self) -> float:
        return self.start + self.duration


def vo_text(text: str, settings: Settings) -> str:
    """The text sent to Polly: sentence breaks and/or a prosody rate as SSML when set.

    The shot list and the captions keep the plain text; only the synthesis request changes.
    """
    if text.lstrip().startswith("<speak") or not (settings.vo_rate or settings.vo_breaks):
        return text
    import re
    from html import escape

    body = escape(text)
    if settings.vo_breaks:
        parts = re.split(r"(?<=[.!?])\s+", body)
        body = f'<break time="{int(settings.vo_breaks)}ms"/>'.join(parts)
    if settings.vo_rate:
        body = f'<prosody rate="{int(settings.vo_rate)}%">{body}</prosody>'
    return f"<speak>{body}</speak>"


ANCHOR_HINT = re.compile(r'"s\d+(?:%[\d.]+)?(?:[+-][\d.]+)?"')
ANCHOR = re.compile(r"^s(\d+)(?:%(\d+(?:\.\d+)?))?(?:([+-])(\d+(?:\.\d+)?))?$")


def resolve_anchor(value: Any, onsets: list[float], durs: list[float], vo_offset: float) -> Any:
    """``"s3"`` -> onset of sentence 3; ``"s3%40"`` -> 40 percent into it; ``"s3+0.4"`` -> plus 0.4 s."""
    if not isinstance(value, str):
        return value
    m = ANCHOR.match(value.strip())
    if not m:
        return value
    n = int(m.group(1)) - 1
    if n < 0 or n >= len(onsets):
        raise ValueError(f"anchor {value!r}: the VO has {len(onsets)} sentence(s)")
    t = vo_offset + onsets[n]
    if m.group(2):
        t += durs[n] * float(m.group(2)) / 100.0
    if m.group(3):
        t += float(m.group(4)) * (1 if m.group(3) == "+" else -1)
    return round(t, 3)


def resolve_tree(obj: Any, onsets: list[float], durs: list[float], vo_offset: float) -> Any:
    if isinstance(obj, dict):
        return {k: resolve_tree(v, onsets, durs, vo_offset) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_tree(v, onsets, durs, vo_offset) for v in obj]
    return resolve_anchor(obj, onsets, durs, vo_offset)


def resolve_shot(shot: Shot, vo: audio_mod.VoResult | None, gap_ms: int = 350) -> Shot:
    """A copy of the shot with every ``s<N>`` time anchor replaced by a measured (or estimated) second."""
    if vo is not None and vo.onsets:
        onsets, durs = vo.onsets, vo.sentence_durations
    else:
        onsets, durs = audio_mod.estimate_onsets(shot.vo or "", gap_ms)
    return dataclasses.replace(
        shot,
        text=resolve_tree(shot.text, onsets, durs, shot.vo_offset),
        pointers=resolve_tree(shot.pointers, onsets, durs, shot.vo_offset),
        params=resolve_tree(shot.params, onsets, durs, shot.vo_offset),
        raw=resolve_tree(shot.raw, onsets, durs, shot.vo_offset),
    )


def synth_all(shots: list[Shot], settings: Settings, offline: bool = False) -> dict[str, audio_mod.VoResult]:
    synth = audio_mod.Synth(
        settings.vo_cache,
        settings.ffprobe,
        voice=settings.voice,
        engine=settings.engine,
        profile=settings.aws_profile,
        region=settings.aws_region,
        draft=settings.draft and settings.draft_vo != "polly",
        say_voice=settings.say_voice,
        silent=settings.no_vo,
        verbose=settings.verbose,
        offline=offline,
        ffmpeg=settings.ffmpeg,
    )
    out: dict[str, audio_mod.VoResult] = {}
    for s in shots:
        if s.vo:
            if settings.vo_sentences:
                out[s.id] = synth.synth_sentences(
                    s.vo, settings.vo_gap_ms, wrap=lambda x: vo_text(x, settings)
                )
            else:
                out[s.id] = synth.synth(vo_text(s.vo, settings))
    return out


def plan(shots: list[Shot], vo: dict[str, audio_mod.VoResult], settings: Settings) -> list[Placed]:
    placed: list[Placed] = []
    t = 0.0
    for i, s in enumerate(shots):
        v = vo.get(s.id)
        if s.duration == "auto":
            dur = (
                s.vo_offset
                + (v.duration if v else audio_mod.estimate_duration(s.vo or ""))
                + settings.auto_pad
            )
            dur = max(dur, s.min_duration)
        else:
            dur = float(s.duration)
        dur = max(0.5, round(dur * settings.fps) / settings.fps)
        kind = s.transition["kind"]
        tdur = float(s.transition["duration"]) if kind != "cut" else 0.0
        if i > 0 and tdur > 0:
            tdur = min(tdur, placed[-1].duration / 2, dur / 2)
            if not s.transition.get("inside"):
                t -= tdur
        placed.append(Placed(s, max(0.0, t), dur, v, kind, tdur))
        t += dur
    return placed


def total_duration(placed: list[Placed]) -> float:
    return placed[-1].end if placed else 0.0


# --------------------------------------------------------------------------- segments


def rate_cap(w: int, h: int, mbit_at_1080p: float) -> list[str]:
    """``-maxrate/-bufsize`` scaled by pixel area: grain is noise, and without a cap x264 at a
    fixed crf spends 50 to 100 Mbit/s preserving it."""
    mbit = max(2.0, mbit_at_1080p * (w * h) / (1920 * 1080))
    return ["-maxrate", f"{mbit:.1f}M", "-bufsize", f"{2 * mbit:.1f}M"]


class FrameWriter:
    def __init__(
        self,
        ffmpeg: str,
        path: Path,
        w: int,
        h: int,
        fps: int,
        crf: int = 14,
        preset: str = "veryfast",
        cap_mbit: float = 0.0,
    ):
        cap = rate_cap(w, h, cap_mbit) if cap_mbit > 0 else []
        cmd = [
            ffmpeg, "-y", "-v", "error", "-nostdin",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
            "-an", "-c:v", "libx264", "-preset", preset, "-crf", str(crf), *cap, "-pix_fmt", "yuv420p",
            "-r", str(fps), "-movflags", "+faststart", str(path),
        ]  # fmt: skip
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, data: bytes) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(data)

    def close(self, ok: bool = True) -> None:
        assert self.proc.stdin is not None and self.proc.stderr is not None
        try:
            self.proc.stdin.close()
        except (BrokenPipeError, ValueError):
            pass
        err = self.proc.stderr.read()
        self.proc.wait()
        if ok and self.proc.returncode != 0:
            raise RuntimeError(f"ffmpeg encode failed: {err.decode(errors='replace')[-800:]}")


def segment_key(p: Placed, settings: Settings, captions: list[tuple[float, float, str]]) -> str:
    fonts = settings.fonts or draw.Fonts.resolve()
    payload = {
        "v": RENDER_VERSION,
        "shot": {k: v for k, v in p.shot.raw.items() if k not in ("vo", "notes", "transition")},
        "duration": p.duration,
        "size": [settings.width, settings.height, settings.fps],
        "captions": captions,
        "fonts": [fonts.sans, fonts.sans_bold, fonts.mono, fonts.engine],
        "look": [
            settings.ease,
            settings.vignette,
            settings.grain,
            settings.grain_seed,
            settings.grain_size,
            settings.vignette_inner,
        ],
    }
    if any(isinstance(t, dict) and t.get("kind") == "progress_rail" for t in p.shot.text):
        payload["start"] = round(p.start, 3)
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:12]


def captions_for(p: Placed) -> list[tuple[float, float, str]]:
    if not p.shot.vo or p.vo is None:
        return []
    cues = audio_mod.cues_for(p.shot.vo, p.vo_start, p.vo.duration, p.vo.onsets, p.vo.sentence_durations)
    return [(a - p.start, b - p.start, text) for a, b, text in cues]


def render_segment(
    p: Placed,
    settings: Settings,
    base_dir: Path,
    force: bool = False,
    chrome_skip_before: float = 0.0,
    chrome_skip_last: bool = False,
) -> Path:
    seg_dir = settings.build_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    p = Placed(
        resolve_shot(p.shot, p.vo, settings.vo_gap_ms), p.start, p.duration, p.vo, p.trans_kind, p.trans_dur
    )
    captions = captions_for(p) if settings.burn_captions else []
    key = segment_key(p, settings, captions)
    if chrome_skip_before > 0 or chrome_skip_last:
        key = hashlib.sha1(f"{key}|{chrome_skip_before:.4f}|{chrome_skip_last}".encode()).hexdigest()[:12]
    out = seg_dir / f"{p.shot.id}-{key}.mp4"
    n = round(p.duration * settings.fps)
    if out.exists() and not force:
        settings.log(f"  {p.shot.id:<14} {p.shot.kind:<9} {p.duration:6.2f}s  {n:5d} frames  cached")
        return out
    t0 = time.perf_counter()
    canvas = settings.canvas
    post = settings.post
    renderer = ShotRenderer(
        p.shot,
        p.duration,
        canvas,
        settings,
        base_dir,
        captions,
        p.start,
        chrome_skip_before,
        chrome_skip_last,
    )
    tmp = out.with_suffix(".part.mp4")
    writer = FrameWriter(
        settings.ffmpeg, tmp, settings.width, settings.height, settings.fps, cap_mbit=settings.segment_cap
    )
    last_key: Any = object()
    last_bytes = b""
    last_arr: np.ndarray | None = None
    drawn = 0
    try:
        for i in range(n):
            t = i / settings.fps
            k = renderer.key(t)
            if k is not None and k == last_key:
                if post.per_frame and last_arr is not None:
                    writer.write(post.grain_bytes(last_arr, i))
                else:
                    writer.write(last_bytes)
                continue
            img = renderer.frame(t)
            if img.size != (settings.width, settings.height):
                img = img.resize((settings.width, settings.height), Image.Resampling.BILINEAR)
            if post.vig is not None:
                img = post.static(img)
            last_key = k if k is not None else object()
            drawn += 1
            if post.per_frame:
                last_arr = np.asarray(img.convert("RGB"))
                writer.write(post.grain_bytes(last_arr, i))
            else:
                last_bytes = img.tobytes()
                writer.write(last_bytes)
    except BaseException:
        writer.close(ok=False)
        raise
    finally:
        renderer.close()
    writer.close()
    tmp.replace(out)
    dt = time.perf_counter() - t0
    settings.log(
        f"  {p.shot.id:<14} {p.shot.kind:<9} {p.duration:6.2f}s  {n:5d} frames  drew {drawn:5d}  {dt:5.1f}s"
    )
    return out


# --------------------------------------------------------------------------- assembly


def decode_frames(ffmpeg: str, src: Path, start: float, n: int, w: int, h: int) -> np.ndarray:
    """``n`` RGB frames of ``src`` from ``start`` seconds as (n, h, w, 3) uint8; the last frame repeats."""
    cmd = [ffmpeg, "-v", "error", "-nostdin", "-ss", f"{max(0.0, start):.4f}", "-i", str(src),
           "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]  # fmt: skip
    proc = subprocess.run(cmd, capture_output=True, check=True)
    frame_bytes = w * h * 3
    got = len(proc.stdout) // frame_bytes
    arr = np.frombuffer(proc.stdout[: got * frame_bytes], dtype=np.uint8).reshape(got, h, w, 3)
    if got == 0:
        return np.zeros((n, h, w, 3), dtype=np.uint8)
    if got < n:
        arr = np.concatenate([arr, np.repeat(arr[-1:], n - got, axis=0)], axis=0)
    return arr


def render_transition(prev_seg: Path, prev_dur: float, next_seg: Path, p: Placed, settings: Settings) -> Path:
    """A ``push_left``/``push_right``/``whip`` clip over the overlap of two segments (cached)."""
    fps, W, H = settings.fps, settings.width, settings.height
    n = max(1, round(p.trans_dur * fps))
    tr = p.shot.transition
    kind = p.trans_kind
    inside = bool(tr.get("inside"))
    curve = tr.get("ease") or settings.ease or ("linear" if kind in ("dissolve", "fade") else "ease_in_out")
    direction = (
        "right"
        if kind == "push_right"
        else ("left" if kind == "push_left" else str(tr.get("direction", "left")))
    )
    key = hashlib.sha1(
        f"{RENDER_VERSION}|{prev_seg.name}|{next_seg.name}|{kind}|{n}|{curve}|{direction}|{W}x{H}|{inside}"
        f"|chrome|{p.start:.3f}".encode()
    ).hexdigest()[:12]
    out = settings.build_dir / "segments" / f"trans-{p.shot.id}-{key}.mp4"
    if out.exists():
        return out
    chrome = None
    if inside:
        # the global chrome (the rail) is drawn here from the global clock, never pushed with a plate
        shot = resolve_shot(p.shot, p.vo, settings.vo_gap_ms)
        hi = [
            t
            for t in shot.text
            if isinstance(t, dict) and float(t.get("z", 60)) >= draw.OverlayRenderer.GLOBAL_Z
        ]
        if hi:
            chrome = draw.OverlayRenderer(settings.canvas, hi, [], p.duration, None, None, None, p.start)
    if inside:
        # the outgoing shot's final frame, held as a plate under the incoming shot's own first frames
        # seek a hair before the last frame's PTS: a seek at or past it yields no frame at all
        last = decode_frames(settings.ffmpeg, prev_seg, prev_dur - 1.0 / fps - 0.002, 1, W, H)
        a = np.repeat(last[:1], n, axis=0)
    else:
        a = decode_frames(settings.ffmpeg, prev_seg, prev_dur - n / fps, n, W, H)
    b = decode_frames(settings.ffmpeg, next_seg, 0.0, n, W, H)
    tmp = out.with_suffix(".part.mp4")
    writer = FrameWriter(settings.ffmpeg, tmp, W, H, fps, cap_mbit=settings.segment_cap)
    try:
        for i in range(n):
            if kind == "whip":
                frame = fx.whip(a[i], b[i], fx.ease(curve, i / n), fx.ease(curve, (i + 1) / n), direction)
            elif kind in ("dissolve", "fade"):
                frame = fx.dissolve(a[i], b[i], fx.ease(curve, (i + 0.5) / n))
            else:
                frame = fx.push(a[i], b[i], fx.ease(curve, (i + 0.5) / n), direction)
            if chrome is not None:
                frame = np.asarray(chrome.composite(Image.fromarray(frame, "RGB"), i / fps).convert("RGB"))
            writer.write(frame.tobytes())
    except BaseException:
        writer.close(ok=False)
        raise
    writer.close()
    tmp.replace(out)
    return out


def assemble_video(placed: list[Placed], segments: list[Path], settings: Settings, out: Path) -> None:
    fps = settings.fps
    inputs = list(segments)
    trans_index: dict[int, int] = {}
    for i in range(1, len(segments)):
        p = placed[i]
        inside = bool(p.shot.transition.get("inside"))
        if (p.trans_kind in fx.CUSTOM_TRANSITIONS or inside) and p.trans_dur > 0:
            clip = render_transition(segments[i - 1], placed[i - 1].duration, segments[i], p, settings)
            trans_index[i] = len(inputs)
            inputs.append(clip)
    cmd = [settings.ffmpeg, "-y", "-v", "error", "-nostdin"]
    for seg in inputs:
        cmd += ["-i", str(seg)]
    parts: list[str] = []
    for i in range(len(inputs)):
        parts.append(f"[{i}:v]fps={fps},settb=AVTB,format=yuv420p[v{i}]")
    cur = "[v0]"
    cur_len = placed[0].duration
    for i in range(1, len(segments)):
        p = placed[i]
        nxt = f"[c{i}]"
        if p.trans_kind == "cut" or p.trans_dur <= 0:
            parts.append(f"{cur}[v{i}]concat=n=2:v=1:a=0,settb=AVTB{nxt}")
            cur_len += p.duration
        elif i in trans_index and p.shot.transition.get("inside"):
            tn = max(1, round(p.trans_dur * fps)) / fps
            parts.append(f"[v{i}]trim=start={tn:.4f},setpts=PTS-STARTPTS[b{i}]")
            parts.append(f"{cur}[v{trans_index[i]}][b{i}]concat=n=3:v=1:a=0,settb=AVTB{nxt}")
            cur_len += p.duration
        elif i in trans_index:
            tn = max(1, round(p.trans_dur * fps)) / fps
            parts.append(f"{cur}trim=end={max(0.0, cur_len - tn):.4f},setpts=PTS-STARTPTS[a{i}]")
            parts.append(f"[v{i}]trim=start={tn:.4f},setpts=PTS-STARTPTS[b{i}]")
            parts.append(f"[a{i}][v{trans_index[i]}][b{i}]concat=n=3:v=1:a=0,settb=AVTB{nxt}")
            cur_len += p.duration - tn
        else:
            name = XFADE_NAMES.get(p.trans_kind, "fade")
            offset = max(0.0, cur_len - p.trans_dur)
            parts.append(
                f"{cur}[v{i}]xfade=transition={name}:duration={p.trans_dur:.3f}:offset={offset:.3f},settb=AVTB{nxt}"
            )
            cur_len += p.duration - p.trans_dur
        cur = nxt
    fades = []
    first = placed[0]
    fade_in = settings.fade_in
    if first.trans_kind != "cut" and first.trans_kind not in fx.CUSTOM_TRANSITIONS:
        fade_in = max(fade_in, float(first.shot.transition["duration"]))
    if fade_in > 0:
        fades.append(f"fade=t=in:st=0:d={fade_in:.3f}:color=black")
    if settings.fade_out > 0:
        fades.append(
            f"fade=t=out:st={max(0.0, cur_len - settings.fade_out):.3f}:d={settings.fade_out:.3f}:color=black"
        )
    bar = fx.letterbox_bars(settings.width, settings.height, settings.letterbox)
    if bar > 0:
        fades.append(f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill")
        fades.append(f"drawbox=x=0:y={settings.height - bar}:w=iw:h={bar}:color=black:t=fill")
    tail = ",".join(fades) if fades else "null"
    parts.append(f"{cur}{tail}[vout]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[vout]"]
    cap = rate_cap(settings.width, settings.height, settings.grain_cap) if settings.grain > 0 else []
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        *cap,
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-movflags",
        "+faststart",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        graph = ";\n  ".join(parts)
        raise RuntimeError(f"ffmpeg assembly failed:\n{proc.stderr[-2000:]}\nfilter graph:\n  {graph}")


# --------------------------------------------------------------------------- audio


def build_audio(
    placed: list[Placed], settings: Settings, base_dir: Path, wav: Path
) -> list[tuple[float, float, str]]:
    total = total_duration(placed) + 0.05
    mixer = audio_mod.Mixer(total)
    cues: list[tuple[float, float, str]] = []
    for p in placed:
        if p.vo and p.vo.path:
            samples = audio_mod.decode_pcm(settings.ffmpeg, p.vo.path)
            mixer.add_vo(samples, p.vo_start)
        if p.shot.vo and p.vo:
            cues += audio_mod.cues_for(
                p.shot.vo, p.vo_start, p.vo.duration, p.vo.onsets, p.vo.sentence_durations
            )
        if p.shot.kind == "clip" and not p.shot.params.get("mute", False):
            src = _resolve(str(p.shot.params["src"]), base_dir)
            if audio_mod.has_audio_stream(settings.ffprobe, src):
                speed = float(p.shot.params.get("speed", 1.0) or 1.0)
                start = float(p.shot.params.get("start", 0) or 0)
                samples = audio_mod.decode_pcm(
                    settings.ffmpeg, src, start=start, duration=p.duration, speed=speed
                )
                samples = samples[: int(p.duration * audio_mod.SR)]
                mixer.add_bed(samples, p.start, float(p.shot.params.get("gain", 0.0)))
    duck = settings.duck_level - settings.music_level
    if settings.music and settings.music_lufs is not None:
        work = wav.parent
        vo_m = audio_mod.measure_array(settings.ffmpeg, mixer.vo, work / "vo-only.wav")
        if vo_m.get("input_i") not in (None, "-inf"):
            vo_gain = -16.0 - float(vo_m["input_i"])
            mixer.vo *= audio_mod.db(vo_gain)
            settings.log(
                f"  voice pre-normalised {vo_gain:+.1f} dB (measured {float(vo_m['input_i']):.1f} LUFS)"
            )
        music = audio_mod.decode_pcm(settings.ffmpeg, settings.music)
        music_m = audio_mod.measure_loudness(settings.ffmpeg, settings.music)
        music_i = float(music_m.get("input_i", -20.0))
        music = audio_mod.loop_crossfade(music, mixer.n, settings.music_crossfade)
        mixer.add_bed(music, 0.0, settings.music_lufs - music_i)
        under = settings.duck_lufs if settings.duck_lufs is not None else settings.music_lufs - 8
        duck = under - settings.music_lufs
        bed = f"{music_i:.1f} LUFS -> {settings.music_lufs:.0f}, {duck:+.0f} dB under speech"
        settings.log(f"  music {settings.music.name}: {bed}")
    elif settings.music:
        music = audio_mod.decode_pcm(settings.ffmpeg, settings.music)
        music = audio_mod.loop_crossfade(music, mixer.n, settings.music_crossfade)
        mixer.add_bed(music, 0.0, settings.music_level)
    mix = mixer.render(duck_db=duck, tail_fade=max(settings.fade_out, 1.0))
    audio_mod.Mixer.write_wav(wav, mix)
    return cues


def mux(video: Path, wav: Path, out: Path, settings: Settings) -> dict[str, str]:
    measured = audio_mod.measure_loudness(settings.ffmpeg, wav)
    af = audio_mod.loudnorm_filter(measured)
    cmd = [
        settings.ffmpeg, "-y", "-v", "error", "-nostdin", "-i", str(video), "-i", str(wav),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", af,
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(out),
    ]  # fmt: skip
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg mux failed:\n{proc.stderr[-2000:]}")
    return measured


# --------------------------------------------------------------------------- top level


def apply_meta(settings: Settings, meta: dict[str, Any], cli_overrides: set[str]) -> None:
    """Shot-list level keys (voice, engine, music, fade_out, auto_pad) unless the CLI set them."""
    for key in ("voice", "engine", "fade_out", "auto_pad", "music_level", "duck_level", "say_voice"):
        if key in meta and key not in cli_overrides:
            setattr(settings, key, type(getattr(settings, key))(meta[key]))
    for key in ("music_lufs", "duck_lufs", "music_crossfade"):
        if key in meta and key not in cli_overrides and meta[key] is not None:
            setattr(settings, key, float(meta[key]))
    if meta.get("vo_rate") and "vo_rate" not in cli_overrides:
        settings.vo_rate = int(meta["vo_rate"])
    if meta.get("vo_breaks") and "vo_breaks" not in cli_overrides:
        settings.vo_breaks = int(meta["vo_breaks"])
    if "vo_sentences" in meta and "vo_sentences" not in cli_overrides:
        settings.vo_sentences = bool(meta["vo_sentences"])
    if meta.get("vo_gap_ms") and "vo_gap_ms" not in cli_overrides:
        settings.vo_gap_ms = int(meta["vo_gap_ms"])
    if "music" in meta and "music" not in cli_overrides and meta["music"]:
        settings.music = Path(meta["music"])
    # v3 look: default curve, post pass, letterbox, global fade-in, text engine
    if meta.get("ease") and "ease" not in cli_overrides:
        if not fx.is_ease(meta["ease"]):
            raise SystemExit(f"ease must be one of {sorted(fx.EASES)}, not {meta['ease']!r}")
        settings.ease = str(meta["ease"])
    for key in ("vignette", "grain", "letterbox", "fade_in"):
        if meta.get(key) is not None and key not in cli_overrides:
            setattr(settings, key, float(meta[key]))
    if meta.get("vignette_inner") is not None:
        settings.vignette_inner = float(meta["vignette_inner"])
    if isinstance(meta.get("rules"), dict):
        settings.rules = dict(meta["rules"])
    if meta.get("grain_seed") is not None:
        settings.grain_seed = int(meta["grain_seed"])
    if meta.get("grain_size") is not None:
        settings.grain_size = float(meta["grain_size"])
    if meta.get("grain_cap") is not None:
        settings.grain_cap = float(meta["grain_cap"])
    if meta.get("text_engine") and "text_engine" not in cli_overrides:
        settings.text_engine = str(meta["text_engine"])
        fonts = settings.fonts or draw.Fonts.resolve()
        settings.fonts = dataclasses.replace(fonts, engine=draw.text_engine(settings.text_engine))


def build(shot_list: ShotList, settings: Settings, out: Path, force: bool = False) -> Path:
    if shot_list.errors:
        for e in shot_list.errors:
            print(f"error: {e}", file=sys.stderr)
        raise SystemExit(f"{len(shot_list.errors)} schema error(s); fix them or run `check`")
    for w in shot_list.warnings:
        settings.log(f"warning: {w}")
    fit = fit_check(shot_list, settings)
    if fit:
        for f in fit:
            print(f"error: {f}", file=sys.stderr)
        raise SystemExit(f"{len(fit)} text-fit error(s); run `check` for details")
    settings.build_dir.mkdir(parents=True, exist_ok=True)
    base_dir = shot_list.base_dir
    if settings.no_vo:
        vo_desc = "silence"
    elif settings.draft:
        vo_desc = f"say {settings.say_voice}"
    else:
        vo_desc = f"polly {settings.voice}/{settings.engine}"
    settings.log(f"voice-over: {vo_desc}")
    t0 = time.perf_counter()
    vo = synth_all(shot_list.shots, settings)
    for sid, v in vo.items():
        src = "(cached)" if v.cached else f"{v.latency:.2f}s"
        settings.log(f"  vo {sid:<14} {v.duration:5.2f}s  {v.voice}/{v.engine}  {src}")
    placed = plan(shot_list.shots, vo, settings)
    gap_problems = gap_report(placed, settings)
    if gap_problems:
        for g in gap_problems:
            print(f"error: {g}", file=sys.stderr)
        raise SystemExit(f"{len(gap_problems)} sentence boundary(ies) with too little silence")
    size = f"{settings.width}x{settings.height}@{settings.fps}"
    settings.log(f"timeline: {len(placed)} shots, {total_duration(placed):.2f}s at {size}")
    settings.log("segments:")
    segments = []
    for i, p in enumerate(placed):
        skip_before = p.trans_dur if (p.shot.transition.get("inside") and p.trans_dur > 0) else 0.0
        nxt = placed[i + 1] if i + 1 < len(placed) else None
        skip_last = bool(nxt and nxt.shot.transition.get("inside") and nxt.trans_dur > 0)
        segments.append(render_segment(p, settings, base_dir, force, skip_before, skip_last))
    work = settings.build_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    video = work / (out.stem + ".video.mp4")
    settings.log("assembling video ...")
    assemble_video(placed, segments, settings, video)
    wav = work / (out.stem + ".mix.wav")
    settings.log("mixing audio ...")
    cues = build_audio(placed, settings, base_dir, wav)
    srt = out.with_suffix(".srt")
    audio_mod.write_srt(srt, cues)
    settings.log("loudness + mux ...")
    out.parent.mkdir(parents=True, exist_ok=True)
    measured = mux(video, wav, out, settings)
    dur = audio_mod.ffprobe_duration(settings.ffprobe, out)
    li = measured.get("input_i", "?")
    took = time.perf_counter() - t0
    settings.log(f"done: {out} ({dur:.2f}s, input loudness {li} LUFS -> -16) captions {srt}  [{took:.1f}s]")
    return out


def fit_check(shot_list: ShotList, settings: Settings) -> list[str]:
    """Measure every overlay with the real fonts: text must fit its plate, `max_x` and the safe frame."""
    canvas = draw.Canvas(draw.REF_W, draw.REF_H, settings.fonts or draw.Fonts.resolve(), settings.ease)
    problems: list[str] = []
    safe = (draw.SAFE_X, draw.SAFE_Y, draw.REF_W - draw.SAFE_X, draw.REF_H - draw.SAFE_Y)
    base_dir = shot_list.base_dir
    loader = lambda s: load_image(_resolve(s, base_dir), settings.build_dir)  # noqa: E731
    vo = synth_all(shot_list.shots, settings, offline=True)
    for shot in shot_list.shots:
        dur = float(shot.duration) if shot.duration != "auto" else max(shot.min_duration, 30.0)
        try:
            shot = resolve_shot(shot, vo.get(shot.id), settings.vo_gap_ms)
        except ValueError as exc:
            problems.append(f"[{shot.id}] {exc}")
            continue
        for i, spec in enumerate(shot.text):
            try:
                ov = draw.make_overlay(spec, canvas, dur, loader)
                m = ov.measure()
            except Exception as exc:
                problems.append(f"[{shot.id}] text[{i}] could not be measured: {exc}")
                continue
            if m is None:
                continue
            tb = m["text"]
            label = (
                f"[{shot.id}] text[{i}] {str(spec.get('text', spec.get('items', spec.get('kind'))))[:40]!r}"
            )
            outside = tb[0] < safe[0] or tb[1] < safe[1] or tb[2] > safe[2] or tb[3] > safe[3]
            if outside and spec.get("safe", True):
                problems.append(f"{label} runs outside the safe frame: {tb} vs {safe}")
            zone = settings.rules.get("caption_zone")
            if zone and spec.get("safe", True) and not spec.get("caption_zone_ok"):
                z0, z1 = (float(v) for v in (zone if isinstance(zone, (list, tuple)) else (940, 1040)))
                if (
                    tb[3] > z0
                    and tb[1] < z1
                    and spec.get("kind") not in ("spotlight", "progress_rail", "bloom")
                ):
                    problems.append(f"{label} enters the caption zone {int(z0)}..{int(z1)}: {tb}")
            pb = m.get("plate")
            if pb and (tb[0] < pb[0] or tb[1] < pb[1] or tb[2] > pb[2] or tb[3] > pb[3]):
                problems.append(f"{label} wider than its plate: text {tb} vs plate {pb}")
            if spec.get("max_x") is not None and tb[2] > float(spec["max_x"]):
                problems.append(f"{label} ends at x {tb[2]} past max_x {spec['max_x']}")
        if shot.kind == "terminal":
            try:
                term = draw.TerminalSource(canvas, shot.params, dur, base_dir)
            except Exception as exc:
                problems.append(f"[{shot.id}] terminal could not be built: {exc}")
                continue
            for li, width, limit in term.overflowing_lines():
                problems.append(
                    f"[{shot.id}] terminal line {li:02d} is {width} px wide, column is {limit} px"
                )
        if settings.rules.get("one_accent"):
            problems += accent_check(shot, dur, str(settings.rules.get("accent", "orange")))
    return problems


def accent_intervals(shot: Shot, dur: float, accent: str) -> list[tuple[float, float, str]]:
    """(from, to, label) stretches during which a content element is in the accent colour.

    Chrome (``chrome: true``) is exempt and parts sharing an ``accent_group`` count as one element;
    a ``recolor`` away from the accent ends a stretch, a recolour into it starts one; text
    ``highlight`` cues in the accent count from their ``at``.
    """
    out: list[tuple[float, float, str]] = []

    def is_acc(c: Any) -> bool:
        return c is not None and str(c) == accent

    def add(color: Any, recolor: list[dict[str, Any]], t_in: float, t_out: float, label: str) -> None:
        cur = is_acc(color)
        start = t_in if cur else None
        for r in sorted(recolor, key=lambda r: float(r["at"])):
            at = float(r["at"])
            nxt = is_acc(r.get("color"))
            if cur and not nxt and start is not None:
                out.append((start, min(at, t_out), label))
                start = None
            elif not cur and nxt:
                start = at
            cur = nxt
        if start is not None:
            out.append((start, t_out, label))

    def walk(spec: dict[str, Any], label: str) -> None:
        if spec.get("chrome"):
            return
        if spec.get("accent_group"):
            label = f"group:{spec['accent_group']} {label}"
        t_in = float(spec.get("in", 0.0) or 0.0)
        t_out = float(spec.get("out", dur) or dur)
        if spec.get("spans"):
            for sp in spec["spans"]:
                walk({**spec, **sp, "spans": None}, f"{label} span {str(sp.get('text', ''))[:24]!r}")
            return
        add(spec.get("color"), list(spec.get("recolor", []) or []), t_in, t_out, label)
        for h in spec.get("highlight", []) or []:
            if is_acc(h.get("color")):
                out.append(
                    (float(h.get("at", t_in)), t_out, f"{label} highlight {str(h.get('match'))[:24]!r}")
                )
        if spec.get("kind") == "panel" and spec.get("bar") and is_acc(spec["bar"].get("color")):
            out.append((t_in, t_out, f"{label} bar"))
        plate = spec.get("plate")
        if isinstance(plate, dict) and plate.get("bar") and is_acc(plate["bar"].get("color")):
            out.append((t_in, t_out, f"{label} plate bar"))

    for i, spec in enumerate(shot.text):
        walk(spec, f"text[{i}] {str(spec.get('text', spec.get('kind')))[:30]!r}")
    for i, spec in enumerate(shot.pointers):
        walk({**spec, "color": spec.get("color", "orange")}, f"pointers[{i}] {spec.get('kind')}")
    if shot.kind == "terminal":
        for h in shot.params.get("highlight", []) or []:
            if is_acc(h.get("color")):
                out.append((float(h.get("at", 0.0)), dur, f"terminal highlight {str(h.get('match'))[:24]!r}"))
    return out


def accent_check(shot: Shot, dur: float, accent: str, slack: float = 0.25) -> list[str]:
    """The one-accent rule: two content elements in the accent colour must not overlap in time
    by more than ``slack`` seconds (the 240 ms recolour crossfade)."""
    ivs = accent_intervals(shot, dur, accent)
    problems: list[str] = []
    for i in range(len(ivs)):
        for j in range(i + 1, len(ivs)):
            a0, a1, la = ivs[i]
            b0, b1, lb = ivs[j]
            ga = la.split(" ", 1)[0] if la.startswith("group:") else None
            gb = lb.split(" ", 1)[0] if lb.startswith("group:") else None
            if ga is not None and ga == gb:
                continue  # one element in several parts (a callout's dot, leader and label)
            ov = min(a1, b1) - max(a0, b0)
            if ov > slack:
                problems.append(
                    f"[{shot.id}] two {accent} content elements overlap for {ov:.2f}s "
                    f"({max(a0, b0):.2f}..{min(a1, b1):.2f}): {la} and {lb}"
                )
    return problems


def gap_report(placed: list[Placed], settings: Settings, verbose: bool = False) -> list[str]:
    """Measure the silence at every stitched sentence boundary; return the boundaries under min_gap."""
    problems: list[str] = []
    allg: list[float] = []
    rows: list[str] = []
    for p in placed:
        v = p.vo
        if not v or not v.path or len(v.onsets) < 2:
            continue
        gaps = audio_mod.boundary_gaps(audio_mod.decode_pcm(settings.ffmpeg, v.path), v.onsets)
        allg += gaps
        rows.append(f"  {p.shot.id:<22}" + " ".join(f"{g:.2f}" for g in gaps))
        for i, g in enumerate(gaps):
            if g < settings.min_gap:
                problems.append(
                    f"[{p.shot.id}] only {g:.2f}s of silence before sentence {i + 2} (min {settings.min_gap})"
                )
    if verbose and allg:
        import statistics

        print("sentence-boundary silence (s), end of speech to the next lead-in:")
        print("\n".join(rows))
        med = statistics.median(allg)
        print(f"  boundaries {len(allg)}  min {min(allg):.3f}  median {med:.3f}  max {max(allg):.3f}")
    return problems


def check(shot_list: ShotList, settings: Settings, max_total: float = 180.0, max_wpm: float = 170.0) -> int:
    print(f"shot list: {shot_list.path}  ({len(shot_list.shots)} shots)")
    fonts = settings.fonts or draw.Fonts.resolve()
    why = "libraqm present" if fonts.engine == "raqm" else "this Pillow has no libraqm"
    curve = settings.ease or "legacy smooth / ease_out"
    look = f"ease {curve}, vignette {settings.vignette:g}, grain {settings.grain:g}"
    print(f"  text engine: {fonts.engine} ({why}); {look}")
    for w in shot_list.warnings:
        print(f"  warning: {w}")
    for e in shot_list.errors:
        print(f"  error:   {e}")
    fit = fit_check(shot_list, settings)
    for f in fit:
        print(f"  error:   {f}")
    if shot_list.errors or fit:
        print(f"{len(shot_list.errors) + len(fit)} error(s)")
        return 1
    vo = synth_all(shot_list.shots, settings, offline=True)
    placed = plan(shot_list.shots, vo, settings)
    print(f"{'id':<14} {'kind':<9} {'start':>7} {'dur':>6}  {'trans':<13} {'words':>5} {'wpm':>5}  vo")
    problems = 0
    for p in placed:
        v = p.vo
        words = v.words if v else 0
        wpm = words / (p.duration - p.shot.vo_offset) * 60 if words and p.duration > p.shot.vo_offset else 0
        flag = ""
        if (
            v
            and v.engine == "estimate"
            and p.shot.duration != "auto"
            and v.duration + p.shot.vo_offset > p.duration
        ):
            flag = "  <- VO est. longer than shot"
            problems += 1
        elif wpm > max_wpm:
            flag = f"  <- fast (> {max_wpm:.0f} wpm)"
            problems += 1
        est = "~" if v and v.engine == "estimate" else ""
        trans = f"{p.trans_kind}" + (f" {p.trans_dur:.1f}" if p.trans_dur else "")
        line = audio_mod.strip_ssml(p.shot.vo or "")[:48]
        head = f"{p.shot.id:<14} {p.shot.kind:<9} {p.start:7.2f} {est}{p.duration:5.2f}  {trans:<13}"
        print(f"{head} {words:>5} {wpm:>5.0f}  {line}{flag}")
    anchored = [p for p in placed if p.vo and p.vo.onsets and ANCHOR_HINT.search(json.dumps(p.shot.raw))]
    if anchored:
        print("sentence onsets, seconds from the shot start (* = estimated, not yet synthesised):")
        for p in anchored:
            est = "*" if p.vo.engine == "estimate" else ""
            marks = "  ".join(
                f"s{i + 1}={p.shot.vo_offset + on:.2f}{est}" for i, on in enumerate(p.vo.onsets)
            )
            print(f"  {p.shot.id:<22}{marks}")
    gap_problems = gap_report(placed, settings, verbose=True)
    total = total_duration(placed)
    total_words = sum(v.words for v in vo.values())
    basis = "cached" if all(v.engine != "estimate" for v in vo.values()) else "estimated"
    minutes = f"{total / 60:.2f} min, limit {max_total:.0f}s"
    print(f"total: {total:.2f}s ({minutes})  VO words {total_words}  {basis} VO")
    if total > max_total:
        print(f"  error: total {total:.1f}s exceeds {max_total:.0f}s")
        problems += 1
    for g in gap_problems:
        print(f"  error: {g}")
    return 1 if problems or gap_problems else 0


def contact_sheet(
    video: Path, every: float, sheet: Path, settings: Settings, cols: int = 5, thumb_w: int = 384
) -> Path:
    tmp = settings.build_dir / "work" / f"frames-{video.stem}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    dur = audio_mod.ffprobe_duration(settings.ffprobe, video)
    rate = subprocess.run(
        [settings.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
         "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    num, _, den = rate.partition("/")
    fps = float(num) / float(den or 1)
    step = max(1, round(every * fps))
    every = step / fps
    subprocess.run(
        [settings.ffmpeg, "-y", "-v", "error", "-nostdin", "-i", str(video), "-vf",
         f"select=not(mod(n\\,{step})),scale={thumb_w}:-2", "-fps_mode", "vfr", str(tmp / "%04d.png")],
        check=True,
    )  # fmt: skip
    files = sorted(tmp.glob("*.png"))
    if not files:
        raise RuntimeError("no frames extracted")
    first = Image.open(files[0])
    tw, th = first.size
    pad, label_h, header = 12, 26, 56
    rows = math.ceil(len(files) / cols)
    sheet_img = Image.new(
        "RGB", (cols * (tw + pad) + pad, header + rows * (th + label_h + pad) + pad), draw.rgb("bg")
    )
    fonts = settings.fonts or draw.Fonts.resolve()
    f_label = fonts.get("mono", 16)
    f_head = fonts.get("sans_bold", 22)
    d = ImageDraw.Draw(sheet_img)
    d.text(
        (pad, 16),
        f"{video.name}  {dur:.1f}s  every {every:g}s  {len(files)} frames",
        font=f_head,
        fill=draw.rgb("text"),
    )
    for i, fpath in enumerate(files):
        im = Image.open(fpath).convert("RGB")
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = header + r * (th + label_h + pad)
        sheet_img.paste(im, (x, y))
        d.rectangle((x, y, x + tw - 1, y + th - 1), outline=draw.rgb("panel_border"))
        t = i * every
        d.text((x, y + th + 4), f"{int(t // 60):02d}:{t % 60:05.2f}", font=f_label, fill=draw.rgb("muted"))
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet_img.save(sheet)
    return sheet


__all__ = [
    "KINDS",
    "Placed",
    "Settings",
    "Shot",
    "ShotList",
    "ShotRenderer",
    "apply_meta",
    "build",
    "check",
    "contact_sheet",
    "find_ffmpeg",
    "fit_check",
    "gap_report",
    "load_shot_list",
    "plan",
    "render_segment",
    "render_transition",
    "resolve_shot",
    "synth_all",
    "total_duration",
    "vo_text",
]
