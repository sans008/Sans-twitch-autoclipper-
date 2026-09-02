"""
Audio intensity signal: RMS energy + onset strength, deviation from a
rolling local baseline (not a global one -- a naturally loud game
shouldn't false-positive just because it's loud throughout).
"""
import os
import subprocess
import tempfile

import numpy as np
import librosa


WINDOW_SEC = 0.5          # RMS window size
BASELINE_WINDOW_SEC = 90  # rolling baseline window (local, not global)


def _extract_audio_wav(video_path: str, sr: int) -> str:
    """ffmpeg is far more reliable than librosa/soundfile at reading audio
    out of arbitrary video containers, so always go through it first."""
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", str(sr), wav_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return wav_path


def analyze_audio(video_path: str, sr: int = 22050) -> dict:
    """
    Returns dict with:
      times: np.ndarray of timestamps (seconds)
      score: np.ndarray of normalized 0-1 audio intensity per timestamp
    """
    wav_path = _extract_audio_wav(video_path, sr)
    try:
        y, sr = librosa.load(wav_path, sr=sr, mono=True)
    finally:
        os.remove(wav_path)

    hop_length = int(WINDOW_SEC * sr)
    rms = librosa.feature.rms(y=y, frame_length=hop_length * 2, hop_length=hop_length)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

    # Align lengths (rms/onset can differ by a frame or two)
    n = min(len(rms), len(onset_env))
    rms, onset_env = rms[:n], onset_env[:n]
    times = librosa.frames_to_time(np.arange(n), sr=sr, hop_length=hop_length)

    # Normalize each 0-1 independently, then combine
    def norm(x):
        x = x - x.min()
        return x / x.max() if x.max() > 0 else x

    rms_n = norm(rms)
    onset_n = norm(onset_env)
    raw = 0.5 * rms_n + 0.5 * onset_n

    # Rolling local baseline subtraction: flag deviation, not raw loudness
    baseline_frames = max(1, int(BASELINE_WINDOW_SEC / WINDOW_SEC))
    baseline = _rolling_median(raw, baseline_frames)
    deviation = np.clip(raw - baseline, 0, None)
    score = norm(deviation)

    return {"times": times, "score": score}


def _rolling_median(x: np.ndarray, window: int) -> np.ndarray:
    half = window // 2
    out = np.empty_like(x)
    for i in range(len(x)):
        lo, hi = max(0, i - half), min(len(x), i + half + 1)
        out[i] = np.median(x[lo:hi])
    return out
