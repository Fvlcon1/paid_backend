

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websocket_manager import manager  

router = APIRouter()

@router.websocket("/ws/notifications/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "reset_pending":
                await manager.reset_counter(user_id)
    except WebSocketDisconnect:
        manager.disconnect(user_id)

