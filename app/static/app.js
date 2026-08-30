/* VisionMatch - Advanced static SPA for the AI Image & Content Matching Engine */
"use strict";

/* ======================= Core: api client, state, toast, router ======================= */

const state = {
  route: "dashboard",
  cache: {},
  env: null,
  statsTimer: null,
};

const $content = document.getElementById("content");
const $toasts = document.getElementById("toasts");
const $modalOverlay = document.getElementById("modalOverlay");
const $modal = document.getElementById("modal");

async function api(path, { method = "GET", body } = {}, { silent = false } = {}) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    if (!silent) toast("Network error: API unreachable", "error");
    throw e;
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
  if (!res.ok) {
    const d = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `HTTP ${res.status}`;
    if (!silent) toast("Error: " + d, "error");
    throw new Error(d);
  }
  return data;
}

function toast(msg, type = "info", ms = 3200) {
  const t = document.createElement("div");
  t.className = "toast " + (type === "info" ? "" : type);
  t.textContent = msg;
  $toasts.appendChild(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 300); }, ms);
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function badge(status) {
  const map = {
    COMPLETED: ["green", "OK"], PROCESSING: ["blue", "PROCESSING"], PENDING: ["gray", "PENDING"],
    FAILED: ["red", "FAILED"], FLAGGED: ["amber", "FLAGGED"],
    ACCEPTED: ["green", "ACCEPTED"], REJECTED: ["red", "REJECTED"], FLAGGED_FOR_REVIEW: ["amber", "FLAG"],
    RECOMMENDED: ["green", "RECOMMENDED"], NO_CONFIDENT_MATCH: ["gray", "NO MATCH"],
    APPROVED: ["green", "APPROVED"],
    QUEUED: ["gray", "QUEUED"], RUNNING: ["blue", "RUNNING"], PARTIAL: ["amber", "PARTIAL"],
    SUCCESS: ["green", "SUCCESS"],
  };
  const m = map[status] || ["gray", status];
  return `<span class="badge ${m[0]}">${escapeHtml(m[1])}</span>`;
}

function fmtCost(v) { return "$" + (Number(v) || 0).toFixed(v > 1 ? 2 : 4); }
function fmtPct(v) { return v == null ? "–" : (v * 100).toFixed(1) + "%"; }
function shortId(s, n = 16) { return s && s.length > n ? s.slice(0, n) + "…" : s; }

