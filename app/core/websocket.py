from datetime import datetime
import json
from typing import Dict

from fastapi import WebSocket
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

_ALLOWED_ORIGINS = {
    "http://localhost:8848",
    "https://localhost:8848",
    "http://127.0.0.1:8848",
    "https://127.0.0.1:8848",
}


class ConnectionManager:
    def __init__(self):
        # user_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, db: AsyncSession) -> int | None:
        """验证 JWT token 后建立连接，返回 user_id"""
        # Origin 检查，防止 CSWSH
        origin = websocket.headers.get("origin", "")
        if origin not in _ALLOWED_ORIGINS:
            await websocket.close(code=4003)
            return None

        # Token 认证
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4001)
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            username = payload.get("sub")
            if not username:
                await websocket.close(code=4001)
                return None
        except JWTError:
            await websocket.close(code=4001)
            return None

        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            await websocket.close(code=4001)
            return None

        await websocket.accept()

        # 同一用户保持最新连接
        old = self.active_connections.get(user.id)
        if old:
            try:
                await old.close(code=1000)
            except Exception:
                pass
        self.active_connections[user.id] = websocket
        return user.id

    def disconnect(self, user_id: int):
        """断开连接"""
        self.active_connections.pop(user_id, None)

    async def send_personal_message(self, user_id: int, message: str):
        """发送私信"""
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(user_id)

    async def broadcast_system(self, content: str):
        """广播系统消息"""
        message = {
            "type": "system",
            "message": content,
            "time": datetime.now(settings.tz).isoformat(),
        }
        for uid in list(self.active_connections.keys()):
            await self.send_personal_message(uid, json.dumps(message, ensure_ascii=False))

    async def is_online(self, user_id: int) -> bool:
        return user_id in self.active_connections


wbmanager = ConnectionManager()
