// files.js: logic for the "Your files" page (app.html)

const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED = ["pdf", "png", "jpg", "jpeg", "docx", "xlsx", "pptx", "txt", "csv"];

const fileList = document.getElementById("file-list");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");

let files = []; // the files currently shown

// ---------- Start ----------
(async function start() {
  const user = await requireLogin();
  renderTopbar("files", user);
  fillIcons();
  loadFiles();
})();

// ---------- Listing files ----------

// Fetches the user's files and draws them (skeleton rows while waiting)
async function loadFiles() {
  if (files.length === 0) {
    fileList.innerHTML = '<div class="skeleton skeleton-row"></div>'.repeat(3);
  }
  try {
    files = await api("GET", "/api/files");
  } catch (error) {
    showToast(error.message, "error");
    fileList.innerHTML = "";
    return;
  }
  renderFiles();
}

// Draws one row per file, or the empty state when there are none
function renderFiles() {
  if (files.length === 0) {
    fileList.innerHTML = `
      <div class="card empty">
        <svg class="empty-art" viewBox="0 0 160 120" fill="none" aria-hidden="true">
          <rect x="28" y="24" width="76" height="86" rx="10" fill="var(--surface-2)" stroke="var(--border)" stroke-width="2"/>
          <rect x="52" y="12" width="76" height="86" rx="10" fill="var(--surface)" stroke="var(--border)" stroke-width="2"/>
          <rect x="66" y="30" width="40" height="6" rx="3" fill="var(--primary-soft)"/>
          <rect x="66" y="44" width="48" height="6" rx="3" fill="var(--border)"/>
          <rect x="66" y="58" width="32" height="6" rx="3" fill="var(--border)"/>
          <circle cx="112" cy="86" r="20" fill="var(--primary)"/>
          <rect x="104" y="84" width="16" height="12" rx="3" fill="var(--on-primary)"/>
          <path d="M107 84v-4a5 5 0 0 1 10 0v4" stroke="var(--on-primary)" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
        <h2>No files yet</h2>
        <p>Upload a confidential file and share it safely with a link that expires.</p>
        <button class="btn btn-primary" type="button" data-action="pick">${icon("upload")} Upload a file</button>
      </div>`;
    return;
  }

  fileList.innerHTML = files
    .map((file) => {
      const links = file.active_link_count;
      const badge = links > 0
        ? `<span class="badge badge-active">${links} active link${links > 1 ? "s" : ""}</span>`
        : '<span class="badge">No active links</span>';
      return `
        <div class="card file-row" data-id="${file.id}">
          ${fileTile(file.original_name)}
          <div class="file-info">
            <div class="file-name" title="${escapeHtml(file.original_name)}">${escapeHtml(file.original_name)}</div>
            <div class="file-meta">
              <span class="mono">${formatBytes(file.size_bytes)}</span>
              <span title="${escapeHtml(formatDateTime(file.created_at))}">Uploaded ${relativeTime(file.created_at)}</span>
              ${badge}
            </div>
          </div>
          <div class="file-actions">
            <button class="btn btn-primary btn-sm" type="button" data-action="share">${icon("share")} Share</button>
            <button class="btn btn-secondary btn-sm" type="button" data-action="links">${icon("link")} Links</button>
            <button class="btn btn-ghost btn-sm" type="button" data-action="delete" aria-label="Delete ${escapeHtml(file.original_name)}">${icon("trash")} Delete</button>
          </div>
        </div>`;
    })
    .join("");
}

// One click listener for all buttons in the list (works for rows added later too)
fileList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  if (button.dataset.action === "pick") return fileInput.click();

  const id = Number(button.closest("[data-id]").dataset.id);
  const file = files.find((f) => f.id === id);
  if (button.dataset.action === "share") openShareModal(file);
  if (button.dataset.action === "links") openLinksModal(file);
  if (button.dataset.action === "delete") deleteFile(file);
});

// ---------- Uploading ----------

document.getElementById("upload-btn").addEventListener("click", () => fileInput.click());
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => {
  uploadMany(Array.from(fileInput.files));
  fileInput.value = ""; // so choosing the same file again works
});

// Highlight the zone while a file is dragged over it
["dragenter", "dragover"].forEach((name) =>
  dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragover");
  })
);
["dragleave", "drop"].forEach((name) =>
  dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragover");
  })
);
dropzone.addEventListener("drop", (event) => uploadMany(Array.from(event.dataTransfer.files)));

