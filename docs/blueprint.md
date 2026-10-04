# SecureShare: Project Blueprint

Last updated: 2026-10-04 · Owner: Sujay

> Put this file at `docs/blueprint.md`. It is the background design document. The detailed build instructions are in `BUILD_SECURESHARE.md`, which wins if the two files disagree.

---

## 1. SecureShare in plain language

SecureShare is a web app for sharing confidential files safely: every link expires, every link has a permission, and every view or download is recorded.

**The problem.** Companies share sensitive files (audit reports, contracts, payslips) over email attachments or public drive links. Once sent, the sender loses control: the link works forever, anyone can forward it, and nobody knows who opened it.

**What SecureShare does.** The owner uploads a file to a private cloud bucket, creates a link with an expiry time and a permission (view only, or download), and shares it. When someone opens the link, the app checks it, records the access, and only then serves the file. After expiry the link is dead.

**Why it fits PwC.** PwC handles confidential client documents every day, and audit is its core business. The project touches three of its practice areas at once: cloud (AWS), security (access control, hashing) and audit (a complete access trail).

**One-line pitch:** "A secure way for companies to share confidential files. Every link expires, access is controlled, and every view or download is logged, so you always know who accessed what and when."

**Hosting:** FastAPI on AWS EC2, PostgreSQL on AWS RDS, files in a private AWS S3 bucket. (Local development uses Docker Postgres first. Deployment comes after the local version works.)

---

## 2. Scope

Exactly five features. Everything else is a "future improvement" to mention in the interview, not something to build.

| ID | Feature | What it does |
| --- | --- | --- |
| F1 | Accounts | Sign up, log in and log out with email and password. Session is a JWT in an HttpOnly cookie. |
| F2 | Upload and list files | Upload a file (max 10 MB) to the private S3 bucket. See your own files with name, size and upload time. Delete a file. |
| F3 | Expiring share links | Create a link for a file with an expiry of 10 minutes, 1 hour, 1 day or 7 days. Revoke a link early. |
| F4 | Link permissions | Each link is either view only (opens in the browser) or download (saves the file). |
| F5 | Audit trail and dashboard | Every upload, link creation, view, download, blocked attempt and revoke is recorded. The dashboard shows the log, filterable by file and action. |

**Who opens a shared link?** Anyone with the link, without logging in, like a Google Drive "anyone with the link" share. The audit log records their IP address and browser. Restricting links to named email addresses is a future improvement.

### Deliberately excluded

| Feature | Why it is out |
| --- | --- |
| Editing files in the browser | A whole project on its own. |
| Malware scanning | Needs ClamAV packaged on the server or a paid AWS service. File type and size checks cover the basics. |
| File version history | Easy with S3 versioning, but adds UI and questions. A good first "next step". |
| PDF watermarking | Medium effort, PDF only. A good second "next step". |
| Teams, roles, sharing between accounts | Adds an authorization model you would need to defend. |
| Email notifications | Needs an email service and templates; adds nothing to the demo. |

---

## 3. Architecture

One FastAPI app on EC2 is the only gatekeeper: the database is private, the bucket is private, and every file access passes through the app's checks first.

```
 File owner / Link visitor
          │  HTTPS
          ▼
 ┌─────────────────────────────────────────────┐
 │ AWS · ap-southeast-2 (Sydney)               │
 │  ┌──────────── VPC (private network) ─────┐ │
 │  │  EC2: Nginx + FastAPI                  │ │
 │  │   - checks logins and share links      │ │      ┌──────────────────┐
 │  │   - writes every audit row        ─────┼─┼────▶ │ S3 bucket        │
 │  │   - IAM role: one bucket only    boto3 │ │      │ private, UUID    │
 │  │          │ SQL (port 5432)             │ │      │ file names       │
 │  │          ▼                             │ │      └──────────────────┘
 │  │  RDS PostgreSQL (no public access)     │ │               │
 │  └────────────────────────────────────────┘ │               │
 └─────────────────────────────────────────────┘               │
          ▲                                                    │
          └──────── redirect with a 60-second presigned URL ───┘
```

Browsers talk only to the app. The app reads and writes Postgres inside the VPC and reaches S3 through its IAM role. S3 serves file bytes only through a short-lived presigned URL that the app hands out.

### Flow 1: Upload

1. Owner picks a file; the browser sends it to `POST /api/files`.
2. The app checks login, size (max 10 MB) and file type.
3. The app uploads it to S3 as `uploads/<uuid>`.
4. The app saves a `files` row and an `upload` audit row.

### Flow 2: Create a share link

