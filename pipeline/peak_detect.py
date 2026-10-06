"""
Combines audio + chat intensity signals into one timeline, then finds
peaks = "high intensity moments" and turns each into a timeframe.
"""
import numpy as np
from scipy.signal import find_peaks
from scipy.interpolate import interp1d


def combine_and_detect(
    audio: dict,
    chat: dict,
    duration: float,
    audio_weight: float = 0.5,
    chat_weight: float = 0.5,
    pre_roll: float = 8.0,
    post_roll: float = 22.0,
    min_gap_sec: float = 45.0,
    max_moments: int = 20,
) -> list:
    """
    Returns a list of moment dicts: [{start, end, score}, ...] sorted by
    start time, highest-intensity moments first when max_moments truncates.
    """
    common_times = np.arange(0, duration, 1.0)

    audio_interp = _safe_interp(audio["times"], audio["score"], common_times)
    chat_interp = _safe_interp(chat["times"], chat["score"], common_times)

    combined = audio_weight * audio_interp + chat_weight * chat_interp
    combined = _smooth(combined, window=5)

    min_distance = max(1, int(min_gap_sec))
    peak_idx, props = find_peaks(
        combined,
        distance=min_distance,
        prominence=0.08,
    )

    peaks = [(common_times[i], combined[i]) for i in peak_idx]
    peaks.sort(key=lambda p: p[1], reverse=True)
    peaks = peaks[:max_moments]
    peaks.sort(key=lambda p: p[0])

    moments = []
    for t, score in peaks:
        start = max(0.0, t - pre_roll)
        end = min(duration, t + post_roll)
        moments.append({"start": round(start, 2), "end": round(end, 2), "score": round(float(score), 4)})

    return _merge_overlapping(moments)


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


def _merge_overlapping(moments: list) -> list:
    if not moments:
        return []
    merged = [moments[0]]
    for m in moments[1:]:
        last = merged[-1]
        if m["start"] <= last["end"]:
            last["end"] = max(last["end"], m["end"])
            last["score"] = max(last["score"], m["score"])
        else:
            merged.append(m)
    return merged
