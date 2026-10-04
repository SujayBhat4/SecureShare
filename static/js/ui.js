// ui.js: small helpers shared by every page (icons, toasts, modal, formatting, theme, top bar).

// ---------- Icons (Lucide-style, drawn inline so we need no icon font) ----------
const ICONS = {
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  files: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
  activity: '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  alert: '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
  checkCircle: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  ban: '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
  shieldAlert: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  shieldCheck: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
};

// Returns an inline <svg> string for an icon name
function icon(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;
}

// Fills every <span data-icon="name"> on the page with that icon
function fillIcons() {
  document.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });
}

// The shield-and-link logo
function brandMark() {
  return '<svg class="brand-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><g transform="translate(7.5 7.5) scale(.375)" stroke-width="4"><path d="M9 17H7A5 5 0 0 1 7 7h2"/><path d="M15 7h2a5 5 0 1 1 0 10h-2"/><path d="M8 12h8"/></g></svg>';
}

// ---------- Small text helpers ----------

// Makes text safe to put inside HTML (stops file names like <script> from running)
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

// 1536 -> "1.5 KB"
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Full date and time in the browser's own time zone (optionally with seconds)
function formatDateTime(iso, withSeconds = false) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: withSeconds ? "medium" : "short" });
}

// "5 minutes ago", "2 hours ago", "3 days ago"
function relativeTime(iso) {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const units = [["minute", 60], ["hour", 3600], ["day", 86400]];
  let result = "1 minute ago";
  for (const [name, size] of units) {
    if (seconds >= size) {
      const count = Math.floor(seconds / size);
      result = `${count} ${name}${count > 1 ? "s" : ""} ago`;
    }
  }
  return seconds >= 30 * 86400 ? formatDateTime(iso) : result;
}

// "8m 12s", "2h 5m", "3d 4h": time left until a date. Returns null when it has passed.
function countdown(iso) {
  let seconds = Math.floor((new Date(iso).getTime() - Date.now()) / 1000);
  if (seconds <= 0) return null;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m ${seconds % 60}s`;
}

// "report.final.PDF" -> "pdf"
function fileExtension(name) {
  return name.includes(".") ? name.split(".").pop().toLowerCase() : "";
}

// The coloured square with the file type, e.g. a red "PDF" tile
function fileTile(name) {
  const ext = fileExtension(name);
  return `<div class="file-tile" data-ext="${escapeHtml(ext)}" aria-hidden="true">${escapeHtml(ext.toUpperCase())}</div>`;
}

// ---------- Theme (light / dark) ----------

// Works out which theme is showing right now
function currentTheme() {
  const saved = document.documentElement.dataset.theme;
  if (saved) return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// Switches theme and remembers the choice in localStorage (key ss_theme)
function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem("ss_theme", next);
  } catch (e) {
    // storage may be blocked; the theme still changes for this visit
  }
}

// The sun / moon button HTML (CSS shows the right icon for the current theme)
function themeToggleButton() {
  return `<button class="icon-btn" id="theme-toggle" type="button" aria-label="Toggle light and dark theme">
    <span class="theme-moon">${icon("moon")}</span><span class="theme-sun">${icon("sun")}</span></button>`;
}

// ---------- Toasts ----------

// Shows a small message in the top right corner. type: success, error or info.
function showToast(message, type = "info") {
  let region = document.getElementById("toast-region");
  if (!region) {
    region = document.createElement("div");
    region.id = "toast-region";
    region.className = "toast-region";
    document.body.appendChild(region);
  }
  const iconName = type === "success" ? "checkCircle" : type === "error" ? "alert" : "info";
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  toast.innerHTML = `${icon(iconName)}<span>${escapeHtml(message)}</span>`;
  region.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("leaving");
    setTimeout(() => toast.remove(), 220);
  }, 4500);
}

// ---------- Modal ----------

// Opens a dialog. body and footer can be HTML strings or elements.
// It traps the Tab key inside, closes on Escape or a click outside, and gives focus back afterwards.
// Returns { modal, close } so the caller can fill it in or close it.
function openModal({ title, body, footer, wide = false, onClose }) {
  const previouslyFocused = document.activeElement;

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal ${wide ? "modal-wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-header">
        <h2 id="modal-title">${escapeHtml(title)}</h2>
        <button class="icon-btn modal-close" type="button" aria-label="Close">${icon("x")}</button>
      </div>
      <div class="modal-body"></div>
      <div class="modal-footer" hidden></div>
    </div>`;
  const modal = backdrop.querySelector(".modal");
  const bodyBox = backdrop.querySelector(".modal-body");
  const footerBox = backdrop.querySelector(".modal-footer");

  function fill(box, content) {
    if (typeof content === "string") box.innerHTML = content;
    else box.replaceChildren(content);
  }
  fill(bodyBox, body);
  if (footer) {
    fill(footerBox, footer);
    footerBox.hidden = false;
  }

  function close() {
    document.removeEventListener("keydown", onKey);
    backdrop.remove();
    if (previouslyFocused && previouslyFocused.focus) previouslyFocused.focus();
    if (onClose) onClose();
  }

  // Escape closes; Tab cycles through the buttons and fields inside the dialog only
  function onKey(event) {
    // If another dialog is open on top of this one (like a confirm box), let that one handle the key
    const open = document.querySelectorAll(".modal-backdrop");
    if (open[open.length - 1] !== backdrop) return;
    if (event.key === "Escape") {
      close();
    } else if (event.key === "Tab") {
      const focusable = modal.querySelectorAll('button:not([disabled]), input, select, a[href], [tabindex]:not([tabindex="-1"])');
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }
  document.addEventListener("keydown", onKey);
  backdrop.addEventListener("mousedown", (event) => {
    if (event.target === backdrop) close();
  });
  backdrop.querySelector(".modal-close").addEventListener("click", close);

  document.body.appendChild(backdrop);
  const firstControl = modal.querySelector(".modal-body button, .modal-body input, .modal-footer button");
  (firstControl || modal.querySelector(".modal-close")).focus();
  return { modal, close };
}

// "Are you sure?" dialog. Returns a Promise that resolves to true (confirmed) or false.
function confirmDialog({ title, message, confirmText = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    let answered = false;
    const footer = document.createElement("div");
    footer.style.display = "contents";
    footer.innerHTML = `
      <button class="btn btn-secondary" type="button" data-answer="no">Cancel</button>
      <button class="btn ${danger ? "btn-danger" : "btn-primary"}" type="button" data-answer="yes">${escapeHtml(confirmText)}</button>`;
    const dialog = openModal({
      title,
      body: `<p class="muted">${escapeHtml(message)}</p>`,
      footer,
      onClose: () => {
        if (!answered) resolve(false);
      },
    });
    footer.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        answered = true;
        resolve(button.dataset.answer === "yes");
        dialog.close();
      });
    });
  });
}

