from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mcp_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().mcp_agent_token}"}
