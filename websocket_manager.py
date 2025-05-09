from typing import Dict
from fastapi import WebSocket
import json

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.pending_counters: Dict[str, Dict[str, int]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        # Initialize all statuses
        self.pending_counters[user_id] = {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "flagged": 0
        }

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        self.pending_counters.pop(user_id, None)

    async def send_notification(self, user_id: str, status: str = "pending"):
        self.pending_counters.setdefault(user_id, {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "flagged": 0
        })

        if status != "pending" and self.pending_counters[user_id]["pending"] > 0:
            self.pending_counters[user_id]["pending"] -= 1

        self.pending_counters[user_id].setdefault(status, 0)
        self.pending_counters[user_id][status] += 1

        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(json.dumps(self.pending_counters[user_id]))

    async def reset_counter(self, user_id: str, status: str = "pending"):
        self.pending_counters.setdefault(user_id, {})[status] = 0

        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(json.dumps(self.pending_counters[user_id]))


manager = WebSocketManager()
