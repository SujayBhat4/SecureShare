import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_event
from app.database import get_db
from app.models import File, ShareLink, User
from app.routers.files import get_own_file
from app.schemas import LinkCreate, LinkOut
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["links"])

# The four expiry choices and how long each one lasts
EXPIRY_OPTIONS = {
    "10m": timedelta(minutes=10),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
}


# Works out whether a link is active, expired or revoked right now
def link_status(link: ShareLink) -> str:
    if link.revoked_at is not None:
        return "revoked"
    if link.expires_at <= datetime.now(timezone.utc):
        return "expired"
    return "active"


# Turns a database link into the JSON shape we return, including the full URL
# built from the address the request came to (so it works locally and in production)
def link_out(link: ShareLink, request: Request) -> LinkOut:
    item = LinkOut.model_validate(link, from_attributes=True)
    item.status = link_status(link)
    item.url = f"{str(request.base_url).rstrip('/')}/s/{link.token}"
    return item


# Creates a share link for one of the user's files
@router.post("/files/{file_id}/links", response_model=LinkOut, status_code=201)
def create_link(
    file_id: int,
    body: LinkCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file = get_own_file(db, file_id, user)
    link = ShareLink(
        file_id=file.id,
        token=secrets.token_urlsafe(32),  # 256 random bits: impossible to guess
        permission=body.permission,
        expires_at=datetime.now(timezone.utc) + EXPIRY_OPTIONS[body.expires_in],
    )
    db.add(link)
    db.commit()
    log_event(
        db, "link_created", request,
        user_id=user.id, file_id=file.id, link_id=link.id,
        detail=f"{body.permission}, expires in {body.expires_in}",
    )
    return link_out(link, request)


# Lists all links of one file (newest first) with their status
@router.get("/files/{file_id}/links", response_model=list[LinkOut])
def list_links(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file = get_own_file(db, file_id, user)
    links = db.scalars(
        select(ShareLink).where(ShareLink.file_id == file.id).order_by(ShareLink.id.desc())
    ).all()
    return [link_out(link, request) for link in links]


# Revokes a link so it stops working immediately. Safe to call twice.
@router.delete("/links/{link_id}")
def revoke_link(
    link_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Join to files so we only find links whose file belongs to this user
    link = db.scalar(
        select(ShareLink)
        .join(File, ShareLink.file_id == File.id)
        .where(ShareLink.id == link_id, File.owner_id == user.id)
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    if link.revoked_at is None:
        link.revoked_at = datetime.now(timezone.utc)
        db.commit()
        log_event(db, "link_revoked", request, user_id=user.id, file_id=link.file_id, link_id=link.id)
    return {"detail": "Link revoked"}
