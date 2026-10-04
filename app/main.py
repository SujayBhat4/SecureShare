from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (importing registers the tables on Base)
from app.database import Base, engine
from app.routers import audit, auth, files, links, share

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Create any missing tables when the app starts (no migrations tool, to keep it simple)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SecureShare")


# Adds three small security headers to every response:
# - nosniff: the browser must trust our Content-Type and not guess
# - X-Frame-Options DENY: our pages cannot be shown inside another site's iframe
# - no-referrer: the browser does not tell other sites which page the user came from
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.include_router(auth.router)
app.include_router(files.router)
app.include_router(links.router)
app.include_router(audit.router)
app.include_router(share.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Health check: lets us (and later a load balancer) see that the app is running
@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# The home page is the landing and login page
@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/static/index.html")