1. Owner picks a permission (view or download) and an expiry.
2. The app checks the owner owns the file, generates a random token, saves a `share_links` row with `expires_at`, and logs `link_created`.
3. The app returns `https://<your-domain>/s/<token>`.

### Flow 3: Open a share link (the heart of the project)

On every request to `/s/{token}` the app runs these checks in order. A failed check logs `access_denied` with the reason and shows the error page.

1. **Does the link exist?** Look up the token.
2. **Is it still active?** Not revoked, and the file not deleted.
3. **Is it within its time?** `expires_at` is later than now (UTC).
4. **Is the action allowed?** The `/download` route also requires `permission = download`.
5. **Record and serve.** Increment `access_count`, log `viewed` or `downloaded`, create a 60-second presigned URL, and redirect. View uses `Content-Disposition: inline`; download uses `attachment`.

```python
@router.get("/s/{token}")
def open_link(token: str, request: Request, db: Session = Depends(get_db)):
    link = db.query(ShareLink).filter_by(token=token).first()
    if link is None:                                      # 1. exists?
        raise HTTPException(status_code=404)

    if link.revoked_at or link.file.deleted_at:           # 2. active?
        log_event(db, "access_denied", link=link, request=request, detail="revoked")
        return expired_page()

    if link.expires_at <= datetime.now(timezone.utc):     # 3. in time?
        log_event(db, "access_denied", link=link, request=request, detail="expired")
        return expired_page()

    link.access_count += 1                                # 5. record and serve
    log_event(db, "viewed", link=link, request=request)
    url = presigned_url(link.file.s3_key, disposition="inline", expires_in=60)
    return RedirectResponse(url)
```

**Why the redirect matters:** the app logs the access before S3 sends a single byte, so downloads cannot bypass the audit trail. Because the presigned URL dies after 60 seconds, forwarding it is useless; the real share link stays under the app's control.

---

## 4. Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Language | Python 3.12 | You already know it. |
| Web framework | FastAPI | Built-in validation with Pydantic, automatic API docs at `/docs`, easy file uploads. |
| Database | PostgreSQL 16 (Docker locally, AWS RDS when deployed) | Handles many users writing at once, unlike SQLite. RDS is managed: AWS handles backups and patching. |
| Database access | SQLAlchemy 2 + psycopg | Switching databases only changes the connection string. |
| File storage | AWS S3 (private bucket) | Cheap, durable storage. Presigned URLs give temporary access without making files public. |
| AWS SDK | boto3 | The official Python library for AWS. |
| Password hashing | Argon2 (`argon2-cffi`) | The current recommended password hashing algorithm. |
| Sessions | JWT (`PyJWT`) in an HttpOnly cookie | JavaScript cannot read the cookie, which protects against token theft. |
| Frontend | Plain HTML, CSS and JavaScript | Nothing to build, nothing extra to explain. FastAPI serves the files. |
| App server | Uvicorn behind Nginx on EC2 | Uvicorn runs FastAPI; Nginx handles HTTPS and forwards requests. |
| Config | `.env` read by `pydantic-settings` | Secrets never live in the code or in Git. |
| Local development | Docker (Postgres only) | One command gives you a local database. |

---

## 5. Database design

Four tables: a user owns files, a file has many share links, and every action becomes one row in the audit log.

| Table | What one row is | Key columns |
| --- | --- | --- |
| `users` | One account | `email` (unique), `password_hash` |
| `files` | One uploaded file's metadata (the bytes live in S3) | `owner_id`, `original_name`, `s3_key`, `size_bytes`, `content_type`, `deleted_at` |
| `share_links` | One link to one file | `token` (unique), `permission`, `expires_at`, `revoked_at`, `access_count` |
| `audit_logs` | One thing that happened | `action`, `file_id`, `link_id`, `user_id`, `ip_address`, `user_agent`, `created_at` |

```sql
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE files (
    id            SERIAL PRIMARY KEY,
    owner_id      INTEGER NOT NULL REFERENCES users(id),
    original_name VARCHAR(255) NOT NULL,
    s3_key        VARCHAR(512) UNIQUE NOT NULL,   -- random UUID, never the real filename
    size_bytes    INTEGER NOT NULL,
    content_type  VARCHAR(100) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ                      -- soft delete keeps audit history valid
);

CREATE TABLE share_links (
    id           SERIAL PRIMARY KEY,
    file_id      INTEGER NOT NULL REFERENCES files(id),
    token        VARCHAR(64) UNIQUE NOT NULL,      -- secrets.token_urlsafe(32)
    permission   VARCHAR(10) NOT NULL CHECK (permission IN ('view', 'download')),
    expires_at   TIMESTAMPTZ NOT NULL,
    revoked_at   TIMESTAMPTZ,
    access_count INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (
    id         SERIAL PRIMARY KEY,
    action     VARCHAR(30) NOT NULL,   -- upload, delete, link_created, link_revoked,
                                       -- viewed, downloaded, access_denied
    user_id    INTEGER REFERENCES users(id),        -- NULL when a link visitor acts
    file_id    INTEGER REFERENCES files(id),
    link_id    INTEGER REFERENCES share_links(id),
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    detail     VARCHAR(255),           -- e.g. "expired", "revoked"
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_file_time ON audit_logs (file_id, created_at DESC);
```

