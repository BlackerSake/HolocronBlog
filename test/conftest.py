import asyncio
import tempfile, os
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

from unittest.mock import AsyncMock
from app.main import app
from app.core.database import Base, get_db
from starlette.middleware.base import BaseHTTPMiddleware

# 测试环境移除限流中间件，避免跨测试累计计数器或依赖 Redis
app.user_middleware = [
    mw for mw in app.user_middleware if mw.cls is not BaseHTTPMiddleware
]
from app.core.security import get_password_hash, create_access_token
from app.models.user import User
from app.models.role import Role, role_permission
from app.models.permission import Permission
from app.core.permissions import ALL_PERMISSIONS, DEFAULT_ROLES
from app.services.permission_service import get_cached_permissions, cache_user_permissions

# 基础设施


class FakeLikeRedis:
    def __init__(self):
        self.strings = {}
        self.sets = {}
        self.streams = {}
        self.zsets = {}

    async def exists(self, key):
        return int(key in self.strings or key in self.sets)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.strings:
            return None
        self.strings[key] = str(value)
        return True

    async def delete(self, *keys):
        for key in keys:
            self.strings.pop(key, None)
            self.sets.pop(key, None)
            self.zsets.pop(key, None)
        return len(keys)

    async def expire(self, key, seconds):
        return int(key in self.strings or key in self.sets)

    async def sadd(self, key, *values):
        bucket = self.sets.setdefault(key, set())
        before = len(bucket)
        bucket.update(str(value) for value in values)
        return len(bucket) - before

    async def sismember(self, key, value):
        return str(value) in self.sets.get(key, set())

    async def get(self, key):
        return self.strings.get(key)

    async def eval(self, script, numkeys, *values):
        users_key, count_key = values[:2]
        stream_key = values[2] if numkeys >= 3 else None
        user_id = str(values[numkeys])
        target_id = str(values[numkeys + 1]) if len(values) > numkeys + 1 else ""
        target_type = str(values[numkeys + 2]) if len(values) > numkeys + 2 else ""
        users = self.sets.setdefault(users_key, set())
        count = int(self.strings.get(count_key, "0"))
        if user_id in users:
            users.remove(user_id)
            count = max(count - 1, 0)
            self.strings[count_key] = str(count)
            is_liked = 0
        else:
            users.add(user_id)
            count += 1
            self.strings[count_key] = str(count)
            is_liked = 1
        event_id = None
        if stream_key:
            event_id = await self.xadd(stream_key, {
                "user_id": user_id,
                "target_id": target_id,
                "target_type": target_type,
                "is_liked": is_liked,
            })
        return [is_liked, count, event_id]

    async def xadd(self, key, fields, maxlen=None, approximate=True):
        stream = self.streams.setdefault(key, [])
        message_id = f"{len(stream) + 1}-0"
        stream.append((message_id, {k: str(v) for k, v in fields.items()}))
        return message_id

    async def xack(self, key, group, *ids):
        return len(ids)
    async def publish(self, channel, message):
        return 0
    
    def pubsub(self):
        class FakePubSub:
            async def psubscribe(self, *patterns):
                return None
            async def punsubscribe(self, *patterns):
                return None
            async def close(self):
                return None
            async def listen(self):
                if False:
                    yield None
                return
        return FakePubSub()
    
    async def zincrby(self, key, amount, member):
        zset = self.zsets.setdefault(key, {})
        member = str(member)
        zset[member] = float(zset.get(member, 0)) + float(amount)
        return zset[member]
    
    async def zadd(self, key, mapping):
        zset = self.zsets.setdefault(key, {})
        for member, score in mapping.items():
            zset[str(member)] = float(score)
        return len(mapping)
    
    async def zrevrange(self, key, start, end):
        items = sorted(
            self.zsets.get(key, {}).items(),
            key=lambda item: item[1],
            reverse=True
        )
        if end == -1:
            sliced = items[start:]
        else:
            sliced = items[start: end + 1]
        return [member for member, _ in sliced]
    
    async def zrem(self, key, *members):
        zset = self.zsets.setdefault(key, {})
        removed = 0
        for member in members:
            removed += int(zset.pop(str(member), None) is not None)
        return removed

    async def scan(self, cursor=0, match=None, count=100):
        import fnmatch
        keys = [k for k in self.strings if match is None or fnmatch.fnmatch(k, match)]
        return (0, keys)

