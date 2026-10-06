const urlInput = document.getElementById("url");
const accessKeyInput = document.getElementById("access-key");
const startBtn = document.getElementById("start-btn");
const audioWeight = document.getElementById("audio-weight");
const weightHint = document.getElementById("weight-hint");
const windowSec = document.getElementById("window-sec");
const maxMoments = document.getElementById("max-moments");

const progressPanel = document.getElementById("progress-panel");
const resultsPanel = document.getElementById("results-panel");
const stageLabel = document.getElementById("stage-label");
const pctLabel = document.getElementById("pct-label");
const pulseFill = document.getElementById("pulse-fill");
const pulseLine = document.getElementById("pulse-line");
const errorMsg = document.getElementById("error-msg");
const momentList = document.getElementById("moment-list");
const resultsTitle = document.getElementById("results-title");

audioWeight.addEventListener("input", () => {
  const a = Math.round(audioWeight.value * 100);
  weightHint.textContent = `${a}% audio / ${100 - a}% chat`;
});

if (accessKeyInput) {
  const savedKey = localStorage.getItem("accessKey");
  if (savedKey) accessKeyInput.value = savedKey;
  accessKeyInput.addEventListener("input", () => {
    localStorage.setItem("accessKey", accessKeyInput.value.trim());
  });
}

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
      chat_weight: 1 - audioWeight.value,
      window_sec: windowSec.value,
      max_moments: maxMoments.value,
    }),
  });
  const data = await res.json();
  if (data.error) {
    showError(data.error);
    return;
  }
  rememberJob(data.job_id);
  poll(data.job_id);
}

function rememberJob(jobId) {
  localStorage.setItem("activeJobId", jobId);
  const url = new URL(window.location);
  url.searchParams.set("job", jobId);
  window.history.replaceState(null, "", url);
}

function forgetJob() {
  localStorage.removeItem("activeJobId");
  const url = new URL(window.location);
  url.searchParams.delete("job");
  window.history.replaceState(null, "", url);
}

function poll(jobId) {
  const interval = setInterval(async () => {
    const res = await fetch(`/api/status/${jobId}${keyParam()}`);
    const job = await res.json();

    if (res.status === 404) {
      clearInterval(interval);
      stopPulse();
      forgetJob();
      showError("Lost track of this job (the server likely restarted while idle). Please paste the link again to restart.");
      return;
    }

    stageLabel.textContent = job.stage.replace(/_/g, " ");
    pctLabel.textContent = `${Math.round(job.pct)}%`;
    pulseFill.style.width = `${job.pct}%`;

    if (job.error) {
      clearInterval(interval);
      stopPulse();
      forgetJob();
      showError(job.error);
      return;
    }

    if (job.stage === "done" && job.moments) {
      clearInterval(interval);
      stopPulse();
      forgetJob();
      renderResults(job);
    }
  }, 1200);
}

function showError(msg) {
  stopPulse();
  startBtn.disabled = false;
  errorMsg.textContent = msg;
  errorMsg.classList.remove("hidden");
}

function renderResults(job) {
  startBtn.disabled = false;
  progressPanel.classList.add("hidden");
  resultsPanel.classList.remove("hidden");
  resultsTitle.textContent = job.title ? `Hype moments in "${job.title}"` : "Hype Moments";

  momentList.innerHTML = "";
  const sorted = job.moments.slice().sort((a, b) => b.score - a.score);
  sorted.forEach((m, i) => {
    const row = document.createElement(m.link ? "a" : "div");
    row.className = "moment-row";
    if (m.link) {
      row.href = m.link;
      row.target = "_blank";
      row.rel = "noopener";
    }
    row.innerHTML = `
      <span class="moment-rank">${i + 1}</span>
      <span class="moment-time">${m.timestamp}</span>
      <span class="moment-bar-track"><span class="moment-bar-fill" style="width:${Math.round(m.score * 100)}%"></span></span>
      <span class="moment-score">${Math.round(m.score * 100)}</span>
      ${m.link ? '<span class="moment-go">Open ›</span>' : ""}
    `;
    momentList.appendChild(row);
  });
}

(function resumeIfActive() {
  const params = new URLSearchParams(window.location.search);
  const jobId = params.get("job") || localStorage.getItem("activeJobId");
  if (!jobId) return;

  progressPanel.classList.remove("hidden");
  stageLabel.textContent = "reconnecting";
  startBtn.disabled = true;
  animatePulse();
  poll(jobId);
})();
