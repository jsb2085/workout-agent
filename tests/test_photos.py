from tests.conftest import auth_header


async def test_photo_upload_stores_object_key(client, alice_token):
    headers = auth_header(alice_token)
    response = await client.post(
        "/physic-photos/",
        headers=headers,
        files={"picture": ("progress.jpg", b"fake-image-bytes", "image/jpeg")},
        data={"is_goal": "false", "is_current": "true", "date": "2026-09-05T09:00:00+00:00"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "object_key" in body
    assert body["is_current"] is True
    assert body["is_goal"] is False

    url = await client.get(f"/physic-photos/{body['id']}/url", headers=headers)
    assert url.status_code == 200
    assert url.json()["url"].startswith("https://minio.test/")


async def test_bob_cannot_see_alice_photo(client, alice_token, bob_token):
    created = await client.post(
        "/physic-photos/",
        headers=auth_header(alice_token),
        files={"picture": ("progress.jpg", b"fake-image-bytes", "image/jpeg")},
        data={"is_goal": "true", "is_current": "false", "date": "2026-09-05T09:00:00+00:00"},
    )
    assert created.status_code == 201
    photo_id = created.json()["id"]

    bob_list = await client.get("/physic-photos/", headers=auth_header(bob_token))
    assert bob_list.json() == []

    bob_get = await client.get(f"/physic-photos/{photo_id}", headers=auth_header(bob_token))
    assert bob_get.status_code == 404


async def test_physique_comparison_returns_latest_and_goal(client, alice_token):
    headers = auth_header(alice_token)
    goal = await client.post(
        "/physic-photos/",
        headers=headers,
        files={"picture": ("goal.jpg", b"goal-bytes", "image/jpeg")},
        data={"is_goal": "true", "is_current": "false", "date": "2026-01-01T09:00:00+00:00"},
    )
    current = await client.post(
        "/physic-photos/",
        headers=headers,
        files={"picture": ("now.jpg", b"now-bytes", "image/jpeg")},
        data={"is_goal": "false", "is_current": "true", "date": "2026-09-05T09:00:00+00:00"},
    )
    assert goal.status_code == 201
    assert current.status_code == 201

    comparison = await client.get("/physic-photos/comparison", headers=headers)
    assert comparison.status_code == 200, comparison.text
    body = comparison.json()
    assert body["missing"] == []
    assert body["goal"]["id"] == goal.json()["id"]
    assert body["latest"]["id"] == current.json()["id"]
    assert body["latest"]["url"].startswith("https://minio.test/")
    assert body["goal"]["url"].startswith("https://minio.test/")
