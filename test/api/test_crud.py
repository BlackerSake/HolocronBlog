"""通用 CRUD 路由测试：直接测 create_crud_router，不绑定具体模型"""
import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.core.database import Base, get_db
from app.routers.crud import create_crud_router
from app.main import app as main_app


# 创建 item 模型（只为测试 create_crud_router 的泛型逻辑） ──
class Item(Base):
    __tablename__ = "test_items"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)


class ItemCreate(BaseModel):
    name: str


class ItemUpdate(BaseModel):
    name: str | None = None


class ItemOut(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


@pytest.fixture
def crud_app():
    """用 create_crud_router 创建一个临时 app"""
    app = FastAPI()
    router = create_crud_router(
        model=Item,
        create_schema=ItemCreate,
        update_schema=ItemUpdate,
        output_schema=ItemOut,
        prefix="/items",
        tags=["Items"],
        resource_name="item",
        permission="category:manage",
    )
    app.include_router(router)
    # 复用主 app 注入的 get_db 覆盖，指向测试数据库
    if get_db in main_app.dependency_overrides:
        app.dependency_overrides[get_db] = main_app.dependency_overrides[get_db]
    return app


@pytest.fixture
async def crud_client(crud_app):
    transport = ASGITransport(app=crud_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestGenericCrud:
    """create_crud_router 的完整 CRUD + 权限测试"""

    LIST_URL = "/items"

    @pytest.fixture(autouse=True)
    async def _prepare_items(self, db_session):
        db_session.add_all([
            Item(name="item-a"),
            Item(name="item-b"),
        ])
        await db_session.commit()

    async def test_list(self, crud_client: AsyncClient):
        """GET → 列表"""
        resp = await crud_client.get(self.LIST_URL)
        assert resp.status_code == 200
        names = {i["name"] for i in resp.json()["data"]}
        assert "item-a" in names
        assert "item-b" in names

    async def test_create_without_auth(self, crud_client: AsyncClient):
        """未认证 → 401"""
        resp = await crud_client.post(self.LIST_URL, json={"name": "hack"})
        assert resp.status_code == 401

    async def test_create_by_non_admin(
        self, crud_client: AsyncClient, auth_headers: dict
    ):
        """普通用户 → 403"""
        resp = await crud_client.post(
            self.LIST_URL, json={"name": "newitem"}, headers=auth_headers,
        )
        assert resp.status_code == 403

    async def test_create_by_admin(
        self, crud_client: AsyncClient, admin_headers: dict
    ):
        """管理员 → 201"""
        resp = await crud_client.post(
            self.LIST_URL, json={"name": "admin-item"}, headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["name"] == "admin-item"

    async def test_create_duplicate_name(
        self, crud_client: AsyncClient, admin_headers: dict
    ):
        """重复名称 → 400"""
        resp = await crud_client.post(
            self.LIST_URL, json={"name": "item-a"}, headers=admin_headers,
        )
        assert resp.status_code == 400

    async def test_update_by_admin(
        self, crud_client: AsyncClient, admin_headers: dict
    ):
        """管理员更新 → 200"""
        resp = await crud_client.put(
            f"{self.LIST_URL}/1",
            json={"name": "item-updated"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "item-updated"

    async def test_update_nonexistent(
        self, crud_client: AsyncClient, admin_headers: dict
    ):
        """更新不存在的 → 404"""
        resp = await crud_client.put(
            f"{self.LIST_URL}/999", json={"name": "ghost"}, headers=admin_headers,
        )
        assert resp.status_code == 404

    async def test_delete_by_admin(
        self, crud_client: AsyncClient, admin_headers: dict
    ):
        """管理员删除 → 204"""
        resp = await crud_client.delete(f"{self.LIST_URL}/1", headers=admin_headers)
        assert resp.status_code == 204

    async def test_delete_by_non_admin(
        self, crud_client: AsyncClient, auth_headers: dict
    ):
        """普通用户删除 → 403"""
        resp = await crud_client.delete(f"{self.LIST_URL}/1", headers=auth_headers)
        assert resp.status_code == 403

    async def test_delete_nonexistent(
        self, crud_client: AsyncClient, admin_headers: dict
    ):
        """删除不存在的 → 404"""
        resp = await crud_client.delete(f"{self.LIST_URL}/999", headers=admin_headers)
        assert resp.status_code == 404