// ---------- Buttons ----------

// Shows or hides the spinner on a button and blocks double clicks
function setLoading(button, loading) {
  button.classList.toggle("is-loading", loading);
  button.disabled = loading;
}

// Copies text to the clipboard and shows "Copied" on the button for 2 seconds
async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    // Fallback for pages without clipboard permission (e.g. plain http on a server)
    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  const original = button.innerHTML;
  button.innerHTML = `${icon("check")} Copied`;
  button.classList.add("is-copied");
  setTimeout(() => {
    button.innerHTML = original;
    button.classList.remove("is-copied");
  }, 2000);
}

// ---------- Top bar (used by the files and dashboard pages) ----------

// Draws the header, wires the theme toggle, the user menu and Log out.
// active is "files" or "dashboard".
function renderTopbar(active, user) {
  const initial = user.email.charAt(0);
  document.getElementById("topbar").innerHTML = `
    <header class="topbar"><div class="container topbar-inner">
      <a class="brand" href="/static/app.html">${brandMark()}<span>SecureShare</span></a>
      <nav class="nav" aria-label="Main">
        <a href="/static/app.html" class="${active === "files" ? "active" : ""}" ${active === "files" ? 'aria-current="page"' : ""}>${icon("files")}<span>Files</span></a>
        <a href="/static/dashboard.html" class="${active === "dashboard" ? "active" : ""}" ${active === "dashboard" ? 'aria-current="page"' : ""}>${icon("activity")}<span>Dashboard</span></a>
      </nav>
      <div class="topbar-right">
        ${themeToggleButton()}
        <div class="user-menu">
          <button class="user-btn" id="user-btn" type="button" aria-haspopup="true" aria-expanded="false">
            <span class="avatar">${escapeHtml(initial)}</span><span class="user-email">${escapeHtml(user.email)}</span>${icon("chevron")}
          </button>
          <div class="dropdown" id="user-dropdown" hidden>
            <div class="dropdown-label">${escapeHtml(user.email)}</div>
            <button type="button" id="logout-btn">${icon("logout")} Log out</button>
          </div>
        </div>
      </div>
    </div></header>`;

  document.getElementById("theme-toggle").addEventListener("click", toggleTheme);

  const userButton = document.getElementById("user-btn");
  const dropdown = document.getElementById("user-dropdown");
  userButton.addEventListener("click", (event) => {
    event.stopPropagation();
    dropdown.hidden = !dropdown.hidden;
    userButton.setAttribute("aria-expanded", String(!dropdown.hidden));
  });
  document.addEventListener("click", () => {
    dropdown.hidden = true;
    userButton.setAttribute("aria-expanded", "false");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") dropdown.hidden = true;
  });
  document.getElementById("logout-btn").addEventListener("click", async () => {
    try {
      await api("POST", "/api/auth/logout");
    } catch (error) {
      // Even if this fails we still go back to the login page
    }
    window.location.href = "/static/index.html";
  });
}

// Used by pages that need a logged-in user: returns the user, or sends the visitor to the login page
async function requireLogin() {
  try {
    return await api("GET", "/api/auth/me");
  } catch (error) {
    window.location.href = "/static/index.html";
    return new Promise(() => {}); // never resolves: the page is leaving anyway
  }
}
