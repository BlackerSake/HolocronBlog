import pytest

from app.services.admin_service import query_all_user_role


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
    
class TestQueryArticles:

    async def test_search_by_username(self, db_session):
        """测试按用户名搜索用户"""
        items, total = await query_all_user_role(db_session, search="charlie")
        assert total == 1
        assert items[0].username == "charlie"
        assert items[0].role.name == "admin"
        assert items[0].email == "charlie@example.com"
    async def test_search_by_email(self, db_session):
        """测试按邮箱搜索用户"""
        items, total = await query_all_user_role(db_session, search="bob@example.com")
        assert total == 1
        assert items[0].username == "bob"
        assert items[0].role.name == "user"
        assert items[0].email == "bob@example.com"
    async def test_search_by_role_name(self, db_session):
        """按角色名筛选"""
        items, total = await query_all_user_role(db_session, role_name="admin")
        assert total == 2
        usernames = {item.username for item in items}
        assert usernames == {"alice", "charlie"}
    
    
    async def test_search_no_match(self, db_session):
        """测试搜索无匹配项"""
        items, total = await query_all_user_role(db_session, search="nonexistent")
        assert total == 0
        assert items == []
    
    async def test_with_pagination(self, db_session):
        """测试分页功能"""
        items, total = await query_all_user_role(db_session, page=1, per_page=1)
        assert total == 3
        assert len(items) == 1
    
    async def test_filter_by_role_name(self, db_session):
        """测试按角色名过滤用户"""
        items, total = await query_all_user_role(db_session, role_name="admin")
        assert total == 2
        usernames = {item.username for item in items}
        assert usernames == {"alice", "charlie"}
    async def test_admin_sees_all_users(self, db_session):
        """测试管理员查看所有用户"""
        items, total = await query_all_user_role(db_session)
        assert total == 3
        usernames = {item.username for item in items}
        assert usernames == {"alice", "bob", "charlie"}

        


