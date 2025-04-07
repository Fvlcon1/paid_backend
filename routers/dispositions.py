# routers/dispositions.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from db import Disposition, User
from dependencies import get_db, get_current_user

router = APIRouter(prefix="/dispositions", tags=["Dispositions"])
logger = logging.getLogger(__name__)

# --- Get all dispositions ---
@router.get("/")
def get_dispositions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        dispositions = db.query(Disposition).all()
        return [{
            "id": d.id,
            "name": d.name,
            "description": d.description
        } for d in dispositions]
    except Exception as e:
        logger.error(f"Error fetching dispositions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving dispositions")
