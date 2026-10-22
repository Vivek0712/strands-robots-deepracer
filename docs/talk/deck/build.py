# ruff: noqa: E501
"""Assemble the deck: framework + section fragments (in file order) -> index.html, with checks.

Checks: every fragment holds only <section class="slide"> elements, no <script>, no http(s)
image/video sources (the deck must work offline at the venue), every referenced asset exists.
Run: python docs/talk/deck/build.py [--out index.html]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TITLE = "Control, simulate and train robots with natural language"

HEAD = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Natural-Language Robots</title>
<meta name="description" content="{TITLE}: a one-hour talk deck on Physical AI with Strands Agents, strands-robots, Strands Decider, Strands Box and an AWS DeepRacer.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
__CSS__
</style>
</head>
<body>
<div class="progress"></div>
<div class="notes"></div>
<main class="deck">
"""
TAIL = """
</main>
<script>
__JS__
</script>
</body>
</html>
"""

SRC_RE = re.compile(r"""(?:src|href|poster)=["']([^"']+)["']""", re.I)


def check_fragment(name: str, html: str, errors: list[str]) -> int:
    if "<script" in html.lower():
        errors.append(f"{name}: contains a <script> (not allowed in a fragment)")
    body = re.sub(r"<!--.*?-->", "", html, flags=re.S).strip()
    if not body.lower().startswith("<section") and not body.lower().startswith("<style"):
        errors.append(f'{name}: must start with <section class="slide"> (or a scoped <style>)')
    for m in SRC_RE.finditer(html):
        ref = m.group(1)
        if ref.startswith(("http://", "https://")):
            if "fonts.googleapis" in ref or m.group(0).lower().startswith("href"):
                continue  # links are fine; hotlinked media is not
            errors.append(f"{name}: hotlinked media {ref}")
        elif ref.startswith("assets/"):
            if not (HERE / ref).is_file() or (HERE / ref).stat().st_size == 0:
                errors.append(f"{name}: missing or empty asset {ref}")
    return len(re.findall(r"<section\b", html, flags=re.I))


MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".svg": "image/svg+xml", ".mp4": "video/mp4", ".webm": "video/webm",
}


def inline_assets(html: str) -> str:
    """Replace every assets/... reference with a data: URI so the deck is one file."""
    import base64

    def swap(m: re.Match[str]) -> str:
        ref = m.group(2)
        path = HERE / ref
        if not path.is_file():
            return m.group(0)
        mime = MIME.get(path.suffix.lower(), "application/octet-stream")
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'{m.group(1)}="data:{mime};base64,{data}"'

    return re.sub(r"""(src|poster)=["'](assets/[^"']+)["']""", swap, html)


def select_slides(html: str, keep: set[int]) -> str:
    """Keep only the slides whose zero-based index within this fragment is in ``keep``.

    Every ``<style>`` block in the fragment is kept wherever it sits: a slide's scoped styles may
    be written just before that slide, inside the chunk of the slide that precedes it.
    """
    styles = re.findall(r"<style>.*?</style>", html, flags=re.S)
    head, *parts = re.split(r'(?=<section class="slide)', html)
    kept = [part for i, part in enumerate(parts) if i in keep]
    kept = [re.sub(r"<style>.*?</style>", "", part, flags=re.S) for part in kept]
    head = re.sub(r"<style>.*?</style>", "", head, flags=re.S)
    return "\n".join(styles) + head + "".join(kept)


def parse_keep(spec: str) -> dict[str, set[int]]:
    """``"01:0,1,3;02:0,2"`` -> {"01": {0,1,3}, "02": {0,2}} (fragment prefix -> slide indexes)."""
    out: dict[str, set[int]] = {}
    for chunk in spec.split(";"):
        if not chunk.strip():
            continue
        prefix, _, idx = chunk.partition(":")
        out[prefix.strip()] = {int(x) for x in idx.split(",") if x.strip()}
    return out


def build(out: Path, inline: bool = False, keep: dict[str, set[int]] | None = None) -> int:
    css = (HERE / "framework.css").read_text(encoding="utf-8")
    js = (HERE / "framework.js").read_text(encoding="utf-8")
    fragments = sorted((HERE / "sections").glob("*.html"))
    if not fragments:
        print("no sections yet", file=sys.stderr)
        return 1
    errors: list[str] = []
    parts: list[str] = []
    total = 0
    for frag in fragments:
        html = frag.read_text(encoding="utf-8")
        if keep is not None:
            wanted = keep.get(frag.name[:2], set())
            html = select_slides(html, wanted)
        n = check_fragment(frag.name, html, errors)
        total += n
        parts.append(f"<!-- {frag.name}: {n} slides -->\n{html}\n")
        print(f"{frag.name}: {n} slides")
    body = "\n".join(parts)
    if inline:
        body = inline_assets(body)
    doc = HEAD.replace("__CSS__", css) + body + TAIL.replace("__JS__", js)
    out.write_text(doc, encoding="utf-8")
    print(f"{total} slides -> {out} ({out.stat().st_size // 1024} KB)")
    for e in errors:
        print("ERROR", e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "index.html"))
    ap.add_argument("--inline", action="store_true", help="embed every asset as a data: URI (one-file deck)")
    ap.add_argument("--keep", default=None, help='slide subset, e.g. "01:0,1,3;02:0,2" (fragment prefix: indexes)')
    args = ap.parse_args()
    raise SystemExit(build(Path(args.out), inline=args.inline, keep=parse_keep(args.keep) if args.keep else None))
