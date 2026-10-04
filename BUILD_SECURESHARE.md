# SecureShare: Full Build Specification for Claude Code

> **Instructions for Claude Code.** Read this whole file first. Build the entire project in one session, working through the phases in section 14 in order. After each phase, run its check before starting the next. Do not add features that are not listed here. Do not ask me questions unless something is truly blocked. When something is ambiguous, pick the simplest option and note it in `EXPLAINED.md`.

---

## 1. What you are building

**SecureShare** is a web app for sharing confidential files safely.

- The owner uploads a file. It is stored in a **private AWS S3 bucket**.
- The owner creates a **share link** with an **expiry time** and a **permission** (`view` or `download`).
- Anyone with the link can open it without logging in. The app checks the link, **records the access**, and only then serves the file.
- Every upload, link creation, view, download, revoke and blocked attempt goes into an **append-only audit log**, shown on a dashboard.

**One-line pitch:** "Every link expires, access is controlled, and every view or download is logged, so you always know who accessed what and when."

**Who it is for:** a college student presenting this to PwC interviewers. The code must be **simple, readable and explainable line by line**. The UI must look **professional and beautiful**, because the demo is a big part of the interview.

---

## 2. Non-negotiable rules

1. **Simple code over clever code.** No metaprogramming, no generic base classes, no repository layer, no dependency-injection frameworks. A student must be able to explain every file.
2. **One job per file.** Follow the folder structure in section 6 exactly.
3. **Comments:** a short comment above each function saying what it does and why. Inline comments only where the logic is not obvious.
4. **Python 3.12 only.** Create the venv with `py -3.12 -m venv venv` (Windows). Do not use 3.13 or 3.14.
5. **Never print, log, hardcode or commit secrets.** All config comes from `.env`. `.env` is already in `.gitignore`.
6. **Do not install libraries outside the list in section 4.**
7. **Do not touch AWS beyond the single S3 bucket named in `.env`.** Do not create, modify or delete any other AWS resource. Do not run any `aws` CLI commands that change infrastructure.
8. **Frontend is plain HTML, CSS and JavaScript.** No React, no build step, no npm, no CSS framework. Fonts from Google Fonts and icons as inline SVG are allowed.
9. **Do not implement** anything in the "Excluded" list in section 3.
10. **Commit to Git** after each phase with a clear message (for example `Phase 3: file upload to S3`). Never commit `.env`.

---

## 3. Scope

### Features (exactly five)

| ID | Feature | Behaviour |
| --- | --- | --- |
| F1 | Accounts | Sign up, log in, log out with email and password. Session is a JWT in an HttpOnly cookie. |
| F2 | Files | Upload (max 10 MB), list own files, delete a file. |
| F3 | Share links | Create a link with expiry of 10 minutes, 1 hour, 1 day or 7 days. Revoke early. |
| F4 | Permissions | Each link is `view` (opens in browser) or `download` (saves the file). |
| F5 | Audit trail and dashboard | Every action logged. Dashboard shows the log with filters, plus summary numbers. |

### Excluded (do not build)

Editing files in the browser, malware scanning, file version history, PDF watermarking, teams or roles, sharing between accounts, email notifications, password reset, email verification, search beyond the audit filters, admin panel, payments.

---

## 4. Tech stack (use only these)

| Layer | Choice |
| --- | --- |
| Language | Python 3.12 |
| Web framework | FastAPI, served by Uvicorn |
| Database | PostgreSQL 16 (local: Docker. Cloud later: AWS RDS) |
| ORM | SQLAlchemy 2.x with `psycopg[binary]` |
| Config | `pydantic-settings`, reading `.env` |
| Passwords | `argon2-cffi` |
| Sessions | `PyJWT`, stored in an HttpOnly cookie |
| AWS | `boto3` |
| File uploads | `python-multipart` |
| Tests | `pytest`, `httpx` |
| Frontend | Plain HTML, CSS, JS (no framework) |

`requirements.txt` must list exactly these, with versions pinned after you install them.

---

## 5. Environment and config

`.env` already exists in the project root with these keys. **Read them, never print them:**

```
DATABASE_URL=postgresql://secureshare:localpass123@localhost:5432/secureshare
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-southeast-2
S3_BUCKET_NAME=secureshare-sujay-2026
JWT_SECRET=...
```

Notes:

- The AWS region is **Sydney (`ap-southeast-2`)**, not Mumbai.
- `DATABASE_URL` uses `postgresql://`. SQLAlchemy with psycopg 3 needs `postgresql+psycopg://`, so `config.py` must convert it. Do not change `.env`.
- `docker-compose.yml` must create Postgres with user `secureshare`, password `localpass123`, database `secureshare`, on port 5432, with a named volume so data survives restarts. Pin `postgres:16`.
- Also create `.env.example` with the same keys and blank secrets.
- `config.py` exposes one `settings` object with: `database_url`, `aws_region`, `s3_bucket_name`, `jwt_secret`, `max_upload_bytes` (10 MB), `allowed_extensions`, `presigned_url_seconds` (60), `session_hours` (12), `cookie_secure` (False locally, True when `ENVIRONMENT=production`). The AWS access key and secret are read automatically by boto3 from the environment, so do not pass them around in code.

---

## 6. Folder structure (exact)

```
secureshare/
├── app/
│   ├── __init__.py
│   ├── main.py            # creates the app, creates tables on startup, includes routers, serves /static
│   ├── config.py          # settings from .env
│   ├── database.py        # engine, SessionLocal, Base, get_db()
│   ├── models.py          # 4 tables
│   ├── schemas.py         # Pydantic request and response shapes
│   ├── security.py        # hash/verify password, create/read JWT, get_current_user()
│   ├── s3_client.py       # upload_file, delete_file, presigned_url
│   ├── audit.py           # log_event(), the ONLY function that writes audit rows
│   └── routers/
│       ├── __init__.py
│       ├── auth.py        # signup, login, logout, me
│       ├── files.py       # upload, list, delete
│       ├── links.py       # create, list, revoke
│       ├── share.py       # public /s/{token} and /s/{token}/download
│       └── audit.py       # GET /api/audit, GET /api/audit/summary
├── static/
│   ├── index.html         # landing + login/signup
│   ├── app.html           # my files + share modal
│   ├── dashboard.html     # audit dashboard
│   ├── link-error.html    # branded "link unavailable" page
│   ├── share-download.html# branded landing page for download-permission links
│   ├── css/
│   │   └── style.css      # whole design system
│   └── js/
│       ├── api.js         # fetch wrapper + error handling
│       ├── ui.js          # toasts, modal, formatting helpers, theme toggle
│       ├── auth.js        # login/signup page logic
│       ├── files.js       # files page logic
│       └── dashboard.js   # dashboard logic
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_links.py
│   └── test_audit.py
├── docs/
│   └── blueprint.md       # (already present)
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
├── CLAUDE.md              # (already present)
├── EXPLAINED.md           # you write this at the end (section 13)
└── README.md
```

Do not nest folders deeper than shown. Do not add files that are not listed, except `__init__.py` files.

---

## 7. Database design

Create the tables with SQLAlchemy models in `models.py` using `Base.metadata.create_all()` on startup (no Alembic). Use timezone-aware timestamps (`TIMESTAMPTZ`), always stored in UTC.

### `users`
| Column | Type | Notes |
| --- | --- | --- |
| id | serial PK | |
| email | varchar(255) | unique, not null, stored lowercase |
| password_hash | varchar(255) | not null |
| created_at | timestamptz | default now |

### `files`
| Column | Type | Notes |
| --- | --- | --- |
| id | serial PK | |
| owner_id | int FK users.id | not null |
| original_name | varchar(255) | not null |
| s3_key | varchar(512) | unique, not null. Format `uploads/<uuid4>` (no filename in the key) |
| size_bytes | int | not null |
| content_type | varchar(100) | not null |
| created_at | timestamptz | default now |
| deleted_at | timestamptz | null. Soft delete |

### `share_links`
| Column | Type | Notes |
| --- | --- | --- |
| id | serial PK | |
| file_id | int FK files.id | not null |
| token | varchar(64) | unique, not null. `secrets.token_urlsafe(32)` |
| permission | varchar(10) | check in (`view`, `download`) |
| expires_at | timestamptz | not null |
| revoked_at | timestamptz | null |
| access_count | int | default 0 |
| created_at | timestamptz | default now |

### `audit_logs` (append-only: the app only ever INSERTs, never UPDATEs or DELETEs)
| Column | Type | Notes |
| --- | --- | --- |
| id | serial PK | |
| action | varchar(30) | `upload`, `delete`, `link_created`, `link_revoked`, `viewed`, `downloaded`, `access_denied` |
| user_id | int FK users.id | null when a link visitor acts |
| file_id | int FK files.id | null allowed |
| link_id | int FK share_links.id | null allowed |
| ip_address | varchar(45) | |
| user_agent | varchar(255) | truncate to 255 |
| detail | varchar(255) | for example `expired`, `revoked`, `view-only link` |
| created_at | timestamptz | default now |

Add index `idx_audit_file_time` on `(file_id, created_at DESC)`.

---

## 8. API specification

All JSON. Base path `/api` except the public share routes. Errors use FastAPI's standard `{"detail": "message"}` with clear human-readable messages.

| Method | Path | Auth | Behaviour |
| --- | --- | --- | --- |
| POST | `/api/auth/signup` | none | Body `{email, password}`. Password min 8 characters. Reject duplicate email with 409. Hash with Argon2. Log the user in (set cookie). |
| POST | `/api/auth/login` | none | Verify password. Set cookie. Wrong email or password gives the same 401 message ("Invalid email or password"). |
| POST | `/api/auth/logout` | user | Clear the cookie. |
| GET | `/api/auth/me` | user | Return `{id, email}`. Frontend uses it to detect login. |
| POST | `/api/files` | user | Multipart upload. Check size (max 10 MB) and extension. Save to S3 as `uploads/<uuid4>`. Insert `files` row. Log `upload`. |
| GET | `/api/files` | user | List own non-deleted files, newest first, each with `active_link_count`. |
| DELETE | `/api/files/{id}` | owner | Delete from S3, set `deleted_at`, revoke all active links for it. Log `delete`. |
| POST | `/api/files/{id}/links` | owner | Body `{permission, expires_in}` where `expires_in` is one of `10m`, `1h`, `1d`, `7d`. Create link. Log `link_created`. Return the link including the full URL built from the request's base URL. |
| GET | `/api/files/{id}/links` | owner | List links with computed `status`: `active`, `expired` or `revoked`. |
| DELETE | `/api/links/{id}` | owner | Set `revoked_at` (idempotent). Log `link_revoked`. |
| GET | `/api/audit` | user | Audit rows for the user's files, newest first. Query params: `file_id`, `action`, `limit` (default 50, max 200), `offset`. Each row includes `file_name` and a human-friendly `actor` (the user's email, or "Link visitor"). |
| GET | `/api/audit/summary` | user | Counts for the dashboard: total files, active links, views in last 7 days, downloads in last 7 days, denied attempts in last 7 days, plus a list of per-day counts for the last 7 days (for the chart). |
| GET | `/s/{token}` | public | See section 9. |
| GET | `/s/{token}/download` | public | See section 9. |
| GET | `/healthz` | none | Returns `{"status": "ok"}`. |

**Ownership rule:** every route with `{id}` loads the row filtered by `owner_id = current_user.id`. If nothing matches, return **404** (never 403), so existence is not leaked.

**Allowed extensions:** `pdf, png, jpg, jpeg, docx, xlsx, pptx, txt, csv`. Reject others with 400. Also reject empty files.

---

## 9. The core flow: opening a share link

This is the heart of the project. Keep it in `routers/share.py`, short and heavily commented.

### `GET /s/{token}`

Run these checks in order. If a check fails, call `log_event(..., "access_denied", detail=<reason>)` where it makes sense, and return the branded `link-error.html` page with the right HTTP status and a reason code.

1. **Exists?** Look up the token. Not found: 404 page "Link not found". (Do not log, there is no file to attach it to.)
2. **Active?** If `revoked_at` is set, or the file has `deleted_at`: 410 page "This link is no longer available". Log `access_denied` with detail `revoked` or `file deleted`.
3. **In time?** If `expires_at <= now (UTC)`: 410 page "This link has expired". Log `access_denied`, detail `expired`.
4. **Serve by permission:**
   - `view`: increment `access_count`, log `viewed`, create a presigned S3 URL (60 seconds, `ResponseContentDisposition=inline`, correct content type) and **redirect (302)** to it.
   - `download`: increment `access_count`, log `viewed`, and return the branded `share-download.html` landing page. The page shows the file name, size and a Download button pointing to `/s/{token}/download`. The page reads file info from `GET /s/{token}/info` (add this small public JSON endpoint that repeats checks 1 to 3 without logging a second view).

### `GET /s/{token}/download`

Same checks 1 to 3. Then:

- If `permission == "view"`: log `access_denied` with detail `view-only link`, return 403 page "Downloading is not allowed on this link".
- Otherwise: increment `access_count`, log `downloaded`, create a presigned URL with `ResponseContentDisposition=attachment; filename="<original_name>"` (60 seconds) and redirect.

### Rules

- The audit row must be written **before** redirecting to S3, so no access can bypass the log.
- `log_event` records IP address (use `request.client.host`, and `X-Forwarded-For` first value if present) and user agent.
- All time comparisons use timezone-aware UTC datetimes.

Add this to `static/link-error.html` rendering: it receives a `reason` and `message` (inject via simple string replacement from the router, no template engine).

---

## 10. Security requirements

- Passwords: Argon2 via `argon2-cffi`. Never log or return hashes.
- JWT in cookie `ss_session`: `HttpOnly`, `SameSite=Lax`, `Secure` when `cookie_secure` is true, 12-hour expiry. Payload holds only the user id and expiry.
- No CORS middleware (same-origin app). All write endpoints accept JSON or multipart only.
- Share tokens: `secrets.token_urlsafe(32)`.
- Presigned URLs live 60 seconds. The share link, not the S3 URL, is the long-lived credential.
- The S3 bucket stays private. Never call `put_object_acl` or change bucket policy from code.
- Do not return the S3 key or bucket name to the browser.
- File size limit enforced while reading the upload (reject above 10 MB even if the header lies).
- Add basic security headers via a tiny middleware: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
- Add simple login rate limiting: max 10 failed logins per IP per 5 minutes using an in-memory dict. Explain in `EXPLAINED.md` that production would use Redis.

---

## 11. UI and design specification (make it beautiful)

The UI is a major part of the demo. Aim for a polished, modern SaaS look comparable to Linear, Vercel or Stripe's dashboard: calm, spacious, precise. It must not look like a default Bootstrap page or a student project.

### 11.1 Design system (all in `static/css/style.css`)

Define everything as CSS custom properties on `:root` and override them for dark mode.

- **Typography:** Google Fonts `Inter` (400, 500, 600, 700) for UI and `JetBrains Mono` for tokens, IP addresses and file sizes. Base size 15px, line-height 1.5. Headings use tight letter-spacing (`-0.02em`).
- **Colour (light):** background `#F7F8FA`, surface `#FFFFFF`, border `#E6E8EC`, text `#0F172A`, muted text `#64748B`, primary `#4F46E5` (indigo) with hover `#4338CA`, primary-soft `#EEF2FF`, success `#16A34A` / soft `#DCFCE7`, warning `#D97706` / soft `#FEF3C7`, danger `#DC2626` / soft `#FEE2E2`.
- **Colour (dark):** background `#0B0F19`, surface `#111827`, border `#1F2937`, text `#E5E7EB`, muted `#94A3B8`, primary `#818CF8`, with matching soft tones.
- **Radius:** 12px for cards and modals, 8px for inputs and buttons, 999px for badges.
- **Shadows:** subtle only (`0 1px 2px rgba(15,23,42,.06)` for cards, `0 12px 32px rgba(15,23,42,.14)` for modals). No heavy drop shadows.
- **Spacing:** use an 8px scale. Generous padding inside cards (24px).
- **Motion:** 150 to 200ms ease transitions on hover and focus; modals fade and slide up 8px; toasts slide in from the top right; skeleton loaders shimmer. Respect `prefers-reduced-motion`.
- **Focus states:** visible 2px primary outline with offset on every interactive element.
- **Dark mode:** follows the system preference by default, with a toggle (sun or moon icon) in the header that saves the choice in `localStorage` (the key `ss_theme`).
- **Icons:** inline SVG (Lucide-style, 1.75 stroke, 20px). No icon fonts, no emoji in the UI.

### 11.2 Reusable components (build once, use everywhere)

Buttons (primary, secondary, ghost, danger, with loading spinner state), inputs with labels and inline error text, select, segmented control, cards, badges (active, expired, revoked, view, download), tables, modal, toast, empty state, skeleton loader, tooltip-free copy button with a "Copied" state, file-type icon tile (colour-coded by extension).

### 11.3 Pages

**`index.html`: landing and auth**

- Split layout on desktop. Left: brand mark (a small shield-and-link logo as inline SVG), headline "Share confidential files. Keep control.", a short subline, and three feature rows with icons: "Links that expire", "Permissions per link", "Every access logged". Subtle indigo gradient background with a soft blurred shape, nothing busy.
- Right: a card with Log in and Sign up tabs (segmented control), form fields, inline validation, a primary full-width button with a loading state, and a password show/hide toggle.
- On mobile, stack the layout and hide the left feature column except for the headline.
- If already logged in (`/api/auth/me` succeeds), redirect to `app.html`.

