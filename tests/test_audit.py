from sqlalchemy import func, select

from app.models import AuditLog
from tests.conftest import make_link, upload_text_file


def audit_count(db):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(AuditLog))


def test_audit_log_only_grows(user_a, client, db):
    """Run every kind of action and check that the row count never goes down."""
    counts = []
    file = upload_text_file(user_a)                                   # upload
    counts.append(audit_count(db))
    link, token = make_link(user_a, file["id"], "view")               # link_created
    counts.append(audit_count(db))
    client.get(f"/s/{token}")                                         # viewed
    counts.append(audit_count(db))
    client.get(f"/s/{token}/download")                                # access_denied
    counts.append(audit_count(db))
    user_a.delete(f"/api/links/{link['id']}")                         # link_revoked
    counts.append(audit_count(db))
    client.get(f"/s/{token}")                                         # access_denied
    counts.append(audit_count(db))
    user_a.delete(f"/api/files/{file['id']}")                         # delete
    counts.append(audit_count(db))

    assert counts == sorted(counts)
    assert counts == [1, 2, 3, 4, 5, 6, 7]  # exactly one new row per action


def test_audit_rows_are_never_changed(user_a, client, db):
    file = upload_text_file(user_a)
    _, token = make_link(user_a, file["id"])
    client.get(f"/s/{token}")
    before = [(r.id, r.action, r.detail, r.created_at) for r in db.scalars(select(AuditLog).order_by(AuditLog.id))]

    user_a.delete(f"/api/files/{file['id']}")
    client.get(f"/s/{token}")

    db.expire_all()
    after = [(r.id, r.action, r.detail, r.created_at) for r in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert after[: len(before)] == before  # the old rows are exactly as they were


def test_audit_list_has_friendly_fields_and_filters(user_a, client):
    first = upload_text_file(user_a, name="first.txt")
    second = upload_text_file(user_a, name="second.txt")
    _, token = make_link(user_a, first["id"])
    client.get(f"/s/{token}")

    rows = user_a.get("/api/audit").json()
    assert rows[0]["action"] == "viewed"          # newest first
    assert rows[0]["actor"] == "Link visitor"
    assert rows[0]["file_name"] == "first.txt"
    upload_row = [r for r in rows if r["action"] == "upload"][0]
    assert upload_row["actor"] == "a@example.com"

    assert {r["file_name"] for r in user_a.get(f"/api/audit?file_id={second['id']}").json()} == {"second.txt"}
    assert [r["action"] for r in user_a.get("/api/audit?action=viewed").json()] == ["viewed"]
    assert len(user_a.get("/api/audit?limit=2").json()) == 2
    assert len(user_a.get("/api/audit?limit=2&offset=2").json()) == 2
    assert user_a.get("/api/audit?limit=201").status_code == 422


def test_audit_only_shows_own_files(user_a, user_b):
    upload_text_file(user_a, name="a-file.txt")
    upload_text_file(user_b, name="b-file.txt")
    assert {r["file_name"] for r in user_a.get("/api/audit").json()} == {"a-file.txt"}
    assert {r["file_name"] for r in user_b.get("/api/audit").json()} == {"b-file.txt"}


def test_audit_requires_login(client):
    assert client.get("/api/audit").status_code == 401
    assert client.get("/api/audit/summary").status_code == 401


def test_summary_counts(user_a, client):
    file = upload_text_file(user_a)
    upload_text_file(user_a, name="other.txt")
    _, view_token = make_link(user_a, file["id"], "view")
    _, download_token = make_link(user_a, file["id"], "download")
    client.get(f"/s/{view_token}")
    client.get(f"/s/{view_token}")
    client.get(f"/s/{view_token}/download")      # blocked
    client.get(f"/s/{download_token}/download")  # downloaded

    summary = user_a.get("/api/audit/summary").json()
    assert summary["total_files"] == 2
    assert summary["active_links"] == 2
    assert summary["views_7d"] == 2
    assert summary["downloads_7d"] == 1
    assert summary["denied_7d"] == 1
    assert len(summary["daily"]) == 7
    today = summary["daily"][-1]
    assert (today["views"], today["downloads"]) == (2, 1)
