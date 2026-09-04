"""
Audio intensity signal: RMS energy + spectral-flux "onset" strength,
deviation from a rolling local baseline (not a global one -- a naturally
loud game shouldn't false-positive just because it's loud throughout).

Computed by streaming raw PCM straight out of an ffmpeg pipe, one small
window at a time -- never loads the whole track into memory. This matters
on memory-constrained hosts (e.g. a 512MB free-tier server): librosa's
approach of loading the full signal + computing a full mel-spectrogram at
once can peak well over a gigabyte on a longer VOD.
"""
import subprocess

import numpy as np


WINDOW_SEC = 0.5          # analysis window size
BASELINE_WINDOW_SEC = 90  # rolling baseline window (local, not global)
SR = 16000                # sample rate for analysis -- plenty for energy/flux,
                           # keeps each window's FFT small


def analyze_audio(video_path: str, sr: int = SR) -> dict:
    """
    Returns dict with:
      times: np.ndarray of timestamps (seconds)
      score: np.ndarray of normalized 0-1 audio intensity per timestamp
    """
    window_samples = int(WINDOW_SEC * sr)
    bytes_per_window = window_samples * 2  # s16le = 2 bytes/sample

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-ac", "1", "-ar", str(sr),
        "-f", "s16le", "-acodec", "pcm_s16le", "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    rms_list = []
    flux_list = []
    prev_spectrum = None

    try:
        while True:
            chunk = proc.stdout.read(bytes_per_window)
            # drop a short trailing partial window rather than pad it
            if not chunk or len(chunk) < bytes_per_window // 2:
                break
            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0

            rms_list.append(float(np.sqrt(np.mean(samples ** 2))))

            spectrum = np.abs(np.fft.rfft(samples))
            if prev_spectrum is not None and len(prev_spectrum) == len(spectrum):
                flux_list.append(float(np.sum(np.clip(spectrum - prev_spectrum, 0, None))))
            else:
                flux_list.append(0.0)
            prev_spectrum = spectrum
    finally:
        proc.stdout.close()
        proc.wait()

    rms_arr = np.array(rms_list, dtype=np.float64)
    flux_arr = np.array(flux_list, dtype=np.float64)
    times = np.arange(len(rms_arr)) * WINDOW_SEC

    if len(rms_arr) == 0:
        return {"times": np.array([0.0]), "score": np.array([0.0])}

    def norm(x):
        x = x - x.min()
        return x / x.max() if x.max() > 0 else x

    raw = 0.5 * norm(rms_arr) + 0.5 * norm(flux_arr)

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
