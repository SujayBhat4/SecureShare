"""Creates a demo account with sample files, links and a week of activity.

Run from the project root:   python -m scripts.seed_demo
Safe to run twice: it does nothing if the demo user already exists.
"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, ShareLink, User

DEMO_EMAIL = "demo@secureshare.dev"
DEMO_PASSWORD = "Demo@12345"

# A few pretend visitors, so the audit table shows different IPs and browsers
VISITORS = [
    ("203.0.113.24", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36"),
    ("198.51.100.77", "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) Safari/605.1.15"),
    ("192.0.2.153", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) Mobile/15E148"),
    ("203.0.113.201", "Mozilla/5.0 (X11; Linux x86_64) Firefox/127.0"),
]


# Builds a tiny but valid one-page PDF containing the given line of text
def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 20 Tf 72 720 Td ({text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n{body}\nendobj\n"
    xref_start = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    return pdf.encode("latin-1")


# Opens a share URL as if a visitor with this IP and browser had clicked it
def visit(client: TestClient, url: str, visitor: tuple, suffix: str = "") -> None:
    path = "/s/" + url.rsplit("/s/", 1)[1] + suffix
    client.get(path, headers={"X-Forwarded-For": visitor[0], "User-Agent": visitor[1]})


def main() -> None:
    db = SessionLocal()
    if db.scalar(select(User).where(User.email == DEMO_EMAIL)):
        print("Demo user already exists, nothing to do.")
        return

    # Real code paths: we call our own API exactly like the browser does
    client = TestClient(app, follow_redirects=False, headers={"X-Forwarded-For": "203.0.113.10"})
    client.post("/api/auth/signup", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})

    pdf = client.post("/api/files", files={"upload": ("client_audit_report.pdf", make_pdf("Client Audit Report (demo)"), "application/pdf")}).json()
    txt = client.post("/api/files", files={"upload": ("meeting_notes.txt", b"Confidential meeting notes (demo).\n", "text/plain")}).json()

    def new_link(file_id: int, permission: str, expires_in: str) -> dict:
        return client.post(f"/api/files/{file_id}/links", json={"permission": permission, "expires_in": expires_in}).json()

    view_link = new_link(pdf["id"], "view", "7d")
    download_link = new_link(pdf["id"], "download", "1d")
    revoked_link = new_link(txt["id"], "view", "1h")
    expired_link = new_link(txt["id"], "view", "10m")
    new_link(txt["id"], "download", "7d")  # one more active link, never opened

    # Visitors today (through the real /s/ routes, so these rows are genuine)
    visit(client, view_link["url"], VISITORS[0])
    visit(client, view_link["url"], VISITORS[1])
    visit(client, view_link["url"], VISITORS[2])
    visit(client, view_link["url"], VISITORS[3], "/download")  # view-only: blocked
    visit(client, download_link["url"], VISITORS[1])
    visit(client, download_link["url"], VISITORS[1], "/download")
    visit(client, revoked_link["url"], VISITORS[0])  # works once, then we revoke it
    client.delete(f"/api/links/{revoked_link['id']}")
    visit(client, revoked_link["url"], VISITORS[3])  # blocked: revoked

    # Make one link already expired (as if its 10 minutes passed), then try to open it
    link_row = db.scalar(select(ShareLink).where(ShareLink.id == expired_link["id"]))
    link_row.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()
    visit(client, expired_link["url"], VISITORS[2])

    # Backdated rows for the last 6 days, so the chart and table look alive on first open.
    # (day offset, hour, action, file, link, visitor index, detail)
    now = datetime.now(timezone.utc)
    history = [
        (6, 10, "viewed", pdf, view_link, 0, None), (6, 11, "viewed", pdf, view_link, 1, None),
        (5, 9, "viewed", pdf, view_link, 2, None), (5, 15, "downloaded", pdf, download_link, 1, None),
        (4, 14, "viewed", pdf, view_link, 3, None), (4, 16, "access_denied", pdf, view_link, 3, "view-only link"),
        (3, 8, "viewed", txt, expired_link, 0, None), (3, 9, "viewed", txt, expired_link, 1, None),
        (3, 9, "viewed", pdf, view_link, 2, None), (3, 17, "downloaded", pdf, download_link, 0, None),
        (2, 11, "viewed", pdf, view_link, 1, None), (2, 13, "access_denied", txt, expired_link, 3, "expired"),
        (2, 18, "downloaded", pdf, download_link, 2, None), (1, 10, "viewed", pdf, view_link, 0, None),
        (1, 12, "viewed", pdf, view_link, 3, None), (1, 12, "viewed", txt, revoked_link, 1, None),
        (1, 20, "access_denied", pdf, view_link, 2, "view-only link"), (1, 21, "downloaded", pdf, download_link, 3, None),
    ]
    for days_ago, hour, action, file, link, visitor, detail in history:
        when = (now - timedelta(days=days_ago)).replace(hour=hour, minute=(hour * 7) % 60, second=0, microsecond=0)
        db.add(AuditLog(
            action=action, file_id=file["id"], link_id=link["id"], detail=detail, created_at=when,
            ip_address=VISITORS[visitor][0], user_agent=VISITORS[visitor][1],
        ))
    db.commit()
    db.close()

    print(f"Demo data ready. Log in with {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
