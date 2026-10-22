"""Voice-over, music and captions for the demo video renderer.

The voice track comes from Amazon Polly (generative engine, neural then standard as
fallbacks) and is cached by a hash of voice, engine and text so re-rendering a
shot list never pays for the same sentence twice. Draft builds use the macOS
``say`` command or silence instead. Mixing happens in numpy: each VO clip is
placed at its shot's start, clip audio and optional music are ducked under the
voice with a smoothed envelope, and the final loudness is measured for a
two-pass ``loudnorm`` to -16 LUFS. Caption cues for the .srt file are cut from
the same VO text so burned-in and sidecar captions always agree.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

SR = 48000
WORDS_PER_SECOND = 2.6  # estimate when no synthesized clip exists yet
ENGINE_FALLBACKS = {"generative": ["generative", "neural", "standard"], "neural": ["neural", "standard"]}


@dataclass
class VoResult:
    path: Path | None
    duration: float
    voice: str
    engine: str
    latency: float
    cached: bool
    text: str
    onsets: list[float] = field(default_factory=list)  # sentence onsets, seconds from the clip start
    sentence_durations: list[float] = field(default_factory=list)

    @property
    def words(self) -> int:
        return len(strip_ssml(self.text).split())


def split_sentences(text: str) -> list[str]:
    """Split plain VO text at sentence ends (. ! ?) followed by whitespace."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", strip_ssml(text)) if p.strip()]
    return parts or [strip_ssml(text)]


def estimate_onsets(text: str, gap_ms: int = 350, wpm: float = 176.0) -> tuple[list[float], list[float]]:
    """Sentence onsets and durations from word counts, for a shot list checked before synthesis."""
    onsets, durs = [], []
    t = 0.0
    for sent in split_sentences(text):
        d = max(0.4, len(sent.split()) / (wpm / 60.0))
        onsets.append(t)
        durs.append(d)
        t += d + gap_ms / 1000.0
    return onsets, durs


