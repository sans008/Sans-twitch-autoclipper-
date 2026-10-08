"""
Chat intensity signal: message-rate spikes over the VOD's chat replay.
Hype moments reliably show up as chat "blowing up" (emote spam, caps,
message floods), which is often a stronger and much cheaper signal than
video motion -- and doesn't require downloading any video at all.
"""
import numpy as np
from chat_downloader import ChatDownloader

WINDOW_SEC = 5.0           # bucket size for message-rate counting
BASELINE_WINDOW_SEC = 120  # rolling baseline window (local, not global)


def analyze_chat(vod_url: str, duration: float) -> dict:
    """
    Returns dict with:
      times: np.ndarray of timestamps (seconds)
      score: np.ndarray of normalized 0-1 chat intensity per timestamp
    """
    downloader = ChatDownloader()
    chat = downloader.get_chat(
        vod_url,
        # interruptible_retry's default behavior tries to read a keypress
        # from the terminal between retries (to let you skip the wait) --
        # that crashes hard with "[Errno 1] Operation not permitted" when
        # there's no real terminal attached, which is always true running
        # as a background job on a server. Also cap attempts: the library's
        # default (15, exponential backoff) can wait over an hour total,
        # way too long for what should fail fast if it's going to fail.
        interruptible_retry=False,
        max_attempts=5,
    )
    message_times = []
    for message in chat:
        t = message.get("time_in_seconds")
        if t is not None and t >= 0:
            message_times.append(t)

    return score_from_message_times(message_times, duration)


def score_from_message_times(message_times, duration: float) -> dict:
    """Pure scoring logic, split out from the network fetch above so it's
    directly testable with synthetic timestamps."""
    n_buckets = max(1, int(duration // WINDOW_SEC) + 1)
    counts = np.zeros(n_buckets)
    for t in message_times:
        bucket = min(int(t // WINDOW_SEC), n_buckets - 1)
        counts[bucket] += 1

    times = np.arange(n_buckets) * WINDOW_SEC

    def norm(x):
        x = x - x.min()
        return x / x.max() if x.max() > 0 else x

    raw = norm(counts)

    baseline_buckets = max(1, int(BASELINE_WINDOW_SEC / WINDOW_SEC))
    baseline = _rolling_median(raw, baseline_buckets)
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
