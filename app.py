"""
Twitch Auto-Clipper -- local Flask app.

Run with:  python app.py
Then open: http://localhost:5000
"""
import os
import threading
import traceback
import uuid
from functools import wraps

from flask import Flask, jsonify, render_template, request, send_from_directory

from pipeline.download import download_vod
from pipeline.audio_analysis import analyze_audio
from pipeline.visual_analysis import analyze_visual
from pipeline.peak_detect import combine_and_detect
from pipeline.clip import process_clips

app = Flask(__name__)

# If set, every request needs this as a URL param (?key=...) or the UI's
# password field. Leave APP_PASSWORD unset for local/private-network use.
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


OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_ROOT, exist_ok=True)

# In-memory job store. Fine for a local single-user tool; swap for a real
# queue/db if this ever needs to run multi-user or survive restarts.
JOBS = {}


def _set_status(job_id, stage, pct=None, error=None, clips=None):
    JOBS[job_id].update({
        "stage": stage,
        "pct": pct if pct is not None else JOBS[job_id].get("pct", 0),
        "error": error,
        "clips": clips if clips is not None else JOBS[job_id].get("clips"),
    })


def run_job(job_id: str, url: str, target_height: int, audio_weight: float,
            clip_length: int, max_clips: int):
    job_dir = os.path.join(OUTPUT_ROOT, job_id)
    try:
        _set_status(job_id, "downloading", 5)

        def hook(d):
            if d.get("status") == "downloading":
                pct = d.get("_percent_str", "0%").strip().replace("%", "")
                try:
                    _set_status(job_id, "downloading", 5 + float(pct) * 0.35)
                except ValueError:
                    pass

        info = download_vod(url, job_dir, progress_hook=hook)
        video_path = info["video_path"]

        _set_status(job_id, "analyzing audio", 45)
        audio = analyze_audio(video_path)

        _set_status(job_id, "analyzing motion", 60)
        visual = analyze_visual(video_path)

        _set_status(job_id, "finding high-intensity moments", 75)
        pre_roll = clip_length * 0.3
        post_roll = clip_length * 0.7
        clips = combine_and_detect(
            audio, visual, duration=info["duration"],
            audio_weight=audio_weight, visual_weight=1 - audio_weight,
            pre_roll=pre_roll, post_roll=post_roll,
            max_clips=max_clips,
        )

        if not clips:
            _set_status(job_id, "done", 100, error="No high-intensity moments found. Try lowering sensitivity.")
            return

        _set_status(job_id, "cutting clips", 85)
        results = process_clips(video_path, clips, job_dir, target_height=target_height)

        _set_status(job_id, "done", 100, clips=results)
        JOBS[job_id]["title"] = info["title"]
    except Exception as e:
        traceback.print_exc()
        _set_status(job_id, "error", JOBS[job_id].get("pct", 0), error=str(e))


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
    JOBS[job_id] = {"stage": "queued", "pct": 0, "error": None, "clips": None}

    thread = threading.Thread(
        target=run_job,
        args=(
            job_id, url,
            int(data.get("target_height", 1080)),
            float(data.get("audio_weight", 0.6)),
            int(data.get("clip_length", 30)),
            int(data.get("max_clips", 15)),
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


@app.route("/clips/<job_id>/<filename>")
@require_password
def serve_clip(job_id, filename):
    return send_from_directory(os.path.join(OUTPUT_ROOT, job_id), filename)


if __name__ == "__main__":
    # host=0.0.0.0 so it's reachable from outside the server itself.
    # Render (and most PaaS hosts) inject the port to bind via $PORT --
    # falls back to 5000 for local/VPS use where nothing sets it.
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
