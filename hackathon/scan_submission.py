"""Scan a Strands Decider 2B hackathon submission the way a first-pass judge would.

This script reads a repository and its Builder Center article and asks the same questions a
judge, or the scanner that runs ahead of one, would ask: does the agent use Strands Decider 2B
through a Strands InterventionHandler, is it paired with Amazon Bedrock, is there a reusable
decision pattern a stranger could drop into their own agent, does the article carry the right
tags and a cover of the right size, does the submission package name its pattern and its video,
and is there anything in the tree that should never be public. Every check prints PASS, WARN or
FAIL with the evidence it found, and the report ends with a fix list ordered by how much each
item is worth. The rubric score at the bottom is a heuristic for shortlisting, not the judges'
number. Stdlib only, Python 3.12.

Usage::

    python hackathon/scan_submission.py --repo . --article docs/article/article.md \\
        [--json out.json] [--md out.md] [--byline "Name, Title"] [--tags a,b] [--no-pytest] \\
        [--include-untracked]

Exit code 1 when any check FAILs, 0 otherwise.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import struct
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

# -- configuration -----------------------------------------------------------------------------

DEFAULT_BYLINE = "Vivek Raja, AWS AI Hero"
DEFAULT_TAGS = ("strands-decider-2b", "guardrails")
PATTERN_DIR = Path("patterns/strands")
PATTERN_FILES = ("_client.py", "tool_call_intervention.py", "README.md")
README_SECTIONS = (
    "What it does",
    "Architecture",
    "Quick start",
    "The decision handed to Decider 2B",
    "Reusable pattern",
    "Safety",
    "Strands stack",
    "Hackathon submission",
    "License",
)
STRANDS_FAMILY = (
    "strands-agents",
    "strands-robots",
    "strands.bidi",
    "strands-harness",
    "Strands Box",
    "strands-decider",
)
DECIDER_MARKERS = (
    "/v1/systemone",
    "strands-decider",
    "strands_decider",
    "StrandsAgents/strands-decider-2B",
    '"noul"',
    '"choice"',
    '"score"',
)
BEDROCK_MARKERS = (
    "BedrockModel",
    "strands.models.bedrock",
    "anthropic.claude",
    "amazon.nova",
    "us.anthropic",
    "bedrock-runtime",
    "nova-sonic",
)
TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".sh",
    ".cedar",
    ".ipynb",
    ".ts",
    ".tsx",
    ".js",
    ".css",
    ".html",
    ".env",
    ".example",
    ".cfg",
    ".ini",
    ".service",
    ".rst",
    ".csv",
    ".jsonl",
}
CODE_EXTENSIONS = {
    ".py",
    ".sh",
    ".ts",
    ".tsx",
    ".js",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".cedar",
    ".example",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp", ".tiff"}
PEOPLE_WORDS = ("frame", "person", "people", "audience", "photo")
APPROVED_PHOTO_GLOB = "docs/article/img/event-*.jpg"
PLACEHOLDER_MARKERS = ("[TESTIMONIALS", "[REPO URL", "TODO", "TBD")
PLACEHOLDER_VALUES = re.compile(
    r"^\s*(\"\"|''|<[^>]*>|\$\{[^}]*\}|\.\.\.|changeme|redacted|xxx+|your[-_ ]|\*+)?\s*$", re.I
)
MAX_TEXT_BYTES = 2_000_000
MAX_EVIDENCE = 12

# -- data model --------------------------------------------------------------------------------

Status = str  # "PASS" | "WARN" | "FAIL"
Bucket = str  # "creativity" | "decider" | "communication" | "originality" | "gate"
BUCKET_MAX = {"creativity": 30, "decider": 30, "communication": 25, "originality": 15}
STATUS_FACTOR = {"PASS": 1.0, "WARN": 0.5, "FAIL": 0.0}
STATUS_RANK = {"FAIL": 0, "WARN": 1, "PASS": 2}


@dataclass
class Check:
    """One named check: its verdict, the evidence lines behind it, and what it is worth."""

    name: str
    title: str
    status: Status
    weight: int
    bucket: Bucket
    gate: bool = False
    evidence: list[str] = field(default_factory=list)
    fix: str = ""

    def add(self, line: str) -> None:
        if len(self.evidence) < MAX_EVIDENCE:
            self.evidence.append(line)
        elif len(self.evidence) == MAX_EVIDENCE:
            self.evidence.append("... (more omitted)")


@dataclass
class Context:
    """Everything the checks read: the repo, the tracked file list and a text cache."""

    repo: Path
    article: Path
    byline: str
    required_tags: tuple[str, ...]
    run_pytest: bool
    include_untracked: bool = False
    files: list[Path] = field(default_factory=list)
    _text: dict[Path, str] = field(default_factory=dict)

    def text(self, rel: Path) -> str:
        if rel not in self._text:
            path = self.repo / rel
            try:
                if path.stat().st_size > MAX_TEXT_BYTES:
                    self._text[rel] = ""
                else:
                    self._text[rel] = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                self._text[rel] = ""
        return self._text[rel]

    def text_files(self) -> Iterable[Path]:
        for rel in self.files:
            if rel.suffix.lower() in TEXT_EXTENSIONS or rel.name in {"Makefile", "LICENSE", "AGENTS.md"}:
                yield rel

    def grep(
        self, needle: str, files: Iterable[Path] | None = None, regex: bool = False
    ) -> list[tuple[Path, int, str]]:
        """Return (file, line number, line) for every line containing the needle."""
        pattern = re.compile(needle) if regex else None
        hits: list[tuple[Path, int, str]] = []
        for rel in files if files is not None else self.text_files():
            for i, line in enumerate(self.text(rel).splitlines(), 1):
                found = pattern.search(line) if pattern else needle in line
                if found:
                    hits.append((rel, i, line.strip()))
        return hits


# -- helpers -----------------------------------------------------------------------------------


def tracked_files(repo: Path, include_untracked: bool = False) -> list[Path]:
    """`git ls-files` when available, else a walk that skips the usual build and venv dirs.

    Tracked files are what a judge sees after the push. ``include_untracked`` adds files that
    are on disk but not yet committed (still honouring .gitignore), to preview the next round.
    """
    cmd = ["git", "ls-files", "-z"]
    if include_untracked:
        cmd += ["--cached", "--others", "--exclude-standard"]
    try:
        out = subprocess.run(cmd, cwd=repo, capture_output=True, check=True, timeout=30).stdout.decode(
            "utf-8", "ignore"
        )
        files = [Path(p) for p in out.split("\0") if p]
        if files:
            return files
    except (OSError, subprocess.SubprocessError):
        pass
    skip = {".git", ".venv", "node_modules", "__pycache__", "dist", ".mypy_cache", ".ruff_cache"}
    files = []
    for path in repo.rglob("*"):
        if path.is_file() and not (set(path.relative_to(repo).parts) & skip):
            files.append(path.relative_to(repo))
    return files


def worst(statuses: Iterable[Status]) -> Status:
    ranked = sorted(statuses, key=lambda s: STATUS_RANK[s])
    return ranked[0] if ranked else "PASS"


def image_size(path: Path) -> tuple[int, int] | None:
    """Width and height from a PNG IHDR or a JPEG SOF marker, without any image library."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height, width = struct.unpack(">HH", data[i + 5 : i + 9])
                return width, height
            seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
            i += 2 + seg_len
    return None


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split a Markdown file into its `---` front matter (flat key: value) and the body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return meta, "\n".join(lines[idx + 1 :])
        if ":" in lines[idx]:
            key, _, value = lines[idx].partition(":")
            meta[key.strip().lower()] = value.strip().strip('"').strip("'")
    return meta, text


