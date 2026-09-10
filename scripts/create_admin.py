
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
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.role import Role
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
USERNAME = "benchuser"
EMAIL = "benchuser@bench.com"
PASSWORD = "benchpass123"
async def create_admin(username, email, password):
    """创建或重置 admin 用户。"""
    async with AsyncSessionLocal() as db:
        logger.info("数据库: %s", settings.DATABASE_URL)
        existing = (await db.execute(
            select(User).where(User.username == username)
        )).scalar_one_or_none()
        admin_role = (await db.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        hashed = get_password_hash(password)

        if existing:
            existing.role_id = admin_role.id
            existing.password = hashed
            existing.is_active = True
            await db.commit()
            logger.info("admin用户'%s'已重置", username)
            return

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
        logger.info("admin用户'%s'创建成功,身份'%s'", username, admin_role.name)
        
if __name__ == "__main__":
    asyncio.run(create_admin(username = USERNAME,
                             email = EMAIL,
                             password = PASSWORD))
