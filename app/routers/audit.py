from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, File, ShareLink, User
from app.schemas import AuditOut, DayCount, SummaryOut
from app.security import get_current_user

router = APIRouter(prefix="/api/audit", tags=["audit"])


# The ids of all files the user owns, including deleted ones (their history stays visible)
def own_file_ids(user: User):
    return select(File.id).where(File.owner_id == user.id)


# Lists audit rows for the user's files, newest first, with optional filters
@router.get("", response_model=list[AuditOut])
def list_audit(
    file_id: int | None = None,
    action: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(AuditLog).where(AuditLog.file_id.in_(own_file_ids(user)))
    if file_id is not None:
        query = query.where(AuditLog.file_id == file_id)
    if action:
        query = query.where(AuditLog.action == action)
    rows = db.scalars(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
    ).all()

    return [
        AuditOut(
            id=row.id,
            action=row.action,
            file_id=row.file_id,
            file_name=row.file.original_name if row.file else None,
            actor=row.user.email if row.user else "Link visitor",
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            detail=row.detail,
            created_at=row.created_at,
        )
        for row in rows
    ]


# Numbers for the dashboard cards and the 7-day chart.
# "Last 7 days" means today and the 6 days before it (days are UTC days).
@router.get("/summary", response_model=SummaryOut)
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    today = now.date()
    first_day = today - timedelta(days=6)
    window_start = datetime.combine(first_day, time.min, tzinfo=timezone.utc)

    total_files = db.scalar(
        select(func.count()).select_from(File).where(File.owner_id == user.id, File.deleted_at.is_(None))
    )
    active_links = db.scalar(
        select(func.count())
        .select_from(ShareLink)
        .join(File, ShareLink.file_id == File.id)
        .where(
            File.owner_id == user.id,
            File.deleted_at.is_(None),
            ShareLink.revoked_at.is_(None),
            ShareLink.expires_at > now,
        )
    )

    # Fetch only the time and action of recent rows, then count them per day in Python
    recent = db.execute(
        select(AuditLog.action, AuditLog.created_at).where(
            AuditLog.file_id.in_(own_file_ids(user)),
            AuditLog.created_at >= window_start,
            AuditLog.action.in_(["viewed", "downloaded", "access_denied"]),
        )
    ).all()

    days = {first_day + timedelta(days=i): DayCount(date=(first_day + timedelta(days=i)).isoformat(), views=0, downloads=0) for i in range(7)}
    totals = {"viewed": 0, "downloaded": 0, "access_denied": 0}
    for action, created_at in recent:
        totals[action] += 1
        day = created_at.astimezone(timezone.utc).date()
        if action == "viewed":
            days[day].views += 1
        elif action == "downloaded":
            days[day].downloads += 1

    return SummaryOut(
        total_files=total_files,
        active_links=active_links,
        views_7d=totals["viewed"],
        downloads_7d=totals["downloaded"],
        denied_7d=totals["access_denied"],
        daily=list(days.values()),
    )