def split_tags(raw: str) -> list[str]:
    raw = raw.strip().strip("[]")
    return [t.strip().strip('"').strip("'").lstrip("#").lower() for t in raw.split(",") if t.strip()]


def headings(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^#{1,6}\s+(.+)$", text, re.M)]


def word_count(text: str) -> int:
    body = re.sub(r"```.*?```", " ", text, flags=re.S)
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", body)
    return len(re.findall(r"\b\w+\b", body))


# -- checks: one function per check --------------------------------------------------------------


def check_decider_usage(ctx: Context) -> Check:
    """Does the code talk to Strands Decider 2B by its official names and question types?"""
    c = Check("decider_usage", "Decider 2B usage", "PASS", 10, "decider", gate=True)
    code = [f for f in ctx.text_files() if f.suffix == ".py" and not f.parts[0].startswith("hackathon")]
    found = 0
    for marker in DECIDER_MARKERS:
        hits = ctx.grep(marker, code)
        if hits:
            found += 1
            rel, line, _ = hits[0]
            c.add(f"{marker}: {len(hits)} hit(s), first {rel}:{line}")
        else:
            c.add(f"{marker}: not found in .py files")
    if found == 0:
        c.status, c.fix = "FAIL", "Reference the Decider server (/v1/systemone) and typed questions in code."
    elif found < 4:
        c.status, c.fix = (
            "WARN",
            "Use the official names (strands-decider, noul/choice/score) so a scanner matches them.",
        )
    return c


def check_intervention_handler(ctx: Context) -> Check:
    """Is the decision wired through a Strands InterventionHandler with before_tool_call?"""
    c = Check("intervention_handler", "InterventionHandler wiring", "PASS", 10, "decider", gate=True)
    code = [f for f in ctx.text_files() if f.suffix == ".py" and not f.parts[0].startswith("hackathon")]
    subclasses = ctx.grep(r"class\s+\w+\(.*InterventionHandler.*\)", code, regex=True)
    hooks = ctx.grep(r"def\s+before_tool_call\s*\(", code, regex=True)
    imports = ctx.grep(r"from\s+strands\.interventions\s+import\s+.*", code, regex=True)
    names = set()
    for _, _, line in imports:
        for name in ("Proceed", "Guide", "Deny", "Confirm"):
            if re.search(rf"\b{name}\b", line):
                names.add(name)
    for rel, line, text in subclasses[:4]:
        c.add(f"subclass {rel}:{line}: {text}")
    for rel, line, _ in hooks[:4]:
        c.add(f"before_tool_call {rel}:{line}")
    c.add(f"imported from strands.interventions: {', '.join(sorted(names)) or 'none'}")
    if not subclasses or not hooks:
        c.status, c.fix = (
            "FAIL",
            "Add an InterventionHandler subclass defining before_tool_call(self, event, **kwargs).",
        )
    elif len(names) < 3:
        c.status, c.fix = (
            "WARN",
            "Import Proceed, Guide, Deny and Confirm from strands.interventions and use them.",
        )
    return c


def check_bedrock(ctx: Context) -> Check:
    """Is the agent's language model on Amazon Bedrock?"""
    c = Check("bedrock_pairing", "Amazon Bedrock pairing", "PASS", 8, "decider", gate=True)
    code = [
        f
        for f in ctx.text_files()
        if f.suffix in {".py", ".ipynb"} and not f.parts[0].startswith("hackathon")
    ]
    found = 0
    for marker in BEDROCK_MARKERS:
        hits = ctx.grep(marker, code)
        if hits:
            found += 1
            rel, line, _ = hits[0]
            c.add(f"{marker}: {len(hits)} hit(s), first {rel}:{line}")
    if found == 0:
        c.status, c.fix = (
            "FAIL",
            "Build the agent on strands.models.bedrock.BedrockModel with a Bedrock model id.",
        )
    elif found < 2:
        c.status, c.fix = (
            "WARN",
            "Name BedrockModel and the model id explicitly so the pairing is machine-readable.",
        )
    return c


def check_reusable_pattern(ctx: Context) -> Check:
    """Does patterns/strands/ hold the drop-in client, the intervention and a how-to README?"""
    c = Check("reusable_pattern", "Reusable decision pattern folder", "PASS", 10, "decider", gate=True)
    missing = []
    for name in PATTERN_FILES:
        rel = PATTERN_DIR / name
        if (ctx.repo / rel).is_file():
            c.add(f"present: {rel}")
        else:
            missing.append(str(rel))
            c.add(f"missing: {rel}")
    readme = ctx.text(PATTERN_DIR / "README.md").lower()
    howto = ("how to use" in readme) or ("drop" in readme)
    c.add(f"README has a how-to-use / drop-in note: {howto}")
    pattern_py = "\n".join(ctx.text(PATTERN_DIR / n) for n in PATTERN_FILES if n.endswith(".py"))
    json_printed = bool(re.search(r"json\.dumps\(\s*QUESTIONS", pattern_py)) or bool(
        re.search(
            r"```json[\s\S]*?\"type\"\s*:\s*\"(noul|choice|score)\"", ctx.text(PATTERN_DIR / "README.md")
        )
    )
    c.add(f"question set shown as JSON (json.dumps(QUESTIONS) or a ```json block): {json_printed}")
    if missing:
        c.status = "FAIL"
        c.fix = f"Create {', '.join(missing)} mirroring upstream examples/strands/."
    elif not howto or not json_printed:
        c.status, c.fix = (
            "WARN",
            "Add a 'How to use' section and print the QUESTIONS dict as JSON in the pattern README.",
        )
    return c


def check_strands_family(ctx: Context) -> Check:
    """Informational: which Strands projects the README names (breadth reads as creativity)."""
    c = Check("strands_family", "Strands family coverage (informational)", "PASS", 3, "creativity")
    readme = ctx.text(Path("README.md")).lower()
    hits = [name for name in STRANDS_FAMILY if name.lower() in readme]
    c.add(f"README mentions {len(hits)}/{len(STRANDS_FAMILY)}: {', '.join(hits) or 'none'}")
    if "strands-decider" not in hits:
        c.status, c.fix = "WARN", "Name strands-decider in the README so the Decider dependency is visible."
    elif len(hits) < 3:
        c.status, c.fix = "WARN", "List each Strands project used and what it contributes."
    return c


def check_readme(ctx: Context) -> Check:
    """Does the README read like a submission: title, hero, badges and the expected sections?"""
    c = Check("readme_quality", "README structure", "PASS", 6, "communication")
    text = ctx.text(Path("README.md"))
    if not text:
        c.status, c.fix = "FAIL", "Write a README.md."
        c.add("README.md missing or empty")
        return c
    heads = headings(text)
    has_title = bool(re.search(r"^#\s+\S|<h1[\s>]", text[:3000], re.M))
    first_section = text.find("\n## ")
    top = text[: first_section if first_section > 0 else 2000]
    hero = bool(re.search(r"!\[[^\]]*\]\([^)]+\)|<img\s", top))
    badges = bool(re.search(r"shields\.io|\[!\[|badge", top, re.I))
    c.add(f"title: {has_title}; hero image above first section: {hero}; badges: {badges}")
    lower_heads = [h.lower() for h in heads]
    missing = [s for s in README_SECTIONS if not any(s.lower() in h for h in lower_heads)]
    present = [s for s in README_SECTIONS if s not in missing]
    c.add(f"sections present ({len(present)}/{len(README_SECTIONS)}): {', '.join(present) or 'none'}")
    if missing:
        c.add(f"sections missing: {', '.join(missing)}")
    if not has_title or len(missing) > 4:
        c.status, c.fix = "FAIL", f"Add README sections: {', '.join(missing)}."
    elif missing or not hero or not badges:
        c.status = "WARN"
        c.fix = (
            "Add the missing README sections, a hero image and badges so the first screen sells the project."
        )
    return c


def check_repo_hygiene_files(ctx: Context) -> Check:
    """LICENSE and a contributor guide (CONTRIBUTING or AGENTS) at the root."""
    c = Check("license_and_guides", "LICENSE and contributor guide", "PASS", 3, "originality", gate=True)
    license_files = [f for f in ctx.files if f.name.upper().startswith("LICENSE") and len(f.parts) == 1]
    guides = [f for f in ctx.files if len(f.parts) == 1 and f.stem.upper() in {"CONTRIBUTING", "AGENTS"}]
    c.add(f"LICENSE: {', '.join(map(str, license_files)) or 'missing'}")
    c.add(f"CONTRIBUTING/AGENTS: {', '.join(map(str, guides)) or 'missing'}")
    if not license_files:
        c.status, c.fix = "FAIL", "Add a LICENSE file (a public repo without one is not reusable)."
    elif not guides:
        c.status, c.fix = "WARN", "Add CONTRIBUTING.md or AGENTS.md."
    return c


def check_notebook(ctx: Context) -> Check:
    """A notebook under notebooks/ gives judges a runnable walk-through."""
    c = Check("notebook", "Walk-through notebook", "PASS", 2, "communication")
    nbs = [f for f in ctx.files if f.suffix == ".ipynb" and f.parts[0] == "notebooks"]
    c.add(f"notebooks/*.ipynb: {', '.join(map(str, nbs)) or 'none'}")
    if not nbs:
        c.status, c.fix = (
            "WARN",
            "Add notebooks/<name>.ipynb that calls the pattern against the fake decider.",
        )
    return c


def check_article_front_matter(ctx: Context) -> Check:
    """Builder Center limits: title, description, exactly five tags, a 1200x675 cover."""
    c = Check("article_front_matter", "Article front matter", "PASS", 8, "communication", gate=True)
    path = ctx.repo / ctx.article
    if not path.is_file():
        c.status, c.fix = "FAIL", f"Write the article at {ctx.article}."
        c.add(f"{ctx.article} missing")
        return c
    meta, _ = parse_front_matter(path.read_text(encoding="utf-8", errors="ignore"))
    problems: list[str] = []
    title = meta.get("title", "")
    desc = meta.get("description", "")
    c.add(f"title: {len(title)} chars (limit 255)")
    c.add(f"description: {len(desc)} chars (limit 512)")
    if not title or len(title) > 255:
        problems.append("title missing or over 255 characters")
    if not desc or len(desc) > 512:
        problems.append("description missing or over 512 characters")
    tags = split_tags(meta.get("tags", ""))
    c.add(f"tags ({len(tags)}): {', '.join(tags) or 'none'}")
    if len(tags) != 5:
        problems.append(f"expected exactly 5 tags, found {len(tags)}")
    for required in ctx.required_tags:
        if required.lower() not in tags:
            problems.append(f"tag '{required}' missing")
    cover = meta.get("cover", "")
    if cover:
        cover_path = path.parent / cover
        size = image_size(cover_path) if cover_path.is_file() else None
        c.add(f"cover {cover}: {'missing' if size is None else f'{size[0]}x{size[1]}'} (want 1200x675)")
        if size is None:
            problems.append("cover image missing or unreadable")
        elif size != (1200, 675):
            problems.append(f"cover is {size[0]}x{size[1]}, want 1200x675")
    else:
        problems.append("no cover in front matter")
    for p in problems:
        c.add(f"problem: {p}")
    if problems:
        c.status, c.fix = "FAIL", "Fix the front matter: " + "; ".join(problems) + "."
    return c


def check_article_body(ctx: Context) -> Check:
    """Byline, a heading that names the Decider, no placeholders left, and the word count."""
    c = Check("article_body", "Article body", "PASS", 6, "communication")
    path = ctx.repo / ctx.article
    if not path.is_file():
        c.status, c.fix = "FAIL", f"Write the article at {ctx.article}."
        return c
    text = path.read_text(encoding="utf-8", errors="ignore")
    _, body = parse_front_matter(text)
    byline_ok = ctx.byline in body
    decider_heading = any("decider" in h.lower() for h in headings(body))
    c.add(f"byline '{ctx.byline}': {byline_ok}")
    c.add(f"heading containing 'Decider': {decider_heading}")
    c.add(f"word count (prose, excluding code blocks and image lines): {word_count(body)}")
    placeholders = []
    for i, line in enumerate(text.splitlines(), 1):
        for marker in PLACEHOLDER_MARKERS:
            if marker in line:
                placeholders.append((i, marker))
        if re.match(r"^\s*<\s*[A-Z][A-Z ]+>\s*$", line):
            placeholders.append((i, line.strip()))
    for i, marker in placeholders[:8]:
        c.add(f"placeholder line {i}: {marker}")
    if not byline_ok or not decider_heading:
        c.status, c.fix = "FAIL", "Add the byline and a section heading that names the Decider decision."
    elif placeholders:
        c.status = "WARN"
        c.fix = f"Resolve {len(placeholders)} placeholder(s) in the article before publishing."
    return c


def check_submission_doc(ctx: Context) -> Check:
    """hackathon/SUBMISSION.md: both tags, the declared pattern, repo and video links."""
    c = Check(
        "submission_doc",
        "Submission package (hackathon/SUBMISSION.md)",
        "PASS",
        6,
        "communication",
        gate=True,
    )
    rel = Path("hackathon/SUBMISSION.md")
    text = ctx.text(rel) if (ctx.repo / rel).is_file() else ""
    if not text:
        c.status, c.fix = "FAIL", "Write hackathon/SUBMISSION.md."
        c.add("hackathon/SUBMISSION.md missing")
        return c
    lower = text.lower()
    missing_tags = [t for t in ctx.required_tags if f"#{t.lower()}" not in lower]
    pattern_declared = bool(re.search(r"declared pattern", lower))
    repo_url = re.search(r"https?://(github|gitlab|bitbucket)\.[^\s)>\]]+", text)
    repo_placeholder = "[repo url" in lower
    video_url = re.search(
        r"https?://(www\.)?(youtu\.be|youtube\.com|vimeo\.com|loom\.com|drive\.google\.com)[^\s)>\]]*", text
    )
    video_placeholder = "[video url" in lower
    under_3 = "3 min" in lower or "three min" in lower
    c.add(f"tags present: {', '.join('#' + t for t in ctx.required_tags if t not in missing_tags) or 'none'}")
    c.add(f"declared pattern line: {pattern_declared}")
    c.add(f"repo URL: {'real' if repo_url else ('placeholder' if repo_placeholder else 'missing')}")
    video_state = "real" if video_url else ("placeholder" if video_placeholder else "missing")
    c.add(f"video URL: {video_state}; mentions 3 min: {under_3}")
    if (
        missing_tags
        or not pattern_declared
        or not (repo_url or repo_placeholder)
        or not (video_url or video_placeholder)
    ):
        c.status, c.fix = (
            "FAIL",
            "SUBMISSION.md needs both tags, a 'Declared pattern' line, a repo URL and a video URL.",
        )
    elif not repo_url or not video_url:
        c.status, c.fix = (
            "WARN",
            "Replace the repo and video URL placeholders with the real links before submitting.",
        )
    return c


def check_originality_statement(ctx: Context) -> Check:
    """The package states that the agent is original and unpublished before the hackathon."""
    c = Check("originality_statement", "Originality statement", "PASS", 3, "originality")
    text = ctx.text(Path("hackathon/SUBMISSION.md")).lower()
    ok = "original" in text and (
        "not published" in text or "unpublished" in text or "first published" in text
    )
    c.add(f"SUBMISSION.md states originality and prior non-publication: {ok}")
    if not ok:
        c.status, c.fix = (
            "WARN",
            "State in SUBMISSION.md that the agent is original and was not published before.",
        )
    return c


def check_secrets(ctx: Context) -> Check:
    """Nothing tracked should hold a password, a key, a token or a tracked .env file."""
    c = Check("secrets", "Secrets scan of tracked files", "PASS", 10, "gate", gate=True)
    fails: list[str] = []
    warns: list[str] = []
    for rel in ctx.files:
        if re.search(r"(^|/)\.env(\.local|\.[a-z]+)?$", str(rel)) and not str(rel).endswith(".example"):
            fails.append(f"tracked env file: {rel}")
    for rel in ctx.text_files():
        in_docs = rel.parts[0] == "docs"
        is_code = rel.suffix.lower() in CODE_EXTENSIONS and not in_docs
        for i, line in enumerate(ctx.text(rel).splitlines(), 1):
            if re.search(r"AKIA[0-9A-Z]{16}", line):
                fails.append(f"{rel}:{i}: AWS access key id")
            if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY", line):
                fails.append(f"{rel}:{i}: private key block")
            elif "-----BEGIN" in line:
                warns.append(f"{rel}:{i}: PEM block header")
            if re.search(r"\bsk-[A-Za-z0-9_-]{20,}", line):
                fails.append(f"{rel}:{i}: sk- token")
            if re.search(r"\bhf_[A-Za-z0-9]{20,}", line):
                fails.append(f"{rel}:{i}: Hugging Face token")
            m = re.search(r"DEEPRACER_PASSWORD\s*=\s*(.*)$", line)
            if m and not PLACEHOLDER_VALUES.match(m.group(1)):
                fails.append(f"{rel}:{i}: DEEPRACER_PASSWORD has a value")
            elif not m:
                literal = re.search(r"password\s*[:=]\s*[\"']?([A-Za-z0-9!@%^&*._-]{4,})", line, re.I)
                if literal and not PLACEHOLDER_VALUES.match(literal.group(1)):
                    if not re.search(r"getenv|os\.environ|keychain|\$\{|\$[A-Z_]", line):
                        warns.append(f"{rel}:{i}: password assignment, review")
            if is_code:
                for ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line):
                    octets = [int(o) for o in ip.split(".")]
                    if max(octets) > 255 or ip in {"127.0.0.1", "0.0.0.0", "255.255.255.255"}:
                        continue
                    if not ip.startswith("0."):
                        warns.append(f"{rel}:{i}: IPv4 literal {ip}")
    for f in fails[:MAX_EVIDENCE]:
        c.add("FAIL " + f)
    for w in warns[: max(0, MAX_EVIDENCE - min(len(fails), MAX_EVIDENCE))]:
        c.add("WARN " + w)
    c.add(f"totals: {len(fails)} fail-grade, {len(warns)} warn-grade across {len(ctx.files)} tracked files")
    if fails:
        c.status, c.fix = (
            "FAIL",
            "Remove the secret, rotate it, and purge it from history before the repo goes public.",
        )
    elif warns:
        c.status, c.fix = (
            "WARN",
            "Review each password assignment and IPv4 literal; move values to env or config.",
        )
    return c


