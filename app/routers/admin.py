from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.log import log_call
from app.models.role import Role
from app.models.user import User
from app.schemas.admin import RoleDetail, RoleUpdate, UserWithRoleList
from app.schemas.common import Response, Paginated
from app.services.permission_service import delete_user_permissions
from app.services.admin_service import query_all_user_role

router = APIRouter(prefix="/admin", tags=["Admin"])


@log_call
@router.get("/users", response_model=Response[Paginated[UserWithRoleList]])
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: str | None = None,
    role_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("role:manage")),
):
    """
    获取用户列表

    支持分页、按用户名/邮箱搜索、按角色名筛选。需 role:manage 权限。

    Args:
        page: 页码，从 1 开始
        per_page: 每页数量，默认 10，最大 100
        search: 搜索关键词（可选，匹配用户名或邮箱）
        role_name: 角色名称筛选（可选）
        db: 数据库会话
        _: 当前登录用户（仅做权限校验）

    Returns:
        Response[Paginated[UserWithRoleList]] — 用户列表及分页信息
    """
    item, total = await query_all_user_role(
        db, page=page,
        per_page=per_page,
        role_name=role_name,
        search=search,
    )
    return Response(data={
        "items": item, "total": total,
        "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    })

@log_call
@router.put("/users/{user_id}", response_model=Response[UserWithRoleList])
async def update_user_role(
    user_id: int,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("role:manage")),
):
    """
    修改目标用户的角色

    更新用户的角色分配及活跃状态。不可修改管理员角色。需 role:manage 权限。
    修改后会清除该用户的权限缓存。

    Args:
        user_id: 目标用户 ID
        body: 角色更新数据（角色 ID 及是否活跃）
        db: 数据库会话
        _: 当前登录用户（仅做权限校验）

    Returns:
        Response[UserWithRoleList] — 更新后的用户信息

    Raises:
        HTTPException 404: 用户或角色不存在
        HTTPException 400: 尝试修改管理员角色
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    role = await db.get(Role, body.id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if user.role_id == 1:
        raise HTTPException(status_code=400, detail="不可修改管理员的角色")

    user.role_id = body.id
    if body.is_active is not None:
        user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    await delete_user_permissions(user.id)

    return Response(data=UserWithRoleList(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        role=RoleDetail.model_validate(role),
    ))





@log_call
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage")),
):
    """
    软删除用户

    将用户设为不活跃（is_active=False），不实际删除记录。不可删除自己或管理员。需 user:manage 权限。

    Args:
        user_id: 目标用户 ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        None — 无内容返回（HTTP 204）

    Raises:
        HTTPException 400: 尝试删除自己、或用户已处于禁用状态、或尝试删除管理员
        HTTPException 404: 用户不存在
    """
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="不能删除自己")


    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已处于禁用状态")
    if user.role_obj.name == "admin":
        raise HTTPException(status_code=400, detail="不可删除其他管理员")

    user.is_active = False
    await db.commit()
    return None
