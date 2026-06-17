"""In-process WebSocket hub for the live "Connect an Expert" chat.

Two kinds of rooms:
- ``chat:<id>``  — the two participants of one expert chat (WhatsApp-style room).
- ``lobby``      — all online experts, so new requests pop into their inbox live.

This is a single-process broadcaster (fine for one Render web service). Move to a
Redis pub/sub backend if the app is ever scaled to multiple workers.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, room: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms[room].add(ws)

    async def disconnect(self, room: str, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms.get(room, set()).discard(ws)
            if not self._rooms.get(room):
                self._rooms.pop(room, None)

    async def broadcast(self, room: str, payload: dict) -> None:
        async with self._lock:
            targets = list(self._rooms.get(room, set()))
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._rooms.get(room, set()).discard(ws)


manager = ConnectionManager()


def chat_room(chat_id: int) -> str:
    return f"chat:{chat_id}"


LOBBY = "lobby"
