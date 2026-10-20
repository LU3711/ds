#!/usr/bin/env python3
"""大肥鱼 QQ 机器人：只和主人私聊。

    QQ 小号  <--->  NapCat (OneBot 11 WebSocket)  <--->  本脚本  <--->  DeepSeek API

只响应主人在私聊里发的消息；群消息和陌生人的私聊一律静默丢弃。
过滤发生在调用 API 之前，所以不会产生额外费用。
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import websockets

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "owner_qq": 0,                                  # 你的 QQ 号，必填
    "ws_url": "ws://127.0.0.1:3001",                # NapCat 的 WebSocket 服务器地址
    "ws_token": "",                                 # 与 NapCat 里填的 token 一致
    "deepseek_api_key": "",                         # 也可用环境变量 DEEPSEEK_API_KEY
    "api_base": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "max_tokens": 80,
    "temperature": 1.0,
    "min_interval": 1.0,                            # 两条回复之间的最小间隔（秒）
    "max_history": 40,                              # 保留多少条对话上下文
    "persona_file": "persona.md",
}


def load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    if os.environ.get("DEEPSEEK_API_KEY"):
        cfg["deepseek_api_key"] = os.environ["DEEPSEEK_API_KEY"]
    return cfg


class FishBot:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        persona_path = Path(cfg["persona_file"])
        if not persona_path.is_absolute():
            persona_path = BASE_DIR / persona_path
        self.persona = persona_path.read_text(encoding="utf-8")
        self.histories: dict[int, list[dict[str, str]]] = {}
        self.last_reply = 0.0
        self.client = httpx.AsyncClient(timeout=30.0)

    # ---------- DeepSeek ----------
    async def ask(self, uid: int, text: str) -> str:
        history = self.histories.setdefault(uid, [])
        history.append({"role": "user", "content": text})
        payload = {
            "model": self.cfg["model"],
            "messages": [{"role": "system", "content": self.persona}]
            + history[-self.cfg["max_history"] :],
            "max_tokens": self.cfg["max_tokens"],
            "temperature": self.cfg["temperature"],
        }
        resp = await self.client.post(
            f"{self.cfg['api_base'].rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.cfg['deepseek_api_key']}"},
            json=payload,
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"].strip()
        history.append({"role": "assistant", "content": reply})
        del history[: -self.cfg["max_history"]]
        return reply

    # ---------- 事件处理 ----------
    async def handle(self, ws: Any, event: dict[str, Any]) -> None:
        # 只处理消息事件
        if event.get("post_type") != "message":
            return
        # 只处理私聊：群消息直接丢弃
        if event.get("message_type") != "private":
            return
        # 只认主人：不是本人就静默，连 API 都不调
        uid = int(event.get("user_id", 0))
        if uid != int(self.cfg["owner_qq"]):
            return
        # 忽略自己发出的消息
        if uid == int(event.get("self_id", 0)):
            return

        text = (event.get("raw_message") or "").strip()
        if not text:
            return

        # 全局限流：防止连着刷屏
        if time.monotonic() - self.last_reply < float(self.cfg["min_interval"]):
            return
        self.last_reply = time.monotonic()

        try:
            reply = await self.ask(uid, text)
        except Exception as exc:  # noqa: BLE001
            reply = f"本鱼出错了…（{type(exc).__name__}）"
            print(f"[error] {exc!r}")

        action = {
            "action": "send_private_msg",
            "params": {"user_id": uid, "message": reply},
            "echo": "send_private_msg",
        }
        await ws.send(json.dumps(action, ensure_ascii=False))
        print(f"[reply] {uid}: {reply}")

    # ---------- 主循环 ----------
    async def run(self) -> None:
        headers = {}
        if self.cfg["ws_token"]:
            headers["Authorization"] = f"Bearer {self.cfg['ws_token']}"

        while True:
            try:
                async with websockets.connect(
                    self.cfg["ws_url"], additional_headers=headers
                ) as ws:
                    print(f"已连接 {self.cfg['ws_url']}")
                    async for raw in ws:
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        # 只处理事件，忽略 action 的回执
                        if "post_type" in event:
                            asyncio.create_task(self.handle(ws, event))
            except Exception as exc:  # noqa: BLE001
                print(f"连接断开：{exc!r}，5 秒后重试")
                await asyncio.sleep(5)


def main() -> None:
    cfg = load_config()
    if not cfg["owner_qq"]:
        raise SystemExit("请先在 config.json 里填写 owner_qq（你的 QQ 号）")
    if not cfg["deepseek_api_key"]:
        raise SystemExit(
            "缺少 deepseek_api_key：写进 config.json，或设置环境变量 DEEPSEEK_API_KEY"
        )
    try:
        asyncio.run(FishBot(cfg).run())
    except KeyboardInterrupt:
        print("已退出")


if __name__ == "__main__":
    main()
