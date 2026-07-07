
"""
创建 admin 用户
docker compose exec api python scripts/create_admin.py
python -m scripts.create_admin
"""
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.role import Role
from passlib.context import CryptContext
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pwd_content = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin():
    """创建 admin 用户"""
    username = "admin"
    email = "admin@exapmple.com"
    password = "admin"
    async with AsyncSessionLocal() as db:
        # 检查存在与否
        result = await db.execute(
            select(User).where(User.username == username)
        )
        exiting = result.scalar_one_or_none()

        if exiting:
            logger.warning(f"admin用户'{username}'已存在")
    
            try:
                await db.delete(exiting)
                await db.commit()
                logger.info(f"已删除用户'{username}'")
            except Exception as e:
                logger.error(f"删除用户'{username}'失败: {e}")
                return 
            
        admin_role = (await db.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        hashed = pwd_content.hash(password)
        admin = User(
            username=username,
            role_id=admin_role.id,
            email=email,
            password=hashed,
            is_active=True,
        )

        # 添加并提交
        db.add(admin)
        await db.commit()
        logging.info(f"admin用户'{username}'创建成功,身份'{admin_role.name}'")
if __name__ == "__main__":
    asyncio.run(create_admin())