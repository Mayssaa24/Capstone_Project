Chart.defaults.maintainAspectRatio = false;

const $ = (id) => document.getElementById(id);
const charts = {};
let stream = null;

// Labels for the scan-activity trend KPI (value comes from summary.trend)
const TREND = { up: "▲ Rising", down: "▼ Falling", flat: "▬ Stable" };

function esc(text) {
  const d = document.createElement("div");
  d.textContent = text ?? "";
  return d.innerHTML;
}

// "Glass container (Altglascontainer)" -> "Glass container"
function shortLabel(label) {
  return String(label).split(" (")[0];
}

function drawChart(key, canvasId, spec, options = {}) {
  const dataset = { data: spec.values, backgroundColor: spec.colors || "#2f9e6b",
                    borderColor: "#2f9e6b", tension: 0.3, fill: spec.type === "line" };
  if (charts[key]) {
    charts[key].data.labels = spec.labels;
    charts[key].data.datasets[0] = dataset;
    charts[key].update();
    return;
  }

  const scales = spec.type === "doughnut"
    ? {}
    : {
        y: { beginAtZero: true, ticks: { precision: 0 } },
        x: {
          ticks: {
            maxRotation: 0,
            autoSkip: false,
            // Shorten long bin names on the axis; tooltips still show the full name
            callback(value) {
              return shortLabel(this.getLabelForValue(value));
            },
          },
        },
      };

  charts[key] = new Chart($(canvasId), {
    type: spec.type,
    data: { labels: spec.labels, datasets: [dataset] },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: spec.type === "doughnut" } },
      scales,
      ...options,
    },
  });
}

function renderDashboard(data) {
  const s = data.summary;
  $("kpi-total").textContent = s.total;
  $("kpi-rate").textContent = `${s.recycling_rate}%`;
  $("kpi-conf").textContent = `${Math.round(s.average_confidence * 100)}%`;
  $("kpi-trend").textContent = TREND[s.trend] || TREND.flat;
  $("kpi-trend").dataset.trend = TREND[s.trend] ? s.trend : "flat";
  drawChart("materials", "chart-materials", data.charts.materials);
  drawChart("bins", "chart-bins", data.charts.bins);
  drawChart("trend", "chart-trend", data.charts.trend);
}

function renderResult(data) {
  if (data.status === "uncertain") {
    $("result").innerHTML = `<p class="error">${esc(data.message)}</p>`;
    return;
  }
  const d = data.decision, a = data.advice;
  const alts = data.alternatives.map((r) => `${esc(r.label)} (${Math.round(r.confidence * 100)}%)`).join(", ");
  $("result").innerHTML = `
    <span class="badge ${d.recyclable ? "" : "no"}">${esc(d.material)}</span>
    <h3>${esc(d.bin)}</h3>
    <p>Detected: <strong>${esc(d.label)}</strong> · ${Math.round(d.confidence * 100)}% sure</p>
    <p><strong>${esc(a.headline)}</strong></p>
    <ul>${a.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
    <p class="fact">${esc(a.fun_fact)}</p>
    ${alts ? `<small>Also possible: ${alts}</small>` : ""}`;
}

async function sendImage(blob) {
  $("preview").src = URL.createObjectURL(blob);
  $("preview").hidden = false;
  $("result").textContent = "Analysing…";
  document.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    const form = new FormData();
    form.append("image", blob, "photo.jpg");
    const res = await fetch("/api/scan", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error?.message || "Request failed");
    renderResult(data);
    renderDashboard(data.dashboard);
  } catch (err) {
    $("result").innerHTML = `<p class="error">${esc(err.message)}</p>`;
  } finally {
    document.querySelectorAll("button").forEach((b) => (b.disabled = false));
  }
}

function stopCamera() {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
  $("camera-panel").hidden = true;
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    $("capture-input").click();            // phone / old browser fallback
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    $("video").srcObject = stream;
    $("camera-panel").hidden = false;
  } catch {
    $("capture-input").click();            // permission denied -> native camera picker
  }
}

$("camera-btn").onclick = startCamera;
$("cancel-btn").onclick = stopCamera;
$("upload-btn").onclick = () => $("file-input").click();
$("snap-btn").onclick = () => {
  const v = $("video"), c = document.createElement("canvas");
  c.width = v.videoWidth; c.height = v.videoHeight;
  c.getContext("2d").drawImage(v, 0, 0);
  stopCamera();
  c.toBlob((blob) => blob && sendImage(blob), "image/jpeg", 0.9);
};
for (const id of ["file-input", "capture-input"]) {
  $(id).onchange = (e) => { if (e.target.files[0]) sendImage(e.target.files[0]); e.target.value = ""; };
}

fetch("/api/dashboard").then((r) => r.json()).then(renderDashboard).catch(() => {});
