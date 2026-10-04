// dashboard.js: logic for the audit dashboard (dashboard.html)

const PAGE_SIZE = 50;
const REFRESH_MS = 15000;

const auditBody = document.getElementById("audit-body");
const loadMoreBox = document.getElementById("load-more-box");
const fileFilter = document.getElementById("filter-file");
const actionFilter = document.getElementById("filter-action");
const chartBox = document.getElementById("chart-box");
const tooltip = document.getElementById("chart-tooltip");

let rows = []; // audit rows currently loaded
let hasMore = false;
let dailyData = []; // chart data from the last summary

// How each action looks in the table: label, icon and badge colour (set in style.css)
const ACTIONS = {
  upload: { label: "Upload", icon: "upload" },
  delete: { label: "Delete", icon: "trash" },
  link_created: { label: "Link created", icon: "link" },
  link_revoked: { label: "Link revoked", icon: "ban" },
  viewed: { label: "Viewed", icon: "eye" },
  downloaded: { label: "Downloaded", icon: "download" },
  access_denied: { label: "Access denied", icon: "shieldAlert" },
};

// ---------- Start ----------
(async function start() {
  const user = await requireLogin();
  renderTopbar("dashboard", user);
  await Promise.all([loadFileOptions(), loadSummary(), loadAudit(true)]);

  // Refresh every 15 seconds, but only while this tab is visible
  setInterval(() => {
    if (!document.hidden) refreshAll();
  }, REFRESH_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshAll();
  });
})();

function refreshAll() {
  loadSummary();
  loadAudit(true, true);
}

// ---------- Summary numbers and chart ----------

async function loadSummary() {
  let summary;
  try {
    summary = await api("GET", "/api/audit/summary");
  } catch (error) {
    showToast(error.message, "error");
    return;
  }
  const numbers = {
    "stat-files": summary.total_files,
    "stat-links": summary.active_links,
    "stat-views": summary.views_7d,
    "stat-denied": summary.denied_7d,
  };
  for (const [id, value] of Object.entries(numbers)) {
    const element = document.getElementById(id);
    element.classList.remove("skeleton");
    element.textContent = value;
  }
  dailyData = summary.daily;
  drawChart(!chartBox.querySelector("svg")); // animate only the first time
}

// Draws the bar chart with plain SVG: two bars (views, downloads) for each of the 7 days
function drawChart(animate) {
  const width = Math.max(chartBox.clientWidth - 48, 260);
  const height = 240;
  const margin = { top: 12, right: 8, bottom: 30, left: 32 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  // Round the top of the scale up to an even number so the grid lines are whole numbers
  const biggest = Math.max(1, ...dailyData.flatMap((d) => [d.views, d.downloads]));
  const top = Math.max(4, Math.ceil(biggest / 4) * 4);
  const y = (value) => margin.top + innerHeight - (value / top) * innerHeight;

  const columnWidth = innerWidth / dailyData.length;
  const barWidth = Math.min(22, columnWidth / 3);

  let svg = `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="Views and downloads per day for the last 7 days">`;

  // Grid lines and the numbers on the left
  svg += '<g class="chart-grid chart-axis">';
  for (let i = 0; i <= 4; i++) {
    const value = (top / 4) * i;
    svg += `<line x1="${margin.left}" x2="${width - margin.right}" y1="${y(value)}" y2="${y(value)}"/>`;
    svg += `<text x="${margin.left - 8}" y="${y(value) + 4}" text-anchor="end">${value}</text>`;
  }
  svg += "</g>";

  dailyData.forEach((day, i) => {
    const center = margin.left + columnWidth * i + columnWidth / 2;
    const date = new Date(day.date + "T00:00:00Z");
    // On narrow screens there is no room for the day number, so show only the weekday
    const label = date.toLocaleDateString(undefined, columnWidth < 52 ? { weekday: "short", timeZone: "UTC" } : { weekday: "short", day: "numeric", timeZone: "UTC" });
    const delay = animate ? `animation-delay:${i * 60}ms` : "animation:none";
    const viewsHeight = innerHeight - (y(day.views) - margin.top);
    const downloadsHeight = innerHeight - (y(day.downloads) - margin.top);

    svg += `<g data-index="${i}">`;
    // Bars with a minimum visible height of 0 when the count is zero
    svg += `<rect class="bar bar-views" x="${center - barWidth - 1}" y="${y(day.views)}" width="${barWidth}" height="${viewsHeight}" rx="4" style="${delay}"/>`;
    svg += `<rect class="bar bar-downloads" x="${center + 1}" y="${y(day.downloads)}" width="${barWidth}" height="${downloadsHeight}" rx="4" style="${delay}"/>`;
    svg += `<text class="chart-axis" x="${center}" y="${height - 8}" text-anchor="middle" style="fill:var(--muted);font-size:11px">${label}</text>`;
    // Invisible rectangle over the whole column: this is what the mouse hovers
    svg += `<rect class="bar-hit" x="${center - columnWidth / 2}" y="${margin.top}" width="${columnWidth}" height="${innerHeight}"><title>${label}: ${day.views} views, ${day.downloads} downloads</title></rect>`;
    svg += "</g>";
  });
  svg += "</svg>";

  chartBox.querySelector("svg")?.remove();
  chartBox.insertAdjacentHTML("afterbegin", svg);

  // Hover tooltip
  chartBox.querySelectorAll("g[data-index]").forEach((group) => {
    const day = dailyData[Number(group.dataset.index)];
    group.addEventListener("mouseenter", () => {
      tooltip.innerHTML = `<strong>${day.date}</strong><br>Views: ${day.views}<br>Downloads: ${day.downloads}`;
      tooltip.classList.add("show");
    });
    group.addEventListener("mousemove", (event) => {
      const box = chartBox.getBoundingClientRect();
      tooltip.style.left = event.clientX - box.left + "px";
      tooltip.style.top = event.clientY - box.top - 12 + "px";
    });
    group.addEventListener("mouseleave", () => tooltip.classList.remove("show"));
  });
}

// Redraw the chart when the window size changes so it always fits
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => dailyData.length && drawChart(false), 150);
});

