from fastapi import APIRouter
from pydantic import BaseModel
from websocket_manager import manager
import anyio

router = APIRouter()

class TriggerRequest(BaseModel):
    user_id: str
    status: str  

@router.post("/ws/trigger")
def trigger_ws_notification(req: TriggerRequest):
    try:
        anyio.from_thread.run(manager.send_notification, req.user_id, req.status)
        return {"message": f"Notification sent to user {req.user_id} with status {req.status}"}
    except Exception as e:
        return {"error": str(e)}
