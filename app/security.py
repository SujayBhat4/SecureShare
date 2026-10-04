from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

COOKIE_NAME = "ss_session"

hasher = PasswordHasher()


# Turns a plain password into a salted Argon2 hash that is safe to store
def hash_password(password: str) -> str:
    return hasher.hash(password)


# Checks a login attempt against the stored hash. Returns True or False.
def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


# Builds the signed session token. It holds only the user id and the expiry time.
def create_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


# Reads a session token and returns the user id, or None if it is invalid or expired
def read_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# FastAPI dependency used by every protected route: finds the logged-in user
# from the cookie, or answers 401 if there is none.
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    user_id = read_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in to continue")
    return user
