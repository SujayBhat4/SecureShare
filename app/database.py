from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# The engine is the connection pool to PostgreSQL
engine = create_engine(settings.database_url)

# Each request gets its own SessionLocal() so requests do not share state
SessionLocal = sessionmaker(bind=engine, autoflush=False)


# Every model class in models.py inherits from this Base
class Base(DeclarativeBase):
    pass


# FastAPI dependency: opens a database session for one request and always closes it
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
