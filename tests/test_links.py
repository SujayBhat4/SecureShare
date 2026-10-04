from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import AuditLog, File, ShareLink
from tests.conftest import make_link, upload_text_file


# ---------- Uploads ----------

def test_upload_rejects_wrong_file_type(user_a):
    response = user_a.post("/api/files", files={"upload": ("virus.exe", b"data")})
    assert response.status_code == 400


def test_upload_rejects_empty_file(user_a):
    response = user_a.post("/api/files", files={"upload": ("empty.txt", b"")})
    assert response.status_code == 400


def test_upload_rejects_file_above_10_mb(user_a):
    too_big = b"x" * (10 * 1024 * 1024 + 1)
    response = user_a.post("/api/files", files={"upload": ("big.txt", too_big)})
    assert response.status_code == 400


def test_upload_stores_file_under_random_key(user_a, mock_s3, db):
    upload_text_file(user_a, name="secret-plan.txt")
    key = db.scalar(select(File.s3_key))
    assert key.startswith("uploads/")
    assert "secret-plan" not in key
    assert key in mock_s3


def test_upload_requires_login(client):
    assert client.post("/api/files", files={"upload": ("a.txt", b"x")}).status_code == 401


# ---------- Ownership: user B must get 404 for user A's things ----------

def test_user_b_cannot_see_delete_or_link_user_a_file(user_a, user_b):
    file = upload_text_file(user_a)
    link, _ = make_link(user_a, file["id"])

    assert user_b.get("/api/files").json() == []
    assert user_b.delete(f"/api/files/{file['id']}").status_code == 404
    assert user_b.post(f"/api/files/{file['id']}/links", json={"permission": "view", "expires_in": "1h"}).status_code == 404
    assert user_b.get(f"/api/files/{file['id']}/links").status_code == 404
    assert user_b.delete(f"/api/links/{link['id']}").status_code == 404

    # ...and nothing changed for user A
    assert len(user_a.get("/api/files").json()) == 1
    assert user_a.get(f"/api/files/{file['id']}/links").json()[0]["status"] == "active"


# ---------- Creating links ----------

def test_link_expiry_matches_each_option(user_a):
    file = upload_text_file(user_a)
    expected = {"10m": timedelta(minutes=10), "1h": timedelta(hours=1), "1d": timedelta(days=1), "7d": timedelta(days=7)}
    for option, duration in expected.items():
        link, _ = make_link(user_a, file["id"], expires_in=option)
        expires_at = datetime.fromisoformat(link["expires_at"])
        remaining = expires_at - datetime.now(timezone.utc)
        assert abs(remaining - duration) < timedelta(seconds=5), option


def test_link_rejects_unknown_expiry_and_permission(user_a):
    file = upload_text_file(user_a)
    assert user_a.post(f"/api/files/{file['id']}/links", json={"permission": "view", "expires_in": "2d"}).status_code == 422
    assert user_a.post(f"/api/files/{file['id']}/links", json={"permission": "edit", "expires_in": "1h"}).status_code == 422


def test_link_list_shows_status_and_revoke_is_idempotent(user_a, db):
    file = upload_text_file(user_a)
    active, _ = make_link(user_a, file["id"])
    expired, expired_token = make_link(user_a, file["id"])
    revoked, _ = make_link(user_a, file["id"])

    row = db.scalar(select(ShareLink).where(ShareLink.token == expired_token))
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert user_a.delete(f"/api/links/{revoked['id']}").status_code == 200
    assert user_a.delete(f"/api/links/{revoked['id']}").status_code == 200  # second time is fine

    statuses = {link["id"]: link["status"] for link in user_a.get(f"/api/files/{file['id']}/links").json()}
    assert statuses == {active["id"]: "active", expired["id"]: "expired", revoked["id"]: "revoked"}
    assert user_a.get("/api/files").json()[0]["active_link_count"] == 1


def test_deleting_a_file_revokes_its_links(user_a, client):
    file = upload_text_file(user_a)
    _, token = make_link(user_a, file["id"])
    assert user_a.delete(f"/api/files/{file['id']}").status_code == 200
    assert user_a.get("/api/files").json() == []
    assert client.get(f"/s/{token}").status_code == 410


# ---------- Opening links (the share flow) ----------

def actions(db):
    return [(row.action, row.detail) for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]


def test_active_view_link_logs_viewed_and_redirects(user_a, client, db):
    file = upload_text_file(user_a)
    link, token = make_link(user_a, file["id"], "view")

    response = client.get(f"/s/{token}", headers={"User-Agent": "TestBrowser", "X-Forwarded-For": "203.0.113.5"})

    assert response.status_code == 302
    assert response.headers["location"].endswith("attachment=False")  # shown inline, not saved
    viewed = db.scalars(select(AuditLog).where(AuditLog.action == "viewed")).one()
    assert viewed.link_id == link["id"]
    assert viewed.user_id is None  # a visitor, not a logged-in user
    assert viewed.ip_address == "203.0.113.5"
    assert viewed.user_agent == "TestBrowser"
    assert db.scalar(select(ShareLink.access_count)) == 1


def test_expired_link_returns_410_and_logs_denied(user_a, client, db):
    file = upload_text_file(user_a)
    _, token = make_link(user_a, file["id"])
    row = db.scalar(select(ShareLink))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    response = client.get(f"/s/{token}")

    assert response.status_code == 410
    assert "This link has expired" in response.text
    assert ("access_denied", "expired") in actions(db)
    assert db.scalar(select(ShareLink.access_count)) == 0


def test_revoked_link_returns_410_and_logs_denied(user_a, client, db):
    file = upload_text_file(user_a)
    link, token = make_link(user_a, file["id"])
    user_a.delete(f"/api/links/{link['id']}")

    response = client.get(f"/s/{token}")

    assert response.status_code == 410
    assert "no longer available" in response.text
    assert ("access_denied", "revoked") in actions(db)


def test_unknown_token_returns_404_page(client):
    response = client.get("/s/not-a-real-token")
    assert response.status_code == 404
    assert "Link not found" in response.text


def test_download_on_view_only_link_is_blocked_and_logged(user_a, client, db):
    file = upload_text_file(user_a)
    _, token = make_link(user_a, file["id"], "view")

    response = client.get(f"/s/{token}/download")

    assert response.status_code == 403
    assert "Downloading is not allowed" in response.text
    assert ("access_denied", "view-only link") in actions(db)
    assert db.scalar(select(ShareLink.access_count)) == 0


def test_download_link_logs_downloaded_and_redirects_as_attachment(user_a, client, db):
    file = upload_text_file(user_a)
    _, token = make_link(user_a, file["id"], "download")

    response = client.get(f"/s/{token}/download")

    assert response.status_code == 302
    assert response.headers["location"].endswith("attachment=True")
    assert ("downloaded", None) in actions(db)


def test_download_link_landing_page_and_info(user_a, client, db):
    file = upload_text_file(user_a, name="report.txt", content=b"12345")
    _, token = make_link(user_a, file["id"], "download")

    page = client.get(f"/s/{token}")
    assert page.status_code == 200
    assert "Download" in page.text
    assert ("viewed", None) in actions(db)

    info = client.get(f"/s/{token}/info")
    assert info.json()["original_name"] == "report.txt"
    assert info.json()["size_bytes"] == 5
    assert "s3_key" not in info.text
    # asking for info does not add a second "viewed" row
    assert [a for a, _ in actions(db)].count("viewed") == 1


def test_expired_link_also_blocks_download_route_and_info(user_a, client, db):
    file = upload_text_file(user_a)
    _, token = make_link(user_a, file["id"], "download")
    row = db.scalar(select(ShareLink))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    assert client.get(f"/s/{token}/download").status_code == 410
    assert client.get(f"/s/{token}/info").status_code == 410


def test_security_headers_are_set(client):
    headers = client.get("/healthz").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
