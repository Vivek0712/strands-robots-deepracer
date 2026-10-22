"""Command line for the demo video renderer: build, vo, frames, check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import compose, draw
from .audio import strip_ssml


def _settings(args: argparse.Namespace, cli_set: set[str]) -> compose.Settings:
    s = compose.Settings()
    s.draft = bool(getattr(args, "draft", False))
    if s.draft:
        s.width, s.height, s.fps = 960, 540, 15
    s.ffmpeg = args.ffmpeg or compose.find_ffmpeg("ffmpeg")
    s.ffprobe = args.ffprobe or str(Path(s.ffmpeg).with_name("ffprobe"))
    s.text_engine = getattr(args, "text_engine", None) or "auto"
    s.fonts = draw.Fonts.resolve(args.font_sans, args.font_sans_bold, args.font_mono, engine=s.text_engine)
    s.build_dir = Path(args.build_dir)
    s.vo_cache = Path(args.vo_cache) if args.vo_cache else Path("docs/video/build/vo")
    s.voice = args.voice
    s.engine = args.engine
    s.say_voice = args.say_voice
    s.aws_profile = args.profile
    s.aws_region = args.region
    s.no_vo = bool(getattr(args, "no_vo", False))
    if getattr(args, "vo_rate", None) is not None:
        s.vo_rate = args.vo_rate
    s.draft_vo = getattr(args, "draft_vo", "say")
    s.burn_captions = bool(getattr(args, "burn_captions", False))
    if getattr(args, "music", None):
        s.music = Path(args.music)
    if getattr(args, "music_level", None) is not None:
        s.music_level = args.music_level
    if getattr(args, "duck_level", None) is not None:
        s.duck_level = args.duck_level
    if getattr(args, "music_lufs", None) is not None:
        s.music_lufs = args.music_lufs
    if getattr(args, "duck_lufs", None) is not None:
        s.duck_lufs = args.duck_lufs
    if getattr(args, "fade_out", None) is not None:
        s.fade_out = args.fade_out
    s.verbose = not getattr(args, "quiet", False)
    return s


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("shots", help="shot list (.yaml/.yml or .json)")
    p.add_argument("--build-dir", default="docs/video/build", help="segment cache and work files")
    p.add_argument("--vo-cache", default=None, help="voice-over cache (default docs/video/build/vo)")
    p.add_argument("--voice", default="Matthew", help="Polly voice id (default Matthew)")
    p.add_argument("--engine", default="generative", choices=["generative", "neural", "standard"])
    p.add_argument("--say-voice", default="Samantha", help="macOS `say` voice for --draft")
    p.add_argument(
        "--vo-rate", type=int, default=None, help="SSML prosody rate in percent, e.g. 90 (neural only)"
    )
    p.add_argument("--draft-vo", default="say", choices=["say", "polly"], help="voice used by --draft builds")
    p.add_argument("--profile", default="heisenberg", help="AWS profile for Polly ('' = default chain)")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--ffmpeg", default=None)
    p.add_argument("--ffprobe", default=None)
    p.add_argument("--font-sans", default=None, help="path[:index] of the regular sans font")
    p.add_argument("--font-sans-bold", default=None)
    p.add_argument("--font-mono", default=None)
    p.add_argument(
        "--text-engine",
        default=None,
        choices=["auto", "basic", "raqm"],
        help="Pillow layout engine (default auto)",
    )
    p.add_argument("--quiet", action="store_true")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m docs.video.render", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="render the shot list to an MP4 (+ .srt)")
    _common(b)
    b.add_argument("--out", required=True, help="output .mp4")
    b.add_argument("--draft", action="store_true", help="960x540, 15 fps, macOS `say` instead of Polly")
    b.add_argument(
        "--no-vo", action="store_true", help="no voice-over at all (silent track, estimated durations)"
    )
    b.add_argument("--music", default=None, help="background music file, ducked under the voice")
    b.add_argument(
        "--music-level", type=float, default=None, help="music gain in dB when no one speaks (default -14)"
    )
    b.add_argument(
        "--duck-level", type=float, default=None, help="music gain in dB under the voice (default -22)"
    )
    b.add_argument("--music-lufs", type=float, default=None, help="music bed integrated loudness, e.g. -30")
    b.add_argument("--duck-lufs", type=float, default=None, help="music loudness under speech, e.g. -38")
    b.add_argument("--burn-captions", action="store_true", help="draw the VO captions into the frames")
    b.add_argument(
        "--fade-out", type=float, default=None, help="final fade to black in seconds (default 0.6)"
    )
    b.add_argument("--force", action="store_true", help="ignore the segment cache")

    v = sub.add_parser("vo", help="synthesise every VO line and print durations")
    _common(v)
    v.add_argument("--draft", action="store_true", help="use macOS `say` instead of Polly")

    f = sub.add_parser("frames", help="contact sheet of a rendered video")
    f.add_argument("video")
    f.add_argument("--every", type=float, default=2.0, help="seconds between frames")
    f.add_argument("--sheet", required=True, help="output .png")
    f.add_argument("--cols", type=int, default=5)
    f.add_argument("--build-dir", default="docs/video/build")
    f.add_argument("--ffmpeg", default=None)
    f.add_argument("--ffprobe", default=None)
    f.add_argument("--font-sans", default=None)
    f.add_argument("--font-sans-bold", default=None)
    f.add_argument("--font-mono", default=None)

    c = sub.add_parser("check", help="validate the schema, assets, total length and VO pace")
    _common(c)
    c.add_argument("--max-total", type=float, default=180.0)
    c.add_argument("--max-wpm", type=float, default=170.0)

    args = ap.parse_args(argv)
    cli_set = {
        a.lstrip("-").replace("-", "_").split("=")[0] for a in (argv or sys.argv[1:]) if a.startswith("--")
    }
    if hasattr(args, "profile") and args.profile == "":
        args.profile = None
    for name in ("voice", "engine", "say_voice", "vo_cache", "profile", "region"):
        if not hasattr(args, name):
            setattr(
                args,
                name,
                {
                    "voice": "Matthew",
                    "engine": "generative",
                    "say_voice": "Samantha",
                    "region": "us-east-1",
                }.get(name),
            )
    settings = _settings(args, cli_set)

    if args.cmd == "frames":
        sheet = compose.contact_sheet(
            Path(args.video), args.every, Path(args.sheet), settings, cols=args.cols
        )
        print(sheet)
        return 0

    shot_list = compose.load_shot_list(Path(args.shots))
    compose.apply_meta(settings, shot_list.meta, cli_set)

    if args.cmd == "check":
        return compose.check(shot_list, settings, args.max_total, args.max_wpm)

    if args.cmd == "vo":
        if shot_list.errors:
            for e in shot_list.errors:
                print(f"error: {e}", file=sys.stderr)
            return 1
        vo = compose.synth_all(shot_list.shots, settings)
        total = 0.0
        for sid, r in vo.items():
            total += r.duration
            src = "cached" if r.cached else f"{r.latency:.2f}s"
            line = strip_ssml(r.text)[:60]
            print(f"{sid:<14} {r.duration:6.2f}s  {r.words:3d} words  {r.voice}/{r.engine}  {src}  {line}")
        words = sum(r.words for r in vo.values())
        print(f"total VO {total:.2f}s, {words} words, {words / total * 60 if total else 0:.0f} wpm")
        return 0

    compose.build(shot_list, settings, Path(args.out), force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
