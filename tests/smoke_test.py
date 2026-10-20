"""离线冒烟测试：不联网、不需要 NapCat，验证三层过滤。

    python tests/smoke_test.py
"""
import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeClient:
    """假的 httpx，被调用就说明过滤失败。"""

    def __init__(self, *args, **kwargs):
        pass

    async def post(self, *args, **kwargs):
        raise RuntimeError("API reached")


httpx = types.ModuleType("httpx")
httpx.AsyncClient = FakeClient
sys.modules["httpx"] = httpx

websockets = types.ModuleType("websockets")
websockets.connect = lambda *args, **kwargs: None
sys.modules["websockets"] = websockets

import fish_bot  # noqa: E402


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


async def main():
    cfg = dict(fish_bot.DEFAULTS)
    cfg["owner_qq"] = 10001
    cfg["min_interval"] = 0.0
    bot = fish_bot.FishBot(cfg)

    bot_id = 99999
    stranger = {
        "post_type": "message",
        "message_type": "private",
        "user_id": 20002,
        "self_id": bot_id,
        "raw_message": "hi",
    }
    group = {
        "post_type": "message",
        "message_type": "group",
        "user_id": 10001,
        "self_id": bot_id,
        "raw_message": "hi",
    }
    owner = {
        "post_type": "message",
        "message_type": "private",
        "user_id": 10001,
        "self_id": bot_id,
        "raw_message": "hi",
    }

    ws = FakeWS()
    await bot.handle(ws, stranger)
    assert ws.sent == [], "陌生人的私聊必须被忽略"
    await bot.handle(ws, group)
    assert ws.sent == [], "群消息必须被忽略"
    await bot.handle(ws, owner)
    assert len(ws.sent) == 1, "主人应该收到回复"
    assert "RuntimeError" in ws.sent[0], "主人的消息应该走到 API 调用"

    print("smoke OK: 陌生人/群消息被忽略，主人消息到达 API")


if __name__ == "__main__":
    asyncio.run(main())
