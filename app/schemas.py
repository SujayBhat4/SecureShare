from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field

# Very simple email shape check: something@something.something, no spaces.
# (A full email library is not in the allowed list, so we keep it basic.)
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# Body of POST /api/auth/signup
class SignupRequest(BaseModel):
    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=128)


# Body of POST /api/auth/login
class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)


# What we return about a user. The password hash is never included.
class UserOut(BaseModel):
    id: int
    email: str


# One file in "Your files". The S3 key and bucket name are never sent to the browser.
class FileOut(BaseModel):
    id: int
    original_name: str
    size_bytes: int
    content_type: str
    created_at: datetime
    active_link_count: int = 0


# Body of POST /api/files/{id}/links
class LinkCreate(BaseModel):
    permission: Literal["view", "download"]
    expires_in: Literal["10m", "1h", "1d", "7d"]


# One share link. status is worked out on each request: active, expired or revoked.
class LinkOut(BaseModel):
    id: int
    file_id: int
    permission: str
    expires_at: datetime
    revoked_at: datetime | None
    access_count: int
    created_at: datetime
    status: str = ""
    url: str = ""


# One row of the audit table, with the file name and a friendly actor filled in
class AuditOut(BaseModel):
    id: int
    action: str
    file_id: int | None
    file_name: str | None
    actor: str
    ip_address: str | None
    user_agent: str | None
    detail: str | None
    created_at: datetime


# Views and downloads on one day (used for the bar chart)
class DayCount(BaseModel):
    date: str
    views: int
    downloads: int


# The numbers on top of the dashboard
class SummaryOut(BaseModel):
    total_files: int
    active_links: int
    views_7d: int
    downloads_7d: int
    denied_7d: int
    daily: list[DayCount]
