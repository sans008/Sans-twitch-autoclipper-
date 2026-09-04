"""
Visual intensity signal: frame-differencing / motion magnitude.

Reads frames straight out of an ffmpeg pipe that's already downsampled to
a low FPS and small resolution (ffmpeg does the heavy decode+downscale
work in optimized C, not Python) -- this avoids decoding every single
frame of the source video just to throw most of them away, which is what
made this stage painfully slow on a CPU-constrained host (a free-tier
server's fraction-of-a-core CPU has to fully decode the whole framerate
otherwise, even though we only need ~1.5 samples/sec).
"""
import subprocess

import numpy as np


SAMPLE_FPS = 1.5  # frames per second to sample for motion analysis
WIDTH, HEIGHT = 160, 90  # small on purpose -- we only need motion magnitude


def analyze_visual(video_path: str) -> dict:
    """
    Returns dict with:
      times: np.ndarray of timestamps (seconds)
      score: np.ndarray of normalized 0-1 motion intensity per timestamp
    """
    frame_bytes = WIDTH * HEIGHT  # 1 byte/pixel, grayscale

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={SAMPLE_FPS},scale={WIDTH}:{HEIGHT}",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    diffs = []
    prev = None

    try:
        while True:
            chunk = proc.stdout.read(frame_bytes)
            if not chunk or len(chunk) < frame_bytes:
                break
            frame = np.frombuffer(chunk, dtype=np.uint8).astype(np.int16)
            if prev is not None:
                diffs.append(float(np.mean(np.abs(frame - prev))))
            prev = frame
    finally:
        proc.stdout.close()
        proc.wait()

    diffs = np.array(diffs, dtype=np.float64)
    times = np.arange(len(diffs)) / SAMPLE_FPS

    if len(diffs) == 0:
        return {"times": np.array([0.0]), "score": np.array([0.0])}

    score = diffs - diffs.min()
    score = score / score.max() if score.max() > 0 else score

    return {"times": times, "score": score}
