from app.routers.auth import MAX_FAILED_LOGINS


def test_signup_logs_user_in(client):
    response = client.post("/api/auth/signup", json={"email": "New@Example.com", "password": "password123"})
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"  # stored in lowercase
    assert "password" not in response.text
    assert client.get("/api/auth/me").status_code == 200


def test_session_cookie_is_httponly(client):
    response = client.post("/api/auth/signup", json={"email": "a@example.com", "password": "password123"})
    cookie = response.headers["set-cookie"].lower()
    assert "ss_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_duplicate_email_is_rejected(client):
    body = {"email": "a@example.com", "password": "password123"}
    assert client.post("/api/auth/signup", json=body).status_code == 201
    assert client.post("/api/auth/signup", json={"email": "A@example.com", "password": "password123"}).status_code == 409


def test_short_password_is_rejected(client):
    response = client.post("/api/auth/signup", json={"email": "a@example.com", "password": "short"})
    assert response.status_code == 422


def test_login_success(client, user_a):
    response = client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert response.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "a@example.com"


def test_login_failure_gives_same_message_for_wrong_email_and_wrong_password(client, user_a):
    wrong_password = client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope-nope"})
    wrong_email = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert wrong_password.status_code == 401
    assert wrong_email.status_code == 401
    assert wrong_password.json() == wrong_email.json() == {"detail": "Invalid email or password"}


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_logout_ends_the_session(user_a):
    assert user_a.post("/api/auth/logout").status_code == 200
    assert user_a.get("/api/auth/me").status_code == 401


def test_login_is_rate_limited_after_too_many_failures(client, user_a):
    for _ in range(MAX_FAILED_LOGINS):
        client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-password"})
    # Even the correct password is refused now
    response = client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert response.status_code == 429