// A file dropped outside the zone would make the browser open it and leave our page
["dragover", "drop"].forEach((name) => window.addEventListener(name, (event) => event.preventDefault()));

// Uploads the chosen files one after the other, with a progress bar
async function uploadMany(chosen) {
  const progress = document.getElementById("progress");
  const bar = document.getElementById("progress-bar");

  for (const file of chosen) {
    // Quick checks in the browser (the server checks again)
    if (!ALLOWED.includes(fileExtension(file.name))) {
      showToast(`${file.name}: this file type is not allowed`, "error");
      continue;
    }
    if (file.size === 0) {
      showToast(`${file.name}: the file is empty`, "error");
      continue;
    }
    if (file.size > MAX_BYTES) {
      showToast(`${file.name}: file is too large (limit 10 MB)`, "error");
      continue;
    }

    progress.hidden = false;
    bar.style.width = "0%";
    try {
      await uploadFile(file, (percent) => (bar.style.width = percent + "%"));
      showToast(`${file.name} uploaded`, "success");
    } catch (error) {
      showToast(error.message, "error");
    }
    progress.hidden = true;
  }
  loadFiles();
}

// ---------- Deleting ----------

async function deleteFile(file) {
  const yes = await confirmDialog({
    title: "Delete this file?",
    message: `"${file.original_name}" will be removed from storage and all its links will stop working.`,
    confirmText: "Delete file",
    danger: true,
  });
  if (!yes) return;
  try {
    await api("DELETE", `/api/files/${file.id}`);
    showToast("File deleted", "success");
    loadFiles();
  } catch (error) {
    showToast(error.message, "error");
  }
}

// ---------- Share modal ----------

const PERMISSION_HINTS = {
  view: "The file opens in the browser. The download button is not offered.",
  download: "Visitors get a page with a Download button and can save the file.",
};

// Builds a segmented control from a list of [value, label] pairs.
// Returns { element, value() } where value() is the selected option.
function segmentedControl(options, selected, onChange) {
  const element = document.createElement("div");
  element.className = "segmented";
  element.setAttribute("role", "radiogroup");
  let current = selected;
  element.innerHTML = options
    .map(([value, label]) => `<button type="button" class="seg ${value === current ? "is-active" : ""}" role="radio" aria-checked="${value === current}" data-value="${value}">${label}</button>`)
    .join("");
  element.addEventListener("click", (event) => {
    const button = event.target.closest(".seg");
    if (!button) return;
    current = button.dataset.value;
    element.querySelectorAll(".seg").forEach((seg) => {
      seg.classList.toggle("is-active", seg === button);
      seg.setAttribute("aria-checked", String(seg === button));
    });
    if (onChange) onChange(current);
  });
  return { element, value: () => current };
}

// Opens the dialog where the owner picks a permission and expiry, then creates the link
function openShareModal(file) {
  const body = document.createElement("div");
  const hint = document.createElement("p");
  hint.className = "seg-hint";
  hint.textContent = PERMISSION_HINTS.view;

  const permission = segmentedControl([["view", "View only"], ["download", "Allow download"]], "view", (value) => {
    hint.textContent = PERMISSION_HINTS[value];
  });
  const expiry = segmentedControl([["10m", "10 min"], ["1h", "1 hour"], ["1d", "1 day"], ["7d", "7 days"]], "1h");

  body.innerHTML = `<p class="muted small" style="margin-bottom:16px">Sharing <strong style="color:var(--text)">${escapeHtml(file.original_name)}</strong></p>
    <div class="label" style="margin-bottom:8px">Permission</div>`;
  body.append(permission.element, hint);
  const expiryLabel = document.createElement("div");
  expiryLabel.className = "label";
  expiryLabel.style.margin = "16px 0 8px";
  expiryLabel.textContent = "Link expires after";
  body.append(expiryLabel, expiry.element);

  const footer = document.createElement("div");
  footer.style.display = "contents";
  footer.innerHTML = `<button class="btn btn-secondary" type="button" data-role="cancel">Cancel</button>
    <button class="btn btn-primary" type="button" data-role="create">${icon("link")} Create link</button>`;

  const dialog = openModal({ title: "Share file", body, footer });
  footer.querySelector('[data-role="cancel"]').addEventListener("click", dialog.close);

  const createButton = footer.querySelector('[data-role="create"]');
  createButton.addEventListener("click", async () => {
    setLoading(createButton, true);
    try {
      const link = await api("POST", `/api/files/${file.id}/links`, {
        permission: permission.value(),
        expires_in: expiry.value(),
      });
      showCreatedLink(dialog, body, footer, link);
      loadFiles();
    } catch (error) {
      showToast(error.message, "error");
      setLoading(createButton, false);
    }
  });
}

