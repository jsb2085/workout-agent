from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.db import Base, configure_engine, get_session
from app import db as db_module
from app.main import app
from app.services import google_auth, storage

GOOGLE_USERS = {
    "alice-token": {"sub": "google-alice", "email": "alice@example.com", "name": "Alice"},
    "bob-token": {"sub": "google-bob", "email": "bob@example.com", "name": "Bob"},
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(tmp_path, monkeypatch) -> AsyncIterator[AsyncClient]:
    database_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    configure_engine(database_url)
    async with db_module.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_session():
        async with db_module.SessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    def fake_verify(token: str):
        if token not in GOOGLE_USERS:
            raise ValueError("Invalid Google token")
        return GOOGLE_USERS[token]

    monkeypatch.setattr(google_auth, "verify_google_id_token", fake_verify)
    monkeypatch.setattr(storage, "ensure_bucket", lambda: None)
    monkeypatch.setattr(storage, "upload_image", lambda *args, **kwargs: None)
    monkeypatch.setattr(storage, "delete_image", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        storage,
        "presigned_get_url",
        lambda object_key, expires_seconds=3600: f"https://minio.test/{object_key}",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await db_module.engine.dispose()


async def login(client: AsyncClient, token: str) -> str:
    response = await client.post("/auth/google", json={"id_token": token})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def alice_token(client: AsyncClient) -> str:
    return await login(client, "alice-token")


@pytest.fixture
async def bob_token(client: AsyncClient) -> str:
    return await login(client, "bob-token")


@pytest.fixture
def mcp_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().mcp_agent_token}"}