def strip_ssml(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def estimate_duration(text: str) -> float:
    return max(0.8, len(strip_ssml(text).split()) / WORDS_PER_SECOND)


def ffprobe_duration(ffprobe: str, path: Path) -> float:
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def text_hash(*parts: str) -> str:
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- synthesis


class Synth:
    """Synthesise one VO line to a cached audio file."""

    def __init__(
        self,
        cache_dir: Path,
        ffprobe: str,
        voice: str = "Matthew",
        engine: str = "generative",
        profile: str | None = "heisenberg",
        region: str = "us-east-1",
        draft: bool = False,
        say_voice: str = "Samantha",
        silent: bool = False,
        verbose: bool = True,
        offline: bool = False,
        ffmpeg: str = "ffmpeg",
    ):
        self.offline = offline
        self.ffmpeg = ffmpeg
        self.cache_dir = cache_dir
        self.ffprobe = ffprobe
        self.voice = voice
        self.engine = engine
        self.profile = profile
        self.region = region
        self.draft = draft
        self.say_voice = say_voice
        self.silent = silent
        self.verbose = verbose
        self._polly = None
        self._polly_failed = False

    def synth(self, text: str) -> VoResult:
        if self.silent:
            return VoResult(None, estimate_duration(text), "none", "silence", 0.0, True, text)
        if self.draft:
            return self._say(text)
        return self._polly_synth(text)

    def synth_sentences(self, text: str, gap_ms: int = 350, wrap: Any = None) -> VoResult:
        """One Polly call per sentence, stitched with ``gap_ms`` of silence; onsets are measured.

        ``wrap`` turns a plain sentence into the text actually sent (SSML), if any. The stitched
        wav and its onset table are cached by the sentence texts, voice and engine.
        """
        sentences = split_sentences(text)
        sent_texts = [wrap(x) if wrap else x for x in sentences]
        backend = "silence" if self.silent else ("say" if self.draft else "polly")
        key = text_hash("stitched-v2", backend, self.voice, self.engine, str(gap_ms), *sent_texts)
        d = self.cache_dir / "stitched"
        d.mkdir(parents=True, exist_ok=True)
        wav, meta = d / f"{key}.wav", d / f"{key}.json"
        if wav.exists() and meta.exists():
            m = json.loads(meta.read_text())
            return VoResult(
                wav, m["duration"], m["voice"], m["engine"], 0.0, True, text, m["onsets"], m["durations"]
            )
        if self.offline or self.silent:
            onsets, durs = estimate_onsets(text, gap_ms)
            total = onsets[-1] + durs[-1] if onsets else estimate_duration(text)
            return VoResult(None, total, "estimate", "estimate", 0.0, True, text, onsets, durs)
        pieces: list[np.ndarray] = []
        onsets: list[float] = []
        durs: list[float] = []
        gap = np.zeros((int(gap_ms / 1000.0 * SR), 2), dtype=np.float32)
        t = 0.0
        latency = 0.0
        voice, engine = self.voice, self.engine
        for st in sent_texts:
            r = self._say(st) if self.draft else self._polly_synth(st)
            latency += r.latency
            voice, engine = r.voice, r.engine
            if r.path is None:
                samples = np.zeros((int(r.duration * SR), 2), dtype=np.float32)
            else:
                samples = trim_silence(decode_pcm(self.ffmpeg, r.path))
            lead = speech_onset(samples)
            onsets.append(t + lead)
            durs.append(len(samples) / SR - lead)
            pieces.append(samples)
            pieces.append(gap)
            t += len(samples) / SR + gap_ms / 1000.0
        mix = np.concatenate(pieces[:-1]) if pieces else np.zeros((0, 2), dtype=np.float32)
        Mixer.write_wav(wav, mix)
        total = len(mix) / SR
        meta.write_text(
            json.dumps(
                {"voice": voice, "engine": engine, "duration": total, "onsets": onsets, "durations": durs,
                 "sentences": sentences, "text": text},
                indent=2,
            )
        )  # fmt: skip
        return VoResult(wav, total, voice, engine, latency, False, text, onsets, durs)

    def _meta(self, base: Path, result: VoResult) -> None:
        base.with_suffix(".json").write_text(
            json.dumps(
                {
                    "voice": result.voice,
                    "engine": result.engine,
                    "duration": result.duration,
                    "latency": result.latency,
                    "text": result.text,
                },
                indent=2,
            )
        )

    def _cached(self, base: Path, ext: str) -> VoResult | None:
        audio, meta = base.with_suffix(ext), base.with_suffix(".json")
        if audio.exists() and meta.exists():
            m = json.loads(meta.read_text())
            return VoResult(
                audio, float(m["duration"]), m["voice"], m["engine"], float(m["latency"]), True, m["text"]
            )
        return None

    def _say(self, text: str) -> VoResult:
        d = self.cache_dir / "say"
        d.mkdir(parents=True, exist_ok=True)
        base = d / text_hash("say", self.say_voice, text)
        hit = self._cached(base, ".wav")
        if hit:
            return hit
        if not shutil.which("say"):
            return VoResult(None, estimate_duration(text), "none", "silence", 0.0, True, text)
        plain = strip_ssml(text)
        t0 = time.perf_counter()
        subprocess.run(
            [
                "say",
                "-v",
                self.say_voice,
                "-o",
                str(base.with_suffix(".wav")),
                "--data-format=LEI16@22050",
                plain,
            ],
            check=True,
            capture_output=True,
        )
        lat = time.perf_counter() - t0
        res = VoResult(
            base.with_suffix(".wav"),
            ffprobe_duration(self.ffprobe, base.with_suffix(".wav")),
            self.say_voice,
            "say",
            lat,
            False,
            text,
        )
        self._meta(base, res)
        return res

    def _client(self):
        if self._polly is None:
            import boto3

            session = boto3.Session(profile_name=self.profile) if self.profile else boto3.Session()
            self._polly = session.client("polly", region_name=self.region)
        return self._polly

    def _polly_synth(self, text: str) -> VoResult:
        d = self.cache_dir / "polly"
        d.mkdir(parents=True, exist_ok=True)
        for engine in ENGINE_FALLBACKS.get(self.engine, [self.engine]):
            hit = self._cached(d / text_hash("polly", self.voice, engine, text), ".mp3")
            if hit:
                return hit
        if self._polly_failed:
            return (
                self._say(text)
                if shutil.which("say")
                else VoResult(None, estimate_duration(text), "none", "silence", 0.0, True, text)
            )
        is_ssml = text.lstrip().startswith("<speak")
        last_err: Exception | None = None
        for engine in ENGINE_FALLBACKS.get(self.engine, [self.engine]):
            base = d / text_hash("polly", self.voice, engine, text)
            try:
                t0 = time.perf_counter()
                resp = self._client().synthesize_speech(
                    Text=text,
                    TextType="ssml" if is_ssml else "text",
                    VoiceId=self.voice,
                    Engine=engine,
                    OutputFormat="mp3",
                    SampleRate="24000",
                )
                data = resp["AudioStream"].read()
                lat = time.perf_counter() - t0
            except Exception as exc:
                last_err = exc
                if self.verbose:
                    print(f"  polly {self.voice}/{engine} failed: {type(exc).__name__}: {str(exc)[:120]}")
                continue
            base.with_suffix(".mp3").write_bytes(data)
            dur = ffprobe_duration(self.ffprobe, base.with_suffix(".mp3"))
            res = VoResult(base.with_suffix(".mp3"), dur, self.voice, engine, lat, False, text)
            self._meta(base, res)
            return res
        self._polly_failed = True
        if self.verbose:
            print(f"  polly unavailable ({last_err}); falling back to `say`/silence for this build")
        return (
            self._say(text)
            if shutil.which("say")
            else VoResult(None, estimate_duration(text), "none", "silence", 0.0, True, text)
        )


# --------------------------------------------------------------------------- decoding and mixing


def decode_pcm(
    ffmpeg: str,
    path: Path,
    start: float | None = None,
    duration: float | None = None,
    speed: float = 1.0,
    sr: int = SR,
) -> np.ndarray:
    """Decode any audio/video file to float32 stereo samples (n, 2)."""
    cmd = [ffmpeg, "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path), "-vn"]
    filters = []
    if speed and abs(speed - 1.0) > 1e-3:
        s = speed
        while s > 2.0:
            filters.append("atempo=2.0")
            s /= 2.0
        while s < 0.5:
            filters.append("atempo=0.5")
            s /= 0.5
        filters.append(f"atempo={s:.4f}")
    if filters:
        cmd += ["-af", ",".join(filters)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-f", "f32le", "-ac", "2", "-ar", str(sr), "-"]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0 or not proc.stdout:
        return np.zeros((0, 2), dtype=np.float32)
    arr = np.frombuffer(proc.stdout, dtype=np.float32)
    return arr.reshape(-1, 2).copy()


def speech_onset(samples: np.ndarray, threshold_db: float = -40.0, sr: int = SR) -> float:
    """Seconds of lead-in before the first 10 ms window above the threshold."""
    if len(samples) == 0:
        return 0.0
    win = max(1, int(0.01 * sr))
    mono = np.abs(samples).max(axis=1)
    n = len(mono) // win
    if n == 0:
        return 0.0
    rms = np.sqrt((mono[: n * win].reshape(n, win) ** 2).mean(axis=1))
    above = np.flatnonzero(rms > db(threshold_db))
    return float(above[0] * win / sr) if len(above) else 0.0


def trim_silence(
    samples: np.ndarray, threshold_db: float = -50.0, keep: float = 0.12, sr: int = SR
) -> np.ndarray:
    """Drop trailing silence below the threshold, keeping ``keep`` seconds of tail."""
    if len(samples) == 0:
        return samples
    mono = np.abs(samples).max(axis=1)
    above = np.flatnonzero(mono > db(threshold_db))
    if len(above) == 0:
        return samples
    end = min(len(samples), int(above[-1] + keep * sr))
    return samples[:end]


def boundary_gaps(
    samples: np.ndarray, onsets: list[float], threshold_db: float = -45.0, sr: int = SR
) -> list[float]:
    """Seconds of silence (every 10 ms window below the threshold) ending where sentence N+1's
    lead-in starts, for each boundary between stitched sentences."""
    if len(onsets) < 2 or len(samples) == 0:
        return []
    win = max(1, int(0.01 * sr))
    mono = np.abs(samples).max(axis=1)
    n = len(mono) // win
    loud = mono[: n * win].reshape(n, win).max(axis=1) > db(threshold_db)
    out: list[float] = []
    for i in range(len(onsets) - 1):
        k = min(n, int(onsets[i + 1] * sr) // win)
        while k > 0 and loud[k - 1]:
            k -= 1
        j = k
        while j > 0 and not loud[j - 1]:
            j -= 1
        out.append((k - j) * win / sr)
    return out


def has_audio_stream(ffprobe: str, path: Path) -> bool:
    out = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return "audio" in out


def db(gain_db: float) -> float:
    return 10 ** (gain_db / 20)


def fade_edges(x: np.ndarray, seconds: float = 0.08, sr: int = SR) -> np.ndarray:
    n = min(len(x) // 2, int(seconds * sr))
    if n > 0:
        ramp = np.linspace(0, 1, n, dtype=np.float32)[:, None]
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    return x


@dataclass
class Placement:
    samples: np.ndarray
    at: float
    kind: str  # "vo" | "clip" | "music"


class Mixer:
    """Places VO, clip audio and music on a stereo float timeline and writes a WAV."""

    def __init__(self, total: float, sr: int = SR):
        self.sr = sr
        self.n = math.ceil(total * sr)
        self.vo = np.zeros((self.n, 2), dtype=np.float32)
        self.bed = np.zeros((self.n, 2), dtype=np.float32)
        self.vo_mask = np.zeros(self.n, dtype=np.float32)
        self.has_vo = False
        self.has_bed = False

    def _add(self, buf: np.ndarray, samples: np.ndarray, at: float) -> None:
        i0 = max(0, round(at * self.sr))
        if i0 >= self.n or len(samples) == 0:
            return
        seg = samples[: self.n - i0]
        buf[i0 : i0 + len(seg)] += seg

    def add_vo(self, samples: np.ndarray, at: float, gain_db: float = 0.0) -> None:
        self.has_vo = True
        self._add(self.vo, samples * db(gain_db), at)
        i0 = max(0, round(at * self.sr))
        self.vo_mask[i0 : min(self.n, i0 + len(samples))] = 1.0

    def add_bed(self, samples: np.ndarray, at: float, gain_db: float = 0.0) -> None:
        self.has_bed = True
        self._add(self.bed, fade_edges(samples.copy()) * db(gain_db), at)

    def duck_envelope(
        self, duck_db: float, pre: float = 0.15, post: float = 0.45, smooth: float = 0.25
    ) -> np.ndarray:
        """Per-sample gain for the bed: 1.0 when no voice, db(duck) around voice, smoothed."""
        mask = self.vo_mask.copy()
        if mask.any():
            k_pre, k_post = int(pre * self.sr), int(post * self.sr)
            idx = np.flatnonzero(mask)
            grown = np.zeros_like(mask)
            # dilate the mask by pre/post seconds using run boundaries
            runs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
            for r in runs:
                grown[max(0, r[0] - k_pre) : min(self.n, r[-1] + k_post)] = 1.0
            win = max(1, int(smooth * self.sr))
            kernel = np.ones(win, dtype=np.float32) / win
            grown = np.convolve(grown, kernel, mode="same")
            mask = np.clip(grown, 0, 1)
        return 1.0 - mask * (1.0 - db(duck_db))

    def render(self, duck_db: float = -8.0, tail_fade: float = 1.5) -> np.ndarray:
        env = self.duck_envelope(duck_db)[:, None]
        mix = self.vo + self.bed * env
        n = min(self.n, int(tail_fade * self.sr))
        if n > 0 and self.has_bed:
            ramp = np.linspace(1, 0, n, dtype=np.float32)[:, None]
            mix[-n:] *= ramp
        peak = float(np.max(np.abs(mix))) if len(mix) else 0.0
        if peak > 0.98:
            mix *= 0.98 / peak
        return mix

    @staticmethod
    def write_wav(path: Path, mix: np.ndarray, sr: int = SR) -> None:
        pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
        with wave.open(str(path), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())


def loop_to_length(samples: np.ndarray, n: int) -> np.ndarray:
    if len(samples) == 0:
        return np.zeros((n, 2), dtype=np.float32)
    reps = math.ceil(n / len(samples))
    return np.tile(samples, (reps, 1))[:n]


def loop_crossfade(samples: np.ndarray, n: int, xf_seconds: float = 2.0, sr: int = SR) -> np.ndarray:
    """Repeat a loop to n samples with equal-power crossfades of xf_seconds at every seam."""
    length = len(samples)
    if length == 0:
        return np.zeros((n, 2), dtype=np.float32)
    xf = min(int(xf_seconds * sr), length // 3)
    if xf <= 0:
        return loop_to_length(samples, n)
    ramp = np.sin(np.linspace(0, math.pi / 2, xf, dtype=np.float32))[:, None]
    unit = samples.astype(np.float32).copy()
    unit[:xf] *= ramp
    unit[-xf:] *= ramp[::-1]
    out = np.zeros((n + length, 2), dtype=np.float32)
    pos = 0
    while pos < n:
        out[pos : pos + length] += unit
        pos += length - xf
    return out[:n]


def measure_array(ffmpeg: str, samples: np.ndarray, work: Path) -> dict[str, str]:
    """Integrated loudness of an in-memory stereo float buffer (writes a temp wav)."""
    work.parent.mkdir(parents=True, exist_ok=True)
    Mixer.write_wav(work, samples)
    return measure_loudness(ffmpeg, work)


# --------------------------------------------------------------------------- loudness


def measure_loudness(
    ffmpeg: str, wav: Path, target_i: float = -16.0, tp: float = -1.5, lra: float = 11.0
) -> dict[str, str]:
    proc = subprocess.run(
        [
            ffmpeg,
            "-v",
            "info",
            "-nostdin",
            "-i",
            str(wav),
            "-af",
            f"loudnorm=I={target_i}:TP={tp}:LRA={lra}:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.S)
    if not m:
        return {}
    return json.loads(m.group(0))


def loudnorm_filter(
    measured: dict[str, str], target_i: float = -16.0, tp: float = -1.5, lra: float = 11.0
) -> str:
    base = f"loudnorm=I={target_i}:TP={tp}:LRA={lra}"
    if measured and measured.get("input_i") not in (None, "-inf"):
        base += (
            f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}:linear=true"
        )
    return base + ",aresample=48000"


# --------------------------------------------------------------------------- captions


def split_cue(text: str, max_chars: int = 84, width: int = 42) -> list[str]:
    """Split VO text into caption pieces; every piece wraps to at most two lines of ``width``."""
    plain = strip_ssml(text)
    if not plain:
        return []
    sentences = re.split(r"(?<=[.!?;:])\s+", plain)
    pieces: list[str] = []
    for sent in sentences:
        words = sent.split()
        cur: list[str] = []
        for w in words:
            cand = " ".join([*cur, w])
            if cur and (len(cand) > max_chars or len(_wrap_lines(cand, width)) > 2):
                pieces.append(" ".join(cur))
                cur = [w]
            else:
                cur.append(w)
        if cur:
            pieces.append(" ".join(cur))
    # merge short neighbours when they still fit two lines
    merged: list[str] = []
    for piece in pieces:
        if merged:
            cand = f"{merged[-1]} {piece}"
            if (
                len(cand) <= max_chars
                and len(_wrap_lines(cand, width)) <= 2
                and not merged[-1].endswith((".", "!", "?"))
            ):
                merged[-1] = cand
                continue
        merged.append(piece)
    return merged


def _wrap_lines(text: str, width: int = 42) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        cand = w if not cur else f"{cur} {w}"
        if len(cand) <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def cues_for(
    text: str,
    start: float,
    duration: float,
    onsets: list[float] | None = None,
    sent_durs: list[float] | None = None,
) -> list[tuple[float, float, str]]:
    if onsets and sent_durs and len(onsets) == len(split_sentences(text)):
        cues: list[tuple[float, float, str]] = []
        for sent, on, d in zip(split_sentences(text), onsets, sent_durs, strict=True):
            for piece in split_cue(sent):
                cues.append((start + on, start + on + d, piece))
        # long sentences split into pieces share their measured speech window by character
        # count, and no piece is shorter than MIN_CUE seconds (a 0.3 s cue flashes on YouTube)
        out: list[tuple[float, float, str]] = []
        i = 0
        while i < len(cues):
            j = i
            while j + 1 < len(cues) and cues[j + 1][0] == cues[i][0]:
                j += 1
            group = cues[i : j + 1]
            out += share_window(group[0][0], group[0][1], [g[2] for g in group])
            i = j + 1
        return out
    pieces = split_cue(text)
    total = sum(len(p) for p in pieces) or 1
    cues: list[tuple[float, float, str]] = []
    t = start
    for p in pieces:
        d = duration * len(p) / total
        cues.append((t, t + d, p))
        t += d
    return cues


MIN_CUE = 1.0  # seconds; the shortest caption piece written to the SRT


def share_window(t0: float, t1: float, pieces: list[str]) -> list[tuple[float, float, str]]:
    """Cue times for ``pieces`` inside [t0, t1]: proportional to their character counts, every
    piece at least ``MIN_CUE`` long when the window allows it (the longer pieces give way)."""
    if not pieces:
        return []
    window = max(0.0, t1 - t0)
    n = len(pieces)
    if window <= MIN_CUE * n:
        d = window / n
        return [(t0 + k * d, t0 + (k + 1) * d, p) for k, p in enumerate(pieces)]
    total = sum(len(p) for p in pieces) or 1
    durs = [window * len(p) / total for p in pieces]
    for _ in range(n):
        short = [k for k, d in enumerate(durs) if d < MIN_CUE]
        if not short:
            break
        deficit = sum(MIN_CUE - durs[k] for k in short)
        for k in short:
            durs[k] = MIN_CUE
        donors = [k for k, d in enumerate(durs) if d > MIN_CUE]
        spare = sum(durs[k] - MIN_CUE for k in donors)
        for k in donors:
            durs[k] -= deficit * (durs[k] - MIN_CUE) / spare
    out: list[tuple[float, float, str]] = []
    t = t0
    for d, p in zip(durs, pieces, strict=True):
        out.append((t, t + d, p))
        t += d
    return out


def srt_time(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path: Path, cues: list[tuple[float, float, str]]) -> None:
    """Cues hold for at least ``MIN_CUE`` seconds when the next cue leaves room (a short
    sentence or split piece otherwise flashes), and never run into the next cue."""
    lines: list[str] = []
    for i, (a, b, text) in enumerate(cues, 1):
        end = max(b, a + MIN_CUE)
        if i < len(cues):
            end = min(end, cues[i][0] - 0.05)
        end = max(end, a + 0.3)
        wrapped = wrap_caption(text)
        lines += [str(i), f"{srt_time(a)} --> {srt_time(end)}", wrapped, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def wrap_caption(text: str, width: int = 42) -> str:
    return "\n".join(_wrap_lines(text, width))


__all__: list[str] = [
    "SR",
    "Mixer",
    "Synth",
    "VoResult",
    "boundary_gaps",
    "cues_for",
    "decode_pcm",
    "estimate_duration",
    "estimate_onsets",
    "ffprobe_duration",
    "has_audio_stream",
    "loop_crossfade",
    "loop_to_length",
    "loudnorm_filter",
    "measure_array",
    "measure_loudness",
    "speech_onset",
    "split_sentences",
    "strip_ssml",
    "trim_silence",
    "write_srt",
]