@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client():
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# DB

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
    async with TestAsyncSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def reset_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def mock_redis():
    import app.services.permission_service as svc
    svc.get_cached_permissions = AsyncMock(return_value=None)
    svc.cache_user_permissions = AsyncMock()
    svc.delete_user_permissions = AsyncMock()
    import app.services.like_service as like_svc
    import app.core.like_stream as like_stream
    fake_like_redis = FakeLikeRedis()
    like_svc.redis_client = fake_like_redis
    like_stream.redis_client = fake_like_redis
    # 各路由模块在 import 时已拿到原始函数引用，需在自身命名空间也 mock
    import app.routers.admin as admin_mod
    admin_mod.delete_user_permissions = AsyncMock()

    import app.services.ranking_service as ranking_svc
    ranking_svc.redis_client = fake_like_redis

    import app.core.cache_consistency as cache_consistency
    cache_consistency.redis_client = fake_like_redis
    return fake_like_redis


@pytest_asyncio.fixture
async def db_session():
    async with TestAsyncSessionLocal() as session:
        yield session


# 角色 & 权限

@pytest_asyncio.fixture(autouse=True)
async def seed_roles(db_session: AsyncSession):
    perm_map = {}
    for perm_name in ALL_PERMISSIONS:
        existing = await db_session.execute(
            select(Permission).where(Permission.name == perm_name)
        )
        perm = existing.scalar_one_or_none()
        if not perm:
            perm = Permission(name=perm_name, description=perm_name)
            db_session.add(perm)
        perm_map[perm_name] = perm
    await db_session.commit()

    for name, cfg in DEFAULT_ROLES.items():
        existing = await db_session.execute(
            select(Role).where(Role.name == name)
        )
        role = existing.scalar_one_or_none()
        if not role:
            role = Role(name=name, description=cfg["description"], is_system=cfg["is_system"])
            db_session.add(role)
            await db_session.flush()
        for perm_name in cfg["permissions"]:
            if perm_name in perm_map:
                await db_session.execute(
                    role_permission.insert().values(
                        role_id=role.id, permission_id=perm_map[perm_name].id
                    )
                )
    await db_session.commit()


# 用户

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    role = await db_session.execute(select(Role).where(Role.name == "user"))
    user = User(
        username="testuser",
        email="testuser@example.com",
        password=get_password_hash("testpass123"),
        role_id=role.scalar_one().id,
        is_active=True,
        nickname="test",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    role = await db_session.execute(select(Role).where(Role.name == "admin"))
    user = User(
        username="adminuser",
        email="admin@example.com",
        password=get_password_hash("adminpass123"),
        role_id=role.scalar_one().id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    role = await db_session.execute(select(Role).where(Role.name == "user"))
    user = User(
        username="otheruser",
        email="other@example.com",
        password=get_password_hash("otherpass123"),
        role_id=role.scalar_one().id,
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

# 分类 & 标签 (给 article 用)

from app.models.category import Category
from app.models.tag import Tag


@pytest_asyncio.fixture
async def category(db_session: AsyncSession) -> Category:
    cat = Category(name="tech", description="tech category")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)
    return cat


@pytest_asyncio.fixture
async def tag(db_session: AsyncSession) -> Tag:
    t = Tag(name="python")
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


# 文章

from app.models.article import Article


@pytest_asyncio.fixture
async def article(db_session, test_user, category) -> Article:
    a = Article(
        title="Test Article",
        slug="test-article",
        content="# Hello",
        content_html="<h1>Hello</h1>",
        summary="test",
        is_published=True,
        author_id=test_user.id,
        category_id=category.id,
    )
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)
    return a


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


# 评论

from app.models.comment import Comment


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


@pytest_asyncio.fixture
async def deleted_comment(db_session, published_article, test_user):
    comment = Comment(
        content="to be deleted",
        article_id=published_article.id,
        author_id=test_user.id,
        is_deleted=True,
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment




def pytest_sessionfinish(session: pytest.Session):
    """全部测试结束后清理临时数据库文件"""
    if os.path.exists(_test_db_path):
        os.unlink(_test_db_path)
