# SecureShare explained (for interviews)

Read this a few times and say the answers out loud. Everything here describes the code exactly as it is built.

---

## 1. The 30-second pitch and the 2-minute walkthrough

### 30-second pitch

> "SecureShare is a web app for sharing confidential files safely. You upload a file to a private AWS S3 bucket, then create a share link that expires after 10 minutes, 1 hour, 1 day or 7 days, and is either view-only or download. Anyone with the link can open it without logging in, but my app checks the link first, writes a row in an audit log with the time, IP and browser, and only then lets the visitor reach the file. So if a file leaks, I know who opened it and when. It is built with FastAPI, PostgreSQL and S3."

### 2-minute walkthrough script

1. **(15 s) Pitch.** Say the pitch above.
2. **(15 s) Upload.** "I log in and upload `client_audit_report.pdf`. It goes to a private S3 bucket under a random name like `uploads/3f2a...`, so the real file name never appears in the bucket."
3. **(25 s) View-only link.** "I click Share, choose View only and 10 minutes. The app makes a random 256-bit token. I paste the link into a private window, which is a visitor with no login, and the PDF opens. Now I add `/download` to the address: 'Downloading is not allowed on this link'."
4. **(20 s) Audit trail.** "On the dashboard there is a `viewed` row and an `access_denied` row, each with time, IP address and browser. The log is append-only: the app only ever inserts rows."
5. **(15 s) Revoke.** "I click Revoke, refresh the visitor window, and it says 'This link is no longer available'. That attempt is logged too."
6. **(15 s) Expiry.** "Here is a link that is already past its time. It shows 'This link has expired' and the denial is in the log."
7. **(15 s) Cloud and code.** "The bucket has Block Public Access on. The core logic is about 40 lines in `routers/share.py`: check the link, write the audit row, then redirect to a 60-second S3 URL."

---

## 2. File-by-file guide (everything under `app/`)

**`main.py`**
- What: creates the FastAPI app, creates the database tables on startup, adds the security-headers middleware, plugs in the routers and serves `/static`.
- Why: one place where the whole app is put together.
- Remember: `Base.metadata.create_all()` runs here, so there are no migrations.

**`config.py`**
- What: reads `.env` into one `settings` object (database URL, bucket, JWT secret, limits like 10 MB and 60 seconds).
- Why: so no secret or magic number is written in the code.
- Remember: it turns `postgresql://` into `postgresql+psycopg://`, and calls `load_dotenv()` so boto3 can find the AWS keys in the environment.

**`database.py`**
- What: creates the SQLAlchemy engine, the `SessionLocal` factory, the `Base` class and the `get_db()` dependency.
- Why: every route needs a database session that is opened for the request and always closed.
- Remember: `get_db()` uses `yield` inside `try/finally`, so the session closes even when an error happens.

**`models.py`**
- What: the four tables as Python classes: `User`, `File`, `ShareLink`, `AuditLog`.
- Why: the database design lives in one file.
- Remember: all timestamps are `TIMESTAMPTZ` (UTC), `files.deleted_at` is a soft delete, and `audit_logs` has the index `idx_audit_file_time`.

**`schemas.py`**
- What: Pydantic classes that describe what goes in and out of the API (signup body, file, link, audit row, summary).
- Why: FastAPI validates the input automatically (for example password minimum 8, `expires_in` must be one of four values) and only the listed fields are returned.
- Remember: `FileOut` has no `s3_key`, so the bucket details never reach the browser.

**`security.py`**
- What: hash and verify passwords (Argon2), create and read the session JWT, and `get_current_user()`.
- Why: all login logic in one place.
- Remember: `get_current_user` is a FastAPI dependency; adding `Depends(get_current_user)` to a route makes it login-only (401 otherwise).

**`s3_client.py`**
- What: three functions: `upload_file`, `delete_file`, `presigned_url`.
- Why: S3 code is in one file, so the tests can replace it with a fake and never touch AWS.
- Remember: the client uses the regional endpoint (`s3.ap-southeast-2.amazonaws.com`); without it the presigned URL pointed at the global address and S3 answered "307 redirect", which breaks the signature.

**`audit.py`**
- What: `log_event()`, the only function that writes audit rows, plus `get_client_ip()`.
- Why: if there is only one writer, I can promise the log is only ever inserted into.
- Remember: `log_event` also commits, so a change made just before it (like `access_count + 1`) is saved in the same transaction.

**`routers/auth.py`**
- What: signup, login, logout and `/me`, plus the login rate limit.
- Why: accounts and sessions.
- Remember: wrong email and wrong password give the same message ("Invalid email or password"), so an attacker cannot learn which emails exist.

**`routers/files.py`**
- What: upload, list and delete files; also `get_own_file()`.
- Why: file management, with the checks (size, type, empty) in one place.
- Remember: `get_own_file` filters by `owner_id`, and returns 404 (not 403) for other people's files.

**`routers/links.py`**
- What: create, list and revoke share links.
- Why: the owner's side of sharing.
- Remember: status (`active`, `expired`, `revoked`) is calculated on every request from `revoked_at` and `expires_at`; it is not stored.

**`routers/share.py`**
- What: the public routes `/s/{token}`, `/s/{token}/info` and `/s/{token}/download`.
- Why: the heart of the project: check, log, then serve.
- Remember: the audit row is written **before** the redirect to S3.

**`routers/audit.py`**
- What: `GET /api/audit` (filters and paging) and `GET /api/audit/summary` (dashboard numbers and the 7-day chart data).
- Why: it feeds the dashboard.
- Remember: it only returns rows for files the current user owns.

---

## 3. The five checks in `share.py`

Opening a link (`GET /s/{token}`) runs these checks in order. The real code:

```python
@router.get("/s/{token}")
def open_link(token: str, request: Request, db: Session = Depends(get_db)):
    # Check 1: does the link exist? (Nothing to log: there is no file to attach it to.)
    link = find_link(db, token)
    if link is None:
        return error_page(404, "not_found", "Link not found")

    # Checks 2 and 3: active and in time. If not, log the blocked attempt and stop.
    problem = find_problem(link)
    if problem:
        status_code, reason, message, detail = problem
        log_event(db, "access_denied", request, file_id=link.file_id, link_id=link.id, detail=detail)
        return error_page(status_code, reason, message)

    # Check 4 (serve by permission). Count the access and log it first (one commit)...
    link.access_count += 1
    log_event(db, "viewed", request, file_id=link.file_id, link_id=link.id)

    # ...then serve. Download links get a landing page; view links go straight to the file.
    if link.permission == "download":
        html = (STATIC_DIR / "share-download.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    file = link.file
    url = s3_client.presigned_url(file.s3_key, file.content_type, file.original_name, as_attachment=False)
    return RedirectResponse(url, status_code=302)
```

And `find_problem` holds checks 2 and 3:

```python
def find_problem(link: ShareLink) -> tuple[int, str, str, str] | None:
    # Check 2: is the link still active?
    if link.revoked_at is not None:
        return 410, "revoked", "This link is no longer available", "revoked"
    if link.file.deleted_at is not None:
        return 410, "revoked", "This link is no longer available", "file deleted"

    # Check 3: is it still within its time? (always compare in UTC)
    if link.expires_at <= datetime.now(timezone.utc):
        return 410, "expired", "This link has expired", "expired"

    return None
```

In plain language:

1. **Does the link exist?** I look up the token. If there is no such link I show "Link not found" (404). I do not log this, because there is no file to attach the event to.
2. **Is it still active?** If the owner revoked it, or deleted the file, the answer is 410 "no longer available". I log `access_denied` with the reason (`revoked` or `file deleted`).
3. **Is it in time?** I compare `expires_at` with the current UTC time. If it has passed: 410 "This link has expired", logged as `access_denied` / `expired`.
4. **Is this action allowed?** This matters on `/s/{token}/download`: if the link is `view` only, I log `access_denied` / `view-only link` and answer 403.
   ```python
   if link.permission == "view":
       log_event(db, "access_denied", request, file_id=link.file_id, link_id=link.id, detail="view-only link")
       return error_page(403, "forbidden", "Downloading is not allowed on this link")
   ```
5. **Record, then serve.** I add 1 to `access_count`, write the `viewed` or `downloaded` audit row, create a 60-second presigned S3 URL and redirect (302). View links use `inline` (opens in the browser); download links use `attachment` (saves the file).

**Why this order matters:** the log row is saved first. Even if the redirect or S3 fails afterwards, there is never an access without a log entry. That is the point of the project.

`GET /s/{token}/info` repeats checks 1 to 3 but does not write to the log. The download landing page uses it to show the file name and size, and the page open was already logged as `viewed`.

---

## 4. Key concepts, simply

**Presigned URL.** A normal S3 URL does not work for a private file. A presigned URL is the same URL with a signature added, made with my AWS keys. S3 checks the signature and the expiry time. My app makes one with `generate_presigned_url(...)`, valid for 60 seconds, for one action on one file. After 60 seconds it stops working.

**JWT in an HttpOnly cookie.** After login the server creates a JWT: a small signed token holding only the user id and the expiry time (12 hours). It is signed with `JWT_SECRET`, so nobody can change it without the server noticing. The server puts it in a cookie called `ss_session` with `HttpOnly` (JavaScript cannot read it, so an injected script cannot steal it), `SameSite=Lax` (the browser does not send it on cross-site POSTs) and `Secure` in production (HTTPS only).

**Argon2 hashing.** I never store passwords. I store an Argon2 hash: a one-way, salted, deliberately slow and memory-hungry function. At login I hash the attempt and compare. If the database leaks, attackers still cannot read the passwords, and guessing is expensive for them.

**Soft delete.** Deleting a file removes the object from S3 but only sets `deleted_at` on the database row. Old audit entries still point to a real file name, and the history stays complete.

**Append-only audit log.** The app only ever INSERTs into `audit_logs`; it has no code that updates or deletes rows, and `log_event()` is the single writer. A log that cannot be edited is a log you can trust. (A stronger version would also remove UPDATE and DELETE rights from the database user.)

**Why the bucket is private.** If the bucket were public, anybody with the URL could read a file forever and I could not expire, revoke or log it. With a private bucket the only way to a file is through my app, which checks the link and writes the log first.

**Why the app redirects to S3 instead of streaming the file.** Streaming would push every byte through my server (slow, costly, memory heavy). With a redirect S3 does the heavy work, and my app only decides who gets a 60-second ticket. The log is still written before the ticket is issued.

---

## 5. Thirty likely interview questions

**Security**

1. **How do you stop someone guessing a share link?** The token is `secrets.token_urlsafe(32)`: 256 random bits from the operating system's secure random generator. Guessing one is not realistic.
2. **What if someone forwards the link?** It works for whoever has it until it expires or is revoked, like a "anyone with the link" share. That is why every access is logged with IP and browser, expiry is short, and the owner can revoke. Restricting links to named emails is a next step.
3. **Why 60 seconds for the presigned URL?** The S3 URL is only a hand-off ticket. If it leaks, it is useless almost immediately. The long-lived credential is my share link, which I check, log and can revoke every time.
4. **How are passwords stored?** Argon2 hashes via `argon2-cffi`, never the password. The hash is never returned by the API or logged.
5. **Why a cookie and not localStorage for the JWT?** An `HttpOnly` cookie cannot be read by JavaScript, so a cross-site scripting bug cannot steal the session. `SameSite=Lax` also limits cross-site request forgery.
6. **How do you stop one user reading another user's files?** Every route with `{id}` loads the row filtered by `owner_id = current_user.id`. No match returns 404, not 403, so the existence of the file is not even revealed. Tests check this.
7. **What stops brute-force logins?** Max 10 failed logins per IP per 5 minutes, kept in an in-memory dict. Argon2 is slow by design too. In production I would use Redis so the counter is shared and survives restarts.
8. **How do you protect against dangerous uploads?** An extension allow-list, a 10 MB limit enforced while reading (even if the header lies), empty files refused, a random S3 key, and a content type chosen by my server from the extension rather than trusted from the browser. There is no malware scanning; that is a listed improvement.
9. **What does "view only" really protect?** It stops casual saving through my app. Anyone who can see a file can still screenshot it. The real fix is watermarking with the viewer's details.

**AWS**

10. **What is an IAM role and why use one?** An identity attached to the EC2 server with temporary credentials, so no AWS keys sit on the machine, limited to put/get/delete on one bucket (least privilege). Locally I use a limited IAM user for the same bucket.
11. **What is S3 and why not store files in the database?** S3 is cheap, very durable object storage. Big binary files in PostgreSQL make backups and queries heavy. The database holds only metadata.
12. **Why are the files named with a UUID?** So the file name never leaks and two files with the same name never collide. The real name lives in the database.
13. **Which region and why does it matter?** `ap-southeast-2` (Sydney). The bucket, the app and later RDS and EC2 should be in the same region for latency and cost. The S3 client also needs the regional endpoint or presigned URLs break.
14. **How would you deploy it?** EC2 running Uvicorn behind Nginx with a Let's Encrypt certificate, PostgreSQL on RDS with no public access (security group only accepts the EC2 instance), the S3 bucket private with an IAM role on the instance, and Uvicorn run by `systemd`.

**Databases**

15. **Why PostgreSQL and not SQLite?** Many users writing at the same time, real constraints, `TIMESTAMPTZ`, and a managed version (RDS) with backups. SQLite is for one-user apps.
16. **Why store timestamps in UTC?** One reference time avoids daylight-saving bugs and server-location bugs. The browser converts to local time for display.
17. **What does the index on `audit_logs` do?** `idx_audit_file_time (file_id, created_at DESC)` makes "show events for this file, newest first" fast without scanning the whole table.
18. **Why do you use a soft delete?** To keep audit history meaningful (a log row about a file that no longer exists in the table would be an orphan) and to avoid accidental data loss.
19. **How do you keep the audit log trustworthy?** One function writes it, it only inserts, and the row is written before the file is served. Tests check that the row count only grows and old rows never change.

**Design choices**

20. **Why redirect to S3 instead of sending the file yourself?** The server stays light and fast; S3 does the transfer. Because the audit row is saved before the redirect, nothing is served without a log entry.
21. **Why not give users the presigned URL as the share link?** I could not revoke it, could not log each access, and the maximum lifetime would be limited by AWS. My own token gives me full control.
22. **Why plain JavaScript, no React?** Nothing to build, nothing extra to explain. The app has three pages, so a framework would be more to defend than the problem needs.
23. **Why is the status of a link not stored?** `active`, `expired` and `revoked` follow from `revoked_at` and `expires_at`, so a stored status could go out of date. I calculate it on each request.
24. **How do you check expiry exactly?** I compare `expires_at` with `datetime.now(timezone.utc)` on every request, so a link dies to the second, with no background job.
25. **What happens if the database is down?** The app cannot check the link, so the request fails and nothing is served. For a security product, failing closed is safer than serving.

**Scaling and improvement**

