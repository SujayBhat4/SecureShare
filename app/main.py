from fastapi import FastAPI

from app import models  # noqa: F401  (importing registers the tables on Base)
from app.database import Base, engine
from app.routers import auth, files, links

# Create any missing tables when the app starts (no migrations tool, to keep it simple)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SecureShare")
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(links.router)


# Health check: lets us (and later a load balancer) see that the app is running
@app.get("/healthz")
def healthz():
    return {"status": "ok"}