**`app.html`: my files**

- Top bar: logo, nav (Files, Dashboard), theme toggle, user email menu with Log out.
- Page header "Your files" with an **Upload** primary button.
- A large **drag-and-drop upload zone** (dashed border, highlights on drag-over, shows a progress bar during upload using `XMLHttpRequest` progress events, shows allowed types and the 10 MB limit). Clicking opens the file picker.
- Files list as cards or rows: coloured file-type tile, name, size (mono), uploaded date (relative like "2 hours ago", full date on hover via `title`), a badge with the number of active links, and actions: **Share**, **Links**, **Delete** (with a confirm modal).
- **Share modal:** shows file name; a segmented control for permission (View only / Allow download) with one-line explanations; a segmented control for expiry (10 min, 1 hour, 1 day, 7 days); a **Create link** button. After creation, show the link in a mono read-only field with a **Copy** button (changes to "Copied" with a check for 2 seconds) and the exact expiry time.
- **Links drawer or modal** for a file: a table of links with permission badge, status badge (active in green with a live countdown like "expires in 8m 12s", expired in amber, revoked in red), access count, and a **Revoke** button (with confirm).
- Empty state when no files: illustration made from simple inline SVG shapes, headline "No files yet", short text, and an Upload button.
- Skeleton loaders while the list loads.

**`dashboard.html`: audit trail**

- Same top bar.
- Row of 4 stat cards: Files, Active links, Views (7 days), Blocked attempts (7 days). Each has a label, large number, and a small muted caption.
- A **7-day activity bar chart** drawn with plain inline SVG (no chart library). Bars for views and downloads per day, with a legend, axis labels, hover tooltip showing the exact numbers, and a smooth load animation.
- **Audit table** below with filters: a select for file, a select for action, and a Clear button. Columns: Time (relative, with exact time in `title`), Action (coloured badge with icon: upload, link created, viewed, downloaded, revoked, delete, access denied), File, Actor, IP (mono), Detail. Newest first, with a "Load more" button for pagination.
- Action badges: viewed (indigo), downloaded (green), access_denied (red), link_created (blue), link_revoked (amber), upload (green), delete (red).
- Empty state when there are no events.
- Auto-refresh the table and stats every 15 seconds while the tab is visible, with a small "Live" dot in the header, so the audit trail updates during the demo without a manual refresh.

**`link-error.html`: public branded error page**

- Centered card, large icon in a soft coloured circle (clock for expired, ban for revoked, shield-off for forbidden, question mark for not found), clear title, one-line explanation, and a muted line "Ask the sender for a new link." Same design system, dark mode aware, no login required.

**`share-download.html`: public download landing page**

- Centered card with a large file-type tile, file name, size, a muted line "Shared securely with SecureShare", an expiry line ("Link expires on ... "), and a large **Download** primary button. Small footer: "This access is being recorded."

### 11.4 UX details that make it feel premium

