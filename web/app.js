const API = window.BIZCHAT_API || "/api/v1";
const $ = (s) => document.querySelector(s);

const state = { tiles: [], segments: [], active: "revenue", thread: crypto.randomUUID() };

/* ---------- dashboard ---------- */

async function loadDashboard() {
  try {
    const r = await fetch(`${API}/dashboard/summary`);
    if (!r.ok) throw new Error(r.status);
    const d = await r.json();
    state.tiles = d.tiles;
    state.segments = d.segments;
    renderTiles();
    renderTrend();
    renderSegments();
    $("#env").textContent = "connected";
  } catch {
    $("#env").textContent = "backend unreachable";
  }
}

const fmt = (m, v) =>
  m === "churn_rate" || m === "gross_margin"
    ? `${v.toFixed(1)}%`
    : m === "revenue"
    ? `$${(v / 1000).toFixed(1)}k`
    : v.toLocaleString();

function renderTiles() {
  $("#tiles").innerHTML = state.tiles
    .map((t) => {
      // For churn a fall is good, so invert the colour, not the sign.
      const good = t.metric === "churn_rate" ? t.change_pct < 0 : t.change_pct >= 0;
      return `<div class="tile ${t.metric === state.active ? "on" : ""}" data-m="${t.metric}">
        <div class="k">${t.metric.replace("_", " ")}</div>
        <div class="v">${fmt(t.metric, t.latest)}</div>
        <div class="delta ${good ? "up" : "down"}">${t.change_pct >= 0 ? "▲" : "▼"} ${Math.abs(t.change_pct)}% vs ${t.periods[0]}</div>
        <svg class="spark" viewBox="0 0 100 32" preserveAspectRatio="none">
          <polyline points="${spark(t.values)}" fill="none"
            stroke="var(--${good ? "accent-2" : "bad"})" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round"/></svg>
      </div>`;
    })
    .join("");
  document.querySelectorAll(".tile").forEach((el) =>
    el.addEventListener("click", () => {
      state.active = el.dataset.m;
      renderTiles();
      renderTrend();
    })
  );
}

const scale = (vals, h, pad) => {
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  return (v) => h - pad - ((v - min) / span) * (h - pad * 2);
};

function spark(vals) {
  const y = scale(vals, 32, 4);
  return vals.map((v, i) => `${(i / (vals.length - 1)) * 100},${y(v).toFixed(1)}`).join(" ");
}

function renderTrend(series) {
  const t = series || state.tiles.find((x) => x.metric === state.active);
  if (!t) return;
  const W = 600;
  const H = 230;
  const P = 28;
  const y = scale(t.values, H, P);
  const x = (i) => P + (i / (t.values.length - 1)) * (W - P * 2);
  const pts = t.values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map(
      (f) =>
        `<line x1="${P}" x2="${W - P}" y1="${P + f * (H - P * 2)}" y2="${P + f * (H - P * 2)}" stroke="var(--line)" stroke-width="1"/>`
    )
    .join("");
  const dots = t.values
    .map(
      (v, i) =>
        `<circle cx="${x(i)}" cy="${y(v)}" r="3.5" fill="var(--accent)"><title>${t.periods[i]}: ${fmt(t.metric, v)}</title></circle>`
    )
    .join("");
  const labels = t.periods
    .map(
      (p, i) =>
        `<text x="${x(i)}" y="${H - 6}" fill="var(--muted)" font-size="11" text-anchor="middle">${p}</text>`
    )
    .join("");
  $("#trend").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${t.metric} trend">
    ${grid}
    <polygon points="${pts} ${W - P},${H - P} ${P},${H - P}" fill="var(--accent)" opacity="0.10"/>
    <polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="2.5"
      stroke-linecap="round" stroke-linejoin="round"/>
    ${dots}${labels}</svg>`;
}

function renderSegments() {
  const max = Math.max(...state.segments.map((s) => s.value));
  $("#segments").innerHTML = state.segments
    .map(
      (s) => `<div class="bar-row"><span>${s.segment}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(s.value / max) * 100}%"></div></div>
      <span class="num">$${(s.value / 1000).toFixed(1)}k</span></div>`
    )
    .join("");
}

/* ---------- chat ---------- */

function bubble(role, text = "") {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const b = document.createElement("div");
  b.className = "bubble";
  b.textContent = text;
  wrap.appendChild(b);
  $("#log").appendChild(wrap);
  $("#log").scrollTop = $("#log").scrollHeight;
  return b;
}

// The agent may append `CHART: {...}` - pull it out and draw it instead of printing it.
function extractChart(text) {
  const i = text.lastIndexOf("CHART:");
  if (i === -1) return { text, chart: null };
  try {
    const chart = JSON.parse(text.slice(i + 6).trim());
    return { text: text.slice(0, i).trimEnd(), chart };
  } catch {
    return { text, chart: null };
  }
}

async function send(message) {
  if (!message.trim()) return;
  $("#send").disabled = true;
  bubble("me", message);
  const out = bubble("bot");
  out.classList.add("cursor");
  let full = "";

  try {
    const res = await fetch(`${API}/chat/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message, thread_id: state.thread }),
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const frames = buf.split("\n\n");
      buf = frames.pop();
      for (const frame of frames) {
        const ev = /^event:\s*(.+)$/m.exec(frame)?.[1] ?? "message";
        const data = [...frame.matchAll(/^data:\s?(.*)$/gm)].map((m) => m[1]).join("\n");
        if (ev === "token") {
          full += data;
          out.textContent = full;
          $("#log").scrollTop = $("#log").scrollHeight;
        } else if (ev === "tool") {
          if (!out.querySelector(".tool")) {
            const tag = document.createElement("span");
            tag.className = "tool";
            tag.textContent = "queried warehouse";
            out.prepend(tag, document.createElement("br"));
          }
        } else if (ev === "error") {
          full += `\n[error] ${data}`;
          out.textContent = full;
        }
      }
    }
  } catch (e) {
    out.textContent = `Could not reach the analyst service (${e.message}).`;
  } finally {
    out.classList.remove("cursor");
    const { text, chart } = extractChart(out.textContent);
    if (chart) {
      out.textContent = text;
      renderTrend({ metric: chart.title, periods: chart.labels, values: chart.values });
    }
    $("#send").disabled = false;
  }
}

/* ---------- wiring ---------- */

$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = $("#input").value;
  $("#input").value = "";
  $("#input").style.height = "auto";
  send(v);
});
$("#input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("#composer").requestSubmit();
  }
});
$("#input").addEventListener("input", (e) => {
  e.target.style.height = "auto";
  e.target.style.height = `${e.target.scrollHeight}px`;
});
$("#suggest").addEventListener("click", (e) => {
  if (e.target.tagName === "BUTTON") send(e.target.textContent);
});
$("#newthread").addEventListener("click", () => {
  state.thread = crypto.randomUUID();
  $("#log").innerHTML = "";
  bubble("bot", "New thread. Previous context cleared.");
});
$("#refresh").addEventListener("click", loadDashboard);
$("#theme").addEventListener("change", (e) => {
  document.documentElement.dataset.theme = e.target.checked ? "light" : "dark";
  renderTiles();
  renderTrend();
});
document.querySelectorAll(".nav").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".nav").forEach((n) => n.classList.remove("active"));
    b.classList.add("active");
  })
);

loadDashboard();
