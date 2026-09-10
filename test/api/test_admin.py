
import pytest

from test.conftest import db_session



@pytest.fixture(autouse=True)
async def seed_users(db_session):
    from sqlalchemy import select
    from app.models.user import User
    from app.models.role import Role
    from app.core.security import get_password_hash

    role1 = (await db_session.execute(select(Role).where(Role.name == "admin"))).scalar_one()
    role2 = (await db_session.execute(select(Role).where(Role.name == "user"))).scalar_one()
    pw = get_password_hash("testpass")

    users = [
        User(id=1, username="alice", email="alice@example.com", password=pw, role_id=role1.id),
        User(id=2, username="bob", email="bob@example.com", password=pw, role_id=role2.id),
        User(id=3, username="charlie", email="charlie@example.com", password=pw, role_id=role1.id),
    ]
    db_session.add_all(users)
    await db_session.commit()

class TestListUsers:
    """GET /users 列表列出所有用户"""

    async def test_admin_sees_all_users(self, client, admin_headers):
        """管理员可以看到所有用户 -> 200"""
        response = await client.get("/admin/users", headers=admin_headers) # admin_hearders 是一个包含管理员身份验证信息的请求头 
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 4
        usernames = {item["username"] for item in data["items"]}
        assert usernames == {"adminuser", "alice", "bob", "charlie"}
    
    async def test_user_have_no_permission(self, client, auth_headers):
        """普通用户没有权限访问 -> 403"""
        response = await client.get("/admin/users", headers=auth_headers)
        assert response.status_code == 403
    
    async def test_list_pagination(self, client, admin_headers):
        """测试分页功能"""
        response = await client.get("/admin/users?page=1&per_page=2", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 4
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["pages"] == 2
    
    async def test_filter_by_role_name(self, client, admin_headers):
        """测试按角色过滤功能 -> 200"""
        response = await client.get("/admin/users?role_name=admin", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 3  # 
        usernames = {item["username"] for item in data["items"]}
        assert usernames == {"adminuser", "charlie", "alice"}
    
    async def test_search_by_username(self, client, admin_headers):
        """测试按用户名搜索用户 -> 200"""
        response = await client.get("/admin/users?search=charlie", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["username"] == "charlie"
        assert data["items"][0]["role"]["name"] == "admin"
        assert data["items"][0]["email"] == "charlie@example.com"
    
    async def test_search_by_email(self, client, admin_headers):
        """测试按邮箱搜索用户 -> 200"""
        response = await client.get("/admin/users?search=bob@example.com", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["username"] == "bob"

    async def test_search_no_match(self, client, admin_headers):
        """测试搜索无匹配项 -> 200 + 空列表"""
        response = await client.get("/admin/users?search=nonexistent", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 0
        assert data["items"] == []


class TestUpdateUserRole:
    """PUT /users/{user_id}/role 更新用户角色"""

    async def test_update_role_by_admin(self, client, admin_headers):
        """管理员更新用户角色 -> 200"""
        response = await client.put(
            "/admin/users/2",
            headers=admin_headers,
            json={"id": 2},
        )
        assert response.status_code == 200
        assert response.json()["data"]["role"]["name"] == "author"
    
    async def test_update_role_user_no_permission(self, client, auth_headers):
        """普通用户尝试更新角色 -> 403"""
        response = await client.put(
            "/admin/users/2",
            headers=auth_headers,
            json={"id": 3},
        )
        assert response.status_code == 403
        assert response.json()["message"] == "权限不足"
    
    async def test_update_role_not_existing(self, client, admin_headers):
        """更新不存在的角色 -> 404"""
        response = await client.put(
            "/admin/users/2",
            headers=admin_headers,
            json={"id": 888},
        )
        assert response.status_code == 404
        assert response.json()["message"] == "角色不存在"
    
    async def test_update_user_not_existing(self, client, admin_headers):
        """更新不存在的用户 -> 404"""
        response = await client.put(
            "/admin/users/999",
            headers=admin_headers,
            json={"id": 1},
        )
        assert response.status_code == 404
        assert response.json()["message"] == "用户不存在"

class TestDeleteUser:
    """DELETE /users/{user_id} 删除用户（软删除）"""

    async def test_delete_user_by_admin(self, client, admin_headers):
        """管理员删除用户 -> 204"""
        response = await client.delete("/admin/users/2", headers=admin_headers)
        assert response.status_code == 204
    
    async def test_delete_user_no_permission(self, client, auth_headers):
        """普通用户尝试删除用户 -> 403"""
        response = await client.delete("/admin/users/2", headers=auth_headers)
        assert response.status_code == 403
        assert response.json()["message"] == "权限不足"
    
    async def test_delete_self(self, client, admin_headers):
        """管理员adminuser尝试删除自己 -> 400"""
        response = await client.delete("/admin/users/4", headers=admin_headers)
        assert response.status_code == 400
        assert response.json()["message"] == "不能删除自己"
    
    async def test_delete_admin_user(self, client, admin_headers):
        """管理员adminuser尝试删除其他管理员charlie -> 400"""

        response = await client.delete("/admin/users/3", headers=admin_headers)
        assert response.status_code == 400
        assert response.json()["message"] == "不可删除其他管理员"
    async def test_delete_user_is_inactive(self, client, admin_headers):
        """删除已禁用的用户 -> 400"""
        await client.delete("/admin/users/2", headers=admin_headers)
        response = await client.delete("/admin/users/2", headers=admin_headers)
        assert response.status_code == 403
        assert response.json()["message"] == "权限不足"
    