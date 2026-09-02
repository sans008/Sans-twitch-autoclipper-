"""
Cuts and encodes each detected high-intensity window into a standalone
clip at up to 1080p (or higher if the source supports it), plus a
thumbnail for the gallery UI.
"""
import os
import subprocess


def get_source_height(video_path: str) -> int:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=height", "-of", "csv=p=0", video_path,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    try:
        return int(out)
    except ValueError:
        return 1080


def make_clip(video_path: str, start: float, end: float, out_path: str,
               target_height: int = 1080) -> str:
    duration = max(0.1, end - start)
    source_h = get_source_height(video_path)
    height = min(target_height, source_h) if source_h else target_height
    # only scale down, never upscale quality
    scale_filter = f"scale=-2:{height}" if height < source_h else "scale=-2:{}".format(source_h)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start), "-i", video_path, "-t", str(duration),
        "-vf", scale_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-c:a", "aac", "-b:a", "160k",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def make_thumbnail(clip_path: str, out_path: str, at_sec: float = 1.0) -> str:
    cmd = [
        "ffmpeg", "-y", "-ss", str(at_sec), "-i", clip_path,
        "-frames:v", "1", "-vf", "scale=320:-2", out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def process_clips(video_path: str, clips: list, output_dir: str, target_height: int = 1080) -> list:
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for i, c in enumerate(clips):
        clip_name = f"clip_{i+1:02d}.mp4"
        thumb_name = f"clip_{i+1:02d}.jpg"
        clip_path = os.path.join(output_dir, clip_name)
        thumb_path = os.path.join(output_dir, thumb_name)

        make_clip(video_path, c["start"], c["end"], clip_path, target_height)
        make_thumbnail(clip_path, thumb_path)

        results.append({
            **c,
            "file": clip_name,
            "thumb": thumb_name,
            "duration": round(c["end"] - c["start"], 1),
        })
    return results
