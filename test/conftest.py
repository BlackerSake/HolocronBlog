import tempfile, os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.models.user import User, UserRole
from starlette.middleware.base import BaseHTTPMiddleware

# 测试环境下移除限流中间件，避免跨测试累计计数器或依赖 Redis
app.user_middleware = [
    mw for mw in app.user_middleware if mw.cls is not BaseHTTPMiddleware
]

# in-memory SQLite 是 per-connection 的，不同 session 互不可见
#     改用临时文件数据库，让所有 session 共享同一份数据 ──
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix="_holocron_test.db")
os.close(_test_db_fd)

test_engine = create_async_engine(
    f"sqlite+aiosqlite:///{_test_db_path}", echo=False,
)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():
    """覆盖 app 的 get_db，使用内存数据库会话"""
    async with TestAsyncSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def reset_db():
    """每个测试函数前重建所有表并重置限流计数器，测试后销毁"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """用 AsyncClient 模拟客户端，指向 FastAPI 应用"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    """提供直接的测试数据库会话，用于数据准备"""
    async with TestAsyncSessionLocal() as session:
        yield session


# 用户 fixtures

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """创建普通测试用户并返回"""
    user = User(
        username="testuser",
        email="testuser@example.com",
        password=get_password_hash("testpass123"),
        role=UserRole.USER.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """创建管理员测试用户并返回"""
    user = User(
        username="adminuser",
        email="admin@example.com",
        password=get_password_hash("adminpass123"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_token(test_user: User) -> str:
    """普通用户的 JWT token"""
    return create_access_token(data={"sub": test_user.username})


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    """管理员用户的 JWT token"""
    return create_access_token(data={"sub": admin_user.username})


@pytest_asyncio.fixture
async def auth_headers(user_token: str) -> dict[str, str]:
    """普通用户的认证请求头"""
    return {"Authorization": f"Bearer {user_token}"}


@pytest_asyncio.fixture
async def admin_headers(admin_token: str) -> dict[str, str]:
    """管理员的认证请求头"""
    return {"Authorization": f"Bearer {admin_token}"}


def pytest_sessionfinish(session: pytest.Session):
    """全部测试结束后清理临时数据库文件"""
    if os.path.exists(_test_db_path):
        os.unlink(_test_db_path)


from app.models.article import Article
from app.models.category import Category
from app.models.comment import Comment


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    user = User(
        username="otheruser",
        email="other@example.com",
        password=get_password_hash("otherpass123"),
        role=UserRole.USER.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_auth_headers(other_user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": other_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def category(db_session: AsyncSession) -> Category:
    cat = Category(name="tech", description="tech category")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)
    return cat


@pytest_asyncio.fixture
async def published_article(db_session, test_user, category):
    article = Article(
        title="Published",
        slug="published-article",
        content="# Hello",
        content_html="<h1>Hello</h1>",
        summary="summary",
        is_published=True,
        author_id=test_user.id,
        category_id=category.id,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def draft_article(db_session, test_user, category):
    article = Article(
        title="Draft",
        slug="draft-article",
        content="# Draft",
        content_html="<h1>Draft</h1>",
        summary="draft",
        is_published=False,
        author_id=test_user.id,
        category_id=category.id,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def existing_comment(db_session, published_article, test_user):
    comment = Comment(
        content="existing comment",
        article_id=published_article.id,
        author_id=test_user.id,
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment


@pytest_asyncio.fixture
async def other_user_comment(db_session, published_article, other_user):
    comment = Comment(
        content="other user's comment",
        article_id=published_article.id,
        author_id=other_user.id,
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment