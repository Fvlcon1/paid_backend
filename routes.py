from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from .schemas import RecentVisitSchema
from .models import RecentVisit
from .database import get_db

router = APIRouter()

@router.get("/recent-visits", response_model=List[RecentVisitSchema])
def get_recent_visits(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    visits = db.query(RecentVisit).offset(skip).limit(limit).all()
    return visits  # FastAPI will automatically convert to Pydantic schema
