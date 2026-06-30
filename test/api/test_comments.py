


class TestCreateComment:
    """POST /api/v1/articles/{slug}/comments"""

    async def test_create_comment_with_no_auth(
            self, client, published_article
    ):
        """用户未认证 -> 返回401"""
        resp = await client.post(
            f"/articles/{published_article.slug}/comments",
            json={"content": "test comment"},
        )
        assert resp.status_code == 401
    
    async def test_article_not_existing(self, client, auth_headers):
        """文章不存在 -> 404"""
        resp = await client.post(
            "/articles/not-existing/comments",
            json={"content": "test comment"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
    
    async def test_create_comment_success(
        self, client, auth_headers, published_article,
    ):
        """创建成功 -> 201"""
        resp = await client.post(
            f"/articles/{published_article.slug}/comments",
            json={"content": "test comment"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["content"] == "test comment"
        assert resp.json()["data"]["parent_id"] is None


class TestListComments:
    async def test_list_comments_with_out_auth(self, client, published_article, auth_headers):
        """未认证 -> 200"""
        resp = await client.get(
            f"/articles/{published_article.slug}/comments",
            headers=auth_headers,
        )
        assert resp.status_code == 200
    
    async def trst_list_comments_not_existing(self, client, auth_headers, published_article):
        """文章不存在 -> 404"""
        resp = await client.get(
            f"/articles/{published_article.slug}1/comments",
            headers=auth_headers,
        )
        assert resp.status_code == 404
    
    async def test_list_comments_with_empty(self, client, auth_headers, published_article):
        """文章没有评论 -> 返回空列表"""
        resp = await client.get(
            f"/articles/{published_article.slug}/comments",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []
    
    async def test_list_comments_with_comments(self, client, auth_headers, published_article, existing_comment):
        """文章有评论 -> 返回评论列表"""
        resp = await client.get(
            f"/articles/{published_article.slug}/comments",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data[0]["content"] == "existing comment"
        assert data[0]["id"] == existing_comment.id

class TestDeleteComment:

    async def test_delete_success(self, client, auth_headers, existing_comment):
        """删除评论成功 -> 204 No Content"""
        resp = await client.delete(
            f"/comments/{existing_comment.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204
