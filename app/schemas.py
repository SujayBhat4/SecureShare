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