**Three design points to remember:**

- **Soft delete.** Deleting a file sets `deleted_at` and removes the object from S3, but keeps the row, so old audit entries still point at a real file name.
- **Random S3 keys.** Files are stored as `uploads/<uuid>`, so a filename never leaks and two files with the same name never collide.
- **Audit log is append-only.** The app only ever inserts into it, never updates or deletes. That is what makes it trustworthy as a record.

---

## 6. API endpoints

Everything under `/api` needs a logged-in user except signup and login. The `/s/{token}` routes are public and protected only by the link itself.

| Method | Path | Who | What it does |
| --- | --- | --- | --- |
| POST | `/api/auth/signup` | Anyone | Create an account. |
| POST | `/api/auth/login` | Anyone | Check password, set the session cookie. |
| POST | `/api/auth/logout` | Logged in | Clear the session cookie. |
| GET | `/api/auth/me` | Logged in | Return the current user. |
| POST | `/api/files` | Logged in | Upload a file (multipart form). Logs `upload`. |
| GET | `/api/files` | Logged in | List my files. |
| DELETE | `/api/files/{id}` | Owner | Delete from S3, soft-delete the row, revoke its links. Logs `delete`. |
| POST | `/api/files/{id}/links` | Owner | Create a link with `permission` and `expires_in`. Logs `link_created`. |
| GET | `/api/files/{id}/links` | Owner | List links for a file with status: active, expired or revoked. |
| DELETE | `/api/links/{id}` | Owner | Revoke a link. Logs `link_revoked`. |
| GET | `/api/audit` | Logged in | Audit entries for my files, newest first, filter by `file_id` and `action`. |
| GET | `/s/{token}` | Anyone with the link | Check the link, log the access, serve the file or the landing page. |
| GET | `/s/{token}/download` | Anyone with the link | Check the link and permission, log `downloaded`, send the file as an attachment. |

**Ownership rule:** every `{id}` route loads the row together with `owner_id = current_user.id`. If no row matches, it returns 404, not 403, so a user cannot even learn that another user's file exists.

---

## 7. Security decisions

| Risk | Decision |
| --- | --- |
| Files exposed publicly | S3 bucket has "Block all public access" on. Files are reachable only through a presigned URL the app creates after checking the link. |
| Presigned URL forwarded | The S3 URL the app generates lives for only 60 seconds. The long-lived thing is your share link, which the app checks every time. |
| Share link guessed | Tokens come from `secrets.token_urlsafe(32)`: 256 random bits, impossible to guess. |
| Password database leaked | Passwords are hashed with Argon2, never stored in plain text. |
| Session token stolen by JavaScript | JWT sits in an `HttpOnly`, `SameSite=Lax` cookie (and `Secure` in production) that expires after 12 hours. |
| Seeing another user's files | Every query filters by `owner_id`; a mismatch returns 404. |
| Dangerous or huge uploads | Max 10 MB; only an allow-list of file types; file is stored under a random name. |
| AWS keys leaked | No AWS keys in code. Locally, a limited IAM user (`secureshare-app-dev`) can only put, get and delete objects in this one bucket. On EC2 the app uses an IAM role with the same minimal permissions. |
| Secrets in Git | All secrets in `.env`, which is in `.gitignore`; only `.env.example` is committed. |
| Database reachable from the internet | RDS is not publicly accessible; its security group accepts connections only from the EC2 instance. |
| Traffic sniffed | HTTPS through Nginx with a free Let's Encrypt certificate. |

**Be honest about one limit:** "view only" stops casual downloading, but anyone who can see a file can screenshot it. Say so if asked. The real fix is watermarking with the viewer's details, which is a listed next step.

---

## 8. AWS setup and deployment (after the local version works)

Region: **ap-southeast-2 (Sydney)**. S3, RDS and EC2 must all be in the same region.

### Cost safety

- [ ] A billing budget exists (done: `secureshare-budget`, $1).
- [ ] Use the smallest sizes: `t3.micro` or `t4g.micro` for EC2 and RDS, 20 GB storage.
- [ ] **Stop RDS** when you are not working on it. AWS restarts a stopped RDS instance automatically after 7 days, so check it weekly.
- [ ] After placements, delete the RDS instance and terminate EC2.

