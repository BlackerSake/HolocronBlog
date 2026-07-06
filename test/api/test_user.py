

from test.conftest import test_user


class TestUpdateUserProfile:

    async def test_update_nickname(self, client, auth_headers):
        """修改 nickname -> 200"""
        resp = await client.patch(
            "/api/v1/me/profile",
            json={"nickname": "new_nickname"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        date = resp.json()
        assert date["data"]["nickname"] == "new_nickname"
    
    async def test_update_avatar(self, client, auth_headers):
        """修改 avatar -> 200"""
        resp = await client.patch(
            "/api/v1/me/profile",
            json={"avatar": "https://example.com/avatar.png"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        date = resp.json()
        assert date["data"]["avatar"] == "https://example.com/avatar.png"
    
    async def test_update_bio(self, client, auth_headers):
        """修改 bio -> 200"""
        resp = await client.patch(
            "/api/v1/me/profile",
            json={"bio": "new bio"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        date = resp.json()
        assert date["data"]["bio"] == "new bio"
    
    async def test_partly_update(self, client, auth_headers):
        """部分修改 -> 200 其他部分没有改变"""
        await client.patch(
            "/api/v1/me/profile",
            json={"bio": "bio"},
            headers=auth_headers,
        )
        # 修改 nickname 部分
        resp = await client.patch(
            "/api/v1/me/profile",
            json={"nickname": "new_nickname"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["nickname"] == "new_nickname"
        assert resp.json()["data"]["bio"] == "bio"

    async def test_update_invalid_url(self, client, auth_headers):
        """用不合法url -> 422"""
        resp = await client.patch(
            "/api/v1/me/profile",
            json={"avatar": "invalid_url"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
    
    async def test_without_auth(self, client):
        """未登录 -> 401"""
        resp = await client.patch(
            "/api/v1/me/profile",
            json={"nickname": "new_nickname"},
        )
        assert resp.status_code == 401

class TestViewUserProfile:

    async def test_view_user_profile(self, client, auth_headers, test_user):
        """查看用户公开资料 -> 200"""
        resp = await client.get(
            f"/api/v1/users/{test_user.id}/profile",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["nickname"] == "test"
        assert data["data"]["username"] == test_user.username
        assert "email" not in data  # 不暴露邮箱

    async def test_user_not_found(self, client, auth_headers):
        """用户不存在 -> 404"""
        resp = await client.get(
            "/api/v1/users/999999/profile",
            headers=auth_headers,
        )
        assert resp.status_code == 404