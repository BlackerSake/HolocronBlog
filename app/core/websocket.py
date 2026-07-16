from datetime import datetime
import json
from urllib.parse import urlparse

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
        self.active_connections: dict[int, set[WebSocket]] = {}

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
        same_origin = urlparse(origin).netloc == websocket.headers.get("host")
        if origin not in _ALLOWED_ORIGINS and not same_origin:
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

        self.active_connections.setdefault(user.id, set()).add(websocket)
        return user.id

    def disconnect(self, user_id: int, websocket: WebSocket):
        """断开并移除指定用户的 WebSocket 连接。"""
        connections = self.active_connections.get(user_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self.active_connections.pop(user_id, None)

    async def send_personal_message(self, user_id: int, message: str):
        """
        向指定用户发送私信。

        Args:
            user_id: 目标用户 ID。
            message: 要发送的文本消息。
        """
        for websocket in list(self.active_connections.get(user_id, ())):
            try:
                await websocket.send_text(message)
            except Exception:
                self.disconnect(user_id, websocket)

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
        return bool(self.active_connections.get(user_id))


wbmanager = ConnectionManager()
