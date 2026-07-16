from app.core.websocket import ConnectionManager


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_text(self, message):
        self.messages.append(message)


async def test_personal_message_reaches_all_user_tabs():
    manager = ConnectionManager()
    first = FakeWebSocket()
    second = FakeWebSocket()
    manager.active_connections[1] = {first, second}

    await manager.send_personal_message(1, "实时通知")
    manager.disconnect(1, first)

    assert first.messages == ["实时通知"]
    assert second.messages == ["实时通知"]
    assert manager.active_connections[1] == {second}
