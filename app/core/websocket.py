from datetime import datetime
import json
from typing import Dict

from fastapi import WebSocket
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

_ALLOWED_ORIGINS = set(settings.cors_origin_list)


class ConnectionManager:
    def __init__(self):
        """初始化连接管理器，维护 user_id 到 WebSocket 的映射。"""
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, db: AsyncSession) -> int | None:
        """
        验证 WebSocket 连接的 JWT 令牌并建立连接。

        依次检查 Origin 防止 CSWSH 攻击、验证查询参数中的 JWT 令牌、
        确认用户存在且未被禁用。同一用户的新连接会关闭旧连接。

        Args:
            websocket: 待建立的 WebSocket 连接。
            db: 异步数据库会话，用于查询用户。

        Returns:
            int | None: 认证通过返回用户 ID，失败返回 None。
        """
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
        """断开并移除指定用户的 WebSocket 连接。"""
        self.active_connections.pop(user_id, None)

    async def send_personal_message(self, user_id: int, message: str):
        """
        向指定用户发送私信。

        Args:
            user_id: 目标用户 ID。
            message: 要发送的文本消息。
        """
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(user_id)

    async def broadcast_system(self, content: str):
        """向所有已连接用户广播系统消息。"""
        message = {
            "type": "system",
            "message": content,
            "time": datetime.now(settings.tz).isoformat(),
        }
        for uid in list(self.active_connections.keys()):
            await self.send_personal_message(uid, json.dumps(message, ensure_ascii=False))

    async def is_online(self, user_id: int) -> bool:
        """检查指定用户当前是否在线。"""
        return user_id in self.active_connections


wbmanager = ConnectionManager()
