import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, SignupRequest, UserOut
from app.security import (
    COOKIE_NAME,
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Login rate limit: max 10 failed logins per IP per 5 minutes.
# Kept in memory for simplicity (production would use Redis so it survives restarts
# and is shared between servers).
MAX_FAILED_LOGINS = 10
WINDOW_SECONDS = 5 * 60
failed_logins: dict[str, list[float]] = {}


# Returns how many failed logins this IP made in the last 5 minutes
# (and forgets the older ones)
def recent_failures(ip: str) -> int:
    cutoff = time.time() - WINDOW_SECONDS
    recent = [t for t in failed_logins.get(ip, []) if t > cutoff]
    failed_logins[ip] = recent
    return len(recent)


# Puts the session JWT in an HttpOnly cookie so JavaScript cannot read it
def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_token(user_id),
        max_age=settings.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


# Creates an account and logs the new user in straight away
@router.post("/signup", response_model=UserOut, status_code=201)
def signup(body: SignupRequest, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    set_session_cookie(response, user.id)
    return user


# Checks email + password and sets the session cookie.
# Wrong email and wrong password give the same message so attackers learn nothing.
@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if recent_failures(ip) >= MAX_FAILED_LOGINS:
        raise HTTPException(status_code=429, detail="Too many failed logins. Try again in a few minutes")

    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        failed_logins.setdefault(ip, []).append(time.time())
        raise HTTPException(status_code=401, detail="Invalid email or password")

    set_session_cookie(response, user.id)
    return user


# Logs out by deleting the cookie
@router.post("/logout")
def logout(response: Response, user: User = Depends(get_current_user)):
    response.delete_cookie(COOKIE_NAME)
    return {"detail": "Logged out"}


# Returns the logged-in user. The frontend calls this to find out if someone is logged in.
@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
