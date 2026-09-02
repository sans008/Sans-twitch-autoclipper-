"""
Downloads a Twitch VOD (or clip) with yt-dlp.
"""
import os
import yt_dlp


def download_vod(url: str, output_dir: str, progress_hook=None) -> dict:
    """
    Downloads the given Twitch URL into output_dir.
    Returns dict with keys: video_path, title, duration, vod_id.
    """
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "source.%(ext)s"),
        # Best video+audio combined, capped at 1080p by default to keep
        # processing fast; bump to 2160/1440 if you want to try for source max.
        "format": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # yt-dlp may adjust the final filename after merge; resolve it.
        video_path = ydl.prepare_filename(info)
        if not video_path.endswith(".mp4"):
            base, _ = os.path.splitext(video_path)
            video_path = base + ".mp4"

    return {
        "video_path": video_path,
        "title": info.get("title", "untitled"),
        "duration": info.get("duration", 0),
        "vod_id": info.get("id", "unknown"),
    }