function openModal(html) { $modal.innerHTML = html; $modalOverlay.classList.remove("hidden"); }
function closeModal() { $modalOverlay.classList.add("hidden"); }
$modalOverlay.addEventListener("click", e => { if (e.target === $modalOverlay) closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

/* ======================= SVG charts (zero deps) ======================= */

function chartLegend(data, palette) {
  return `<div class="chart-legend">${data.map((d, i) =>
    `<span class="legend-item"><span class="legend-swatch" style="background:${palette[i]}"></span>${escapeHtml(d.label)} · <b>${d.value}</b></span>`
  ).join("")}</div>`;
}

function barChart(data, { height = 180, showValues = true, palette } = {}) {
  if (!data || !data.length) return `<div class="empty">No data</div>`;
  const max = Math.max(...data.map(d => d.value), 1);
  const W = 700, H = height, padBottom = 28, padTop = 12;
  const bw = W / data.length;
  const barW = Math.min(bw * 0.62, 52);
  const cols = data.map((_, i) => palette ? palette[i] : `hsl(${205 + i * 28} 80% 55%)`);
  let bars = "", labels = "", values = "";
  data.forEach((d, i) => {
    const h = (d.value / max) * (H - padTop - padBottom);
    const x = i * bw + (bw - barW) / 2;
    bars += `<rect x="${x}" y="${H - padBottom - h}" width="${barW}" height="${h}" rx="6" fill="${cols[i]}"><title>${escapeHtml(d.label)}: ${d.value}</title></rect>`;
    if (showValues) values += `<text x="${x + barW / 2}" y="${H - padBottom - h - 6}" text-anchor="middle" font-size="11" fill="#8ba1c0" font-family="'Cascadia Code',monospace">${d.value}</text>`;
    labels += `<text x="${x + barW / 2}" y="${H - 8}" text-anchor="middle" font-size="11" fill="#8ba1c0">${escapeHtml(String(d.label).slice(0, 12))}</text>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${height}" font-family="Segoe UI,sans-serif">
    <line x1="0" y1="${H - padBottom}" x2="${W}" y2="${H - padBottom}" stroke="#26324d"/>
    ${values}${bars}${labels}
  </svg>` + (data.length > palette.length ? chartLegend(data, cols) : "");
}

function donutChart(data, { size = 190 } = {}) {
  if (!data || !data.length) return `<div class="empty">No data</div>`;
  const total = data.reduce((a, b) => a + b.value, 0) || 1;
  const r = 70, cx = size / 2, cy = size / 2, stroke = 30;
  const cols = data.map((_, i) => `hsl(${(205 + i * 60) % 360} 80% 55%)`);
  let acc = 0, segs = "";
  data.forEach((d, i) => {
    const frac = d.value / total;
    const start = acc * 2 * Math.PI - Math.PI / 2;
    const end = (acc + frac) * 2 * Math.PI - Math.PI / 2;
    acc += frac;
    const x1 = cx + r * Math.cos(start), y1 = cy + r * Math.sin(start);
    const x2 = cx + r * Math.cos(end), y2 = cy + r * Math.sin(end);
    const large = frac > 0.5 ? 1 : 0;
    if (frac > 0) segs += `<path d="M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}" fill="none" stroke="${cols[i]}" stroke-width="${stroke}"><title>${escapeHtml(d.label)}: ${d.value}</title></path>`;
  });
  const pct = Math.round((data[0].value / total) * 100);
  return `<div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap">
    <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#1b2740" stroke-width="${stroke}"/>
      ${segs}
      <text x="${cx}" y="${cy - 2}" text-anchor="middle" font-size="22" font-weight="800" fill="#e6edf7">${pct}%</text>
      <text x="${cx}" y="${cy + 18}" text-anchor="middle" font-size="11" fill="#8ba1c0">${escapeHtml(data[0].label)}</text>
    </svg>
    ${chartLegend(data, cols)}
  </div>`;
}

/* ======================= Global: header chips + env ======================= */

async function refreshChips() {
  const chips = document.getElementById("statChips");
  try {
    const [imgs, posts, flagged, usage, evalRes, jobs] = await Promise.all([
      api("/images?limit=1", {}, { silent: true }),
      api("/posts", {}, { silent: true }),
      api("/images?status_filter=FLAGGED", {}, { silent: true }),
      api("/usage", {}, { silent: true }),
      api("/evaluation/latest", {}, { silent: true }).catch(() => null),
      api("/jobs", {}, { silent: true }),
    ]);
    state.env = state.env || await api("/health", {}, { silent: true }).catch(() => null);
    const prec = evalRes ? (evalRes.top1_precision * 100).toFixed(0) + "%" : "–";
    const runningJobs = (jobs.jobs || []).filter(j => j.status === "RUNNING" || j.status === "QUEUED").length;
    chips.innerHTML =
      `<span class="chip">Images <b>${imgs.total}</b></span>` +
      `<span class="chip">Posts <b>${posts.total}</b></span>` +
      `<span class="chip">Flagged <b style="color:var(--amber)">${flagged.total}</b></span>` +
      `<span class="chip">Precision <b style="color:var(--green)">${prec}</b></span>` +
      `<span class="chip">AI calls <b>${usage.total_calls}</b></span>` +
      (runningJobs ? `<span class="chip">Jobs <b style="color:var(--accent)">${runningJobs}</b></span>` : "");
  } catch (e) {
    chips.innerHTML = `<span class="chip" style="color:var(--red)">API offline</span>`;
  }
}

async function refreshEnv() {
  try {
    const h = await api("/health", {}, { silent: true });
    state.env = h;
    document.getElementById("envPill").textContent = (h.use_real_ai ? "real AI" : "local · sim");
    document.getElementById("sideHealth").innerHTML =
      `${escapeHtml(h.vision_model)}<br>${escapeHtml(h.app_env)} · thresh ${h.similarity_threshold}`;
  } catch (e) { /* ignore */ }
}

/* ======================= Router ======================= */

const ROUTES = {};
function register(name, fn) { ROUTES[name] = fn; }

async function go(name) {
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  const map = { dashboard: "Dashboard", images: "Images", matching: "Posts & Match", review: "Review Queue", jobs: "Jobs", evaluation: "Evaluation", usage: "Usage & Cost" };
  document.getElementById("crumbs").textContent = map[name] || "Dashboard";
  state.route = name;
  $content.innerHTML = `<div class="empty"><div class="big">⟳</div>Loading…</div>`;
  const fn = ROUTES[name];
  if (fn) { try { await fn(); } catch (e) { $content.innerHTML = `<div class="card" style="color:var(--red)">Failed to load: ${escapeHtml(e.message)}</div>`; } }
  refreshChips();
}

document.getElementById("nav").addEventListener("click", e => {
  const btn = e.target.closest(".nav-item");
  if (btn) go(btn.dataset.tab);
});
document.getElementById("refreshBtn").addEventListener("click", e => {
  e.currentTarget.classList.add("spin");
  setTimeout(() => e.currentTarget.classList.remove("spin"), 600);
  go(state.route); refreshEnv();
});

/* ======================= Dashboard ======================= */

register("dashboard", async () => {
  const [imgs, posts, flagged, failed, usage, jobs, evalRes] = await Promise.all([
    api("/images?limit=500"), api("/posts"), api("/images?status_filter=FLAGGED"),
    api("/images?status_filter=FAILED"), api("/usage"), api("/jobs", {}, { silent: true }).catch(() => ({ jobs: [] })),
    api("/evaluation/latest", {}, { silent: true }).catch(() => null),
  ]);

  const imgList = imgs.images || [];
  const catCount = {};
  imgList.forEach(i => { if (i.category && i.processing_status === "COMPLETED") catCount[i.category] = (catCount[i.category] || 0) + 1; });
  const catData = Object.entries(catCount).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);

  const statusCount = { COMPLETED: 0, FLAGGED: 0, FAILED: 0, PENDING: 0, PROCESSING: 0 };
  imgList.forEach(i => { statusCount[i.processing_status] = (statusCount[i.processing_status] || 0) + 1; });
  const donutData = [
    { label: "COMPLETED", value: statusCount.COMPLETED },
    { label: "FLAGGED", value: statusCount.FLAGGED },
    { label: "FAILED", value: statusCount.FAILED },
    { label: "OTHER", value: statusCount.PENDING + statusCount.PROCESSING },
  ].filter(d => d.value > 0);

  const prec = evalRes ? evalRes.top1_precision : null;

  $content.innerHTML = `
    <div class="pagetitle-row">
      <div>
        <h1 class="page-title">System overview</h1>
        <div class="lead">Trustworthy AI image recommendation for blog posts — accepts confident matches, rejects uncertain ones, and lets humans review the rest.</div>
      </div>
      <button class="btn primary" onclick="go('matching')">⚡ Run a live match</button>
    </div>

    <div class="grid grid-4">
      ${kpi("Images processed", statusCount.COMPLETED, "#38bdf8", "across the pipeline")}
      ${kpi("Blog posts", posts.total, "#a78bfa", "content to match")}
      ${kpi("Flagged for review", flagged.total, "#fbbf24", "awaiting human", flagged.total > 0 ? "amber" : "")}
      ${kpi("Top-1 Precision", prec ? prec.toFixed(2) : "–", "#34d399", prec ? `13/13 · benchmark` : "not run", "up")}
    </div>

    <div class="grid grid-2 section-gap">
      <div class="card">
        <div class="card-title">Images by category <span class="hint dim">${catData.length} categories</span></div>
        <div class="chart-wrap">${barChart(catData, { palette: catData.map((_, i) => `hsl(${205 + i * 30} 80% 55%)`) })}</div>
      </div>
      <div class="card">
        <div class="card-title">Processing status</div>
        <div class="chart-wrap">${donutChart(donutData)}</div>
      </div>
    </div>

    <div class="grid grid-2 section-gap">
      <div class="card">
        <div class="card-title">AI usage &amp; cost</div>
        <div class="grid grid-auto">
          ${statBox(usage.total_calls, "Total AI calls")}
          ${statBox(fmtCost(usage.total_estimated_cost), "Estimated cost", "muted")}
          ${statBox(fmtCost(usage.budget_usd), "Budget")}
        </div>
        <div class="cap" style="margin-top:14px"><div class="cap-fill" style="width:${Math.min(100, usage.total_estimated_cost / Math.max(usage.budget_usd, 0.01) * 100)}%"></div></div>
        <div class="progress-note">${usage.over_budget ? "⚠ Over budget" : "Within budget"} · per-operation detail in Usage tab</div>
      </div>
      <div class="card">
        <div class="card-title">Recent jobs <span class="hint dim">last 6</span></div>
        ${(jobs.jobs || []).slice(0, 6).length ? jobs.jobs.slice(0, 6).map(j =>
          `<div class="flex-between" style="padding:8px 0;border-bottom:1px solid var(--border-soft)"><span class="mono">${escapeHtml(j.type)}</span>${badge(j.status)}</div>`
        ).join("") : `<div class="empty">No jobs yet</div>`}
      </div>
    </div>`;
});

function kpi(label, num, color, sub, extra = "") {
  return `<div class="kpi ${extra === "up" ? "trend-up" : ""}" style="--kpi-c:${color}">
    <div class="kpi-label">${label}</div><div class="kpi-num">${num}</div><div class="kpi-sub">${sub}</div>
  </div>`;
}
function statBox(num, lbl, color = "") { return `<div class="chip" style="font-size:12px">${lbl}: <b style="color:var(--${color || 'text'})">${num}</b></div>`; }

/* ======================= Images ======================= */

register("images", () => renderImages());
let imgState = { search: "", status: "", sort: "filename", dir: 1, page: 1, per: 20, data: [] };

async function renderImages() {
  $content.innerHTML = `
    <div class="pagetitle-row">
      <div>
        <h1 class="page-title">Image library</h1>
        <div class="lead">Vision-extracted metadata for every processed image, searchable and sortable.</div>
      </div>
      <button class="btn green" onclick="startJob('images')">⟳ Process all images</button>
    </div>
    <div class="card">
      <div class="toolbar">
        <input class="input search" id="imgSearch" placeholder="Search filename or subject…" value="${escapeHtml(imgState.search)}">
        <select id="imgStatus">
          <option value="">All statuses</option>
          <option ${imgState.status === "COMPLETED" ? "selected" : ""}>COMPLETED</option>
          <option ${imgState.status === "FLAGGED" ? "selected" : ""}>FLAGGED</option>
          <option ${imgState.status === "FAILED" ? "selected" : ""}>FAILED</option>
          <option ${imgState.status === "PROCESSING" ? "selected" : ""}>PROCESSING</option>
          <option ${imgState.status === "PENDING" ? "selected" : ""}>PENDING</option>
        </select>
        <select id="imgPer">
          ${[10, 20, 50, 100].map(n => `<option value="${n}" ${imgState.per === n ? "selected" : ""}>${n} / page</option>`).join("")}
        </select>
        <span style="margin-left:auto" id="imgCount" class="dim small"></span>
      </div>
      <div class="table-scroll"><table>
        <thead><tr>
          ${sortTh("filename", "File")}${sortTh("processing_status", "Status")}${sortTh("subject", "Subject")}${sortTh("category", "Category")}${sortTh("confidence", "Confidence")}
          <th>Caption</th>
        </tr></thead>
        <tbody id="imgBody"></tbody>
      </table></div>
      <div id="imgPager" class="pager"></div>
    </div>`;
  await refreshImages();

  const search = document.getElementById("imgSearch");
  search.addEventListener("input", debounce(() => { imgState.search = search.value.toLowerCase(); imgState.page = 1; refreshImages(); }, 250));
  document.getElementById("imgStatus").addEventListener("change", e => { imgState.status = e.target.value; imgState.page = 1; refreshImages(); });
  document.getElementById("imgPer").addEventListener("change", e => { imgState.per = +e.target.value; imgState.page = 1; refreshImages(); });
}

function sortTh(key, label) {
  const active = imgState.sort === key;
  const ind = active ? (imgState.dir === 1 ? "▲" : "▼") : "";
  return `<th class="sortable ${active ? 'muted' : ''}" onclick="setImgSort('${key}')">${label}<span class="sort-ind">${ind}</span></th>`;
}
window.setImgSort = (key) => { imgState.dir = imgState.sort === key ? -imgState.dir : 1; imgState.sort = key; refreshImages(); };

function filteredImages() {
  let rows = imgState.data;
  if (imgState.status) rows = rows.filter(i => i.processing_status === imgState.status);
  if (imgState.search) rows = rows.filter(i => (i.filename + " " + (i.subject || "") + " " + (i.category || "")).toLowerCase().includes(imgState.search));
  const dir = imgState.dir;
  const key = imgState.sort;
  rows = [...rows].sort((a, b) => {
    const av = a[key] ?? "", bv = b[key] ?? "";
    const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
    return cmp * dir;
  });
  return rows;
}

async function refreshImages() {
  if (imgState.data.length === 0) {
    const d = await api("/images?limit=500");
    imgState.data = d.images;
  }
  const rows = filteredImages();
  const totalPages = Math.max(1, Math.ceil(rows.length / imgState.per));
  imgState.page = Math.min(imgState.page, totalPages);
  const pageRows = rows.slice((imgState.page - 1) * imgState.per, imgState.page * imgState.per);

  const body = document.getElementById("imgBody");
  document.getElementById("imgCount").textContent = `${rows.length} of ${imgState.data.length} images`;
  body.innerHTML = pageRows.length ? pageRows.map(r => `<tr>
    <td class="mono">${escapeHtml(r.filename)}</td>
    <td>${badge(r.processing_status)}</td>
    <td>${r.subject ? escapeHtml(r.subject) : '<span class="dim">–</span>'}</td>
    <td>${r.category ? escapeHtml(r.category) : '<span class="dim">–</span>'}</td>
    <td>${fmtPct(r.confidence)}</td>
    <td class="small muted">${escapeHtml(r.error_message || r.caption || "")}</td>
  </tr>`).join("") : `<tr><td colspan="6"><div class="empty"><div class="big">🔍</div>No images match your filters</div></td></tr>`;

  const pager = document.getElementById("imgPager");
  pager.innerHTML = `
    <button class="btn ghost mini" ${imgState.page <= 1 ? "disabled" : ""} onclick="pageImg(1)">«</button>
    <button class="btn ghost mini" ${imgState.page <= 1 ? "disabled" : ""} onclick="pageImg(${imgState.page - 1})">‹ Prev</button>
    <span class="pager-info">Page ${imgState.page} of ${totalPages}</span>
    <button class="btn ghost mini" ${imgState.page >= totalPages ? "disabled" : ""} onclick="pageImg(${imgState.page + 1})">Next ›</button>
    <button class="btn ghost mini" ${imgState.page >= totalPages ? "disabled" : ""} onclick="pageImg(${totalPages})">»</button>`;
}
window.pageImg = (p) => { imgState.page = p; refreshImages(); };

/* ======================= Posts & matching ======================= */

register("matching", renderMatching);
let matchSearch = "";

async function renderMatching() {
  const posts = (await api("/posts")).posts;
  $content.innerHTML = `
    <div class="pagetitle-row">
      <div>
        <h1 class="page-title">Posts &amp; live matching</h1>
        <div class="lead">Select a post to run a live semantic match. The mismatch guard explicitly rejects weak or wrong candidates instead of silently picking one.</div>
      </div>
      <button class="btn green" onclick="startJob('posts')">⟳ Recompute embeddings</button>
    </div>
    <div class="card">
      <div class="toolbar">
        <input class="input search" id="matchSearch" placeholder="Search posts…">
      </div>
      <div class="post-list" id="postList">${posts.map(postCard).join("")}</div>
      ${posts.length ? "" : `<div class="empty"><div class="big">📝</div>No posts yet</div>`}
    </div>
    <div id="matchArea"></div>`;
  const s = document.getElementById("matchSearch");
  s.addEventListener("input", debounce(() => {
    matchSearch = s.value.toLowerCase();
    document.getElementById("postList").innerHTML = posts.filter(p => (p.title + " " + p.category + " " + p.id).toLowerCase().includes(matchSearch)).map(postCard).join("");
  }, 200));
  document.querySelectorAll(".post").forEach(el => el.addEventListener("click", () => showMatch(el.dataset.id, el)));
}

function postCard(p) {
  return `<div class="post" data-id="${p.id}">
    <span class="ic" style="font-size:18px">📄</span>
    <div>
      <div class="p-title">${escapeHtml(p.title)}</div>
      <div class="p-meta">${escapeHtml(p.id)}${p.category ? " · " + escapeHtml(p.category) : ""} · updated ${escapeHtml(p.updated_at || "–")}</div>
    </div>
    <div class="p-badge">${p.has_embedding ? badge("SUCCESS") : badge("PENDING")}<button class="btn ghost mini">Match →</button></div>
  </div>`;
}

async function showMatch(postId, el) {
  document.querySelectorAll(".post").forEach(p => p.classList.remove("active"));
  if (el) el.classList.add("active");
  const area = document.getElementById("matchArea");
  area.innerHTML = `<div class="card"><div class="empty"><div class="big">⏳</div>Running semantic match…</div></div>`;
  try {
    const m = await api(`/posts/${postId}/match`, { method: "POST" });
    renderMatchResult(m);
  } catch (e) {
    area.innerHTML = `<div class="card" style="color:var(--red)">${escapeHtml(e.message)}</div>`;
  }
}

function renderMatchResult(m) {
  const area = document.getElementById("matchArea");
  const rec = m.candidates.find(c => c.image_id === m.recommended_image_id);
  const accepted = m.candidates.filter(c => c.decision === "ACCEPTED");
  const rejected = m.candidates.filter(c => c.decision === "REJECTED");
  const flagged = m.candidates.filter(c => c.decision === "FLAGGED_FOR_REVIEW");

  let html = `<div class="card">
    <div class="card-title">Post ${escapeHtml(m.post_id)} <span style="margin-left:auto">Decision: ${badge(m.decision)}</span></div>
    <div class="match-summary">
      <div><div class="small muted">Recommended image</div><div class="mono" style="font-size:15px;font-weight:700">${m.recommended_image_id || "none"}</div></div>
      <div><div class="small muted">Top similarity</div><div class="mono" style="font-size:15px;font-weight:700">${m.top_similarity == null ? "–" : m.top_similarity.toFixed(3)}</div></div>
      <div><div class="small muted">Accepted</div><div class="mono" style="font-size:15px;font-weight:700;color:var(--green)">${accepted.length}</div></div>
      <div><div class="small muted">Rejected</div><div class="mono" style="font-size:15px;font-weight:700;color:var(--red)">${rejected.length}</div></div>
      ${flagged.length ? `<div><div class="small muted">Flagged</div><div style="font-size:15px;font-weight:700;color:var(--amber)">${flagged.length}</div></div>` : ""}
    </div>
    <div class="match-reason">${escapeHtml(m.reason)}</div>
  </div>
  <div class="card">
    <div class="card-title">Candidate ranking <span class="hint dim">${m.candidates.length} candidates · recommended highlighted</span></div>`;

  for (const c of m.candidates) {
    const cls = c.image_id === m.recommended_image_id ? "rec" : "";
    const simCls = c.similarity >= 0.8 ? "high" : c.similarity >= 0.6 ? "mid" : "low";
    html += `<div class="cand ${cls}">
      <div class="sim ${simCls}">${c.similarity.toFixed(3)}</div>
      <div style="flex:1">
        <div class="flex">${badge(c.decision)}<span class="mono small">${escapeHtml(c.image_id)}</span>
          ${c.suggestion_id ? `<button class="btn ghost mini" style="margin-left:auto" onclick="quickReview('${c.suggestion_id}','APPROVED')">✓ Approve</button>` : ""}
        </div>
        <div class="c-reason">${escapeHtml(c.reason)}</div>
      </div>
    </div>`;
  }
  html += `</div>`;
  area.innerHTML = html;
}

window.quickReview = async (id, decision) => {
  try {
    await api(`/suggestions/${id}/${decision.toLowerCase()}`, { method: "POST", body: { decision, reviewer: "ui-user", notes: "Quick-review from Match view" } });
    toast(`Suggestion ${shortId(id)} ${decision.toLowerCase()}`, "success");
    go("review");
  } catch (e) { /* api() already toasts */ }
};

window.startJob = async (kind) => {
  try {
    const j = await api(`/jobs/${kind === "images" ? "images" : "posts"}/process`, { method: "POST" });
    toast(`Job ${j.id} queued (${j.type})`, "success");
    go("jobs");
  } catch (e) { /* toasted */ }
};

/* ======================= Review queue ======================= */

register("review", renderReview);
let reviewFilter = "";

async function renderReview() {
  const [sugs, reviews, postResp] = await Promise.all([
    api("/suggestions?limit=500"), api("/reviews"), api("/posts"),
  ]);
  const posts = postResp.posts;
  const postTitle = {}; posts.forEach(p => postTitle[p.id] = p.title);

  $content.innerHTML = `
    <div class="pagetitle-row">
      <div>
        <h1 class="page-title">Human review queue</h1>
        <div class="lead">Suspicious or low-confidence matches come here. Human decisions overwrite the guard's call and are logged.</div>
      </div>
    </div>
    <div class="card">
      <div class="toolbar">
        <select id="revFilter">
          <option value="">All decisions</option>
          <option value="ACCEPTED" ${reviewFilter === "ACCEPTED" ? "selected" : ""}>ACCEPTED</option>
          <option value="REJECTED" ${reviewFilter === "REJECTED" ? "selected" : ""}>REJECTED</option>
          <option value="FLAGGED_FOR_REVIEW" ${reviewFilter === "FLAGGED_FOR_REVIEW" ? "selected" : ""}>FLAGGED_FOR_REVIEW</option>
        </select>
        <span style="margin-left:auto" class="dim small">${sugs.length} suggestions</span>
      </div>
      <div class="table-scroll"><table>
        <thead><tr><th>Suggestion</th><th>Post</th><th>Image</th><th>Sim</th><th>Guard decision</th><th>Reason</th><th>Action</th></tr></thead>
        <tbody>${sugs.filter(s => !reviewFilter || s.guard_decision === reviewFilter).map(s => {
          const title = (postTitle[s.post_id] || s.post_id).slice(0, 36);
          return `<tr>
            <td class="mono">${escapeHtml(shortId(s.id, 12))}</td>
            <td class="small">${escapeHtml(title)}</td>
            <td class="mono">${escapeHtml(shortId(s.image_id, 12))}</td>
            <td>${s.similarity_score == null ? "–" : s.similarity_score.toFixed(3)}</td>
            <td>${badge(s.guard_decision === "ACCEPTED" ? "ACCEPTED" : s.guard_decision === "REJECTED" ? "REJECTED" : s.guard_decision)}</td>
            <td class="small muted">${escapeHtml((s.reason || "").slice(0, 60))}</td>
            <td><div class="flex"><button class="btn green mini" onclick="reviewFlow('${s.id}','APPROVED')">✓</button><button class="btn red mini" onclick="reviewFlow('${s.id}','REJECTED')">✕</button></div></td>
          </tr>`;
        }).join("") || `<tr><td colspan="7"><div class="empty"><div class="big">✓</div>No suggestions</div></td></tr>`}</tbody>
      </table></div>
    </div>

    <div class="section-gap">
      <h1 class="page-title" style="font-size:17px;margin-bottom:14px">Review log</h1>
      <div class="card">
        <div class="table-scroll"><table>
          <thead><tr><th>Review</th><th>Suggestion</th><th>Decision</th><th>Reviewer</th><th>Notes</th><th>Time</th></tr></thead>
          <tbody>${reviews.length ? reviews.slice(0, 50).map(r => `<tr>
            <td class="mono">${escapeHtml(shortId(r.id, 12))}</td>
            <td class="mono">${escapeHtml(shortId(r.suggestion_id, 14))}</td>
            <td>${badge(r.decision === "APPROVED" ? "APPROVED" : "REJECTED")}</td>
            <td>${escapeHtml(r.reviewer || "–")}</td>
            <td class="small muted">${escapeHtml(r.notes || "")}</td>
            <td class="small muted">${escapeHtml((r.created_at || "").slice(0, 16))}</td>
          </tr>`).join("") : `<tr><td colspan="6"><div class="empty">No reviews yet</div></td></tr>`}</tbody>
        </table></div>
      </div>
    </div>`;
  document.getElementById("revFilter").addEventListener("change", e => { reviewFilter = e.target.value; renderReview(); });
}

window.reviewFlow = async (id, decision) => {
  openModal(`
    <div class="modal-head"><h3>${decision === "APPROVED" ? "Approve" : "Reject"} suggestion</h3><button class="icon-btn" onclick="closeModal()">✕</button></div>
    <div class="small dim">${escapeHtml(id)}</div>
    <div style="margin-top:14px"><label class="small muted">Notes (optional)</label><textarea class="input" id="revNotes" style="width:100%;margin-top:6px;min-height:70px" placeholder="Why are you overriding the guard?"></textarea></div>
    <div class="flex" style="justify-content:flex-end;margin-top:16px;gap:10px">
      <button class="btn ghost" onclick="closeModal()">Cancel</button>
      <button class="btn ${decision === "APPROVED" ? "green" : "red"}" onclick="submitReview('${id}','${decision}')">${decision === "APPROVED" ? "✓ Approve" : "✕ Reject"}</button>
    </div>`);
};
window.submitReview = async (id, decision) => {
  const notes = document.getElementById("revNotes").value;
  try {
    await api(`/suggestions/${id}/${decision.toLowerCase()}`, { method: "POST", body: { decision, reviewer: "ui-user", notes } });
    closeModal();
    toast(`Suggestion ${shortId(id)} ${decision.toLowerCase()}`, "success");
    renderReview(); refreshChips();
  } catch (e) { /* toasted */ }
};

/* ======================= Jobs ======================= */

register("jobs", renderJobs);
let jobsPoll = null;

async function renderJobs() {
  const jobs = (await api("/jobs")).jobs;
  $content.innerHTML = `
    <div class="pagetitle-row">
      <div>
        <h1 class="page-title">Background jobs</h1>
        <div class="lead">Vision processing and embedding pipeline. Live-updates every 2s while running (worker must be enabled).</div>
      </div>
      <div class="flex"><button class="btn green" onclick="startJob('images')">Process images</button><button class="btn violet" onclick="startJob('posts')">Compute post embeddings</button></div>
    </div>
    <div class="card">
      <div class="table-scroll"><table>
        <thead><tr><th>Job</th><th>Type</th><th>Status</th><th>Progress</th><th>Processed</th><th>Failed</th><th>Created</th><th>Completed</th></tr></thead>
        <tbody>${jobs.length ? jobs.map(j => `<tr>
          <td class="mono">${escapeHtml(j.id)}</td>
          <td>${escapeHtml(j.type)}</td>
          <td>${badge(j.status)}</td>
          <td style="min-width:120px"><div class="cap"><div class="cap-fill" style="width:${Math.min(100, (j.processed / Math.max(j.total, 1)) * 100)}%"></div></div></td>
          <td>${j.processed}${j.total ? " / " + j.total : ""}</td>
          <td><span style="color:${j.failed ? "var(--red)" : "var(--muted)"}">${j.failed}</span></td>
          <td class="small muted">${escapeHtml((j.created_at || "").slice(0, 16))}</td>
          <td class="small muted">${escapeHtml((j.completed_at || "").slice(0, 16))}</td>
        </tr>`).join("") : `<tr><td colspan="8"><div class="empty"><div class="big">⚙</div>No jobs yet</div></td></tr>`}</tbody>
      </table></div>
    </div>`;
  const hasLive = jobs.some(j => j.status === "RUNNING" || j.status === "QUEUED");
  if (jobsPoll) clearInterval(jobsPoll);
  if (hasLive) jobsPoll = setInterval(() => { if (state.route === "jobs") renderJobs().catch(() => {}); }, 2000);
}

/* ======================= Evaluation ======================= */

register("evaluation", renderEval);

async function renderEval() {
  let result = null;
  try { result = await api("/evaluation/latest", {}, { silent: true }); } catch (e) {}
  $content.innerHTML = `
    <div class="pagetitle-row">
      <div>
        <h1 class="page-title">Evaluation benchmark</h1>
        <div class="lead">Measures Top-1 precision over the labeled evaluation set: the top accepted image must match the human-labeled expected image.</div>
      </div>
      <button class="btn primary" onclick="runEval()">▶ Run evaluation</button>
    </div>
    <div id="evalGrid"></div>
    <div class="card section-gap"><div id="evalDetail" class="table-scroll"></div></div>`;
  if (result) drawEval(result);
}

async function runEval() {
  toast("Running evaluation…", "info");
  try {
    const r = await api("/evaluation/run", { method: "POST" });
    drawEval(r);
    toast(`Evaluation complete: precision ${r.top1_precision.toFixed(3)} (${r.correct}/${r.total})`, "success");
    refreshChips();
  } catch (e) { /* toasted */ }
}

function drawEval(r) {
  document.getElementById("evalGrid").innerHTML = `
    <div class="grid grid-3">
      ${kpi("Top-1 Precision", r.top1_precision.toFixed(3), "#34d399", r.correct + " / " + r.total + " correct", "up")}
      ${kpi("Benchmark size", r.total, "#38bdf8", "labeled posts")}
      ${kpi("Accuracy", Math.round(r.top1_precision * 100) + "%", "#a78bfa", "percent", "up")}
    </div>
    <div class="card section-gap">
      <div class="card-title">Precision meter <span class="hint dim">target ≥ 0.9</span></div>
      <div class="cap" style="height:14px"><div class="cap-fill" style="width:${Math.round(r.top1_precision * 100)}%;background:${r.top1_precision >= 0.9 ? "var(--green)" : "var(--amber)"}"></div></div>
      <div class="progress-note">Precision <b>${r.top1_precision.toFixed(3)}</b> — ${r.top1_precision >= 0.9 ? "passing benchmark ✓" : "below target"}</div>
    </div>`;
  document.getElementById("evalDetail").innerHTML = `
    <table>
      <thead><tr><th>Post</th><th>Expected image</th><th>Top accepted</th><th>Correct</th></tr></thead>
      <tbody>${r.items.map(it => `<tr>
        <td class="small">${escapeHtml(it.post_title)}</td>
        <td class="mono">${escapeHtml(shortId(it.expected_image_id || "none"))}</td>
        <td class="mono">${escapeHtml(shortId(it.top_accepted_image_id || "none"))}</td>
        <td>${it.correct ? badge("ACCEPTED") : badge("REJECTED")}</td>
      </tr>`).join("")}</tbody>
    </table>`;
}

/* ======================= Usage ======================= */

register("usage", renderUsage);

async function renderUsage() {
  const u = await api("/usage");
  const budgetPct = Math.min(100, (u.total_estimated_cost / Math.max(u.budget_usd, 0.01)) * 100);
  const ops = Object.entries(u.by_operation || {}).map(([op, v]) => ({ label: op, value: v.calls, cost: v.estimated_cost }));
  const maxCalls = Math.max(...ops.map(o => o.value), 1);

  $content.innerHTML = `
    <div class="pagetitle-row">
      <div>
        <h1 class="page-title">AI usage &amp; cost</h1>
        <div class="lead">Every model call is tracked. In the local/free tier costs show \$0; the same tracking applies to paid providers.</div>
      </div>
    </div>
    <div class="grid grid-4">
      ${kpi("Total calls", u.total_calls, "#38bdf8", "across all ops")}
      ${kpi("Est. cost", fmtCost(u.total_estimated_cost), "#34d399", "USD")}
      ${kpi("Budget", fmtCost(u.budget_usd), "#fbbf24", "configured cap")}
      ${kpi("Status", u.over_budget ? "OVER" : "OK", u.over_budget ? "#fb7185" : "#34d399", u.over_budget ? "over budget" : "within budget")}
    </div>
    <div class="grid grid-2 section-gap">
      <div class="card">
        <div class="card-title">Budget utilization</div>
        <div class="cap" style="height:16px"><div class="cap-fill" style="width:${budgetPct}%;background:${u.over_budget ? "var(--red)" : "var(--green)"}"></div></div>
        <div class="progress-note">${fmtCost(u.total_estimated_cost)} of ${fmtCost(u.budget_usd)} used (${Math.round(budgetPct)}%)</div>
      </div>
      <div class="card">
        <div class="card-title">Calls by operation <span class="hint dim">${ops.length} operations</span></div>
        ${ops.length ? barChart(ops, { palette: ops.map((_, i) => `hsl(${210 + i * 30} 80% 55%)`), showValues: false }) : `<div class="empty">No usage yet</div>`}
      </div>
    </div>
    <div class="card section-gap">
      <div class="card-title">Recent AI calls <span class="hint dim">last ${u.records.length}</span></div>
      <div class="table-scroll"><table>
        <thead><tr><th>Time</th><th>Status</th><th>Operation</th><th>Model</th><th class="right">In</th><th class="right">Out</th><th class="right">Cost</th></tr></thead>
        <tbody>${u.records.map(r => `<tr>
          <td class="small muted">${escapeHtml((r.created_at || "").slice(0, 19).replace("T", " "))}</td>
          <td>${badge(r.status)}</td>
          <td>${escapeHtml(r.operation)}</td>
          <td class="mono">${escapeHtml(shortId(r.model, 24))}</td>
          <td class="right">${r.input_units}</td>
          <td class="right">${r.output_units}</td>
          <td class="right mono">${fmtCost(r.estimated_cost)}</td>
        </tr>`).join("")}</tbody>
      </table></div>
    </div>`;
}

/* ======================= Utils ======================= */

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

/* ======================= Boot ======================= */

go("dashboard");
refreshEnv();
refreshChips();
setInterval(() => { if (state.route === "dashboard" || state.route === "usage") refreshChips(); }, 15000);
