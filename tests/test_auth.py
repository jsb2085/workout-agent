from app.services.tokens import decode_access_token
from tests.conftest import USERS


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_register_issues_jwt(client):
    response = await client.post("/auth/register", json=USERS["alice"])
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["name"] == "Alice"
    user_id = decode_access_token(body["access_token"])
    assert str(user_id) == body["user"]["id"]


async def test_register_rejects_duplicate_email(client):
    first = await client.post("/auth/register", json=USERS["alice"])
    assert first.status_code == 201
    second = await client.post("/auth/register", json=USERS["alice"])
    assert second.status_code == 409


async def test_login_returns_same_user(client):
    created = await client.post("/auth/register", json=USERS["alice"])
    assert created.status_code == 201
    response = await client.post(
        "/auth/login",
        json={"email": USERS["alice"]["email"], "password": USERS["alice"]["password"]},
    )
    assert response.status_code == 200
    assert response.json()["user"]["id"] == created.json()["user"]["id"]


async def test_login_rejects_bad_password(client):
    await client.post("/auth/register", json=USERS["alice"])
    response = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


async def test_login_rejects_unknown_email(client):
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "password1"},
    )
    assert response.status_code == 401


async def test_me_requires_auth(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client, alice_token):
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {alice_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"
