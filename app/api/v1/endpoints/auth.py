
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.user import UserCreate, UserOut
from app.schemas.token import Token
from app.schemas.common import Response
from datetime import timedelta
from jose import JWTError, jwt

import logging

logger = logging.getLogger(__name__)

router = APIRouter() # 路由,用来创建API
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
    """密码加密,哈希值"""
    # 防御性截断到 72 字节（UTF-8)
    password_bytes = password.encode("utf-8")[:72]

    return pwd_context.hash(password_bytes)

@router.post("/register",
             response_model=Response[UserOut],
             status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate,
                   db: AsyncSession = Depends(get_db),
                   ):
    # 检查用户名是否已存在
    existing_user = await db.execute(
        # 查询有没有用户名相同的用户
        select(User).where(User.username == user_data.username)
    )

    if existing_user.scalar_one_or_none(): # 如果已经存在
        logger.error(f"用户名'{user_data.username}'已存在")
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 检查邮箱是否已存在
    existing_email = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing_email.scalar_one_or_none():
        logger.error(f"邮箱'{user_data.email}'已存在")
        raise HTTPException(status_code=400, detail="邮箱已存在")

    # 创建用户实例(以 ORM 对象)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password=hash_password(user_data.password),
    )

    # ORM 添加并提交 (⚠️注意: 这里只是内存对象,提交之后才会写入数据库)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return Response(data=new_user)
    
@router.post("/login", response_model=Response[Token])
async def login(
    from_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    ):
    # 获取用户数据
    username = from_data.username
    password = from_data.password
    
    # 1. 查询用户是否存在
    result = await db.execute(
        select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="用户名不正确"
        )
    # 2. 验证密码
    if not verify_password(password, user.password):
        raise HTTPException(
            status_code=401,
            detail="密码错误"
        )
    # 3. 检查状态, 账户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="账号未激活"
        )
    # 4. 生成token
    access_token = create_access_token(
        data={"sub": user.username}
    )
    return Response(data=Token(access_token=access_token, token_type="bearer"))
    # bearer : 持有即授权 
    # 服务器不检查客户端身份（比如是不是同一个 IP、同一个设备），
    # 只看 token 本身是否有效。所以谁“持有”（bear）这个 token，谁就能访问资源。



    