- Optimistic, instant feedback: buttons show spinners, never freeze silently.
- Every API error appears as a toast with a clear message (use the server's `detail`).
- Forms: pressing Enter submits; the first field is focused on load.
- Keyboard accessible: modals trap focus and close on Escape; buttons have proper labels; contrast meets WCAG AA.
- Fully responsive down to 360px wide. Tables become stacked cards on small screens.
- Page titles and a simple inline-SVG favicon (shield) set via a data URI.
- No layout shift: reserve space for skeletons.
- All dates shown in the browser's local time.

---

## 12. Tests (`pytest`)

Use a separate test database (`secureshare_test`) created automatically, and **mock `s3_client`** so tests never touch real AWS. Required tests:

- Signup, duplicate email rejected, login success and failure, `/me` requires login.
- Upload rejects wrong type, empty file and files above 10 MB.
- User B cannot see, delete or link user A's file (404).
- Link creation returns the right `expires_at` for each option.
- Opening an **active** link logs `viewed` and redirects.
- Opening an **expired** link returns 410 and logs `access_denied` with `expired`.
- Opening a **revoked** link returns 410 and logs `access_denied` with `revoked`.
- `/s/{token}/download` on a **view-only** link returns 403 and logs `access_denied`.
- `/s/{token}/download` on a download link logs `downloaded` and redirects.
- `audit_logs` is never updated or deleted by any route (assert row counts only grow).

All tests must pass before you finish.

---

## 13. Documentation you must write

### `README.md`
Project pitch, feature list, architecture diagram as a **Mermaid** block (browser, FastAPI, PostgreSQL, S3, with the 60-second presigned URL redirect), tech stack table, local setup steps (Docker, venv, `.env`, run), how to run tests, and a short "Security decisions" list. Leave a clearly marked placeholder for a demo GIF.

### `EXPLAINED.md` (very important)
The owner will present this project in interviews and must understand it. Write this in simple, friendly English:

1. **The 30-second pitch** and a **2-minute walkthrough script**.
2. **File-by-file guide:** for every file under `app/`, three lines: what it does, why it exists, and the one thing to remember.
3. **The five checks** in `share.py` explained step by step in plain language, with the code excerpt.
4. **Key concepts explained simply:** presigned URL, JWT in an HttpOnly cookie, Argon2 hashing, soft delete, append-only audit log, why the bucket is private, why the app redirects to S3 instead of streaming the file.
5. **30 likely interview questions with short model answers**, covering security, AWS, databases, the design choices, scaling (load balancer, read replica, partitioning `audit_logs`, direct-to-S3 uploads for big files), and "what would you improve?".
6. **Known limits** stated honestly (for example, view-only cannot stop screenshots; in-memory rate limiting does not survive restarts; tables created without migrations).

---

## 14. Build phases (do all, in order, verifying each)

| Phase | Build | Check before moving on |
| --- | --- | --- |
| 1. Foundation | venv with Python 3.12, `requirements.txt`, `docker-compose.yml`, `config.py`, `database.py`, `models.py`, minimal `main.py` with `/healthz` | `docker compose up -d` works, app starts, `/healthz` returns ok, tables exist in Postgres |
| 2. Auth | `schemas.py`, `security.py`, `routers/auth.py`, login rate limit | signup, login, `/me`, logout work (test with the `/docs` page or httpx) |
| 3. Files and S3 | `s3_client.py`, `audit.py`, `routers/files.py` | upload appears in the S3 bucket under a random key, list and delete work, audit rows are written |
| 4. Links | `routers/links.py` | create, list with status, revoke work for each expiry option |
| 5. Share flow | `routers/share.py`, `link-error.html`, `share-download.html` | active link works, expired and revoked links are blocked and logged, view-only cannot download |
| 6. Audit API | `routers/audit.py` (list with filters, summary) | filters and summary counts are correct |
| 7. Design system | `style.css`, `ui.js`, `api.js` | a small test page renders all components in light and dark mode |
| 8. Pages | `index.html`, `app.html`, `dashboard.html`, plus their JS | the full demo flow works in the browser |
| 9. Tests | everything in section 12 | `pytest` passes |
| 10. Docs and polish | `README.md`, `EXPLAINED.md`, `.env.example`, final cleanup | see the final checklist below |

If a check fails, fix it before continuing. Commit after each phase.

### AWS note
Use the single S3 bucket from `.env` in `ap-southeast-2`. If an S3 call fails with an access or region error, stop and tell me exactly what failed. Do not try to fix it by changing AWS resources or permissions.

---

## 15. Seed data for the demo

Add `scripts/seed_demo.py` (the one allowed extra file) that creates a demo account (`demo@secureshare.dev`, password `Demo@12345`) and, using real code paths, uploads two small sample files (a generated PDF and a text file), creates a few links, and generates a handful of view, download and denied events across the last 7 days (insert backdated audit rows directly) so the dashboard chart and table look alive on first open. It must be safe to run twice (skip if the demo user exists).

---

## 16. Final checklist (verify before you say you are done)

- [ ] `docker compose up -d` then `uvicorn app.main:app --reload` starts with no errors
- [ ] Full flow works in the browser: sign up, upload, create a view-only link, open it in a private window, see it logged, open `/download` and see it blocked and logged, revoke, see it blocked
- [ ] Expired links are blocked (test by temporarily setting an `expires_at` in the past, or via the tests)
- [ ] The UI looks polished in light and dark mode, and works at 360px width
- [ ] `pytest` passes
- [ ] `git status` shows `.env` is not tracked; `git log` shows one commit per phase
- [ ] No secrets appear in any file, log output or commit
- [ ] `README.md` and `EXPLAINED.md` are complete
- [ ] Print a short summary: how to run the app, how to run the tests, the demo account, and the URLs to open
