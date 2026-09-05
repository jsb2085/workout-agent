from app.services.tokens import decode_access_token


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_google_login_issues_jwt(client):
    response = await client.post("/auth/google", json={"id_token": "alice-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["name"] == "Alice"
    user_id = decode_access_token(body["access_token"])
    assert str(user_id) == body["user"]["id"]


async def test_google_login_rejects_bad_token(client):
    response = await client.post("/auth/google", json={"id_token": "nope"})
    assert response.status_code == 401


async def test_me_requires_auth(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client, alice_token):
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {alice_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"
