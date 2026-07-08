# crud.py,基本的CRUD
from typing import Type
from unittest import result
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.models.user import User
from app.schemas.common import Response
from app.core.log import log_call

import logging
logging.getLogger("router.crud").setLevel(logging.INFO)


def create_crud_router(
        model: Type[BaseModel],
        create_schema: Type[BaseModel],
        update_schema: Type[BaseModel],
        output_schema: Type[BaseModel],
        prefix: str,
        tags: list[str],
        resource_name: str,
        permission: str,
) -> APIRouter:
    """
    创建通用 CRUD 路由器

    为指定模型自动生成 list（公开列表）、create（创建）、update（更新）、delete（删除）四个路由端点。
    其中 create、update、delete 需要管理员权限，通过 `require_permission` 依赖检查。

    Args:
        model: SQLAlchemy 模型类
        create_schema: 创建请求的 Pydantic 模式
        update_schema: 更新请求的 Pydantic 模式
        output_schema: 输出响应的 Pydantic 模式
        prefix: 路由前缀（如 "/categories"）
        tags: 路由标签列表（用于 API 文档分组）
        resource_name: 资源中文名称（用于错误提示，如 "分类"）
        permission: 所需权限字符串（如 "category:manage"）

    Returns:
        APIRouter — 配置好的路由器实例，包含 list/create/update/delete 四个端点

    Examples:
        >>> from app.models.category import Category
        >>> from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryOut
        >>> router = create_crud_router(
        ...     model=Category,
        ...     create_schema=CategoryCreate,
        ...     update_schema=CategoryUpdate,
        ...     output_schema=CategoryOut,
        ...     prefix="/categories",
        ...     tags=["Categories"],
        ...     resource_name="category",
        ...     permission="category:manage",
        ... )

    Raises:
        HTTPException 400: 创建时名称已存在
        HTTPException 404: 更新或删除时资源不存在
    """

    router = APIRouter(prefix=prefix,tags=tags)
    
    @router.get("",response_model=Response[list[output_schema]])
    @log_call
    async def list_item(db: AsyncSession = Depends(get_db)):
        """
        获取列表

        返回所有资源的列表，按 ID 升序排列，无需登录。

        Args:
            db: 数据库会话

        Returns:
            Response[list[output_schema]] — 资源列表
        """
        result =  await db.execute(
            select(model).order_by(model.id)
        )
        return Response(data=result.scalars().all())

    @router.post("",response_model=Response[output_schema],
             status_code=status.HTTP_201_CREATED)
    @log_call
    async def create_item(
        item_in: create_schema, # pyright: ignore[reportInvalidTypeForm]
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_permission(permission)),
    ):  
        """
        新建资源

        创建一条新的资源记录。需拥有对应的管理权限。
        创建前会检查资源名称是否已存在。

        Args:
            item_in: 创建数据
            db: 数据库会话
            current_user: 当前登录用户（仅做权限校验）

        Returns:
            Response[output_schema] — 创建成功的资源数据

        Raises:
            HTTPException 400: 资源名称已存在
        """
        # 检查名称是否有重复
        existing = await db.execute(
            select(model).where(model.name == item_in.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{resource_name}名称已存在",
            )
        
        new_item = model(**item_in.model_dump())
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        return Response(data=new_item)
    
    @router.put("/{item_id}",response_model=Response[output_schema])
    @log_call
    async def update_item(
        item_id: int,
        item_in: update_schema, # pyright: ignore[reportInvalidTypeForm]
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_permission(permission)),
    ):
        """
        更新资源

        更新指定 ID 的资源记录（支持部分更新）。需拥有对应的管理权限。

        Args:
            item_id: 资源 ID
            item_in: 更新数据（仅更新传入的字段）
            db: 数据库会话
            current_user: 当前登录用户（仅做权限校验）

        Returns:
            Response[output_schema] — 更新后的资源数据

        Raises:
            HTTPException 404: 资源不存在
        """
        
        result = await db.execute(
            select(model).where(model.id == item_id)
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{resource_name}不存在",
            )
        # 进行更新
        update_data = item_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)

        await db.commit()
        await db.refresh(item)
        return Response(data=item)

    @router.delete("/{item_id}",status_code=status.HTTP_204_NO_CONTENT)
    @log_call
    async def delete_item(
        item_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_permission(permission)),
    ):
        """
        删除资源

        删除指定 ID 的资源记录。需拥有对应的管理权限。

        Args:
            item_id: 资源 ID
            db: 数据库会话
            current_user: 当前登录用户（仅做权限校验）

        Returns:
            None — 无内容返回（HTTP 204）

        Raises:
            HTTPException 404: 资源不存在
        """
        
        result = await db.execute(
            select(model).where(model.id == item_id)
        )
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{resource_name}不存在",
            )
        # 进行删除
        await db.delete(item)
        await db.commit()
        return None
    return router