### Deployment steps

1. **S3 bucket:** private, "Block all public access" on, default encryption on.
2. **RDS PostgreSQL:** smallest instance, "Public access: No", its own security group.
3. **EC2 instance:** Ubuntu, `t3.micro`. Security group allows SSH (22) from **your IP only**, and HTTP/HTTPS (80, 443) from anywhere.
4. **Connect them:** the RDS security group allows port 5432 only from the EC2 security group.
5. **IAM role for EC2:** allows only `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on `arn:aws:s3:::<your-bucket>/*`. Attach it to the instance so no keys live on the server.
6. **Deploy the app:** clone the repo, create a virtualenv, install requirements, write `.env`, run Uvicorn as a `systemd` service so it restarts on crash or reboot.
7. **Nginx + HTTPS:** Nginx forwards to Uvicorn on port 8000. Point a domain or free subdomain at the EC2 public IP and run Certbot for a Let's Encrypt certificate.

**Architecture sentence for the README:** "Users reach Nginx on EC2 over HTTPS. FastAPI stores metadata and audit logs in RDS PostgreSQL inside the VPC, and files in a private S3 bucket accessed through an IAM role."

---

## 9. Demo script (2 minutes)

Two browser windows: your logged-in account on the left, a private window (the "client") on the right.

1. **Pitch (15 s).** Say the one-line pitch.
2. **Upload (15 s).** Upload `client_audit_report.pdf`. Mention: "it goes to a private S3 bucket under a random name."
3. **View-only link (20 s).** Create a view-only link that expires in 10 minutes. Paste it in the private window: the PDF opens. Try `/download` on it: "Download not allowed for this link."
4. **Audit trail (20 s).** Open the dashboard: `viewed` and `access_denied` rows with time, IP and browser. Say: "if this file leaks, we know exactly who opened it and when."
5. **Revoke (15 s).** Click revoke, refresh the private window: "This link is no longer available."
6. **Expiry (15 s).** Open a link you created earlier with the shortest expiry, now expired. Show the expired page and the denial in the log.
7. **Cloud tour (20 s).** Show the S3 console: "Block all public access" is on.

**Before every demo:** create a link that will already be expired by demo time, log in on both windows, keep the S3 console tab open, and have a screen recording ready in case the Wi-Fi fails.

---

## 10. Interview preparation

Practise each answer out loud until it takes under 30 seconds.

| Question | Short answer |
| --- | --- |
| Walk me through the project. | The one-line pitch, then the architecture sentence, then the checks when a link opens. |
| Why is the S3 bucket private? | So no file can be reached except through my app, which checks the link and writes the audit log first. |
| What is a presigned URL? | A temporary S3 URL signed with AWS credentials. It allows one action on one object until it expires. I make them last 60 seconds. |
| Why not give users the presigned URL directly as the share link? | Then I could not revoke it, could not log each access, and the longest expiry would be limited by AWS. My own token gives me control. |
| How do you check expiry? | Compare `expires_at` with the current UTC time on every request. Expiry is checked by the app, so it is exact to the second. |
| How are passwords stored? | As Argon2 hashes. At login I hash the attempt and compare; the real password is never stored. |
| Why JWT in a cookie, not localStorage? | An HttpOnly cookie cannot be read by JavaScript, so a script injected into the page cannot steal the session. |
| Why PostgreSQL instead of SQLite? | Many users writing at the same time, a managed service on RDS with backups, and it is what production systems use. |
| What is an IAM role and why use one? | An identity attached to the EC2 instance with temporary credentials. No AWS keys on the server, and it can only touch one bucket: least privilege. |
| What if the database is down? | Links fail closed: the app cannot verify a link, so it denies access. For a security product, refusing is safer than serving. |
| How would you scale it? | Run several app servers behind a load balancer (the app is stateless), add a read replica for the dashboard, partition `audit_logs` by month. |
| How would you handle a 2 GB file? | Let the browser upload straight to S3 with a presigned upload URL, so the file never passes through my server. |
| What would you add next? | S3 versioning for file history, PDF watermarking with the viewer's email, restricting links to named emails, malware scanning on upload. |
| What was the hardest part? | Pick one you actually hit while building, for example making sure downloads are logged even though S3 serves the bytes. |

**Know these cold:** the checks in `routers/share.py`, `log_event()` in `audit.py`, and `presigned_url()` in `s3_client.py`. If an interviewer asks you to open one file, open `share.py`; it shows the whole project in about 40 lines.
