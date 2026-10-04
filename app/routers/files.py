import logging
import os
import uuid
from datetime import datetime, timezone

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import s3_client
from app.audit import log_event
from app.config import settings
from app.database import get_db
from app.models import File, ShareLink, User
from app.schemas import FileOut
from app.security import get_current_user

router = APIRouter(prefix="/api/files", tags=["files"])

# We pick the content type from the extension ourselves instead of trusting
# the browser, so a file can never claim to be something it is not.
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "csv": "text/csv",
}


# Loads one of the current user's files, or answers 404.
# Filtering by owner_id means other users get 404, so they cannot tell the file exists.
def get_own_file(db: Session, file_id: int, user: User) -> File:
    file = db.scalar(
        select(File).where(File.id == file_id, File.owner_id == user.id, File.deleted_at.is_(None))
    )
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return file


# Reads the upload in small pieces and stops as soon as it passes the size limit,
# so a client that lies about Content-Length cannot make us load a huge file.
async def read_limited(upload: UploadFile) -> bytes:
    data = b""
    while chunk := await upload.read(1024 * 1024):
        data += chunk
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=400, detail="File is too large. The limit is 10 MB")
    return data


# Uploads a file to S3 under a random key and saves its details in the database
@router.post("", response_model=FileOut, status_code=201)
async def upload_file(
    request: Request,
    upload: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Keep only the file name part (no folders) and cap its length
    name = os.path.basename((upload.filename or "").replace("\\", "/"))[:255]
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in settings.allowed_extensions:
        allowed = ", ".join(settings.allowed_extensions)
        raise HTTPException(status_code=400, detail=f"This file type is not allowed. Allowed: {allowed}")

    data = await read_limited(upload)
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="The file is empty")

    key = f"uploads/{uuid.uuid4()}"
    content_type = CONTENT_TYPES[extension]
    try:
        s3_client.upload_file(key, data, content_type)
    except (BotoCoreError, ClientError) as error:
        logging.error("S3 upload failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="Could not save the file to storage")

    file = File(
        owner_id=user.id,
        original_name=name,
        s3_key=key,
        size_bytes=len(data),
        content_type=content_type,
    )
    db.add(file)
    db.commit()
    log_event(db, "upload", request, user_id=user.id, file_id=file.id)
    return FileOut.model_validate(file, from_attributes=True)


# Lists the user's own files, newest first, with how many links are still active
@router.get("", response_model=list[FileOut])
def list_files(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    files = db.scalars(
        select(File)
        .where(File.owner_id == user.id, File.deleted_at.is_(None))
        .order_by(File.created_at.desc(), File.id.desc())
    ).all()

    # One query that counts active links (not revoked, not expired) per file
    now = datetime.now(timezone.utc)
    counts = dict(
        db.execute(
            select(ShareLink.file_id, func.count())
            .where(
                ShareLink.file_id.in_([f.id for f in files]),
                ShareLink.revoked_at.is_(None),
                ShareLink.expires_at > now,
            )
            .group_by(ShareLink.file_id)
        ).all()
    )

    result = []
    for file in files:
        item = FileOut.model_validate(file, from_attributes=True)
        item.active_link_count = counts.get(file.id, 0)
        result.append(item)
    return result


# Deletes the file from S3, soft-deletes the row and revokes every link to it
@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file = get_own_file(db, file_id, user)
    try:
        s3_client.delete_file(file.s3_key)
    except (BotoCoreError, ClientError) as error:
        logging.error("S3 delete failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="Could not delete the file from storage")

    now = datetime.now(timezone.utc)
    file.deleted_at = now
    for link in file.links:
        if link.revoked_at is None:
            link.revoked_at = now
    db.commit()
    log_event(db, "delete", request, user_id=user.id, file_id=file.id)
    return {"detail": "File deleted"}
