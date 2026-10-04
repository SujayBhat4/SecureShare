from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog


# Finds the visitor's IP. Behind a proxy (Nginx) the real IP is the first value
# in the X-Forwarded-For header; otherwise we use the direct connection.
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host if request.client else "unknown"


# The ONLY function in the app that writes audit rows. It only ever INSERTs
# (never updates or deletes), which is what makes the log trustworthy.
# It also commits, so any change made just before it (like access_count + 1)
# is saved in the same transaction as the log row.
def log_event(
    db: Session,
    action: str,
    request: Request,
    user_id: int | None = None,
    file_id: int | None = None,
    link_id: int | None = None,
    detail: str | None = None,
) -> None:
    row = AuditLog(
        action=action,
        user_id=user_id,
        file_id=file_id,
        link_id=link_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:255],
        detail=detail,
    )
    db.add(row)
    db.commit()