// ---------- Filters ----------

// Fills the "All files" dropdown with the user's files
async function loadFileOptions() {
  try {
    const files = await api("GET", "/api/files");
    for (const file of files) {
      const option = document.createElement("option");
      option.value = file.id;
      option.textContent = file.original_name;
      fileFilter.appendChild(option);
    }
  } catch (error) {
    showToast(error.message, "error");
  }
}

fileFilter.addEventListener("change", () => loadAudit(true));
actionFilter.addEventListener("change", () => loadAudit(true));
document.getElementById("clear-filters").addEventListener("click", () => {
  fileFilter.value = "";
  actionFilter.value = "";
  loadAudit(true);
});
document.getElementById("load-more").addEventListener("click", () => loadAudit(false));

// ---------- Audit table ----------

// Loads audit rows. reset=true starts again from the newest row;
// reset=false adds the next page (Load more).
// keepSize=true (auto refresh) reloads as many rows as are already on screen.
async function loadAudit(reset, keepSize = false) {
  const limit = keepSize ? Math.min(200, Math.max(PAGE_SIZE, rows.length)) : PAGE_SIZE;
  const params = new URLSearchParams({ limit: limit, offset: reset ? 0 : rows.length });
  if (fileFilter.value) params.set("file_id", fileFilter.value);
  if (actionFilter.value) params.set("action", actionFilter.value);

  if (reset && rows.length === 0) {
    auditBody.innerHTML = '<div style="padding:16px"><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div></div>';
  }

  let page;
  try {
    page = await api("GET", `/api/audit?${params}`);
  } catch (error) {
    showToast(error.message, "error");
    return;
  }
  rows = reset ? page : rows.concat(page);
  hasMore = page.length === limit;
  renderAudit();
}

function renderAudit() {
  loadMoreBox.hidden = !hasMore;
  if (rows.length === 0) {
    auditBody.innerHTML = `
      <div class="empty">
        <h2>No events yet</h2>
        <p>Uploads, links and every view or download will appear here as they happen.</p>
      </div>`;
    return;
  }

  auditBody.innerHTML = `
    <div class="table-wrap"><table class="table">
      <thead><tr><th>Time</th><th>Action</th><th>File</th><th>Actor</th><th>IP</th><th>Detail</th></tr></thead>
      <tbody>${rows
        .map((row) => {
          const action = ACTIONS[row.action] || { label: row.action, icon: "info" };
          return `
        <tr>
          <td data-label="Time" title="${escapeHtml(formatDateTime(row.created_at, true))}">${relativeTime(row.created_at)}</td>
          <td data-label="Action"><span class="badge badge-${escapeHtml(row.action)}">${icon(action.icon)}${action.label}</span></td>
          <td data-label="File" class="cell-file" title="${escapeHtml(row.file_name || "")}">${escapeHtml(row.file_name || "-")}</td>
          <td data-label="Actor">${escapeHtml(row.actor)}</td>
          <td data-label="IP" class="mono">${escapeHtml(row.ip_address || "-")}</td>
          <td data-label="Detail" class="muted" title="${escapeHtml(row.user_agent || "")}">${escapeHtml(row.detail || "-")}</td>
        </tr>`;
        })
        .join("")}</tbody>
    </table></div>`;
}