def check_people_photos(ctx: Context) -> Check:
    """Images under docs/ whose names suggest people, outside the approved event photos."""
    c = Check("people_photos", "People-photo policy (human review)", "PASS", 2, "gate", gate=True)
    approved = {str(p.relative_to(ctx.repo)) for p in ctx.repo.glob(APPROVED_PHOTO_GLOB)}
    flagged = []
    for rel in ctx.files:
        if rel.suffix.lower() in IMAGE_EXTENSIONS and rel.parts and rel.parts[0] == "docs":
            if str(rel) in approved:
                continue
            if any(w in rel.name.lower() for w in PEOPLE_WORDS):
                flagged.append(str(rel))
    c.add(f"approved event photos: {len(approved)}")
    for f in flagged:
        c.add(f"review: {f}")
    if flagged:
        c.status, c.fix = "WARN", "Open each flagged image; keep it only if no real person is shown."
    return c


def check_tests(ctx: Context) -> Check:
    """Tests exist and pytest can collect them."""
    c = Check("tests", "Tests present and collectable", "PASS", 4, "decider")
    test_files = [f for f in ctx.files if f.parts and f.parts[0] == "tests" and f.name.startswith("test_")]
    c.add(f"test files under tests/: {len(test_files)}")
    if not test_files:
        c.status, c.fix = "FAIL", "Add tests/unit/test_<module>.py covering the gate's refusal table."
        return c
    if not ctx.run_pytest:
        c.add("pytest collection skipped (--no-pytest)")
        return c
    python = ctx.repo / ".venv" / "bin" / "python"
    if not python.exists():
        c.add("pytest collection skipped: .venv/bin/python not found")
        c.status, c.fix = "WARN", "Create the venv (make venv) so the scanner can collect tests."
        return c
    try:
        proc = subprocess.run(
            [str(python), "-m", "pytest", "--collect-only", "-q", "tests/unit"],
            cwd=ctx.repo,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        c.add("pytest collection timed out after 180 s")
        c.status, c.fix = "WARN", "Investigate slow test collection."
        return c
    except OSError as exc:
        c.add(f"pytest could not run: {exc}")
        c.status = "WARN"
        return c
    m = re.search(r"(\d+) tests? collected", proc.stdout + proc.stderr)
    count = int(m.group(1)) if m else 0
    c.add(f"pytest --collect-only tests/unit: {count} tests, exit {proc.returncode}")
    if proc.returncode not in (0, 5) or count == 0:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
        for line in tail:
            c.add(f"pytest: {line}")
        c.status, c.fix = "FAIL", "Fix test collection errors."
    return c


CHECKS: tuple[Callable[[Context], Check], ...] = (
    check_decider_usage,
    check_intervention_handler,
    check_bedrock,
    check_reusable_pattern,
    check_strands_family,
    check_readme,
    check_repo_hygiene_files,
    check_notebook,
    check_article_front_matter,
    check_article_body,
    check_submission_doc,
    check_originality_statement,
    check_secrets,
    check_people_photos,
    check_tests,
)

# -- scoring and report ------------------------------------------------------------------------


def rubric_estimate(checks: list[Check]) -> dict[str, dict[str, float]]:
    """Heuristic: each rubric bucket earns its weight times the fraction of check weight passing."""
    out: dict[str, dict[str, float]] = {}
    for bucket, maximum in BUCKET_MAX.items():
        members = [c for c in checks if c.bucket == bucket]
        total = sum(c.weight for c in members)
        earned = sum(c.weight * STATUS_FACTOR[c.status] for c in members)
        fraction = earned / total if total else 0.0
        out[bucket] = {"max": maximum, "estimate": round(maximum * fraction, 1), "checks": len(members)}
    out["total"] = {
        "max": 100,
        "estimate": round(sum(v["estimate"] for v in out.values()), 1),
        "checks": len(checks),
    }
    return out


def summary_table(checks: list[Check]) -> str:
    rows = ["| Check | Status | Weight | Gate | First evidence |", "|---|---|---|---|---|"]
    for c in checks:
        first = c.evidence[0] if c.evidence else ""
        rows.append(f"| {c.title} | {c.status} | {c.weight} | {'yes' if c.gate else ''} | {first} |")
    return "\n".join(rows)


def render_markdown(ctx: Context, checks: list[Check], score: dict[str, dict[str, float]]) -> str:
    counts = {s: sum(1 for c in checks if c.status == s) for s in ("PASS", "WARN", "FAIL")}
    lines = [
        "# Submission scan",
        "",
        f"Repo: `{str(ctx.repo).replace(str(Path.home()), chr(126))}`  ",
        f"Article: `{ctx.article}`  ",
        f"Generated: {_dt.datetime.now().astimezone().isoformat(timespec='seconds')}  ",
        f"Result: {counts['PASS']} PASS, {counts['WARN']} WARN, {counts['FAIL']} FAIL; "
        f"heuristic rubric estimate {score['total']['estimate']}/100",
        "",
        "## Summary",
        "",
        summary_table(checks),
        "",
        "## Qualification gates",
        "",
        "Hard requirements. Any FAIL here is a likely disqualification regardless of score.",
        "",
    ]
    for c in checks:
        if c.gate:
            lines.append(f"- {c.status}: {c.title}" + (f" ({c.fix})" if c.status != "PASS" and c.fix else ""))
    lines += [
        "",
        "## Estimated rubric score (heuristic)",
        "",
        "This maps check weights onto the official buckets (Creativity 30, Decider 2B 30, Communication 25,",
        "Originality 15). It measures whether the evidence a judge looks for is present, not how good the",
        "work is. Use it to rank rounds against each other, never as a predicted judge score.",
        "",
        "| Bucket | Checks | Estimate | Max |",
        "|---|---|---|---|",
    ]
    for bucket, v in score.items():
        lines.append(f"| {bucket} | {int(v['checks'])} | {v['estimate']} | {int(v['max'])} |")
    lines += ["", "## Fix list (by weight)", ""]
    fixes = sorted((c for c in checks if c.status != "PASS"), key=lambda c: (c.status != "FAIL", -c.weight))
    if not fixes:
        lines.append("Nothing to fix.")
    for c in fixes:
        lines.append(f"- [{c.status}, weight {c.weight}] {c.title}: {c.fix}")
    lines += ["", "## Evidence", ""]
    for c in checks:
        lines.append(f"### {c.title} ({c.status}, weight {c.weight}, bucket {c.bucket})")
        lines.append("")
        lines.extend(f"- {e}" for e in c.evidence)
        lines.append("")
    return "\n".join(lines)


# -- entry point -------------------------------------------------------------------------------


def run(ctx: Context) -> tuple[list[Check], dict[str, dict[str, float]]]:
    ctx.files = tracked_files(ctx.repo, ctx.include_untracked)
    checks = [fn(ctx) for fn in CHECKS]
    return checks, rubric_estimate(checks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", default=".", help="repository root (default: .)")
    parser.add_argument(
        "--article", default="docs/article/article.md", help="article path relative to the repo"
    )
    parser.add_argument("--json", dest="json_out", help="write the full result as JSON here")
    parser.add_argument("--md", dest="md_out", help="write the Markdown report here (it is always printed)")
    parser.add_argument("--byline", default=DEFAULT_BYLINE, help="expected byline line in the article body")
    parser.add_argument(
        "--tags", default=",".join(DEFAULT_TAGS), help="comma-separated tags that must be present"
    )
    parser.add_argument("--no-pytest", action="store_true", help="skip pytest collection")
    parser.add_argument(
        "--include-untracked", action="store_true", help="also scan uncommitted files (next-round preview)"
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    ctx = Context(
        repo=repo,
        article=Path(args.article),
        byline=args.byline,
        required_tags=tuple(t.strip() for t in args.tags.split(",") if t.strip()),
        run_pytest=not args.no_pytest,
        include_untracked=args.include_untracked,
    )
    checks, score = run(ctx)
    report = render_markdown(ctx, checks, score)
    print(report)
    exit_code = 1 if any(c.status == "FAIL" for c in checks) else 0
    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md_out).write_text(report + "\n", encoding="utf-8")
    if args.json_out:
        payload = {
            "repo": str(repo),
            "article": str(ctx.article),
            "generated": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "checks": [asdict(c) for c in checks],
            "score": score,
            "exit_code": exit_code,
        }
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
