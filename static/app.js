const urlInput = document.getElementById("url");
const accessKeyInput = document.getElementById("access-key");
const startBtn = document.getElementById("start-btn");
const audioWeight = document.getElementById("audio-weight");
const weightHint = document.getElementById("weight-hint");
const clipLength = document.getElementById("clip-length");
const maxClips = document.getElementById("max-clips");
const targetHeight = document.getElementById("target-height");

const progressPanel = document.getElementById("progress-panel");
const resultsPanel = document.getElementById("results-panel");
const stageLabel = document.getElementById("stage-label");
const pctLabel = document.getElementById("pct-label");
const pulseFill = document.getElementById("pulse-fill");
const pulseLine = document.getElementById("pulse-line");
const errorMsg = document.getElementById("error-msg");
const resultsGrid = document.getElementById("results-grid");
const resultsTitle = document.getElementById("results-title");

audioWeight.addEventListener("input", () => {
  const a = Math.round(audioWeight.value * 100);
  weightHint.textContent = `${a}% audio / ${100 - a}% motion`;
});

// Decorative animated waveform while a job runs, just to make "processing"
// feel like what the tool is actually doing (reading an intensity signal).
let pulseTimer = null;
function animatePulse() {
  const points = [];
  const n = 40;
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 400;
    const y = 20 + Math.sin(i * 0.7 + Date.now() / 200) * 8 * Math.random();
    points.push(`${x},${y}`);
  }
  pulseLine.setAttribute("points", points.join(" "));
  pulseTimer = requestAnimationFrame(animatePulse);
}

function stopPulse() {
  if (pulseTimer) cancelAnimationFrame(pulseTimer);
}

startBtn.addEventListener("click", startJob);
urlInput.addEventListener("keydown", (e) => { if (e.key === "Enter") startJob(); });

function keyParam() {
  const k = accessKeyInput ? accessKeyInput.value.trim() : "";
  return k ? `?key=${encodeURIComponent(k)}` : "";
}

async function startJob() {
  const url = urlInput.value.trim();
  if (!url) return;

  startBtn.disabled = true;
  resultsPanel.classList.add("hidden");
  errorMsg.classList.add("hidden");
  progressPanel.classList.remove("hidden");
  stageLabel.textContent = "queued";
  pctLabel.textContent = "0%";
  pulseFill.style.width = "0%";
  animatePulse();

  const res = await fetch(`/api/start${keyParam()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      audio_weight: audioWeight.value,
      clip_length: clipLength.value,
      max_clips: maxClips.value,
      target_height: targetHeight.value,
    }),
  });
  const data = await res.json();
  if (data.error) {
    showError(data.error);
    return;
  }
  poll(data.job_id);
}

function poll(jobId) {
  const interval = setInterval(async () => {
    const res = await fetch(`/api/status/${jobId}${keyParam()}`);
    const job = await res.json();

    stageLabel.textContent = job.stage.replace(/_/g, " ");
    pctLabel.textContent = `${Math.round(job.pct)}%`;
    pulseFill.style.width = `${job.pct}%`;

    if (job.error) {
      clearInterval(interval);
      showError(job.error);
      return;
    }

    if (job.stage === "done" && job.clips) {
      clearInterval(interval);
      stopPulse();
      renderResults(jobId, job);
    }
  }, 1200);
}

function showError(msg) {
  stopPulse();
  startBtn.disabled = false;
  errorMsg.textContent = msg;
  errorMsg.classList.remove("hidden");
}

function renderResults(jobId, job) {
  startBtn.disabled = false;
  progressPanel.classList.add("hidden");
  resultsPanel.classList.remove("hidden");
  resultsTitle.textContent = job.title ? `Clips from "${job.title}"` : "Clips";

  resultsGrid.innerHTML = "";
  job.clips
    .slice()
    .sort((a, b) => b.score - a.score)
    .forEach((clip, i) => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <img src="/clips/${jobId}/${clip.thumb}${keyParam()}" alt="clip ${i + 1} thumbnail">
        <div class="card-body">
          <div class="card-meta">
            <span>${clip.duration}s · ${formatTime(clip.start)}</span>
            <span class="score-tag">${Math.round(clip.score * 100)}</span>
          </div>
          <a class="dl" href="/clips/${jobId}/${clip.file}${keyParam()}" download>Download</a>
        </div>
      `;
      resultsGrid.appendChild(card);
    });
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
