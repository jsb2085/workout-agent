from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app import db as db_module
from app.config import get_settings
from app.db import Base, configure_engine, get_session
from app.main import app
from app.services import storage

USERS = {
    "alice": {"email": "alice@example.com", "password": "password1", "name": "Alice"},
    "bob": {"email": "bob@example.com", "password": "password2", "name": "Bob"},
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


async def register_user(client: AsyncClient, key: str) -> str:
    payload = USERS[key]
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def alice_token(client: AsyncClient) -> str:
    return await register_user(client, "alice")


@pytest.fixture
async def bob_token(client: AsyncClient) -> str:
    return await register_user(client, "bob")


@pytest.fixture
def mcp_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().mcp_agent_token}"}
