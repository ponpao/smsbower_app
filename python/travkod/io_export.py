"""Audio import/export: read any soundfile-supported input, write WAV/FLAC/MP3.

MP3 is written via `lameenc` if present, otherwise via an `ffmpeg` fallback; if
neither is available the caller is told to pick a lossless format. Sample-rate
and bit-depth conversion happen here so the DSP engine always works at the source
rate and we resample once, at export.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Optional, Tuple

import numpy as np
import soundfile as sf


_SUBTYPE = {16: "PCM_16", 24: "PCM_24", 32: "FLOAT"}


def read_audio(path: str) -> Tuple[np.ndarray, int]:
    audio, sr = sf.read(path, always_2d=True, dtype="float32")
    return audio, sr


def resample(audio: np.ndarray, sr: int, target_sr: int) -> Tuple[np.ndarray, int]:
    if target_sr is None or target_sr == sr:
        return audio, sr
    from scipy.signal import resample_poly
    from math import gcd
    g = gcd(int(sr), int(target_sr))
    up, down = target_sr // g, sr // g
    out = resample_poly(audio, up, down, axis=0)
    return out.astype(np.float32), target_sr


def export(audio: np.ndarray, sr: int, out_path: str, *,
           fmt: str = "wav", bit_depth: int = 24, target_sr: Optional[int] = None,
           mp3_bitrate: int = 320) -> str:
    fmt = fmt.lower()
    audio, sr = resample(audio, sr, target_sr) if target_sr else (audio, sr)
    audio = np.clip(audio, -1.0, 1.0)

    base = os.path.splitext(out_path)[0]
    if fmt == "wav":
        path = base + ".wav"
        sf.write(path, audio, sr, subtype=_SUBTYPE.get(bit_depth, "PCM_24"))
    elif fmt == "flac":
        path = base + ".flac"
        sub = "PCM_24" if bit_depth >= 24 else "PCM_16"
        sf.write(path, audio, sr, subtype=sub)
    elif fmt == "mp3":
        path = base + ".mp3"
        _write_mp3(audio, sr, path, mp3_bitrate)
    else:
        raise ValueError(f"Unsupported format: {fmt}")
    return path


def _write_mp3(audio: np.ndarray, sr: int, path: str, bitrate: int) -> None:
    try:
        import lameenc  # type: ignore
        pcm16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        enc = lameenc.Encoder()
        enc.set_bit_rate(bitrate)
        enc.set_in_sample_rate(sr)
        enc.set_channels(audio.shape[1])
        enc.set_quality(2)
        data = enc.encode(pcm16.tobytes())
        data += enc.flush()
        with open(path, "wb") as f:
            f.write(data)
        return
    except Exception:
        pass

    if shutil.which("ffmpeg"):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        try:
            sf.write(wav_path, audio, sr, subtype="PCM_16")
            subprocess.run(
                ["ffmpeg", "-y", "-i", wav_path, "-b:a", f"{bitrate}k", path],
                check=True, capture_output=True,
            )
        finally:
            os.unlink(wav_path)
        return

    raise RuntimeError(
        "MP3 export needs `lameenc` (pip install lameenc) or ffmpeg on PATH. "
        "Choose WAV or FLAC for a lossless export instead."
    )


def concat(clips, sr: int, gap_s: float = 0.0) -> np.ndarray:
    """Merge multiple (audio, sr) clips into one array (Merge > One File)."""
    parts = []
    gap = np.zeros((int(sr * gap_s), 2), dtype=np.float32) if gap_s > 0 else None
    for i, (audio, csr) in enumerate(clips):
        a, _ = resample(audio, csr, sr) if csr != sr else (audio, sr)
        if a.shape[1] == 1:
            a = np.repeat(a, 2, axis=1)
        parts.append(a.astype(np.float32))
        if gap is not None and i < len(clips) - 1:
            parts.append(gap)
    return np.concatenate(parts, axis=0)
