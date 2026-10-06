"""
Hype Moment Finder -- local Flask app.

Paste a Twitch VOD link. It downloads ONLY the audio (not the video --
20-50x smaller) plus the chat replay, finds where chat floods and/or
audio spikes happen, and gives you a list of timestamps with direct
links into the VOD at that moment. You do the clipping yourself from
there -- this just tells you where to look.

Run with:  python app.py
Then open: http://localhost:5000
"""
import os
import re
import shutil
import threading
import traceback
import uuid
from functools import wraps

from flask import Flask, jsonify, render_template, request

from pipeline.download import download_audio_only
from pipeline.audio_analysis import analyze_audio
from pipeline.chat_analysis import analyze_chat
from pipeline.peak_detect import combine_and_detect

app = Flask(__name__)

APP_PASSWORD = os.environ.get("APP_PASSWORD")


def require_password(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not APP_PASSWORD:
            return fn(*args, **kwargs)
        supplied = request.args.get("key") or (request.json or {}).get("key") if request.is_json else request.args.get("key")
        if supplied != APP_PASSWORD:
            return jsonify({"error": "wrong or missing key"}), 401
        return fn(*args, **kwargs)
    return wrapped


TMP_ROOT = os.path.join(os.path.dirname(__file__), "tmp")
os.makedirs(TMP_ROOT, exist_ok=True)

JOBS = {}


def _set_status(job_id, stage, pct=None, error=None, moments=None):
    JOBS[job_id].update({
        "stage": stage,
        "pct": pct if pct is not None else JOBS[job_id].get("pct", 0),
        "error": error,
        "moments": moments if moments is not None else JOBS[job_id].get("moments"),
    })


def _extract_vod_id(url: str) -> str:
    m = re.search(r"videos/(\d+)", url)
    return m.group(1) if m else ""


def _format_hms(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m}m{s}s" if h else f"{m}m{s}s"


def run_job(job_id: str, url: str, audio_weight: float, chat_weight: float,
            window_sec: int, max_moments: int):
    job_dir = os.path.join(TMP_ROOT, job_id)
    try:
        _set_status(job_id, "downloading audio", 5)

        def hook(d):
            if d.get("status") == "downloading":
                pct = d.get("_percent_str", "0%").strip().replace("%", "")
                try:
                    _set_status(job_id, "downloading audio", 5 + float(pct) * 0.25)
                except ValueError:
                    pass

        info = download_audio_only(url, job_dir, progress_hook=hook)
        audio_path = info["audio_path"]
        duration = info["duration"] or 1

        _set_status(job_id, "analyzing audio", 35)
        audio = analyze_audio(audio_path)

        _set_status(job_id, "reading chat replay", 55)
        chat = analyze_chat(url, duration)

        _set_status(job_id, "finding hype moments", 85)
        pre_roll = window_sec * 0.3
        post_roll = window_sec * 0.7
        moments = combine_and_detect(
            audio, chat, duration=duration,
            audio_weight=audio_weight, chat_weight=chat_weight,
            pre_roll=pre_roll, post_roll=post_roll,
            max_moments=max_moments,
        )

        vod_id = info.get("vod_id") or _extract_vod_id(url)
        for m in moments:
            m["timestamp"] = _format_hms(m["start"])
            m["link"] = f"https://www.twitch.tv/videos/{vod_id}?t={m['timestamp']}" if vod_id else None

        if not moments:
            _set_status(job_id, "done", 100, error="No standout hype moments found. Try lowering sensitivity or a different VOD.")
        else:
            _set_status(job_id, "done", 100, moments=moments)
            JOBS[job_id]["title"] = info["title"]
    except Exception as e:
        traceback.print_exc()
        _set_status(job_id, "error", JOBS[job_id].get("pct", 0), error=str(e))
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@app.route("/")
def index():
    return render_template("index.html", needs_key=bool(APP_PASSWORD))


@app.route("/api/start", methods=["POST"])
@require_password
def start():
    data = request.json
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"stage": "queued", "pct": 0, "error": None, "moments": None}

    thread = threading.Thread(
        target=run_job,
        args=(
            job_id, url,
            float(data.get("audio_weight", 0.5)),
            float(data.get("chat_weight", 0.5)),
            int(data.get("window_sec", 30)),
            int(data.get("max_moments", 20)),
        ),
        daemon=True,
    )
    thread.start()
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
@require_password
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(job)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
