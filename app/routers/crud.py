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
    ## 创建通用CRUD路由
    生成 list(公开列表), create(创建), update(更新), delete(删除)四个路由  
    其中create, update, delete需要 admin 权限
    """

    router = APIRouter(prefix=prefix,tags=tags)
    
    @router.get("",response_model=Response[list[output_schema]])
    @log_call
    async def list_item(db: AsyncSession = Depends(get_db)):
        """
        ## 获取列表
        user 可以查看所有item
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
        ## 新建 item
        仅 admin 角色可以创建(通过依赖检查完成)
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
        ## 更新 item
        仅 admin 角色可以创建(通过依赖检查完成)
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
        ## 删除 item
        仅 admin 角色可以创建(通过依赖检查完成)
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