26. **How would you scale it?** The app is stateless (the session is in a cookie), so run several copies behind a load balancer. Add a read replica for the dashboard queries and partition `audit_logs` by month. Move the login rate limit to Redis.
27. **How would you handle a 2 GB file?** Let the browser upload straight to S3 with a presigned upload URL (multipart), so the file never passes through my server.
28. **What would you improve next?** S3 versioning for file history, PDF watermarking with the viewer's email, links restricted to named emails, malware scanning on upload, email alerts, and database migrations with Alembic.
29. **How did you test it?** `pytest` with a separate test database and a mocked S3. It covers signup and login, upload rules, ownership (404 for other users), every expiry option, active, expired and revoked links, view-only vs download, and that the audit log only grows.
30. **What was the hardest part?** Pick one you really hit. Two real ones from this build: making sure every access is logged even though S3 serves the bytes (solved by writing the log first and redirecting afterwards), and presigned URLs failing with a 307 redirect until I set the regional S3 endpoint.

---

## 6. Known limits (say these honestly)

- **View-only cannot stop screenshots** or someone photographing the screen.
- **A presigned URL works for 60 seconds** for anyone who gets it, and the `viewed` row is written when the link is opened, not when S3 finishes sending bytes.
- **The login rate limit is in memory:** it resets when the app restarts and is not shared between servers. It is keyed on the direct connection IP, so behind a proxy it would need the real client IP. Production would use Redis.
- **`X-Forwarded-For` can be faked** if the app is reached directly instead of behind a trusted proxy, so the IP in the audit log is only as trustworthy as the setup in front of the app.
- **Sessions cannot be revoked early:** logout deletes the cookie, but a copied JWT stays valid until its 12 hours end.
- **Tables are created without migrations** (`create_all`). Changing a column later needs a tool such as Alembic.
- **Links are bearer links:** anyone holding the URL can open it. Tokens in URLs can also appear in browser history or proxy logs.
- **Uploads pass through the server** (max 10 MB), so big files would need direct-to-S3 uploads.
- **No malware scanning, no password reset, no email verification** (all out of scope on purpose).
- **Email validation is a simple pattern check**, not a full email library.
- **Expired links and soft-deleted rows stay in the database**; there is no clean-up job.
- **The audit log is protected by code, not by the database.** The app never updates or deletes it, but a database user with full rights still could.

---

## 7. Choices I made where the spec was open

| Topic | Choice | Why |
| --- | --- | --- |
| `.gitignore` | Rewrote it. Every line had three leading spaces, so nothing was being ignored (it would have committed `.env` and `venv/`). Added `.pytest_cache/`. | Safety. |
| `blueprint.md` | Moved from the project root to `docs/blueprint.md`. | The spec says it lives in `docs/`. |
| AWS keys | `config.py` calls `load_dotenv()` (python-dotenv is installed automatically with pydantic-settings). | boto3 only reads real environment variables, not `.env` files. |
| S3 client | Set the regional endpoint and virtual-host addressing. | Without it presigned URLs returned "307 TemporaryRedirect". |
| Upload form field | Named `upload`. | Avoids a clash with the `File` model name in the code. |
| Content type | Chosen from the extension by the server, not trusted from the browser. | A file cannot pretend to be HTML. |
| Chart days | Days are UTC days; "last 7 days" means today and the 6 days before. | One simple rule used by both the cards and the chart. |
| Revoking twice | Allowed (idempotent) but only the first revoke writes a `link_revoked` row. | No duplicate log entries. |
| Deleting a file | Revokes its links and writes one `delete` row (not one row per link). | Matches the spec. |
| Rate limit IP | Uses the direct connection IP; the audit log uses `X-Forwarded-For` first. | The spec asks for this in `log_event`; trusting a header for security limits would be weaker. |
| Email check | A simple regex instead of a library. | No extra library allowed. |
| Extra files | `scripts/__init__.py` and `tests/__init__.py` so `python -m scripts.seed_demo` and test imports work. | They are `__init__.py` files only. |
| Test dependency warning | `starlette.testclient` prints a deprecation notice about `httpx`. | It is only a warning; I did not install anything outside the allowed list. |
