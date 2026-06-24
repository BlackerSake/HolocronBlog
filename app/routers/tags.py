from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.tag import Tag
from app.schemas.tag import TagCreate, TagOut, TagUpdate, TagOut



router = APIRouter(
    prefix="/tags",
    tags=["Tags"],
)

# 公开列表(无需认证)
@router.get("",response_model=list[TagOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result =  await db.execute(
        select(Tag).order_by(Tag.id)
    )
    return result.scalars().all() 

# 创建标签(需要认证)
@router.post("",response_model=TagOut,
             status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag_in: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有admin可以创建标签")
    
    # 检查名称是否有重复
    existing = await db.execute(
        select(Tag).where(Tag.name == tag_in.name)
    ) 
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该名称已经存在")
    
    new_tag = Tag(**tag_in.model_dump()) # 
    db.add(new_tag)
    await db.commit()
    await db.refresh(new_tag)
    return new_tag

# 更新标签 (需要认证)
@router.put("/{tag_id}",response_model=TagOut)
async def update_tag(
    tag_id: int,
    tag_in: TagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    tag = await db.get(Tag, tag_id)  # 获取 目标标签 信息
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有admin可以更新标签")
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    # 进行更新
    update_data = tag_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tag, key, value) # 进行 指定字段 的更新
    
    await db.commit()
    await db.refresh(tag)
    return tag

# 删除标签 (需要认证)
@router.delete("/{tag_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    tag = await db.get(Tag, tag_id)

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有admin可以删除标签")
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    await db.delete(tag)
    await db.commit()
    return None
