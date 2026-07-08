
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.security import OAuth2PasswordRequestForm
from app.core.database import get_db
from app.core.config import settings
from app.core.security import verify_password, create_access_token, create_refresh_token, get_password_hash
from app.core.log import log_call
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, UserOut
from app.schemas.token import Token, TokenRefreshRequest
from app.schemas.common import Response
from datetime import timedelta
from jose import JWTError, jwt

import logging

logger = logging.getLogger(__name__)

router = APIRouter() # 路由,用来创建API

@router.post("/register",
             response_model=Response[UserOut],
             status_code=status.HTTP_201_CREATED)
@log_call
async def register(user_data: UserCreate,
                   db: AsyncSession = Depends(get_db),
                   ):
    """用户注册

    检查用户名和邮箱是否已存在，对密码进行哈希处理，
    为新建用户分配默认角色后写入数据库。

    Args:
        user_data: 注册参数，包含用户名、邮箱和密码
        db: 数据库会话（由FastAPI自动注入）

    Returns:
        Response[UserOut]: 包含新建用户信息的统一响应

    Raises:
        HTTPException 400: 用户名或邮箱已存在
        HTTPException 422: 密码强度不符合要求
    """
    # 检查用户名是否已存在
    existing_user = await db.execute(
        # 查询有没有用户名相同的用户
        select(User).where(User.username == user_data.username)
    )

    if existing_user.scalar_one_or_none(): # 如果已经存在
        logger.error(f"用户名'{user_data.username}'已存在")
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 邮箱可选，未提供时自动生成占位
    email = user_data.email or f"{user_data.username}@holocron.com"

    # 检查邮箱是否已存在
    existing_email = await db.execute(
        select(User).where(User.email == email)
    )
    if existing_email.scalar_one_or_none():
        logger.error(f"邮箱'{email}'已存在")
        raise HTTPException(status_code=400, detail="邮箱已存在")

    # 创建用户实例(以 ORM 对象)，分配默认角色
    try:
        hashed = get_password_hash(user_data.password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    default_role = await db.execute(select(Role).where(Role.name == "user"))
    default_role_id = default_role.scalar_one().id
    new_user = User(
        username=user_data.username,
        email=email,
        password=hashed,
        role_id=default_role_id,
    )

    # ORM 添加并提交 (⚠️注意: 这里只是内存对象,提交之后才会写入数据库)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return Response(data=new_user)
    
@router.post("/login")
@log_call
async def login(
    from_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    ):
    """用户登录

    验证用户名和密码，检查账户状态，生成访问令牌和刷新令牌。

    Args:
        from_data: OAuth2 表单格式的登录参数（用户名、密码）
        db: 数据库会话（由FastAPI自动注入）

    Returns:
        Response[dict]: 包含 access_token、refresh_token 和用户信息的统一响应

    Raises:
        HTTPException 401: 用户名不正确、密码错误或账号未激活
    """
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
    refresh_token = create_refresh_token(user.username)
    return Response(data={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "role_name": user.role},
    })
    # bearer : 持有即授权
    # 服务器不检查客户端身份（比如是不是同一个 IP、同一个设备），
    # 只看 token 本身是否有效。所以谁“持有”（bear）这个 token，谁就能访问资源。


@router.post("/refresh")
@log_call
async def refresh_token(
    body: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """刷新令牌：用 refresh_token 换新的 access_token + refresh_token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="refresh_token 无效或已过期",
    )
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        if payload.get("purpose") != "refresh":
            raise credentials_exception
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception

    access_token = create_access_token(data={"sub": username})
    refresh_token = create_refresh_token(username)
    return Response(data={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "role_name": user.role},
    })



    