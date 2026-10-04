from datetime import datetime, timezone
from html import escape
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import s3_client
from app.audit import log_event
from app.database import get_db
from app.models import ShareLink

# PUBLIC routes: anyone with the link can open them, no login.
# The link itself (a random token) is the only credential.
router = APIRouter(tags=["share"])

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


# Builds the branded "link unavailable" page. The reason picks the icon and the
# message is the text; both are put into the HTML by simple string replacement.
def error_page(status_code: int, reason: str, message: str) -> HTMLResponse:
    html = (STATIC_DIR / "link-error.html").read_text(encoding="utf-8")
    html = html.replace("{{reason}}", escape(reason)).replace("{{message}}", escape(message))
    return HTMLResponse(html, status_code=status_code)


# Looks up the link by its token. Returns None if there is no such link.
def find_link(db: Session, token: str) -> ShareLink | None:
    return db.scalar(select(ShareLink).where(ShareLink.token == token))


# Checks 2 and 3 of the flow. Returns None if the link is fine, otherwise
# (http status, page reason, message for the visitor, detail for the audit log).
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


# Opens a share link. This is the heart of the project: every check runs, and the
# access is written to the audit log BEFORE the visitor is sent to S3.
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


# Small public JSON endpoint used by the download landing page to show file details.
# It repeats checks 1 to 3 but does NOT write to the audit log (the page open was already logged).
@router.get("/s/{token}/info")
def link_info(token: str, db: Session = Depends(get_db)):
    link = find_link(db, token)
    if link is None:
        return JSONResponse({"detail": "Link not found"}, status_code=404)

    problem = find_problem(link)
    if problem:
        status_code, reason, message, detail = problem
        return JSONResponse({"detail": message}, status_code=status_code)

    return {
        "original_name": link.file.original_name,
        "size_bytes": link.file.size_bytes,
        "expires_at": link.expires_at.isoformat(),
        "permission": link.permission,
    }


# Downloads the file. Same checks 1 to 3, then the link must allow downloads.
@router.get("/s/{token}/download")
def download_file(token: str, request: Request, db: Session = Depends(get_db)):
    link = find_link(db, token)
    if link is None:
        return error_page(404, "not_found", "Link not found")

    problem = find_problem(link)
    if problem:
        status_code, reason, message, detail = problem
        log_event(db, "access_denied", request, file_id=link.file_id, link_id=link.id, detail=detail)
        return error_page(status_code, reason, message)

    # Check 4: a view-only link may not be used to save the file
    if link.permission == "view":
        log_event(db, "access_denied", request, file_id=link.file_id, link_id=link.id, detail="view-only link")
        return error_page(403, "forbidden", "Downloading is not allowed on this link")

    # Check 5: record, then serve with a "save as" header
    link.access_count += 1
    log_event(db, "downloaded", request, file_id=link.file_id, link_id=link.id)
    file = link.file
    url = s3_client.presigned_url(file.s3_key, file.content_type, file.original_name, as_attachment=True)
    return RedirectResponse(url, status_code=302)
