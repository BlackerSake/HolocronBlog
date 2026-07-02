from app.services.permission_service import get_current_user_permissions


async def test_get_current_user_permissions(test_user):
    """测试用户权限获取 -> 返回用户权限"""
    permissions = await get_current_user_permissions(test_user)
    assert "upload:create" in permissions


async def test_get_admin_permissions(admin_user):
    """测试管理员权限获取 -> 返回管理员权限"""
    permissions = await get_current_user_permissions(admin_user)
    assert permissions == {
        "article:create", "article:update", "article:delete", "article:publish", "article:unpublish",
        "category:manage", "tag:manage",
        "comment:create", "comment:delete",
        "upload:create",
        "user:manage", "role:manage",
    }

async  def test_get_cache_permissions(test_user):
    """测试缓存权限获取 -> 返回用户权限"""
    permissions = await get_current_user_permissions(test_user)
    assert "upload:create" in permissions