// Replaces the share form with the new link, a Copy button and the exact expiry time
function showCreatedLink(dialog, body, footer, link) {
  body.innerHTML = `
    <div class="badge badge-active" style="margin-bottom:12px">${icon("checkCircle")} Link created</div>
    <div class="copy-field">
      <input class="input" id="new-link" readonly value="${escapeHtml(link.url)}" aria-label="Share link">
      <button class="btn btn-secondary" type="button" id="copy-link">${icon("copy")} Copy</button>
    </div>
    <p class="muted small" style="margin-top:12px">
      ${link.permission === "view" ? "View only" : "Download allowed"} · expires on
      <strong style="color:var(--text)">${escapeHtml(formatDateTime(link.expires_at, true))}</strong>
    </p>`;
  footer.innerHTML = '<button class="btn btn-primary" type="button">Done</button>';
  footer.querySelector("button").addEventListener("click", dialog.close);

  const input = document.getElementById("new-link");
  const copyButton = document.getElementById("copy-link");
  copyButton.addEventListener("click", () => copyText(link.url, copyButton));
  input.addEventListener("focus", () => input.select());
  copyButton.focus();
}

// ---------- Links modal ----------

// Shows every link of a file with its status, access count and a Revoke button
async function openLinksModal(file) {
  const body = document.createElement("div");
  body.innerHTML = '<div class="skeleton skeleton-row"></div>';
  let timer = null;
  const dialog = openModal({
    title: `Links for ${file.original_name}`,
    body,
    wide: true,
    onClose: () => clearInterval(timer),
  });

  // Loads the links and draws the table
  async function refresh() {
    let links;
    try {
      links = await api("GET", `/api/files/${file.id}/links`);
    } catch (error) {
      showToast(error.message, "error");
      return;
    }
    if (links.length === 0) {
      body.innerHTML = '<p class="muted" style="padding:16px 0">No links yet. Use Share to create one.</p>';
      return;
    }
    body.innerHTML = `
      <div class="table-modal-wrap"><div class="table-wrap"><table class="table">
        <thead><tr><th>Permission</th><th>Status</th><th>Opened</th><th>Created</th><th></th></tr></thead>
        <tbody>${links
          .map(
            (link) => `
          <tr data-link-id="${link.id}">
            <td data-label="Permission"><span class="badge badge-${link.permission}">${link.permission === "view" ? "View only" : "Download"}</span></td>
            <td data-label="Status"><span class="status-badge badge badge-${link.status}" data-status="${link.status}" data-expires="${link.expires_at}"></span></td>
            <td data-label="Opened" class="num mono">${link.access_count}</td>
            <td data-label="Created" title="${escapeHtml(formatDateTime(link.created_at))}">${relativeTime(link.created_at)}</td>
            <td class="actions">${link.status === "active" ? `<button class="btn btn-danger-soft btn-sm" type="button" data-revoke="${link.id}">Revoke</button>` : ""}</td>
          </tr>`
          )
          .join("")}</tbody>
      </table></div></div>`;
    updateStatuses();
  }

  // Writes the status text of every badge. Active links show a live countdown.
  function updateStatuses() {
    body.querySelectorAll(".status-badge").forEach((badge) => {
      let status = badge.dataset.status;
      let text = status;
      if (status === "active") {
        const left = countdown(badge.dataset.expires);
        if (left === null) {
          status = "expired"; // the time ran out while the window was open
          text = "expired";
        } else {
          text = `expires in ${left}`;
        }
      }
      badge.className = `status-badge badge badge-${status}`;
      badge.textContent = text;
    });
  }

  body.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-revoke]");
    if (!button) return;
    const yes = await confirmDialog({
      title: "Revoke this link?",
      message: "Anyone who opens it afterwards will see that it is no longer available.",
      confirmText: "Revoke link",
      danger: true,
    });
    if (!yes) return;
    try {
      await api("DELETE", `/api/links/${button.dataset.revoke}`);
      showToast("Link revoked", "success");
      await refresh();
      loadFiles();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  await refresh();
  timer = setInterval(updateStatuses, 1000); // live countdown
}
