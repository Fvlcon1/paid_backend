from typing import Dict, List
from fastapi import WebSocket
import json

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.pending_counters: Dict[str, Dict[str, int]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)
        # Only set default counters if not already set
        self.pending_counters.setdefault(user_id, {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "flagged": 0
        })

    def disconnect(self, user_id: str, websocket: WebSocket):
        connections = self.active_connections.get(user_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.active_connections.pop(user_id, None)
            self.pending_counters.pop(user_id, None)  # Optional: remove if no one is listening

    async def send_notification(self, user_id: str, status: str = "pending"):
        self.pending_counters.setdefault(user_id, {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "flagged": 0
        })

        if status != "pending" and self.pending_counters[user_id]["pending"] > 0:
            self.pending_counters[user_id]["pending"] -= 1

        self.pending_counters[user_id][status] += 1

        for ws in self.active_connections.get(user_id, []):
            try:
                await ws.send_text(json.dumps(self.pending_counters[user_id]))
            except:
                continue  # You could also mark broken sockets and clean them up

    async def reset_counter(self, user_id: str, status: str = "pending"):
        self.pending_counters.setdefault(user_id, {})[status] = 0
        for ws in self.active_connections.get(user_id, []):
            try:
                await ws.send_text(json.dumps(self.pending_counters[user_id]))
            except:
                continue

manager = WebSocketManager()
