import os

import psycopg
import pytest
from dotenv import load_dotenv

# Point the app at a separate test database BEFORE the app is imported.
# Environment variables win over .env, so settings.database_url will be the test one.
load_dotenv()
real_url = os.environ["DATABASE_URL"]
TEST_DB_NAME = "secureshare_test"
os.environ["DATABASE_URL"] = real_url.rsplit("/", 1)[0] + "/" + TEST_DB_NAME

# Create the test database if it does not exist yet. This must happen before the app is
# imported, because importing app.main already connects to the database and creates tables.
with psycopg.connect(real_url, autocommit=True) as connection:
    exists = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,)).fetchone()
    if not exists:
        connection.execute(f"CREATE DATABASE {TEST_DB_NAME}")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import s3_client  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import auth  # noqa: E402


# Builds fresh tables once at the start of the test run
@pytest.fixture(scope="session", autouse=True)
def test_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


# Before every test: empty all tables (test code may do this; the app never does)
# and forget old failed logins, so tests do not affect each other
@pytest.fixture(autouse=True)
def clean_state(test_database):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE audit_logs, share_links, files, users RESTART IDENTITY CASCADE"))
    auth.failed_logins.clear()


# Replaces the real S3 functions so tests never touch AWS.
# presigned_url returns a fake address that shows which kind of link was asked for.
@pytest.fixture(autouse=True)
def mock_s3(monkeypatch):
    stored = {}
    monkeypatch.setattr(s3_client, "upload_file", lambda key, data, content_type: stored.__setitem__(key, data))
    monkeypatch.setattr(s3_client, "delete_file", lambda key: stored.pop(key, None))
    monkeypatch.setattr(
        s3_client,
        "presigned_url",
        lambda key, content_type, original_name, as_attachment: f"https://s3.test/{key}?attachment={as_attachment}",
    )
    return stored


# A direct database session for checking rows or changing data inside a test
@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


# Makes a new browser-like client (own cookie jar) that is not logged in
def new_client() -> TestClient:
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def client():
    return new_client()


# A client that is already signed up and logged in as user A
@pytest.fixture
def user_a():
    client = new_client()
    client.post("/api/auth/signup", json={"email": "a@example.com", "password": "password123"})
    return client


# A second logged-in user, to test that users cannot see each other's data
@pytest.fixture
def user_b():
    client = new_client()
    client.post("/api/auth/signup", json={"email": "b@example.com", "password": "password123"})
    return client


# Uploads a small text file as the given client and returns the file JSON
def upload_text_file(client, name="notes.txt", content=b"hello"):
    response = client.post("/api/files", files={"upload": (name, content)})
    assert response.status_code == 201, response.text
    return response.json()


# Creates a share link for a file and returns (link JSON, token)
def make_link(client, file_id, permission="view", expires_in="1h"):
    response = client.post(f"/api/files/{file_id}/links", json={"permission": permission, "expires_in": expires_in})
    assert response.status_code == 201, response.text
    link = response.json()
    return link, link["url"].rsplit("/", 1)[1]
