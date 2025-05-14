import asyncio
from typing import Dict, List
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)

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
            self.pending_counters.pop(user_id, None)  

    async def send_notification(self, user_id: str, status: str = "pending"):
        """Send notification to clients when claim status changes."""
        logger.info(f"Sending notification to user {user_id} for status {status}")
        
        self.pending_counters.setdefault(user_id, {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "flagged": 0
        })

       
        if status != "pending" and self.pending_counters[user_id]["pending"] > 0:
            self.pending_counters[user_id]["pending"] -= 1

       
        self.pending_counters[user_id][status] += 1
        
        
        logger.info(f"Updated counters for user {user_id}: {self.pending_counters[user_id]}")

       
        await self._broadcast_to_user(user_id, self.pending_counters[user_id])

    async def reset_counter(self, user_id: str, status: str = "pending"):
        
        logger.info(f"Resetting counter for user {user_id}, status {status}")
        
        self.pending_counters.setdefault(user_id, {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "flagged": 0
        })[status] = 0
        
        await self._broadcast_to_user(user_id, self.pending_counters[user_id])

    async def _broadcast_to_user(self, user_id: str, data: dict):
       
        message = json.dumps(data)
        logger.info(f"Broadcasting to user {user_id}: {message}")
        
        for ws in self.active_connections.get(user_id, []):
            try:
                await ws.send_text(message)
                logger.info(f"Successfully sent to a connection for user {user_id}")
            except Exception as e:
                logger.error(f"Error sending to websocket: {str(e)}")
                continue 

manager = WebSocketManager()


def run_async(coroutine):
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coroutine)