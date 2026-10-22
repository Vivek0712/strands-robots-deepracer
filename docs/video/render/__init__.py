"""Deterministic, shot-list driven renderer for the 3-minute hackathon demo video.

Edit the YAML or JSON shot list, run ``.venv/bin/python -m docs.video.render build
shots.yaml --out out.mp4`` and get a 1920x1080 30 fps MP4 with Amazon Polly
voice-over, captions and transitions. ``--draft`` renders 960x540 at 15 fps with
the macOS ``say`` voice for quick iteration. See README.md for the schema.
"""

from .compose import Settings, build, check, contact_sheet, load_shot_list

__version__ = "0.1.0"
__all__ = ["Settings", "__version__", "build", "check", "contact_sheet", "load_shot_list"]
