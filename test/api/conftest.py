import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.security import create_access_token


@pytest_asyncio.fixture
async def user_token(test_user) -> str:
    return create_access_token(data={"sub": test_user.username})


@pytest_asyncio.fixture
async def admin_token(admin_user) -> str:
    return create_access_token(data={"sub": admin_user.username})


@pytest_asyncio.fixture
async def auth_headers(user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_token}"}


@pytest_asyncio.fixture
async def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
async def other_auth_headers(other_user) -> dict[str, str]:
    token = create_access_token(data={"sub": other_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def crud_client(client, seed_roles) -> AsyncClient:
    yield client
