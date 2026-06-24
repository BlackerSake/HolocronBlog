from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryOut

""" 
实现路由
"""

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)

# 公开列表(无需认证)
@router.get("",response_model=list[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result =  await db.execute(
        select(Category).order_by(Category.id)
    )
    return result.scalars().all() 

# 创建分类(需要认证)
@router.post("",response_model=CategoryOut,
             status_code=status.HTTP_201_CREATED)
async def create_category(
    category_in: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有admin可以创建分类")
    
    # 检查名称是否有重复
    existing = await db.execute(
        select(Category).where(Category.name == category_in.name)
    ) 
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该名称已经存在")
    
    new_category = Category(**category_in.model_dump()) # 
    db.add(new_category)
    await db.commit()
    await db.refresh(new_category)
    return new_category

# 更新分类 (需要认证)
@router.put("/{category_id}",response_model=CategoryOut)
async def update_category(
    category_id: int,
    category_in: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    category = await db.get(Category, category_id)  # 获取 目标分类 信息
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有admin可以更新分类")
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    # 进行更新
    update_data = category_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value) # 进行 指定字段 的更新
    
    await db.commit()
    await db.refresh(category)
    return category

# 删除分类 (需要认证)
@router.delete("/{category_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    category = await db.get(Category, category_id)

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有admin可以删除分类")
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    await db.delete(category)
    await db.commit()
    return None
