# routers/medicines.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
import logging

from db import Medicines
from schemas import MedicineResponse
from dependencies import get_db

router = APIRouter(prefix="/medicines", tags=["Medicines"])
logger = logging.getLogger(__name__)

# --- Search medicines ---
@router.get("/search", response_model=List[MedicineResponse])
def search_medicines(
    query: Optional[str] = Query(None, description="Search by code or generic name"),
    limit: int = Query(15, description="Limit results"),
    db: Session = Depends(get_db)
):
    try:
        if query:
            term = f"{query}%"
            medicines = db.query(Medicines).filter(
                or_(
                    Medicines.code.ilike(term),
                    Medicines.generic_name.ilike(term)
                )
            ).limit(limit).all()

            for med in medicines:
                med.created_at = datetime.utcnow()
            db.commit()
        else:
            medicines = db.query(Medicines).order_by(Medicines.created_at.desc()).limit(limit).all()

        return medicines
    except Exception as e:
        logger.error(f"Error searching medicines: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching medicines")
