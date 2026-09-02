"""
Visual intensity signal: frame-differencing / motion magnitude, sampled
at a low FPS (full-framerate analysis is wasteful and slow). Catches
fast camera movement, on-screen action, quick cuts.
"""
import cv2
import numpy as np


SAMPLE_FPS = 1.5  # frames per second to sample for motion analysis


def analyze_visual(video_path: str) -> dict:
    """
    Returns dict with:
      times: np.ndarray of timestamps (seconds)
      score: np.ndarray of normalized 0-1 motion intensity per timestamp
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_interval = max(1, int(round(fps / SAMPLE_FPS)))

    times, diffs = [], []
    prev_gray = None
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            small = cv2.resize(frame, (160, 90))  # downscale, we only need magnitude
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                diffs.append(float(np.mean(diff)))
                times.append(frame_idx / fps)
            prev_gray = gray
        frame_idx += 1

    cap.release()

    diffs = np.array(diffs, dtype=np.float64)
    times = np.array(times, dtype=np.float64)

    if len(diffs) == 0:
        return {"times": np.array([0.0]), "score": np.array([0.0])}

    score = diffs - diffs.min()
    score = score / score.max() if score.max() > 0 else score

    return {"times": times, "score": score}
