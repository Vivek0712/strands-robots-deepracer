"""Render a cover candidate: headless Chrome at 2x, downsample, vignette, grain.

Usage: python3 render.py A [B C ...]
Reads cover-<X>.html next to this file, writes
docs/video/build/cover-candidates/cover-<X>.png and cover-<X>-300.png.
"""
import subprocess, sys, pathlib
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parents[4] / "docs/video/build/cover-candidates"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1200, 675


def shoot(html: pathlib.Path, png: pathlib.Path) -> Image.Image:
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2", f"--window-size={W},{H}",
                    "--allow-file-access-from-files", "--default-background-color=0b0b10ff",
                    "--virtual-time-budget=3000", f"--screenshot={png}", html.as_uri()],
                   check=True, capture_output=True)
    im = Image.open(png).convert("RGB")
    assert im.size == (2 * W, 2 * H), im.size
    return im.resize((W, H), Image.LANCZOS)


def vignette(a: np.ndarray, inner=0.60, corner=0.18) -> np.ndarray:
    y, x = np.mgrid[0:H, 0:W].astype(float)
    r = np.hypot(x - W / 2, y - H / 2) / np.hypot(W / 2, H / 2)
    t = np.clip((r - inner) / (1 - inner), 0, 1)
    t = t * t * (3 - 2 * t)
    return a * (1 - corner * t)[..., None]


def grain(a: np.ndarray, sigma=3.0, seed=7) -> np.ndarray:
    n = np.random.default_rng(seed).normal(0, sigma, (H, W))
    return a + n[..., None]


def build(tag: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / f"_raw-{tag}.png"
    im = shoot(HERE / f"cover-{tag}.html", raw)
    raw.unlink()
    a = np.asarray(im).astype(float)
    a = grain(vignette(a))
    out = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    out.save(OUT / f"cover-{tag}.png", optimize=True)
    out.resize((300, 169), Image.LANCZOS).save(OUT / f"cover-{tag}-300.png")
    print(tag, out.size)


def sheet() -> None:
    ims = [Image.open(OUT / f"cover-{t}.png") for t in "ABC"]
    pad = 24
    s = Image.new("RGB", (pad + 3 * (600 + pad), 338 + 2 * pad), (20, 20, 26))
    for i, im in enumerate(ims):
        s.paste(im.resize((600, 338), Image.LANCZOS), (pad + i * (600 + pad), pad))
    s.save(OUT / "candidates-sheet.png", optimize=True)


if __name__ == "__main__":
    for t in sys.argv[1:]:
        sheet() if t == "sheet" else build(t)
