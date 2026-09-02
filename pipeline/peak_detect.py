"""
Combines audio + visual intensity signals into one timeline, then finds
peaks = "high intensity moments" and turns each into a clip window.
"""
import numpy as np
from scipy.signal import find_peaks
from scipy.interpolate import interp1d


def combine_and_detect(
    audio: dict,
    visual: dict,
    duration: float,
    audio_weight: float = 0.6,
    visual_weight: float = 0.4,
    pre_roll: float = 8.0,
    post_roll: float = 22.0,
    min_gap_sec: float = 45.0,
    max_clips: int = 15,
) -> list:
    """
    Returns a list of clip dicts: [{start, end, score}, ...] sorted by
    start time, highest-intensity moments first when max_clips truncates.
    """
    # Common timeline (1 sample per second) so audio/visual (different
    # native resolutions) can be summed directly.
    common_times = np.arange(0, duration, 1.0)

    audio_interp = _safe_interp(audio["times"], audio["score"], common_times)
    visual_interp = _safe_interp(visual["times"], visual["score"], common_times)

    combined = audio_weight * audio_interp + visual_weight * visual_interp
    combined = _smooth(combined, window=5)

    min_distance = max(1, int(min_gap_sec))
    peak_idx, props = find_peaks(
        combined,
        distance=min_distance,
        prominence=0.08,
    )

    peaks = [(common_times[i], combined[i]) for i in peak_idx]
    # Highest score first, cap to max_clips, then re-sort chronologically
    peaks.sort(key=lambda p: p[1], reverse=True)
    peaks = peaks[:max_clips]
    peaks.sort(key=lambda p: p[0])

    clips = []
    for t, score in peaks:
        start = max(0.0, t - pre_roll)
        end = min(duration, t + post_roll)
        clips.append({"start": round(start, 2), "end": round(end, 2), "score": round(float(score), 4)})

    return _merge_overlapping(clips)


def _safe_interp(x, y, common_times):
    if len(x) < 2:
        return np.zeros_like(common_times)
    f = interp1d(x, y, bounds_error=False, fill_value=0.0)
    return np.nan_to_num(f(common_times))


def _smooth(x, window=5):
    if len(x) < window:
        return x
    kernel = np.ones(window) / window
    return np.convolve(x, kernel, mode="same")


def _merge_overlapping(clips: list) -> list:
    if not clips:
        return []
    merged = [clips[0]]
    for c in clips[1:]:
        last = merged[-1]
        if c["start"] <= last["end"]:
            last["end"] = max(last["end"], c["end"])
            last["score"] = max(last["score"], c["score"])
        else:
            merged.append(c)
    return merged
